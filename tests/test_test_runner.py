"""Indexer tests belong to the server: a dropped caller stops nothing."""

from __future__ import annotations

import asyncio

import pytest

from pyjackett.core.exceptions import IndexerTestFailedError

V1 = "/api/v1"


@pytest.fixture
def indexer(client, context):
    client.post(f"{V1}/indexers/faketracker/add")
    return context.indexers.get_indexer("faketracker")


async def test_a_test_outlives_a_caller_that_goes_away(context, indexer):
    release = asyncio.Event()

    async def slow_verify():
        await release.wait()

    indexer.verify = slow_verify
    caller = asyncio.create_task(context.test_runner.run("faketracker"))
    await asyncio.sleep(0)
    caller.cancel()  # the dashboard was reloaded
    await asyncio.gather(caller, return_exceptions=True)
    assert context.test_runner.is_running("faketracker")
    release.set()
    await context.test_runner.run("faketracker")  # joins, then finishes
    assert not context.test_runner.is_running("faketracker")
    assert indexer.last_error is None


async def test_callers_share_the_test_already_running(context, indexer):
    release = asyncio.Event()
    calls = []

    async def counted_verify():
        calls.append(1)
        await release.wait()

    indexer.verify = counted_verify
    runs = [
        asyncio.create_task(context.test_runner.run("faketracker"))
        for _ in range(3)
    ]
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*runs)
    assert len(calls) == 1


async def test_a_failed_test_is_remembered_on_the_indexer(context, indexer):
    async def nothing_found():
        raise IndexerTestFailedError("No results.")

    indexer.verify = nothing_found
    with pytest.raises(IndexerTestFailedError):
        await context.test_runner.run("faketracker")
    assert indexer.last_error == "No results."
    assert not context.test_runner.is_running("faketracker")
