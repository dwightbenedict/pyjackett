"""The public indexers a fresh install configures."""

from __future__ import annotations

# Major, general purpose trackers that answered with relevant results for
# software, movie, TV and anime searches in a health check of every public
# indexer (Nov 2026). Left out on purpose: adult and tiny regional sites,
# trackers that were dead, blocked or erratic (EZTV, showRSS, Anime Tosho,
# Tokyo Toshokan, the KickassTorrents mirrors, ...) and 1337x, which needs
# FlareSolverr. "PYJACKETT_INDEXERS=all" configures every public indexer.
DEFAULT_PUBLIC_INDEXERS = frozenset(
    {
        "thepiratebay",
        "therarbg",
        "torrentgalaxyclone",
        "limetorrents",
        "torrentdownload",
        "torrentscsv",
        "torrentkitty",
        "yts",
        "nyaasi",
        "internetarchive",
        "linuxtracker",
        "rutracker-ru",
        "torrent9",
    }
)
