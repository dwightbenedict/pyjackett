"""Parses JSON search responses into releases."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyjackett.cardigann.json_path import MISSING, select_token
from pyjackett.cardigann.json_selectors import (
    handle_json_selector,
    select_rows,
)
from pyjackett.cardigann.result_context import ResultContext
from pyjackett.cardigann.row_filters import should_skip_row
from pyjackett.cardigann.template import Variables
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo

logger = logging.getLogger(__name__)

PARENT_SELECTOR_PREFIX = ".."


class NoRowsError(Exception):
    """The row selector matched nothing and that is not 'no results'."""


def _declares_no_results(
    parsed: Any, context: ResultContext, variables: Variables
) -> bool:
    """True when the optional ``rows.count`` selector reports zero rows."""
    count_block = context.search.rows.count
    if count_block is None:
        return False
    try:
        text = handle_json_selector(
            count_block, parsed, variables, context.filter_context
        )
        return int(text) < 1
    except Exception as error:
        logger.debug("Failed to parse JSON rows count: %s", error)
        return False


def _row_objects(row: Any, context: ResultContext) -> list[dict]:
    """The object(s) to read fields from for one row."""
    rows_block = context.search.rows
    target = row
    if rows_block.attribute is not None:
        target = select_token(row, rows_block.attribute)
        if target is MISSING or target is None:
            return []
    if rows_block.multiple:
        children = target.values() if isinstance(target, dict) else target
        return [child for child in children if isinstance(child, dict)]
    return [target]


def _parse_object(
    row: dict,
    item: dict,
    context: ResultContext,
    variables: Variables,
    query: TorznabQuery,
    search_url: str,
) -> ReleaseInfo | None:
    def extract(spec, required):
        selector = spec.block.selector or ""
        parent = row if selector.startswith(PARENT_SELECTOR_PREFIX) else item
        return handle_json_selector(
            spec.block, parent, variables, context.filter_context, required
        )

    release = context.row_parser.parse_row(extract, variables, search_url)
    skip = should_skip_row(
        context.search.rows.filters,
        release,
        query,
        context.caps,
        variables,
        json.dumps(row),
        context.indexer_id,
    )
    return None if skip else release


def parse_json_results(
    parsed: Any,
    context: ResultContext,
    variables: Variables,
    query: TorznabQuery,
    search_url: str,
) -> list[ReleaseInfo]:
    """Parse a decoded JSON document; field errors propagate."""
    if _declares_no_results(parsed, context, variables):
        return []
    rows = select_rows(parsed, context.search.rows.selector, variables)
    if rows is None:
        if context.search.rows.missing_attribute_equals_no_results:
            return []
        raise NoRowsError("Error Parsing Rows Selector. There are 0 rows.")
    releases = []
    for row in rows:
        for item in _row_objects(row, context):
            release = _parse_object(
                row, item, context, variables, query, search_url
            )
            if release is not None:
                releases.append(release)
    return releases
