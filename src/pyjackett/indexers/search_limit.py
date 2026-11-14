"""Caps how many indexer searches run at the same time."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class SearchLimit:
    """A server-wide bound on in-flight indexer searches.

    Shared by every request, so many clients searching at once still cost a
    fixed amount of memory and CPU. ``None`` (or 0) means no bound.
    """

    def __init__(self, slots: int | None = None) -> None:
        self._semaphore = asyncio.Semaphore(slots) if slots else None

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one search slot, waiting for a free one when needed."""
        if self._semaphore is None:
            yield
            return
        async with self._semaphore:
            yield
