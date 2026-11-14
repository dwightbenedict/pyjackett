"""Runs indexer tests in the background, out of reach of dropped requests."""

from __future__ import annotations

import asyncio

from pyjackett.errors import describe_failure
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.manager import IndexerManager


class IndexerTestRunner:
    """Tests indexers; a test belongs to the server, not to the caller.

    A caller that goes away (a reloaded dashboard) leaves the test running,
    and asking for an indexer that is already being tested joins that test.
    """

    def __init__(self, indexers: IndexerManager) -> None:
        self._indexers = indexers
        self._running: dict[str, asyncio.Task[None]] = {}

    def is_running(self, indexer_id: str) -> bool:
        return indexer_id in self._running

    async def run(self, indexer_id: str) -> None:
        """Test the indexer and raise its failure, if any."""
        indexer = self._indexers.get_indexer(indexer_id)
        task = self._running.get(indexer.id) or self._start(indexer)
        await asyncio.shield(task)

    async def close(self) -> None:
        tasks = list(self._running.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _start(self, indexer: BaseIndexer) -> asyncio.Task[None]:
        task = asyncio.create_task(self._test(indexer))
        self._running[indexer.id] = task
        task.add_done_callback(lambda done: self._finished(indexer, done))
        return task

    async def _test(self, indexer: BaseIndexer) -> None:
        try:
            await self._indexers.test_indexer(indexer.id)
        except Exception as error:
            indexer.last_error = describe_failure(error)
            raise
        indexer.last_error = None

    def _finished(self, indexer: BaseIndexer, task: asyncio.Task[None]) -> None:
        self._running.pop(indexer.id, None)
        if not task.cancelled():
            task.exception()  # seen here when no caller is left to see it
