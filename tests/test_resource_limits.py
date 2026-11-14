"""Bounds that keep a small host healthy: concurrency, cache, credentials."""

from __future__ import annotations

import asyncio

import pytest

from pyjackett.adapters.definition_cache import DefinitionCache
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.server_config import ServerConfig
from pyjackett.services.cache import ResultsCache
from pyjackett.services.environment import (
    ADMIN_PASSWORD_ENV,
    API_KEY_ENV,
    CACHE_MAX_RELEASES_ENV,
    DEFAULT_CACHE_MAX_RELEASES,
    MAX_CONCURRENCY_ENV,
    MAX_ROWS_ENV,
    RETRIES_ENV,
    SKIP_FAILING_ENV,
    SYNC_DEFINITIONS_ENV,
    cache_limit_from,
    non_negative_int,
    positive_int,
    skip_failing_from,
    sync_definitions_from,
)
from pyjackett.services.indexers.search_limit import SearchLimit
from pyjackett.wiring import build_context


class Indexer:
    def __init__(self, indexer_id: str) -> None:
        self.id = indexer_id
        self.name = indexer_id
        self.type = "public"


def releases(count: int) -> list[ReleaseInfo]:
    return [ReleaseInfo(title=f"r{n}", guid=f"g{n}") for n in range(count)]


def query(term: str) -> TorznabQuery:
    return TorznabQuery(query_type="search", search_term=term)


# ---- SearchLimit ------------------------------------------------------------


async def test_search_limit_never_runs_more_than_its_slots():
    limit = SearchLimit(2)
    running = peak = 0

    async def search() -> None:
        nonlocal running, peak
        async with limit.slot():
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(*(search() for _ in range(8)))
    assert peak == 2


@pytest.mark.parametrize("slots", [None, 0])
async def test_search_limit_without_slots_is_unbounded(slots):
    limit = SearchLimit(slots)
    running = peak = 0

    async def search() -> None:
        nonlocal running, peak
        async with limit.slot():
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(*(search() for _ in range(5)))
    assert peak == 5


async def test_search_limit_frees_the_slot_of_a_cancelled_search():
    limit = SearchLimit(1)
    started = asyncio.Event()

    async def hold() -> None:
        async with limit.slot():
            started.set()
            await asyncio.sleep(60)

    task = asyncio.ensure_future(hold())
    await started.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    async with asyncio.timeout(1):
        async with limit.slot():
            pass


# ---- cache cap --------------------------------------------------------------


def test_cache_drops_the_oldest_queries_over_the_total_cap():
    from test_injection import FakeClock

    clock = FakeClock()
    cache = ResultsCache(ServerConfig(), clock, max_total_results=10)
    first, second, third = (Indexer(n) for n in "abc")
    cache.cache_results(first, query("old"), releases(6))
    clock.seconds += 1
    cache.cache_results(second, query("mid"), releases(3))
    clock.seconds += 1
    cache.cache_results(third, query("new"), releases(4))  # 13 > 10
    assert cache.search(first, query("old")) is None
    assert len(cache.search(second, query("mid"))) == 3
    assert len(cache.search(third, query("new"))) == 4


def test_cache_without_a_total_cap_keeps_everything():
    cache = ResultsCache(ServerConfig())
    for name in "abc":
        cache.cache_results(Indexer(name), query("q"), releases(50))
    assert all(
        len(cache.search(Indexer(name), query("q"))) == 50 for name in "abc"
    )


# ---- environment ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("8", 8), (" 3 ", 3), ("0", None), ("-2", None), ("x", None), ("", None)],
)
def test_positive_int_ignores_unusable_values(value, expected):
    assert positive_int({MAX_CONCURRENCY_ENV: value}, MAX_CONCURRENCY_ENV) == (
        expected
    )


def test_positive_int_of_an_unset_variable_is_none():
    assert positive_int({}, MAX_CONCURRENCY_ENV) is None


