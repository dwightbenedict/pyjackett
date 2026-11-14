"""In-memory cache of search results.

Identical requests are answered from memory instead of hitting the tracker
again. Test queries and failed requests are never cached, and the cache is
bounded both by age (TTL) and by results per indexer.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pyjackett.adapters.clock import SYSTEM_CLOCK, Clock
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.server_config import ServerConfig
from pyjackett.domain.tracker_result import TrackerCacheResult

if TYPE_CHECKING:
    from pyjackett.services.indexers.base import BaseIndexer

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY_LISTING = 300
MAX_RESULTS_LISTING = 3000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass
class _CachedQuery:
    created: datetime
    results: list[ReleaseInfo]


@dataclass
class _TrackerCache:
    tracker_id: str
    tracker_name: str
    tracker_type: str | None
    queries: dict[str, _CachedQuery] = field(default_factory=dict)


def _query_hash(query: TorznabQuery) -> str:
    return hashlib.sha256(query.cache_key().encode("utf-8")).hexdigest()


class ResultsCache:
    """Thread-safe store of releases keyed by indexer and query."""

    def __init__(
        self,
        config: ServerConfig,
        clock: Clock = SYSTEM_CLOCK,
        max_total_results: int | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._max_total_results = max_total_results
        self._trackers: dict[str, _TrackerCache] = {}
        self._lock = threading.RLock()

    @property
    def ttl(self) -> timedelta:
        return timedelta(seconds=self._config.cache_ttl)

    # ---- writing ----------------------------------------------------------

    def cache_results(
        self,
        indexer: BaseIndexer,
        query: TorznabQuery,
        releases: list[ReleaseInfo],
    ) -> None:
        if query.is_test:
            return
        with self._lock:
            if not self._is_enabled():
                return
            tracker = self._trackers.setdefault(
                indexer.id,
                _TrackerCache(indexer.id, indexer.name, indexer.type),
            )
            tracker.queries[_query_hash(query)] = _CachedQuery(
                self._clock.now(), [release.clone() for release in releases]
            )
            self._prune_by_max_results(tracker)
            self._prune_by_total_results()

    # ---- reading ----------------------------------------------------------

    def search(
        self, indexer: BaseIndexer, query: TorznabQuery
    ) -> list[ReleaseInfo] | None:
        with self._lock:
            if not self._is_enabled():
                return None
            self._prune_by_ttl()
            tracker = self._trackers.get(indexer.id)
            cached = (
                tracker.queries.get(_query_hash(query)) if tracker else None
            )
            if cached is None:
                return None
            logger.debug(
                "CACHE hit / %s: %d releases", indexer.id, len(cached.results)
            )
            return [release.clone() for release in cached.results]

    def cached_results(self) -> list[TrackerCacheResult]:
        """Newest-first listing of everything cached, for the dashboard."""
        with self._lock:
            if not self._is_enabled():
                return []
            self._prune_by_ttl()
            listing = [
                result
                for tracker in self._trackers.values()
                for result in self._listing_for(tracker)
            ]
        listing.sort(key=_by_publish_date, reverse=True)
        return listing[:MAX_RESULTS_LISTING]

    @staticmethod
    def _listing_for(tracker: _TrackerCache) -> list[TrackerCacheResult]:
        seen: set[str | None] = set()
        listing: list[TrackerCacheResult] = []
        newest_first = sorted(
            tracker.queries.values(), key=lambda q: q.created, reverse=True
        )
        for query in newest_first:
            for release in query.results:
                if release.guid in seen:
                    continue
                seen.add(release.guid)
                listing.append(
                    TrackerCacheResult.from_release(
                        release,
                        tracker.tracker_name,
                        tracker.tracker_id,
                        tracker.tracker_type,
                        query.created,
                    )
                )
        return listing[:MAX_RESULTS_PER_QUERY_LISTING]

    # ---- invalidation -------------------------------------------------------

    def clean_indexer_cache(self, indexer: BaseIndexer) -> None:
        with self._lock:
            self._trackers.pop(indexer.id, None)

    def clean_cache(self) -> None:
        with self._lock:
            self._trackers.clear()

    # ---- pruning ------------------------------------------------------------

    def _is_enabled(self) -> bool:
        if not self._config.cache_enabled:
            self._trackers.clear()  # the user may have just disabled it
        return self._config.cache_enabled

    def _prune_by_ttl(self) -> None:
        expiry = self._clock.now() - self.ttl
        for tracker in self._trackers.values():
            expired = [
                k for k, q in tracker.queries.items() if q.created < expiry
            ]
            for key in expired:
                del tracker.queries[key]

    def _prune_by_total_results(self) -> None:
        """Drop the oldest queries of any indexer until the cache fits."""
        if self._max_total_results is None:
            return
        entries = [
            (query.created, tracker, key, len(query.results))
            for tracker in self._trackers.values()
            for key, query in tracker.queries.items()
        ]
        total = sum(size for *_, size in entries)
        entries.sort(key=lambda entry: entry[0])
        for _, tracker, key, size in entries:
            if total <= self._max_total_results:
                break
            del tracker.queries[key]
            total -= size

    def _prune_by_max_results(self, tracker: _TrackerCache) -> None:
        """Drop the oldest queries until the indexer fits its quota."""
        newest_first = sorted(
            tracker.queries.items(), key=lambda kv: kv[1].created, reverse=True
        )
        total = sum(len(q.results) for _, q in newest_first)
        while (
            total > self._config.cache_max_results_per_indexer and newest_first
        ):
            key, oldest = newest_first.pop()
            del tracker.queries[key]
            total -= len(oldest.results)


def _by_publish_date(result: TrackerCacheResult) -> datetime:
    return result.publish_date or _EPOCH
