"""Row level filters (``search.rows.filters``)."""

from __future__ import annotations

import logging

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.cardigann.definition import FilterBlock
from pyjackett.domain.cardigann.template import Variables
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo

logger = logging.getLogger(__name__)


def _id_search_covers_query(query: TorznabQuery, caps: TorznabCapabilities) -> bool:
    """True when the tracker searched by id, so titles need no matching."""
    imdb = caps.movie_search_imdb_available or caps.tv_search_imdb_available
    checks = (
        (query.imdb_id is not None and imdb),
        (
            query.tmdb_id is not None
            and (caps.movie_search_tmdb_available or caps.tv_search_tmdb_available)
        ),
        (query.tvdb_id is not None and caps.tv_search_tvdb_available),
        (query.douban_id is not None and imdb),
        (query.trakt_id is not None and imdb),
        (query.tvmaze_id is not None and caps.tv_search_imdb_available),
        (query.rage_id is not None and caps.tv_search_imdb_available),
    )
    return any(checks)


def _and_match(
    block: FilterBlock,
    release: ReleaseInfo,
    query: TorznabQuery,
    caps: TorznabCapabilities,
    variables: Variables,
    indexer_id: str,
) -> bool:
    """True if the release must be skipped (some query word is missing)."""
    if _id_search_covers_query(query, caps):
        return False
    limit = int(block.args) if block.args is not None else -1
    keywords = variables.get(".Keywords")
    if query.match_query_string_and(release.title or "", limit, keywords):
        return False
    logger.debug(
        "CardigannIndexer (%s): skipping %s (andmatch filter)",
        indexer_id,
        release.title,
    )
    return True


def should_skip_row(
    filters: list[FilterBlock] | None,
    release: ReleaseInfo,
    query: TorznabQuery,
    caps: TorznabCapabilities,
    variables: Variables,
    row_text: str,
    indexer_id: str,
) -> bool:
    """Apply the row filters; True if the row must be dropped."""
    skip = False
    for block in filters or []:
        if block.name == "andmatch":
            skip |= _and_match(block, release, query, caps, variables, indexer_id)
        elif block.name == "strdump":
            logger.debug("CardigannIndexer (%s): row strdump: %s", indexer_id, row_text)
        else:
            logger.error(
                "CardigannIndexer (%s): Unsupported rows filter: %s",
                indexer_id,
                block.name,
            )
    return skip
