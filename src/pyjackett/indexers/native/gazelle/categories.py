"""Category tables of the Gazelle based trackers."""

from __future__ import annotations

CategoryTable = list[tuple[str, str] | tuple[str, str, str]]

BROKEN_STONES: CategoryTable = [
    ("1", "PC/Mac", "MacOS Apps"),
    ("2", "PC/Mac", "MacOS Games"),
    ("3", "PC/Mobile-iOS", "iOS Apps"),
    ("4", "PC/Mobile-iOS", "iOS Games"),
    ("5", "Other", "Graphics"),
    ("6", "Audio", "Audio"),
    ("7", "Other", "Tutorials"),
    ("8", "Other", "Other"),
]

DIC_MUSIC: CategoryTable = [
    ("1", "Audio", "Music"),
    ("2", "PC", "Applications"),
]

ORPHEUS: CategoryTable = [
    ("1", "Audio", "Music"),
    ("2", "PC", "Applications"),
    ("3", "Books/EBook", "E-Books"),
    ("4", "Audio/Audiobook", "Audiobooks"),
    ("5", "Other", "E-Learning Videos"),
    ("6", "Other", "Comedy"),
    ("7", "Books/Comics", "Comics"),
]

REDACTED: CategoryTable = [
    ("1", "Audio", "Music"),
    ("2", "PC", "Applications"),
    ("3", "Books", "E-Books"),
    ("4", "Audio/Audiobook", "Audiobooks"),
    ("5", "Movies", "E-Learning Videos"),
    ("6", "Audio", "Comedy"),
    ("7", "Books", "Comics"),
]

ALPHA_RATIO: CategoryTable = [
    ("1", "TV/SD", "TvSD"),
    ("2", "TV/HD", "TvHD"),
    ("3", "TV/UHD", "TvUHD"),
    ("4", "TV/SD", "TvDVDRip"),
    ("5", "TV/SD", "TvPackSD"),
    ("6", "TV/HD", "TvPackHD"),
    ("7", "TV/UHD", "TvPackUHD"),
    ("8", "Movies/SD", "MovieSD"),
    ("9", "Movies/HD", "MovieHD"),
    ("10", "Movies/UHD", "MovieUHD"),
    ("11", "Movies/SD", "MoviePackSD"),
    ("12", "Movies/HD", "MoviePackHD"),
    ("13", "Movies/UHD", "MoviePackUHD"),
    ("14", "XXX", "MovieXXX"),
    ("15", "Movies/BluRay", "Bluray"),
    ("16", "TV/Anime", "AnimeSD"),
    ("17", "TV/Anime", "AnimeHD"),
    ("18", "PC/Games", "GamesPC"),
    ("19", "Console/XBox", "GamesxBox"),
    ("20", "Console/PS4", "GamesPS"),
    ("21", "Console/Wii", "GamesNin"),
    ("22", "PC/0day", "AppsWindows"),
    ("23", "PC/Mac", "AppsMAC"),
    ("24", "PC/0day", "AppsLinux"),
    ("25", "PC/Mobile-Other", "AppsMobile"),
    ("26", "XXX", "0dayXXX"),
    ("27", "Books", "eBook"),
    ("28", "Audio/Audiobook", "AudioBook"),
    ("29", "Audio/Other", "Music"),
    ("30", "Other", "Misc"),
]

GREAT_POSTER_WALL: CategoryTable = [
    ("1", "Movies", "Movies 电影"),
]

SECRET_CINEMA: CategoryTable = [
    ("1", "Movies", "Movies"),
    ("2", "Audio", "Music"),
]
