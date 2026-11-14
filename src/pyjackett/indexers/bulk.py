"""Runs one indexer operation over many indexers and reports each outcome."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pyjackett.core.exceptions import describe_failure
from pyjackett.indexers.manager import IndexerManager
from pyjackett.indexers.test_runner import IndexerTestRunner

Outcome = dict[str, Any]


class BulkIndexerOperations:
    """Add, test and delete several indexers; one failure stops no other."""

    def __init__(
        self, indexers: IndexerManager, test_runner: IndexerTestRunner
    ) -> None:
        self._indexers = indexers
        self._test_runner = test_runner

    async def add(self, ids: list[str]) -> list[Outcome]:
        return await self._run(ids, self._add)

    async def test(self, ids: list[str]) -> list[Outcome]:
        return await self._run(ids, self._test)

    async def delete(self, ids: list[str]) -> list[Outcome]:
        return await self._run(ids, self._delete)

    async def _add(self, indexer_id: str) -> None:
        self._indexers.add_indexer(indexer_id)

    async def _test(self, indexer_id: str) -> None:
        await self._test_runner.run(indexer_id)

    async def _delete(self, indexer_id: str) -> None:
        self._indexers.delete_indexer(indexer_id)

    @staticmethod
    async def _run(
        ids: list[str], operation: Callable[[str], Awaitable[None]]
    ) -> list[Outcome]:
        async def attempt(indexer_id: str) -> Outcome:
            try:
                await operation(indexer_id)
            except Exception as error:
                return {
                    "id": indexer_id,
                    "status": "error",
                    "error": describe_failure(error),
                }
            return {"id": indexer_id, "status": "ok", "error": None}

        return list(await asyncio.gather(*(attempt(i) for i in ids)))
