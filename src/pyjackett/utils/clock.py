"""Time, sleeping and jitter behind one seam so tests can control them."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Everything the code needs to know about, or wait for, time."""

    def now(self) -> datetime:
        """Wall clock time in the local zone."""

    def time(self) -> float:
        """Seconds since the epoch."""

    def monotonic(self) -> float:
        """Seconds from an arbitrary origin; never goes backwards."""

    async def sleep(self, seconds: float) -> None:
        """Wait without blocking the event loop."""

    def jitter(self, low: float, high: float) -> float:
        """A random factor between ``low`` and ``high``."""


class SystemClock:
    """The real clock."""

    def now(self) -> datetime:
        return datetime.now().astimezone()

    def time(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def jitter(self, low: float, high: float) -> float:
        return random.uniform(low, high)


SYSTEM_CLOCK: Clock = SystemClock()


class Stopwatch:
    """Measures how long something took on the given clock."""

    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._clock = clock
        self._started = clock.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return int((self._clock.monotonic() - self._started) * 1000)
