"""Identical searches made at the same time share one run."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.search_limit import SearchLimit
from pyjackett.services.single_flight import SingleFlight
from pyjackett.wiring import build_context


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


# ---- SingleFlight -----------------------------------------------------------


async def test_callers_with_one_key_share_a_single_run():
    flights = SingleFlight()
    runs = []
    gate = asyncio.Event()

    async def work() -> list[int]:
        runs.append(1)
        await gate.wait()
        return [1, 2]

    callers = [
        asyncio.ensure_future(flights.run("k", work, list)) for _ in range(3)
    ]
    await settle()
    gate.set()
    results = await asyncio.gather(*callers)
    assert len(runs) == 1
    assert results == [[1, 2]] * 3
    assert results[0] is not results[1] is not results[2]  # joiners get copies


async def test_different_keys_run_separately_and_a_key_can_run_again():
    flights = SingleFlight()
    runs = []

    async def work() -> int:
        runs.append(1)
        return len(runs)

    await asyncio.gather(flights.run("a", work), flights.run("b", work))
    await flights.run("a", work)
    assert len(runs) == 3


async def test_work_goes_on_while_one_caller_still_waits():
    flights = SingleFlight()
    gate = asyncio.Event()

    async def work() -> str:
        await gate.wait()
        return "done"

    quitter = asyncio.ensure_future(flights.run("k", work))
    stayer = asyncio.ensure_future(flights.run("k", work))
    await settle()
    quitter.cancel()
    await settle()
    gate.set()
    assert await stayer == "done"


async def test_work_stops_when_every_caller_gave_up():
    flights = SingleFlight()
    cancelled = asyncio.Event()

    async def work() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    callers = [asyncio.ensure_future(flights.run("k", work)) for _ in range(2)]
    await settle()
    for caller in callers:
        caller.cancel()
    async with asyncio.timeout(1):
        await cancelled.wait()


async def test_a_failure_reaches_every_caller():
    flights = SingleFlight()
    gate = asyncio.Event()

    async def work() -> None:
        await gate.wait()
        raise ValueError("boom")

    callers = [asyncio.ensure_future(flights.run("k", work)) for _ in range(2)]
    await settle()
    gate.set()
    results = await asyncio.gather(*callers, return_exceptions=True)
    assert [type(r) for r in results] == [ValueError, ValueError]


# ---- indexers ---------------------------------------------------------------


class CountingIndexer(BaseIndexer):
    id = name = "counting"

    def __init__(self, dependencies) -> None:
        super().__init__(dependencies)
        self.calls = 0
        self.running = 0
        self.peak = 0
        self.gate: asyncio.Event | None = None
        self.fail = False

    async def apply_configuration(self, config):
        raise NotImplementedError

    def can_handle_query(self, query) -> bool:
        return True

    def _accepts(self, query, is_meta_indexer) -> bool:
        return True

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        self.calls += 1
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.fail:
                raise ValueError("tracker down")
            return [ReleaseInfo(title=query.search_term, guid="g")]
        finally:
            self.running -= 1

    def _post_process(self, query, releases):
        return releases

    def _record_outcome(self, query, releases) -> None:
        pass


def make_indexer(tmp_path, slots=None) -> CountingIndexer:
    context = build_context(tmp_path, include_bundled=False, environ={})
    deps = dataclasses.replace(
        context.indexers._deps, search_limit=SearchLimit(slots)
    )
    return CountingIndexer(deps)


def query(term: str) -> TorznabQuery:
    return TorznabQuery(query_type="search", search_term=term)


async def test_identical_searches_hit_the_tracker_once(tmp_path):
    indexer = make_indexer(tmp_path)
    indexer.gate = asyncio.Event()
    searches = [
        asyncio.ensure_future(indexer.results_for_query(query("x")))
        for _ in range(4)
    ]
    await settle()
    indexer.gate.set()
    results = await asyncio.gather(*searches)
    assert indexer.calls == 1
    assert all(len(r.releases) == 1 for r in results)
    releases = [r.releases[0] for r in results]
    assert len({id(release) for release in releases}) == 4  # none shared


async def test_different_searches_each_hit_the_tracker(tmp_path):
    indexer = make_indexer(tmp_path)
    await asyncio.gather(
        indexer.results_for_query(query("a")),
        indexer.results_for_query(query("b")),
    )
    assert indexer.calls == 2


async def test_a_failed_search_is_recorded_once_for_all_waiters(tmp_path):
    from pyjackett.errors import IndexerError

    indexer = make_indexer(tmp_path)
    indexer.gate = asyncio.Event()
    indexer.fail = True
    searches = [
        asyncio.ensure_future(indexer.results_for_query(query("x")))
        for _ in range(3)
    ]
    await settle()
    indexer.gate.set()
    results = await asyncio.gather(*searches, return_exceptions=True)
    assert all(isinstance(r, IndexerError) for r in results)
    assert indexer.calls == 1
    assert indexer.health._error_count == 1


@pytest.mark.parametrize("slots", [1, 2])
async def test_searches_wait_for_a_free_slot(tmp_path, slots):
    indexer = make_indexer(tmp_path, slots)
    await asyncio.gather(
        *(indexer.results_for_query(query(str(n))) for n in range(6))
    )
    assert indexer.calls == 6
    assert indexer.peak <= slots


# ---- failing indexers -------------------------------------------------------


async def test_the_aggregate_skips_failing_indexers_when_asked(tmp_path):
    from pyjackett.services.indexers.meta.imdb import ImdbSupport
    from pyjackett.services.indexers.meta.meta_indexer import AggregateIndexer

    searched = []

    class Member(CountingIndexer):
        async def perform_query(self, query):
            searched.append(self.id)
            return [ReleaseInfo(title="t", guid=self.id)]

    for skip, expected in ((False, {"ok", "bad"}), (True, {"ok"})):
        searched.clear()
        context = build_context(tmp_path / str(skip), include_bundled=False)
        deps = dataclasses.replace(context.indexers._deps, skip_failing=skip)
        members = []
        for name in ("ok", "bad"):
            member = Member(deps)
            member.id = member.name = name
            member.is_configured = True
            members.append(member)
        members[1].health.record_failure()
        assert members[1].is_failing
        aggregate = AggregateIndexer(deps, ImdbSupport(None), members)
        await aggregate.results_for_query(query("x"))
        assert set(searched) == expected
