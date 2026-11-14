"""Turns HTTP query parameters into :class:`TorznabQuery` objects."""

from __future__ import annotations

from collections.abc import Mapping

import regex

from pyjackett.domain.category_catalog import MOVIES
from pyjackett.domain.numbers import coerce_int, format_imdb_id
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.text import is_blank

_SEASON_EPISODE = regex.compile(r"\bS(\d{2,4})E(\d{2,4}[A-Za-z]?)$")
_EPISODE = regex.compile(r"\bE(\d{2,4}[A-Za-z]?)$")
_SEASON = regex.compile(r"\bS(\d{2,4})$")
_SHORT_IMDB_LENGTH = 10

_INT_PARAMETERS = {
    "season": "season",
    "rid": "rage_id",
    "tvdbid": "tvdb_id",
    "tvmazeid": "tvmaze_id",
    "tmdbid": "tmdb_id",
    "traktid": "trakt_id",
    "doubanid": "douban_id",
    "year": "year",
}
_TEXT_PARAMETERS = {
    "album": "album",
    "artist": "artist",
    "label": "label",
    "track": "track",
    "genre": "genre",
    "title": "title",
    "author": "author",
    "publisher": "publisher",
}


def _parse_categories(params: Mapping[str, str]) -> list[int]:
    raw = params.get("cat")
    if raw is not None:
        return [int(c) for c in raw.split(",") if c.strip()]
    if params.get("t") == "movie" and not is_blank(params.get("imdbid")):
        return [MOVIES.id]
    return []


def _apply_optional(query: TorznabQuery, params: Mapping[str, str]) -> None:
    for name, attribute in _INT_PARAMETERS.items():
        if not is_blank(params.get(name)):
            setattr(query, attribute, int(params[name]))
    for name, attribute in _TEXT_PARAMETERS.items():
        if not is_blank(params.get(name)):
            setattr(query, attribute, params[name])


def torznab_query(params: Mapping[str, str]) -> TorznabQuery:
    """Build the query from ``?t=...&q=...`` style parameters."""
    query = TorznabQuery(
        query_type=params.get("t") or "search",
        search_term=params.get("q"),
        imdb_id=params.get("imdbid"),
        episode=params.get("ep"),
        categories=_parse_categories(params),
        api_key=params.get("apikey"),
    )
    for name, attribute in (
        ("extended", "extended"),
        ("limit", "limit"),
        ("offset", "offset"),
    ):
        if not is_blank(params.get(name)):
            setattr(query, attribute, coerce_int(params[name]))
    if params.get("cache", "").lower() in ("true", "false"):
        query.cache = params["cache"].lower() == "true"
    _apply_optional(query, params)
    return query


def potato_query(params: Mapping[str, str]) -> TorznabQuery:
    return TorznabQuery(
        query_type="TorrentPotato",
        categories=[MOVIES.id],
        search_term=params.get("search"),
        imdb_id=params.get("imdbid"),
    )


# ---- dashboard manual search ------------------------------------------------


def _split_season_episode(text: str, query: TorznabQuery) -> str:
    """Move a trailing ``S01E02`` / ``E02`` / ``S01`` out of the text."""
    match = _SEASON_EPISODE.search(text)
    if match:
        query.season = int(match.group(1))
        query.episode = match.group(2).lstrip("0")
        return text[: match.start()].strip()
    match = _EPISODE.search(text)
    if match:
        query.episode = match.group(1).lstrip("0")
        text = text[: match.start()].strip()
    match = _SEASON.search(text)
    if match:
        query.season = int(match.group(1))
        text = text[: match.start()].strip()
    return text


def _imdb_only_query(query: TorznabQuery) -> TorznabQuery | None:
    """A search term like ``tt1234567`` is an IMDb lookup."""
    term = query.sanitized_search_term
    if not term.startswith("tt") or len(term) > _SHORT_IMDB_LENGTH:
        return None
    imdb_id = format_imdb_id(term)
    if imdb_id is None:
        return None
    return TorznabQuery(
        query_type="search",
        imdb_id=imdb_id,
        categories=query.categories,
        season=query.season,
        episode=query.episode,
    )


def manual_search_query(params: Mapping[str, object]) -> TorznabQuery:
    """Build the query of the dashboard's manual search form."""
    query = TorznabQuery(query_type="search")
    text = f"{params.get('query') or ''}".strip()
    if text:
        text = _split_season_episode(text, query)
    query.search_term = text.strip()
    query.categories = list(params.get("categories") or [])
    for name, attribute in (
        ("imdbid", "imdb_id"),
        ("tmdbid", "tmdb_id"),
        ("tvdbid", "tvdb_id"),
        ("tvmazeid", "tvmaze_id"),
    ):
        value = params.get(name)
        if value not in (None, ""):
            setattr(
                query, attribute, value if name == "imdbid" else int(value)
            )
    return _imdb_only_query(query) or query
