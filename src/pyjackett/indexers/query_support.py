"""Decides whether an indexer can answer a given Torznab query."""

from __future__ import annotations

import logging

from pyjackett.core.capabilities import TorznabCapabilities
from pyjackett.core.query import TorznabQuery

logger = logging.getLogger(__name__)

POTATO_QUERY_TYPE = "TorrentPotato"


def _supports_imdb_lookup(
    caps: TorznabCapabilities, query: TorznabQuery
) -> bool:
    if not query.is_imdb_query:
        return False
    return (caps.tv_search_imdb_available and query.is_tv_search) or (
        caps.movie_search_imdb_available and query.is_movie_search
    )


def _requires_missing_imdb_support(
    caps: TorznabCapabilities, query: TorznabQuery
) -> bool:
    """Movie queries by imdb id need imdb support (potato carries a title)."""
    return (
        query.is_movie_search
        and query.is_imdb_query
        and not caps.movie_search_imdb_available
        and query.query_type != POTATO_QUERY_TYPE
    )


def _supports_search_mode(
    caps: TorznabCapabilities, query: TorznabQuery
) -> bool:
    return (
        (caps.search_available and query.is_search)
        or (caps.tv_search_available and query.is_tv_search)
        or (caps.movie_search_available and query.is_movie_search)
        or (caps.music_search_available and query.is_music_search)
        or (caps.book_search_available and query.is_book_search)
    )


def _supports_external_id(
    caps: TorznabCapabilities, query: TorznabQuery
) -> bool:
    return (
        (caps.tv_search_tvrage_available and query.is_tvrage_query)
        or (caps.tv_search_tvdb_available and query.is_tvdb_query)
        or (caps.movie_search_imdb_available and query.is_imdb_query)
        or (
            caps.movie_search_tmdb_available
            and query.is_tmdb_query
            and query.is_movie_search
        )
        or (
            caps.tv_search_tmdb_available
            and query.is_tmdb_query
            and query.is_tv_search
        )
    )


def can_handle_query(
    caps: TorznabCapabilities, query: TorznabQuery | None
) -> bool:
    """Mirror of Jackett's capability routing rules."""
    if query is None:
        return False
    if query.query_type == "caps":
        return True
    if _supports_imdb_lookup(caps, query):
        return True
    if _requires_missing_imdb_support(caps, query):
        return False
    return _supports_search_mode(caps, query) or _supports_external_id(
        caps, query
    )


def can_handle_categories(
    caps: TorznabCapabilities,
    query: TorznabQuery,
    indexer_name: str,
    is_meta_indexer: bool = False,
) -> bool:
    """False when none of the requested categories exist in the indexer."""
    if not query.has_specified_categories:
        return True
    supported = caps.categories.supported_categories(query.categories)
    if not supported:
        if not is_meta_indexer:
            logger.error(
                "All categories provided are unsupported in %s: %s",
                indexer_name,
                ",".join(map(str, query.categories)),
            )
        return False
    unsupported = [c for c in query.categories if c not in supported]
    if unsupported and not is_meta_indexer:
        logger.warning(
            "Some of the categories provided are unsupported in %s: %s",
            indexer_name,
            ",".join(map(str, unsupported)),
        )
    return True