def test_cache_limit_defaults_and_overrides():
    assert cache_limit_from({}) == DEFAULT_CACHE_MAX_RELEASES
    assert cache_limit_from({CACHE_MAX_RELEASES_ENV: "500"}) == 500
    assert cache_limit_from({CACHE_MAX_RELEASES_ENV: "nope"}) == (
        DEFAULT_CACHE_MAX_RELEASES
    )


def test_environment_fixes_the_api_key_and_password_across_restarts(tmp_path):
    environ = {API_KEY_ENV: "fixed-key", ADMIN_PASSWORD_ENV: "s3cret"}
    for _ in range(2):  # a restart on an ephemeral disk starts from scratch
        data_dir = tmp_path / "fresh"
        for leftover in data_dir.glob("*.json"):
            leftover.unlink()
        context = build_context(
            data_dir, include_bundled=False, environ=environ
        )
        assert context.config.api_key == "fixed-key"
        assert context.security.is_valid_api_key("fixed-key")
        assert context.security.check_authorised("s3cret")
        assert not context.security.check_authorised("admin")


def test_without_environment_credentials_stay_generated(tmp_path):
    context = build_context(tmp_path, include_bundled=False, environ={})
    assert context.config.api_key
    assert context.security.uses_default_credentials


# ---- definition cache -------------------------------------------------------

DEFINITION = """\
id: cached
name: Cached
description: A tracker
language: en-US
type: public
encoding: UTF-8
links:
  - https://cached.test/
caps:
  categorymappings:
    - {id: 1, cat: Movies}
  modes:
    search: [q]
search:
  paths:
    - path: /search
  rows:
    selector: tr
  fields:
    title:
      selector: a
"""


class CountingParser:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def __call__(self, text: str):
        from pyjackett.domain.cardigann.definition_loader import (
            parse_definition,
        )

        self.texts.append(text)
        return parse_definition(text)


def test_definition_cache_parses_a_text_only_once(tmp_path):
    parser = CountingParser()
    cache = DefinitionCache(tmp_path / "defs.bin", parser)
    first = cache.parse(DEFINITION)
    assert cache.parse(DEFINITION) is first
    assert len(parser.texts) == 1


def test_definition_cache_survives_a_restart(tmp_path):
    path = tmp_path / "defs.bin"
    cache = DefinitionCache(path, CountingParser())
    expected = cache.parse(DEFINITION)
    cache.save()
    parser = CountingParser()
    restarted = DefinitionCache(path, parser)
    assert restarted.parse(DEFINITION) == expected
    assert parser.texts == []


def test_definition_cache_reparses_an_edited_text(tmp_path):
    path = tmp_path / "defs.bin"
    cache = DefinitionCache(path, CountingParser())
    cache.parse(DEFINITION)
    cache.save()
    parser = CountingParser()
    edited = DefinitionCache(path, parser).parse(
        DEFINITION.replace("name: Cached", "name: Renamed")
    )
    assert edited.name == "Renamed"
    assert len(parser.texts) == 1


def test_definition_cache_drops_definitions_that_were_not_used(tmp_path):
    path = tmp_path / "defs.bin"
    cache = DefinitionCache(path, CountingParser())
    cache.parse(DEFINITION)
    cache.parse(DEFINITION.replace("id: cached", "id: other"))
    cache.save()
    second = DefinitionCache(path, CountingParser())
    second.parse(DEFINITION)  # the other one is gone after this save
    second.save()
    parser = CountingParser()
    DefinitionCache(path, parser).parse(
        DEFINITION.replace("id: cached", "id: other")
    )
    assert len(parser.texts) == 1


def test_definition_cache_ignores_a_damaged_file(tmp_path):
    path = tmp_path / "defs.bin"
    path.write_bytes(b"not a pickle")
    parser = CountingParser()
    cache = DefinitionCache(path, parser)
    assert cache.parse(DEFINITION).id == "cached"
    assert len(parser.texts) == 1
    cache.save()  # and the next start gets a good file
    again = CountingParser()
    DefinitionCache(path, again).parse(DEFINITION)
    assert again.texts == []


