"""Convert .NET and Go date layouts into ``strptime`` formats.

Indexer definitions describe dates with .NET custom format strings
(``yyyy-MM-dd HH:mm zzz``); the Cardigann spec also allows Go layouts
(``2006-01-02 15:04``). Both are translated and parsed here.
"""

from __future__ import annotations

import re
from datetime import datetime

_NET_TOKEN = re.compile(
    r"'[^']*'|yyyy|yy|MMMM|MMM|MM|M|dddd|ddd|dd|d|HH|H|hh|h|mm|m|ss|s"
    r"|f+|F+|tt|zzz|zz|z|."
)
_NET_TO_STRPTIME = {
    "yyyy": "%Y",
    "yy": "%y",
    "MMMM": "%B",
    "MMM": "%b",
    "MM": "%m",
    "M": "%m",
    "dddd": "%A",
    "ddd": "%a",
    "dd": "%d",
    "d": "%d",
    "HH": "%H",
    "H": "%H",
    "hh": "%I",
    "h": "%I",
    "mm": "%M",
    "m": "%M",
    "ss": "%S",
    "s": "%S",
    "tt": "%p",
    "zzz": "%z",
    "zz": "%z",
    "z": "%z",
}

_GO_TOKEN = re.compile(
    r"January|Jan|Monday|Mon|2006|06|01|02|_2|15|03|04|05|PM|pm|MST"
    r"|Z07:00|Z0700|Z07|-07:00|-0700|-07|\.0+|\.9+|1|2|3|4|5|."
)
_GO_TO_STRPTIME = {
    "January": "%B",
    "Jan": "%b",
    "Monday": "%A",
    "Mon": "%a",
    "2006": "%Y",
    "06": "%y",
    "01": "%m",
    "02": "%d",
    "_2": "%d",
    "15": "%H",
    "03": "%I",
    "04": "%M",
    "05": "%S",
    "PM": "%p",
    "pm": "%p",
    "MST": "%Z",
    "Z07:00": "%z",
    "Z0700": "%z",
    "Z07": "%z",
    "-07:00": "%z",
    "-0700": "%z",
    "-07": "%z",
    "1": "%m",
    "2": "%d",
    "3": "%I",
    "4": "%M",
    "5": "%S",
}
_NET_HINT_CHARS = "yhd"


def _escape_literal(text: str) -> str:
    return text.replace("%", "%%")


def _net_token_to_strptime(token: str) -> str:
    if token in _NET_TO_STRPTIME:
        return _NET_TO_STRPTIME[token]
    if token[0] in "fF":
        return "%f"
    if token.startswith("'"):
        return _escape_literal(token.strip("'"))
    return _escape_literal(token)


def _go_token_to_strptime(token: str) -> str:
    if token in _GO_TO_STRPTIME:
        return _GO_TO_STRPTIME[token]
    if token.startswith("."):
        return "%f"
    return _escape_literal(token)


def net_format_to_strptime(layout: str) -> str:
    return "".join(_net_token_to_strptime(token) for token in _NET_TOKEN.findall(layout))


def go_layout_to_strptime(layout: str) -> str:
    return "".join(_go_token_to_strptime(token) for token in _GO_TOKEN.findall(layout))


def looks_like_net_format(layout: str) -> bool:
    lowered = layout.lower()
    return any(hint in lowered for hint in _NET_HINT_CHARS)


def parse_exact(text: str, strptime_format: str) -> datetime | None:
    try:
        return datetime.strptime(text, strptime_format)
    except ValueError:
        return None


def parse_with_layout(text: str, layout: str) -> tuple[datetime, str]:
    """Parse ``text`` with a .NET or Go layout.

    Returns the parsed value and the ``strptime`` format that matched.
    Raises ``ValueError`` if no interpretation fits.
    """
    candidates = []
    if looks_like_net_format(layout):
        candidates.append(net_format_to_strptime(layout))
    candidates.append(go_layout_to_strptime(layout))
    for candidate in candidates:
        parsed = parse_exact(text, candidate)
        if parsed is not None:
            return parsed, candidate
    raise ValueError(f'Error while parsing DateTime "{text}", using layout "{layout}"')
