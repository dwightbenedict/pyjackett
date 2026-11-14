"""Per-indexer search statistics and the recent search history."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from pyjackett.adapters.clock import SYSTEM_CLOCK, Clock

MAX_HISTORY_ENTRIES = 200

OUTCOME_OK = "ok"
OUTCOME_CACHE = "cache"
OUTCOME_ERROR = "error"
OUTCOME_RATE_LIMITED = "rate_limited"


@dataclass
class IndexerStats:
    """Counters of one indexer since the server started."""

    searches: int = 0
    successes: int = 0
    cache_hits: int = 0
    errors: int = 0
    rate_limited: int = 0
    total_elapsed_ms: int = 0
    last_elapsed_ms: int | None = None
    last_error: str | None = None

    @property
    def tracker_requests(self) -> int:
        return self.successes + self.errors + self.rate_limited

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        requests = self.tracker_requests
        data["success_rate"] = self.successes / requests if requests else None
        data["average_elapsed_ms"] = (
            self.total_elapsed_ms // self.successes if self.successes else None
        )
        data["cache_hit_rate"] = self.cache_hits / self.searches if self.searches else None
        return data


@dataclass
class SearchRecord:
    """One search sent to one indexer."""

    when: str
    indexer_id: str
    term: str
    outcome: str
    results: int = 0
    elapsed_ms: int = 0
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class SearchRecorder:
    """Collects statistics; indexers report every search they run."""

    def __init__(
        self,
        clock: Clock = SYSTEM_CLOCK,
        capacity: int = MAX_HISTORY_ENTRIES,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._stats: dict[str, IndexerStats] = {}
        self._history: deque[SearchRecord] = deque(maxlen=capacity)

    # ---- recording ----------------------------------------------------------

    def record_success(self, indexer_id: str, term: str, results: int, elapsed_ms: int) -> None:
        with self._lock:
            stats = self._stats_of(indexer_id)
            stats.searches += 1
            stats.successes += 1
            stats.total_elapsed_ms += elapsed_ms
            stats.last_elapsed_ms = elapsed_ms
        self._remember(indexer_id, term, OUTCOME_OK, results, elapsed_ms)

    def record_cache_hit(self, indexer_id: str, term: str, results: int) -> None:
        with self._lock:
            stats = self._stats_of(indexer_id)
            stats.searches += 1
            stats.cache_hits += 1
        self._remember(indexer_id, term, OUTCOME_CACHE, results)

    def record_failure(self, indexer_id: str, term: str, error: str, rate_limited: bool) -> None:
        with self._lock:
            stats = self._stats_of(indexer_id)
            stats.searches += 1
            stats.last_error = error
            if rate_limited:
                stats.rate_limited += 1
            else:
                stats.errors += 1
        outcome = OUTCOME_RATE_LIMITED if rate_limited else OUTCOME_ERROR
        self._remember(indexer_id, term, outcome, error=error)

    def _stats_of(self, indexer_id: str) -> IndexerStats:
        return self._stats.setdefault(indexer_id, IndexerStats())

    def _remember(
        self,
        indexer_id: str,
        term: str,
        outcome: str,
        results: int = 0,
        elapsed_ms: int = 0,
        error: str | None = None,
    ) -> None:
        record = SearchRecord(
            self._clock.now().isoformat(),
            indexer_id,
            term,
            outcome,
            results,
            elapsed_ms,
            error,
        )
        with self._lock:
            self._history.appendleft(record)

    # ---- reading ------------------------------------------------------------

    def last_elapsed_ms(self, indexer_id: str) -> int | None:
        """How long the indexer's latest successful search took."""
        with self._lock:
            stats = self._stats.get(indexer_id)
            return stats.last_elapsed_ms if stats else None

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Statistics by indexer id."""
        with self._lock:
            return {k: v.to_json() for k, v in sorted(self._stats.items())}

    def totals(self) -> dict[str, Any]:
        with self._lock:
            merged = IndexerStats()
            for stats in self._stats.values():
                merged.searches += stats.searches
                merged.successes += stats.successes
                merged.cache_hits += stats.cache_hits
                merged.errors += stats.errors
                merged.rate_limited += stats.rate_limited
                merged.total_elapsed_ms += stats.total_elapsed_ms
            return merged.to_json()

    def history(self, limit: int = MAX_HISTORY_ENTRIES) -> list[dict]:
        """Newest search first."""
        with self._lock:
            return [r.to_json() for r in list(self._history)[:limit]]

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()
            self._history.clear()
