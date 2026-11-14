"""The value filters of a definition (``filters: - name: ... args: ...``).

Every filter is a small function registered under its Cardigann name;
:func:`apply_filters` runs a chain of them over a value.
"""

from __future__ import annotations

import html
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pyjackett.domain import dates
from pyjackett.domain.cardigann.definition import FilterBlock
from pyjackett.domain.cardigann.json_path import (
    MISSING,
    select_token,
    token_to_string,
)
from pyjackett.domain.cardigann.template import Variables, apply_template
from pyjackett.domain.regex_compat import first_group, replace_all
from pyjackett.domain.text import make_valid_file_name, strip_diacritics
from pyjackett.domain.urls import (
    base64url_decode,
    base64url_encode,
    get_query_argument,
    url_decode,
    url_encode,
)

logger = logging.getLogger(__name__)

_VALIDATE_DELIMITERS = ',/)(.;[]"|: '


@dataclass
class FilterContext:
    """What filters may need besides the value itself."""

    indexer_id: str = ""
    encoding: str = "utf-8"
    variables: Variables | None = None
    extra: dict[str, Any] = field(default_factory=dict)


Filter = Callable[[str, Any, FilterContext], str | None]

FILTERS: dict[str, Filter] = {}


def register(*names: str) -> Callable[[Filter], Filter]:
    """Make a function available under the given Cardigann filter names."""

    def decorator(handler: Filter) -> Filter:
        for name in names:
            FILTERS[name] = handler
        return handler

    return decorator


def _template(text: str, context: FilterContext) -> str:
    return apply_template(text, context.variables or {}) or ""


# ---- value extraction -------------------------------------------------------


@register("querystring")
def _querystring(data, args, context):
    return get_query_argument(data, args)


@register("regexp")
def _regexp(data, args, context):
    return first_group(args, data)


@register("split")
def _split(data, args, context):
    separator, position = args[0], int(args[1])
    parts = data.split(separator[0])
    return parts[position + len(parts) if position < 0 else position]


@register("validate")
def _validate(data, args, context):
    allowed = _split_words(args)
    present = _split_words(data)
    return ",".join(word for word in dict.fromkeys(allowed) if word in present)


def _split_words(text: str) -> list[str]:
    words, current = [], []
    for char in text.lower():
        if char in _VALIDATE_DELIMITERS:
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        words.append("".join(current))
    return words


# ---- text transformation ----------------------------------------------------


@register("re_replace")
def _re_replace(data, args, context):
    replacement = _template(args[1], context)
    return replace_all(args[0], replacement, data)


@register("replace")
def _replace(data, args, context):
    return data.replace(args[0], _template(args[1], context))


@register("trim")
def _trim(data, args, context):
    return data.strip(args[0]) if args else data.strip()


@register("prepend")
def _prepend(data, args, context):
    return _template(args, context) + data


@register("append")
def _append(data, args, context):
    return data + _template(args, context)


@register("tolower")
def _tolower(data, args, context):
    return data.lower()


@register("toupper")
def _toupper(data, args, context):
    return data.upper()


@register("validfilename")
def _validfilename(data, args, context):
    return make_valid_file_name(data, "_", False)


@register("diacritics")
def _diacritics(data, args, context):
    if args != "replace":
        raise ValueError("unsupported diacritics filter argument")
    return strip_diacritics(data)


@register("htmldecode")
def _htmldecode(data, args, context):
    return html.unescape(data)


@register("htmlencode")
def _htmlencode(data, args, context):
    return html.escape(data)


# ---- encodings --------------------------------------------------------------


@register("base64decode")
def _base64decode(data, args, context):
    return base64url_decode(data).decode("utf-8")


@register("base64encode")
def _base64encode(data, args, context):
    return base64url_encode(data.encode("utf-8"))


@register("urldecode")
def _urldecode(data, args, context):
    return url_decode(data, context.encoding)


@register("urlencode")
def _urlencode(data, args, context):
    return url_encode(data, context.encoding)


# ---- dates ------------------------------------------------------------------


@register("timeparse", "dateparse")
def _dateparse(data, args, context):
    try:
        return dates.format_rfc1123z(dates.parse_layout(data, args))
    except ValueError as error:
        logger.debug(str(error))
        return data


@register("timeago", "reltime")
def _timeago(data, args, context):
    return dates.format_rfc1123z(dates.from_time_ago(data))


@register("fuzzytime")
def _fuzzytime(data, args, context):
    return dates.format_rfc1123z(dates.from_unknown(data))


# ---- json -------------------------------------------------------------------


@register("jsonjoinarray")
def _jsonjoinarray(data, args, context):
    selected = select_token(json.loads(data), args[0])
    if selected is MISSING or not isinstance(selected, list):
        raise ValueError(f"jsonjoinarray: {args[0]} is not an array")
    return args[1].join(token_to_string(item) or "" for item in selected)


# ---- debugging --------------------------------------------------------------


@register("hexdump")
def _hexdump(data, args, context):
    dump = "".join(f"{c}({ord(c):02X})" for c in data)
    logger.debug(
        "CardigannIndexer (%s): strdump: %s", context.indexer_id, dump
    )
    return data


@register("strdump")
def _strdump(data, args, context):
    shown = data.replace("\r", "\\r").replace("\n", "\\n")
    tag = f"({args}):" if args else ":"
    logger.debug(
        "CardigannIndexer (%s): strdump%s %s", context.indexer_id, tag, shown
    )
    return data


def apply_filters(
    data: str | None,
    filters: list[FilterBlock] | None,
    context: FilterContext,
) -> str | None:
    """Run ``filters`` in order; unknown filter names are ignored."""
    for block in filters or []:
        handler = FILTERS.get(block.name)
        if handler is not None:
            data = handler(data, block.args, context)
    return data
