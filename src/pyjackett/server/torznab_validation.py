"""Parameter checks that precede a Torznab search."""

from __future__ import annotations

from dataclasses import dataclass

from pyjackett.core.query import TorznabQuery
from pyjackett.indexers.base import BaseIndexer
from pyjackett.utils.numbers import format_imdb_id

INCORRECT_PARAMETER = 201
FUNCTION_NOT_AVAILABLE = 203


@dataclass
class TorznabProblem:
    code: int
    description: str


def _unsupported(kind: str, scope: str) -> TorznabProblem:
    return TorznabProblem(
        FUNCTION_NOT_AVAILABLE,
        f"Function Not Available: {kind} is not supported for {scope} "
        "search by this indexer",
    )


def _check_imdb(query: TorznabQuery, indexer: BaseIndexer):
    query.imdb_id = format_imdb_id(query.imdb_id)
    if query.imdb_id is None:
        return TorznabProblem(
            INCORRECT_PARAMETER, "Incorrect parameter: invalid imdbid format"
        )
    caps = indexer.torznab_caps
    if query.is_movie_search and not caps.movie_search_imdb_available:
        return _unsupported("imdbid", "movie")
    if query.is_tv_search and not caps.tv_search_imdb_available:
        return _unsupported("imdbid", "TV")
    return None


def _check_tmdb(query: TorznabQuery, indexer: BaseIndexer):
    caps = indexer.torznab_caps
    if query.is_movie_search and not caps.movie_search_tmdb_available:
        return _unsupported("tmdbid", "movie")
    if query.is_tv_search and not caps.tv_search_tmdb_available:
        return _unsupported("tmdbid", "TV")
    return None


def _check_tvdb(query: TorznabQuery, indexer: BaseIndexer):
    if query.is_tv_search and not indexer.torznab_caps.tv_search_available:
        return _unsupported("tvdbid", "movie")
    return None


def validate_query(
    query: TorznabQuery, indexer: BaseIndexer
) -> TorznabProblem | None:
    """First problem found with the id parameters, or None."""
    if query.imdb_id is not None:
        problem = _check_imdb(query, indexer)
        if problem:
            return problem
    if query.tmdb_id is not None:
        problem = _check_tmdb(query, indexer)
        if problem:
            return problem
    if query.tvdb_id is not None:
        return _check_tvdb(query, indexer)
    return None
