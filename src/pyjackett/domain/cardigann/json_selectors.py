"""Selector semantics for JSON responses.

Row and field selectors are JSONPath expressions optionally followed by
CSS-like filters (``:has(key)``, ``:not(key)``, ``:contains(text)``).
"""

from __future__ import annotations

import logging
from typing import Any

import regex

from pyjackett.domain.cardigann.definition import SelectorBlock
from pyjackett.domain.cardigann.filters import FilterContext, apply_filters
from pyjackett.domain.cardigann.html_selectors import SelectorError
from pyjackett.domain.cardigann.json_path import (
    MISSING,
    select_token,
    token_to_string,
)
from pyjackett.domain.cardigann.template import Variables, apply_template
from pyjackett.domain.text import normalize_space

logger = logging.getLogger(__name__)

_FILTER = regex.compile(r"\:(?<filter>.+?)\((?<key>.+?)\)(?=:|\z)")


# ---- filters after the path -------------------------------------------------


def _passes_has(parsed: Any, key: str) -> bool:
    if _FILTER.match(key):
        return parse_field_selector(parsed, key) is not None
    return select_token(parsed, key) is not MISSING


def _passes_filter(parsed: Any, name: str, key: str) -> bool:
    if name == "has":
        return _passes_has(parsed, key)
    if name == "not":
        return not _passes_has(parsed, key)
    if name == "contains":
        return key in (token_to_string(parsed) or "")
    logger.error("Unsupported JSON selector filter: %s", name)
    return True


def parse_field_selector(parsed: Any, row_selector: str) -> str | None:
    """Path part of ``row_selector``; None if a filter rejects ``parsed``."""
    path = row_selector.split(":")[0]
    if path.strip():
        target = select_token(parsed, path)
        if target is MISSING:
            return None
    else:
        target = parsed
    for match in _FILTER.finditer(row_selector):
        if not _passes_filter(
            target, match.group("filter"), match.group("key")
        ):
            return None
    return path


def select_rows(
    parsed_json: Any, row_selector: str, variables: Variables
) -> list[Any] | None:
    """Rows of a JSON document, or None when the selector is invalid."""
    row_selector = apply_template(row_selector, variables)
    path = row_selector.split(":")[0]
    filters = row_selector[len(path) :]
    try:
        rows = select_token(parsed_json, path)
        if rows is MISSING or not isinstance(rows, list):
            return None
        return [
            row
            for row in rows
            if parse_field_selector(row, filters) is not None
        ]
    except (ValueError, TypeError) as error:
        logger.debug(
            'Failed to parse JSON rows for "%s": %s', row_selector, error
        )
        return None


# ---- single values ----------------------------------------------------------


def _selected_text(selection: Any) -> str | None:
    if isinstance(selection, list):  # arrays become comma separated lists
        return ",".join(token_to_string(item) or "" for item in selection)
    return token_to_string(selection)


def _select_value(
    block: SelectorBlock,
    parent: Any,
    variables: Variables,
    required: bool,
) -> tuple[str | None, bool]:
    """Evaluate ``block.selector``; returns (value, matched)."""
    path = apply_template(block.selector.lstrip("."), variables)
    field_path = parse_field_selector(parent, path)
    selection = MISSING
    if field_path is not None:
        selection = select_token(parent, field_path) if field_path else parent
    if selection is MISSING:
        if required:
            raise SelectorError(f'Selector "{path}" didn\'t match {parent}')
        return None, False
    return _selected_text(selection), True


def _case_value(
    block: SelectorBlock,
    value: str | None,
    variables: Variables,
    required: bool,
) -> str | None:
    for key, template in block.case.items():
        if (value is not None and value == key) or key == "*":
            return apply_template(template, variables)
    if required:
        raise SelectorError(
            f'None of the case selectors "{",".join(block.case)}" matched'
        )
    return None


def handle_json_selector(
    block: SelectorBlock,
    parent: Any,
    variables: Variables,
    context: FilterContext,
    required: bool = True,
) -> str | None:
    """Extract and filter one value from a JSON object."""
    context.variables = variables
    if block.text is not None:
        text = apply_template(block.text, variables)
        return apply_filters(text, block.filters, context)
    value = None
    if block.selector is not None:
        value, matched = _select_value(block, parent, variables, required)
        if not matched:
            return None
    if block.case is not None:
        value = _case_value(block, value, variables, required)
        if value is None:
            return None
    return apply_filters(normalize_space(value), block.filters, context)
