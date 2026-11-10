"""Date parsing for scraped values.

Every function returns timezone aware datetimes expressed in the local time
zone, which is what the Torznab feed needs.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from dateutil import parser as dateutil_parser

from pyjackett.utils.date_formats import parse_with_layout
from pyjackett.utils.numbers import coerce_float
from pyjackett.utils.text import normalize_space

RFC1123Z_FORMAT = "%a, %d %b %Y %H:%M:%S %z"

_RFC1123Z = re.compile(
    r"^[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} [+-]\d{4}$"
)
_TIME_AGO = re.compile(r"(?i)\bago")
_TODAY = re.compile(r"(?i)\btoday(?:[\s,]+(?:at){0,1}\s*|[\s,]*|$)")
_TOMORROW = re.compile(r"(?i)\btomorrow(?:[\s,]+(?:at){0,1}\s*|[\s,]*|$)")
_YESTERDAY = re.compile(r"(?i)\byesterday(?:[\s,]+(?:at){0,1}\s*|[\s,]*|$)")
_DAY_OF_WEEK = re.compile(
    r"(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"\s+at\s+"
)
_MISSING_YEAR = re.compile(r"^(\d{1,2}-\d{1,2})(\s|$)")
_MISSING_YEAR_WITH_TIME = re.compile(
    r"^(\d{1,2}\s+\w{3})\s+(\d{1,2}:\d{1,2}.*)$"
)
_TIME_AGO_PART = re.compile(r"\s*?([\d.]+)\s*?([^\d\s.]+)\s*?")
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
# (substrings, exact abbreviations, seconds), checked in this order
_UNIT_SECONDS = (
    (("sec",), ("s",), 1),
    (("min",), ("m",), 60),
    (("hour", "hr"), ("h",), 3600),
    (("day",), ("d",), 86400),
    (("week", "wk"), ("w",), 7 * 86400),
    (("month",), ("mo",), 30 * 86400),
    (("year",), ("y",), 365 * 86400),
)


def local_now() -> datetime:
    return datetime.now().astimezone()


def to_local(moment: datetime) -> datetime:
    """Attach the local zone to naive values, convert aware ones."""
    return moment.astimezone()


def format_rfc1123z(moment: datetime) -> str:
    """Interchange format used between filters (always with an offset)."""
    return to_local(moment).strftime(RFC1123Z_FORMAT)


def from_unix_timestamp(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp).astimezone()


def _unit_to_seconds(unit: str) -> int:
    for words, abbreviations, seconds in _UNIT_SECONDS:
        if unit in abbreviations or any(word in unit for word in words):
            return seconds
    raise ValueError(f"TimeAgo parsing failed, unknown unit: {unit}")


def from_time_ago(text: str, relative_from: datetime | None = None):
    """Parse relative expressions like "2 hours 1 day ago"."""
    text = text.lower()
    now = relative_from or local_now()
    if "now" in text:
        return now
    for noise in (",", "ago", "and"):
        text = text.replace(noise, "")
    total = timedelta()
    for amount, unit in _TIME_AGO_PART.findall(text):
        total += timedelta(
            seconds=coerce_float(amount) * _unit_to_seconds(unit)
        )
    return now - total


def from_fuzzy_time(
    text: str, date_format: str | None = None, now: datetime | None = None
) -> datetime:
    """Parse an arbitrary date/time string; missing parts default to today."""
    today = (now or local_now()).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    try:
        parsed = dateutil_parser.parse(
            text, fuzzy=True, dayfirst=date_format == "UK", default=today
        )
    except (ValueError, OverflowError) as error:
        raise ValueError("FromFuzzyTime parsing failed") from error
    return to_local(parsed)


def _from_fuzzy_past_time(
    text: str, date_format: str | None, now: datetime
) -> datetime:
    result = from_fuzzy_time(text, date_format, now)
    return result.replace(year=result.year - 1) if result > now else result


def _time_of_day(text: str) -> timedelta:
    if not text.strip():
        return timedelta()
    parsed = dateutil_parser.parse(text)
    return timedelta(
        hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second
    )


def _relative_day(
    match: re.Match, text: str, now: datetime, day_offset: int
) -> datetime:
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    clock = _time_of_day(text.replace(match.group(0), ""))
    return midnight + clock + timedelta(days=day_offset)


def _from_weekday(match: re.Match, text: str, now: datetime) -> datetime:
    moment = _relative_day(match, text, now, 0)
    target = _WEEKDAYS.index(match.group(1).lower())
    while moment.weekday() != target:
        moment -= timedelta(days=1)
    return moment


def _parse_rfc1123z(text: str) -> datetime | None:
    if not _RFC1123Z.match(text):
        return None
    return to_local(datetime.strptime(text, RFC1123Z_FORMAT))


def _parse_relative_words(text: str, now: datetime) -> datetime | None:
    if _TIME_AGO.search(text):
        return from_time_ago(text, now)
    for pattern, offset in ((_TODAY, 0), (_YESTERDAY, -1), (_TOMORROW, 1)):
        match = pattern.search(text)
        if match:
            return _relative_day(match, text, now, offset)
    match = _DAY_OF_WEEK.search(text)
    if match:
        return _from_weekday(match, text, now)
    return None


def _parse_missing_year(
    text: str, date_format: str | None, now: datetime
) -> datetime | None:
    match = _MISSING_YEAR.match(text)
    if match:
        date = match.group(1)
        text = text.replace(date, f"{now.year}-{date}")
        return _from_fuzzy_past_time(text, date_format, now)
    match = _MISSING_YEAR_WITH_TIME.match(text)
    if match:
        text = f"{match.group(1)} {now.year} {match.group(2)}"
        return _from_fuzzy_past_time(text, date_format, now)
    return None


def _parse_special_cases(
    text: str, date_format: str | None, now: datetime
) -> datetime | None:
    exact = _parse_rfc1123z(text)
    if exact is not None:
        return exact
    if text.isdigit():
        return from_unix_timestamp(int(text))
    if "now" in text.lower():
        return now
    relative = _parse_relative_words(text, now)
    if relative is not None:
        return relative
    return _parse_missing_year(text, date_format, now)


def from_unknown(
    text: str,
    date_format: str | None = None,
    relative_from: datetime | None = None,
) -> datetime:
    """Best effort parser used by the ``date`` field of a definition."""
    text = normalize_space(text)
    now = relative_from or local_now()
    try:
        special = _parse_special_cases(text, date_format, now)
        return special or from_fuzzy_time(text, date_format, now)
    except Exception as error:
        raise ValueError(
            f'DateTime parsing failed for "{text}": {error}'
        ) from error


def parse_layout(
    text: str, layout: str, relative_from: datetime | None = None
) -> datetime:
    """Parse ``text`` with a definition layout (the dateparse filter)."""
    now = relative_from or local_now()
    parsed, used_format = parse_with_layout(normalize_space(text), layout)
    moment = to_local(parsed)
    has_year = "%Y" in used_format or "%y" in used_format
    if not has_year and moment > now:
        moment = moment.replace(year=moment.year - 1)
    return moment
