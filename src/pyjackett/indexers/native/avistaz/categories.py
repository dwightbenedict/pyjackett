"""Category tables of the AvistaZ network."""

from __future__ import annotations

CategoryTable = list[tuple[str, str] | tuple[str, str, str]]

ANIME_Z: CategoryTable = [
    ("TV", "TV/Anime", "Anime > TV"),
    ("TV_SHORT", "TV/Anime", "Anime > TV Short"),
    ("MOVIE", "Movies", "Anime > Movie"),
    ("SPECIAL", "TV/Anime", "Anime > Special"),
    ("OVA", "TV/Anime", "Anime > OVA"),
    ("ONA", "TV/Anime", "Anime > ONA"),
    ("MUSIC", "TV/Anime", "Anime > Music"),
    ("MANGA", "Books/Comics", "Manga > Manga"),
    ("NOVEL", "Books/Foreign", "Manga > Novel"),
    ("ONE_SHOT", "Books/Foreign", "Manga > One-Shot"),
]
