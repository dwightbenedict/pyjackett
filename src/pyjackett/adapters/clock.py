"""Time, sleeping and jitter behind one seam so tests can control them."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime


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


SYSTEM_CLOCK = SystemClock()
