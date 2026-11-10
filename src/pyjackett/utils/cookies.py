"""Cookie header helpers.

Cookies are passed around as plain ``name=value; name2=value2`` strings so
they can be stored in an indexer configuration file.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

EXPIRED_COOKIE_VALUE = "__pyjackett_expired__"

_COOKIE_PAIR = re.compile(r'([^()<>@,;:\\"/\[\]?={}\s]+)=([^,;\\"\s]+)')


def header_to_dict(header: str | None) -> dict[str, str]:
    """Parse a cookie header; expired markers remove earlier values."""
    cookies: dict[str, str] = {}
    for name, value in _COOKIE_PAIR.findall(header or ""):
        if value == EXPIRED_COOKIE_VALUE:
            cookies.pop(name, None)
        else:
            cookies[name] = value
    return cookies


def dict_to_header(cookies: dict[str, str] | None) -> str:
    if not cookies:
        return ""
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def merge_headers(*headers: str | None) -> str:
    """Merge several cookie headers; the last occurrence of a name wins."""
    joined = " ".join(header for header in headers if header)
    return dict_to_header(header_to_dict(joined))


def _max_age_expired(value: str) -> bool | None:
    try:
        return int(value) <= 0
    except ValueError:
        return None


def _expires_expired(value: str) -> bool | None:
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment < datetime.now(UTC)


def _is_expired(attributes: list[str]) -> bool:
    """Max-Age has precedence over Expires (RFC 6265)."""
    verdicts: dict[str, bool | None] = {}
    for attribute in attributes:
        key, _, value = attribute.partition("=")
        key = key.strip().lower()
        if key == "max-age":
            verdicts[key] = _max_age_expired(value.strip())
        elif key == "expires":
            verdicts[key] = _expires_expired(value.strip())
    verdict = verdicts.get("max-age")
    if verdict is None:
        verdict = verdicts.get("expires")
    return bool(verdict)


def set_cookie_to_pair(set_cookie: str) -> str:
    """Convert a Set-Cookie header into a ``name=value;`` pair."""
    attributes = [part.strip() for part in set_cookie.split(";")]
    name, separator, _ = attributes[0].partition("=")
    if not separator:
        return attributes[0] + ";"
    if _is_expired(attributes[1:]):
        return f"{name}={EXPIRED_COOKIE_VALUE};"
    return attributes[0] + ";"
