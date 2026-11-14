"""Measuring how long something took."""

from __future__ import annotations

from pyjackett.services.ports import Clock


class Stopwatch:
    """Measures how long something took on the given clock."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._started = clock.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return int((self._clock.monotonic() - self._started) * 1000)
