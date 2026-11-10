"""A single search result returned by an indexer."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyjackett.indexers.base import BaseIndexer

_BYTES_PER_GIGABYTE = 1024.0**3


@dataclass(eq=False)
class ReleaseInfo:
    """Torznab-flavoured description of one torrent."""

    title: str | None = None
    guid: str | None = None
    link: str | None = None
    details: str | None = None
    publish_date: datetime | None = None
    category: list[int] = field(default_factory=list)
    size: int | None = None
    files: int | None = None
    grabs: int | None = None
    description: str | None = None
    rage_id: int | None = None
    tvdb_id: int | None = None
    imdb: int | None = None
    tmdb: int | None = None
    tvmaze_id: int | None = None
    trakt_id: int | None = None
    douban_id: int | None = None
    genres: list[str] | None = None
    languages: list[str] = field(default_factory=list)
    subs: list[str] = field(default_factory=list)
    year: int | None = None
    author: str | None = None
    book_title: str | None = None
    publisher: str | None = None
    artist: str | None = None
    album: str | None = None
    label: str | None = None
    track: str | None = None
    seeders: int | None = None
    peers: int | None = None
    poster: str | None = None
    info_hash: str | None = None
    magnet_uri: str | None = None
    minimum_ratio: float | None = None
    minimum_seed_time: int | None = None
    download_volume_factor: float | None = None
    upload_volume_factor: float | None = None
    origin: BaseIndexer | None = field(default=None, repr=False)

    @property
    def gain(self) -> float:
        """Seeders per gigabyte; used to rank aggregated results."""
        if self.seeders is None or self.size is None:
            return 0.0
        return self.seeders * (self.size / _BYTES_PER_GIGABYTE)

    def clone(self) -> ReleaseInfo:
        """Shallow copy that does not share mutable collections."""
        duplicate = copy.copy(self)
        duplicate.category = list(self.category)
        duplicate.languages = list(self.languages)
        duplicate.subs = list(self.subs)
        if self.genres is not None:
            duplicate.genres = list(self.genres)
        return duplicate
