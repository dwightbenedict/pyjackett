"""What an indexer can search for (the Torznab ``t=caps`` document)."""

from __future__ import annotations

from pyjackett.core.category_mappings import CategoryMappings
from pyjackett.core.search_modes import MODE_PARAMETERS, SearchMode


class TorznabCapabilities:
    """Search modes, parameters, limits and categories of one indexer."""

    def __init__(self) -> None:
        self.limits_max: int | None = 100
        self.limits_default: int | None = 100
        self.search_available = True
        self.supports_raw_search = False
        # TV imdb search is disabled upstream (issue #8107); definitions may
        # opt in explicitly through ``allowtvsearchimdb``.
        self.tv_search_imdb_available = False
        self.categories = CategoryMappings()
        self._parameters: dict[SearchMode, list[str]] = {
            mode: [] for mode in SearchMode if mode is not SearchMode.SEARCH
        }

    # ---- parameters ----------------------------------------------------

    def set_parameters(self, mode: SearchMode, names: list[str]) -> None:
        """Replace the parameters of ``mode``; unknown names are errors."""
        allowed = MODE_PARAMETERS[mode]
        seen: list[str] = []
        for name in names:
            name = name.lower()
            if name not in allowed:
                raise ValueError(f"Not supported {mode.value} param: {name}")
            if name in seen:
                raise ValueError(f"Duplicate {mode.value} param: {name}")
            seen.append(name)
        self._parameters[mode] = seen

    def parameters(self, mode: SearchMode) -> list[str]:
        return list(self._parameters[mode])

    def supports(self, mode: SearchMode, parameter: str) -> bool:
        if parameter == "imdbid" and mode is SearchMode.TV:
            return self.tv_search_imdb_available
        return parameter in self._parameters[mode]

    def mode_available(self, mode: SearchMode) -> bool:
        if mode is SearchMode.SEARCH:
            return self.search_available
        return bool(self._parameters[mode])

    def advertised_parameters(self, mode: SearchMode) -> list[str]:
        """Parameters in canonical order; ``q`` is always supported."""
        if mode is SearchMode.SEARCH:
            return ["q"]
        return [
            name
            for name in MODE_PARAMETERS[mode]
            if name == "q" or self.supports(mode, name)
        ]

    # ---- convenience flags used by query routing --------------------------

    @property
    def tv_search_available(self) -> bool:
        return self.mode_available(SearchMode.TV)

    @property
    def movie_search_available(self) -> bool:
        return self.mode_available(SearchMode.MOVIE)

    @property
    def music_search_available(self) -> bool:
        return self.mode_available(SearchMode.MUSIC)

    @property
    def book_search_available(self) -> bool:
        return self.mode_available(SearchMode.BOOK)

    @property
    def movie_search_imdb_available(self) -> bool:
        return self.supports(SearchMode.MOVIE, "imdbid")

    @property
    def movie_search_tmdb_available(self) -> bool:
        return self.supports(SearchMode.MOVIE, "tmdbid")

    @property
    def tv_search_tvdb_available(self) -> bool:
        return self.supports(SearchMode.TV, "tvdbid")

    @property
    def tv_search_tvrage_available(self) -> bool:
        return self.supports(SearchMode.TV, "rid")

    @property
    def tv_search_tmdb_available(self) -> bool:
        return self.supports(SearchMode.TV, "tmdbid")

    # ---- aggregation --------------------------------------------------------

    def merge(self, other: TorznabCapabilities) -> TorznabCapabilities:
        """Union with another indexer's caps (used by meta indexers)."""
        self.search_available = self.search_available or other.search_available
        self.supports_raw_search = (
            self.supports_raw_search or other.supports_raw_search
        )
        for mode, names in other._parameters.items():
            merged = self._parameters[mode] + [
                name for name in names if name not in self._parameters[mode]
            ]
            self._parameters[mode] = merged
        self.categories.merge(other.categories)
        return self