def test_definition_cache_does_not_hide_invalid_definitions(tmp_path):
    cache = DefinitionCache(tmp_path / "defs.bin", CountingParser())
    with pytest.raises(ValueError):
        cache.parse("id: broken\nunknownKey: 1\n")


def test_definition_cache_without_a_path_stores_nothing(tmp_path):
    cache = DefinitionCache(None, CountingParser())
    cache.parse(DEFINITION)
    cache.save()
    assert list(tmp_path.iterdir()) == []


def test_cardigann_source_parses_each_definition_once_per_text(tmp_path):
    from pyjackett.services.indexers.dependencies import IndexerDependencies
    from pyjackett.services.indexers.sources import CardigannSource

    definitions = tmp_path / "defs"
    definitions.mkdir()
    (definitions / "cached.yml").write_text(DEFINITION, encoding="utf-8")
    parser = CountingParser()
    cache = DefinitionCache(tmp_path / "defs.bin", parser)
    source = CardigannSource([definitions], cache)
    context = build_context(tmp_path / "data", include_bundled=False)
    dependencies: IndexerDependencies = context.indexers._deps
    for _ in range(2):
        assert [i.id for i in source.load(dependencies)] == ["cached"]
    assert len(parser.texts) == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, True), ("1", True), ("true", True), ("0", False), ("Off", False)],
)
def test_definition_sync_can_be_switched_off(value, expected):
    environ = {} if value is None else {SYNC_DEFINITIONS_ENV: value}
    assert sync_definitions_from(environ) is expected


# ---- row cap, failing indexers, retries ------------------------------------


def search_through_fake_tracker(tmp_path, environ):
    import xml.etree.ElementTree as ET

    from fastapi.testclient import TestClient

    import fakes
    from conftest import FIXTURES, fake_tracker, sign_in_as_admin
    from pyjackett.interfaces.api import create_app

    context = build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(fake_tracker),
        include_bundled=False,
        environ=environ,
    )
    with TestClient(create_app(context)) as client:
        sign_in_as_admin(client)
        client.post("/api/v2.0/indexers/faketracker/config", json=[])
        reply = client.get(
            "/api/v2.0/indexers/faketracker/results/torznab/api",
            params={"apikey": context.config.api_key, "t": "search"},
        )
    return ET.fromstring(reply.text).findall(".//item")


def test_a_row_cap_limits_the_releases_parsed_per_search(tmp_path):
    assert len(search_through_fake_tracker(tmp_path / "a", {})) == 2
    capped = search_through_fake_tracker(tmp_path / "b", {MAX_ROWS_ENV: "1"})
    assert len(capped) == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0", 0), ("2", 2), (" 1 ", 1), ("-1", None), ("x", None), ("", None)],
)
def test_non_negative_int_allows_zero(value, expected):
    environ = {RETRIES_ENV: value}
    assert non_negative_int(environ, RETRIES_ENV) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("0", False), ("1", True), ("Yes", True)],
)
def test_skipping_failing_indexers_is_opt_in(value, expected):
    environ = {} if value is None else {SKIP_FAILING_ENV: value}
    assert skip_failing_from(environ) is expected


def test_retries_can_be_set_from_the_environment(tmp_path):
    for value, expected in ((None, 2), ("0", 0), ("1", 1)):
        environ = {} if value is None else {RETRIES_ENV: value}
        context = build_context(
            tmp_path / (value or "default"),
            extra_definition_dirs=[__import__("conftest").FIXTURES],
            include_bundled=False,
            environ=environ,
        )
        context.indexers.init_indexers()
        indexer = context.indexers.get_indexer("faketracker")
        assert indexer.retry_attempts() == expected
