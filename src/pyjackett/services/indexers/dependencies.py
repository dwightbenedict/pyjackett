"""The collaborators every indexer is built with."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol

from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.services.indexers.search_limit import SearchLimit
from pyjackett.services.ports import CertificateTrust, Clock, HttpClient, SecretProtector
from pyjackett.services.single_flight import SingleFlight

if TYPE_CHECKING:
    from pyjackett.services.indexers.base import BaseIndexer


class SearchCache(Protocol):
    """What an indexer needs from the results cache."""

    @property
    def ttl(self) -> timedelta:
        """Protocol method."""

    def search(self, indexer: BaseIndexer, query: TorznabQuery) -> list[ReleaseInfo] | None:
        """Protocol method."""

    def cache_results(
        self,
        indexer: BaseIndexer,
        query: TorznabQuery,
        releases: list[ReleaseInfo],
    ) -> None:
        """Protocol method."""


class StatsRecorder(Protocol):
    """Where indexers report the searches they run."""

    def record_success(self, indexer_id: str, term: str, results: int, elapsed_ms: int) -> None:
        """Protocol method."""

    def record_cache_hit(self, indexer_id: str, term: str, results: int) -> None:
        """Protocol method."""

    def record_failure(self, indexer_id: str, term: str, error: str, rate_limited: bool) -> None:
        """Protocol method."""


class NoStats:
    """Discards everything; the default when nobody collects statistics."""

    def record_success(self, indexer_id, term, results, elapsed_ms) -> None:
        pass

    def record_cache_hit(self, indexer_id, term, results) -> None:
        pass

    def record_failure(self, indexer_id, term, error, rate_limited) -> None:
        pass


@dataclass
class IndexerDependencies:
    protector: SecretProtector
    cache: SearchCache
    client_factory: Callable[[], HttpClient]
    trusted_certificates: CertificateTrust
    clock: Clock
    stats: StatsRecorder = field(default_factory=NoStats)
    search_limit: SearchLimit = field(default_factory=SearchLimit)
    single_flight: SingleFlight = field(default_factory=SingleFlight)
    max_rows: int | None = None  # releases parsed per tracker and search
    skip_failing: bool = False  # leave failing indexers out of "all"
    retries: int | None = None  # replaces the default request retries
