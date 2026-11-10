"""The search modes of Torznab and the parameters each one accepts."""

from __future__ import annotations

from enum import StrEnum


class SearchMode(StrEnum):
    SEARCH = "search"
    TV = "tv-search"
    MOVIE = "movie-search"
    MUSIC = "music-search"
    BOOK = "book-search"


# Canonical parameter order, as advertised in the capabilities document.
MODE_PARAMETERS: dict[SearchMode, tuple[str, ...]] = {
    SearchMode.SEARCH: ("q",),
    SearchMode.TV: (
        "q",
        "season",
        "ep",
        "imdbid",
        "tvdbid",
        "rid",
        "tmdbid",
        "tvmazeid",
        "traktid",
        "doubanid",
        "year",
        "genre",
    ),
    SearchMode.MOVIE: (
        "q",
        "imdbid",
        "tmdbid",
        "traktid",
        "doubanid",
        "year",
        "genre",
    ),
    SearchMode.MUSIC: (
        "q",
        "album",
        "artist",
        "label",
        "track",
        "year",
        "genre",
    ),
    SearchMode.BOOK: ("q", "title", "author", "publisher", "year", "genre"),
}
