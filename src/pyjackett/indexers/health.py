"""Tracks whether an indexer is currently answering queries."""

from __future__ import annotations

import time
from collections.abc import Callable

ERROR_VALIDITY_SECONDS = 10 * 60
MAX_VALIDITY_SECONDS = 24 * 60 * 60


class IndexerHealth:
    """Healthy/failing state with exponential back-off on repeated errors."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._error_count = 0
        self._expires_at = 0.0

    def record_success(self, validity_seconds: float) -> None:
        self._error_count = 0
        self._expires_at = self._clock() + validity_seconds

    def record_failure(self) -> None:
        """Each consecutive failure doubles how long the state is kept."""
        delay = min(
            MAX_VALIDITY_SECONDS,
            ERROR_VALIDITY_SECONDS * 2**self._error_count,
        )
        self._error_count += 1
        self._expires_at = self._clock() + delay

    def record_rate_limit(self, retry_after_seconds: float) -> None:
        self._expires_at = self._clock() + retry_after_seconds

    def reset(self) -> None:
        self._error_count = 0
        self._expires_at = 0.0

    @property
    def is_healthy(self) -> bool:
        return self._error_count == 0 and self._expires_at > self._clock()

    @property
    def is_failing(self) -> bool:
        return self._error_count > 0 and self._expires_at > self._clock()
