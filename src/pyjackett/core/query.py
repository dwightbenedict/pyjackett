"""A Torznab search request, independent of the HTTP layer."""

from __future__ import annotations

import copy
import dataclasses
import json
from dataclasses import dataclass, field

from pyjackett.core.category_catalog import (
    MOVIES,
    MOVIES_3D,
    MOVIES_BLURAY,
    MOVIES_DVD,
    MOVIES_FOREIGN,
    MOVIES_HD,
    MOVIES_OTHER,
    MOVIES_SD,
    MOVIES_UHD,
    MOVIES_WEBDL,
)
from pyjackett.core.query_text import (
    episode_search_string,
    sanitize_search_term,
)
from pyjackett.utils.text import (
    contains_ignore_case,
    is_blank,
    significant_words,
)

_FALLBACK_MOVIE_CATEGORIES = (
    MOVIES,
    MOVIES_FOREIGN,
    MOVIES_OTHER,
    MOVIES_SD,
    MOVIES_HD,
    MOVIES_3D,
    MOVIES_BLURAY,
    MOVIES_DVD,
    MOVIES_WEBDL,
    MOVIES_UHD,
)


@dataclass
class TorznabQuery:
    """Every parameter a Torznab client may send."""

    query_type: str | None = None
    categories: list[int] = field(default_factory=list)
    extended: int = 0
    api_key: str | None = None
    limit: int = 0
    offset: int = 0
    rage_id: int | None = None
    tvdb_id: int | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    tvmaze_id: int | None = None
    trakt_id: int | None = None
    douban_id: int | None = None
    season: int | None = None
    episode: str | None = None
    search_term: str | None = None
    album: str | None = None
    artist: str | None = None
    label: str | None = None
    track: str | None = None
    year: int | None = None
    genre: str | None = None
    author: str | None = None
    title: str | None = None
    publisher: str | None = None
    interactive_search: bool = False
    is_test: bool = False
    cache: bool = True
    _word_cache: list[str] | None = field(default=None, repr=False)

    # ---- search kind -------------------------------------------------

    @property
    def is_search(self) -> bool:
        return self.query_type == "search"

    @property
    def is_tv_search(self) -> bool:
        return self.query_type == "tvsearch"

    @property
    def is_movie_search(self) -> bool:
        is_potato = self.query_type == "TorrentPotato"
        return self.query_type == "movie" or (
            is_potato and not is_blank(self.search_term)
        )

    @property
    def is_music_search(self) -> bool:
        return self.query_type == "music"

    @property
    def is_book_search(self) -> bool:
        return self.query_type == "book"

    # ---- external id presence ------------------------------------------

    @property
    def is_tvrage_query(self) -> bool:
        return self.rage_id is not None

    @property
    def is_tvdb_query(self) -> bool:
        return self.tvdb_id is not None

    @property
    def is_imdb_query(self) -> bool:
        return self.imdb_id is not None

    @property
    def is_tmdb_query(self) -> bool:
        return self.tmdb_id is not None

    @property
    def is_tvmaze_query(self) -> bool:
        return self.tvmaze_id is not None

    @property
    def is_trakt_query(self) -> bool:
        return self.trakt_id is not None

    @property
    def is_douban_query(self) -> bool:
        return self.douban_id is not None

    @property
    def is_genre_query(self) -> bool:
        return self.genre is not None

    @property
    def imdb_id_short(self) -> str | None:
        return self.imdb_id.lstrip("t") if self.imdb_id else None

    # ---- derived classification ------------------------------------------

    @property
    def is_id_search(self) -> bool:
        text_filters = (
            self.episode,
            self.album,
            self.artist,
            self.label,
            self.genre,
            self.track,
            self.author,
            self.title,
            self.publisher,
        )
        external_ids = (
            self.imdb_id,
            self.tvdb_id,
            self.rage_id,
            self.trakt_id,
            self.tvmaze_id,
            self.tmdb_id,
            self.douban_id,
            self.year,
        )
        return (
            any(not is_blank(value) for value in text_filters)
            or (self.season or 0) > 0
            or any(value is not None for value in external_ids)
        )

    @property
    def is_rss_search(self) -> bool:
        return is_blank(self.search_term) and not self.is_id_search

    @property
    def has_specified_categories(self) -> bool:
        return bool(self.categories)

    # ---- text helpers ------------------------------------------------------

    @property
    def sanitized_search_term(self) -> str:
        return sanitize_search_term(self.search_term)

    def episode_search_string(self) -> str:
        return episode_search_string(self.season, self.episode)

    def query_string(self) -> str:
        episode = self.episode_search_string()
        return f"{self.sanitized_search_term} {episode}".strip()

    def match_query_string_and(
        self,
        title: str,
        limit: int | None = None,
        query_string_override: str | None = None,
    ) -> bool:
        """True if every significant query word appears in ``title``.

        Some trackers do not support AND logic for search terms; this lets
        us filter the results ourselves. ``limit`` caps the number of query
        characters compared (for trackers that truncate titles).
        """
        if self._word_cache is None:
            text = query_string_override
            if is_blank(text):
                text = self.query_string()
            if limit and limit > 0:
                text = text[:limit]
            self._word_cache = significant_words(text)
        return all(contains_ignore_case(title, w) for w in self._word_cache)

    # ---- copies -------------------------------------------------------------

    def clone(self) -> TorznabQuery:
        duplicate = copy.copy(self)
        duplicate.categories = list(self.categories)
        duplicate._word_cache = (
            list(self._word_cache) if self._word_cache else None
        )
        return duplicate

    def create_fallback(self, search: str) -> TorznabQuery:
        fallback = self.clone()
        if not fallback.categories:
            fallback.categories = [c.id for c in _FALLBACK_MOVIE_CATEGORIES]
        fallback.search_term = search
        return fallback

    def cache_key(self) -> str:
        """Stable text identifying the query for the results cache."""
        data = dataclasses.asdict(self)
        for ignored in ("cache", "_word_cache"):
            data.pop(ignored, None)
        if data["search_term"] is None:
            data["search_term"] = ""
        return json.dumps(data, sort_keys=True, default=str)
