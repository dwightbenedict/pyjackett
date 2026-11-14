"""Parses HTML and XML search responses into releases."""

from __future__ import annotations

import logging

from pyjackett.cardigann import html_dom
from pyjackett.cardigann.html_dom import Element
from pyjackett.cardigann.html_selectors import handle_selector
from pyjackett.cardigann.result_context import ResultContext
from pyjackett.cardigann.row_filters import should_skip_row
from pyjackett.cardigann.template import Variables, apply_template
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.utils import dates

logger = logging.getLogger(__name__)


def merge_following_rows(rows: list[Element], count: int) -> list[Element]:
    """Fold each group of ``count`` rows after a row into that row.

    Used by trackers that spread one result over several ``<tr>``.
    """
    if count <= 0:
        return rows
    remaining = list(rows)
    index = 0
    while index < len(remaining):
        current = remaining[index]
        following = remaining[index + 1 : index + 1 + count]
        for row in following:
            html_dom.copy_children(row, current)
        del remaining[index + 1 : index + 1 + count]
        index += 1
    return remaining


def select_rows(
    document, context: ResultContext, variables: Variables
) -> list[Element]:
    rows_block = context.search.rows
    selector = apply_template(rows_block.selector, variables)
    rows = list(html_dom.query_selector_all(document, selector))
    return merge_following_rows(rows, rows_block.after)


# ---- date headers -----------------------------------------------------------


def _previous_candidate(element: Element) -> Element | None:
    """Previous sibling, or the parent's previous sibling at the start."""
    previous = html_dom.previous_element(element)
    parent = html_dom.parent_element(element)
    if previous is None and parent is not None:
        previous = html_dom.previous_element(parent)
    return previous


def find_date_header(
    row: Element, context: ResultContext, variables
) -> str | None:
    """Walk backwards from ``row`` to the nearest date heading."""
    block = context.search.rows.dateheaders
    candidate = _previous_candidate(row)
    while candidate is not None:
        try:
            return handle_selector(
                block, candidate, variables, context.filter_context
            )
        except Exception:  # not a date heading, keep looking
            candidate = _previous_candidate(candidate)
    return None


def _apply_date_header(
    row: Element, release: ReleaseInfo, context: ResultContext, variables
) -> None:
    block = context.search.rows.dateheaders
    if block is None or release.publish_date is not None:
        return
    value = find_date_header(row, context, variables)
    if value is None and not block.optional:
        raise RuntimeError(f"No date header row found for {release.title}")
    if value is not None:
        release.publish_date = dates.from_unknown(value)


# ---- rows -------------------------------------------------------------------


def _parse_row(
    row: Element,
    context: ResultContext,
    variables: Variables,
    query: TorznabQuery,
    search_url: str,
) -> ReleaseInfo | None:
    """One release from ``row``; None if a row filter dropped it."""

    def extract(spec, required):
        return handle_selector(
            spec.block, row, variables, context.filter_context, required
        )

    release = context.row_parser.parse_row(extract, variables, search_url)
    skip = should_skip_row(
        context.search.rows.filters,
        release,
        query,
        context.caps,
        variables,
        html_dom.to_html(row),
        context.indexer_id,
    )
    if skip:
        return None
    _apply_date_header(row, release, context, variables)
    return release


def parse_html_results(
    document,
    context: ResultContext,
    variables: Variables,
    query: TorznabQuery,
    search_url: str,
) -> list[ReleaseInfo]:
    """Parse every row of a document; unparsable rows are logged, skipped."""
    releases = []
    for row in select_rows(document, context, variables):
        if context.is_full(releases):
            break
        try:
            release = _parse_row(row, context, variables, query, search_url)
        except Exception:
            logger.exception(
                "CardigannIndexer (%s): Error while parsing row '%s'",
                context.indexer_id,
                html_dom.to_html(row),
            )
            continue
        if release is not None:
            releases.append(release)
    return releases
