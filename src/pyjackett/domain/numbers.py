"""Lenient number parsing used on scraped values."""

from __future__ import annotations

import re

_IMDB_ID = re.compile(r"^(?:tt)?(\d{1,8})$")
_SIZE_UNITS = (("kb", 1), ("mb", 2), ("gb", 3), ("tb", 4))


def _keep_number_chars(value: str) -> str:
    return "".join(c for c in value if c.isdigit() or c in ".,")


def _collapse_thousand_dots(number: str) -> str:
    """Keep only the last dot as decimal separator ("1.018.29" => 1018.29)."""
    if number.count(".") > 1:
        head, _, tail = number.rpartition(".")
        return head.replace(".", "") + "." + tail
    return number


def _normalize_decimal(value: str) -> str:
    digits = _keep_number_chars(value).strip().replace("-", "0")
    digits = digits.replace(",", ".") if digits else "0"
    return _collapse_thousand_dots(digits)


def _normalize_integer(value: str) -> str:
    digits = _keep_number_chars(value).strip().replace("-", "0")
    return digits.replace(",", "").replace(".", "") or "0"


def coerce_float(value: str) -> float:
    return float(_normalize_decimal(value))


def coerce_int(value: str) -> int:
    return int(_normalize_integer(value))


def extract_first_integer(value: str | None) -> int | None:
    """Return the first run of digits found in ``value``."""
    if value is None or value.strip() == "":
        return None
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def parse_imdb_id(value: str | None) -> int | None:
    if value is None:
        return None
    match = _IMDB_ID.match(value)
    return int(match.group(1)) if match else None


def format_imdb_id(value: str | None) -> str | None:
    """Normalize an IMDb id to its full ``tt0000000`` form."""
    imdb_id = parse_imdb_id(value)
    return f"tt{imdb_id:07d}" if imdb_id else None


def bytes_from_unit(unit: str, value: float) -> int:
    unit = unit.replace("i", "").lower()
    for suffix, power in _SIZE_UNITS:
        if suffix in unit:
            return int(value * 1024**power)
    return int(value)


def parse_size(value: str) -> int:
    """Parse "1.018,29 MB" style sizes into bytes."""
    number = _collapse_thousand_dots((_keep_number_chars(value) or "0").replace(",", "."))
    unit = "".join(c for c in value if c.isalpha())
    return bytes_from_unit(unit, float(number))
