"""Indexers implemented in code rather than by a YAML definition.

To add one: subclass :class:`NativeIndexer`, set its identity attributes,
implement ``perform_query`` and list the class in ``NATIVE_INDEXERS``.
"""

from __future__ import annotations

from pyjackett.indexers.native.avistaz.sites import (
    AvistaZ,
    CinemaZ,
    ExoticaZ,
    PrivateHD,
)
from pyjackett.indexers.native.base import NativeIndexer
from pyjackett.indexers.native.gazelle.sites import (
    AlphaRatio,
    BrokenStones,
    DicMusic,
    GreatPosterWall,
    Orpheus,
    Redacted,
    SecretCinema,
)
from pyjackett.indexers.native.torrents_csv import TorrentsCsv

# Classes instantiated at startup, each taking ``IndexerDependencies``.
NATIVE_INDEXERS: list[type[NativeIndexer]] = [
    AlphaRatio,
    AvistaZ,
    BrokenStones,
    CinemaZ,
    DicMusic,
    ExoticaZ,
    GreatPosterWall,
    Orpheus,
    PrivateHD,
    Redacted,
    SecretCinema,
    TorrentsCsv,
]
