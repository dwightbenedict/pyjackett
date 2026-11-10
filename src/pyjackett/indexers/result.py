"""The outcome of querying one indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pyjackett.core.release import ReleaseInfo

if TYPE_CHECKING:
    from pyjackett.indexers.base import BaseIndexer


@dataclass
class IndexerResult:
    indexer: BaseIndexer
    releases: list[ReleaseInfo] = field(default_factory=list)
    elapsed_ms: int = 0
    is_from_cache: bool = False
