"""The clock, session signer and logging seams can be driven from tests."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
import pytest

from pyjackett.config.server_config import ServerConfig
from pyjackett.http.client import WebClient
from pyjackett.http.models import WebRequest, WebResult
from pyjackett.http.session import HttpSession
from pyjackett.indexers.retry import retry_request
from pyjackett.services.cache import ResultsCache
from pyjackett.services.log_cache import LogCache
from pyjackett.services.security import (
    SECONDS_PER_DAY,
    SESSION_DAYS,
    SecurityService,
)
from pyjackett.utils.clock import Stopwatch


class FakeClock:
    """Time only moves when a test (or a sleep) says so."""

    def __init__(self) -> None:
        self.seconds = 1_700_000_000.0
        self.slept: list[float] = []

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.seconds).astimezone()

    def time(self) -> float:
        return self.seconds

    def monotonic(self) -> float:
        return self.seconds

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.seconds += seconds

    def jitter(self, low: float, high: float) -> float:
        return 1.0


def test_stopwatch_measures_on_the_given_clock():
    clock = FakeClock()
    watch = Stopwatch(clock)
    clock.seconds += 1.5
    assert watch.elapsed_ms == 1500


async def test_retry_backs_off_on_the_injected_clock():
    clock = FakeClock()
    calls = []

    async def operation() -> WebResult:
        calls.append(1)
        return WebResult(status=500)

    result = await retry_request(operation, retries=2, name="x", clock=clock)
    assert result.status == 500
    assert len(calls) == 3
    assert clock.slept == [2.0, 4.0]


async def test_web_client_throttles_with_the_injected_clock():
    clock = FakeClock()
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    session = HttpSession(ServerConfig(), transport=transport)
    client = WebClient(session, clock, request_delay=5.0)
    request = WebRequest(url="http://tracker.test/")
    await client.get_result(request)
    assert clock.slept == []  # nothing to wait for on the first request
    clock.seconds += 2
    await client.get_result(request)
    assert clock.slept == [3.0]
    await session.aclose()


def test_cache_expires_entries_by_the_injected_clock():
    from pyjackett.core.query import TorznabQuery

    clock = FakeClock()
    config = ServerConfig()
    config.cache_ttl = 60
    cache = ResultsCache(config, clock)

    class Indexer:
        id = "x"
        name = "X"
        type = "public"

    query = TorznabQuery(query_type="search", search_term="a")
    cache.cache_results(Indexer(), query, [])
    assert cache.search(Indexer(), query) == []
    clock.seconds += 61
    assert cache.search(Indexer(), query) is None


def test_session_cookie_expires_by_the_injected_clock():
    clock = FakeClock()
    config = ServerConfig()
    security = SecurityService(config, clock)
    cookie = security.create_session_cookie()
    assert security.is_valid_session(cookie)
    assert not security.is_valid_session(cookie + "x")
    clock.seconds += SESSION_DAYS * SECONDS_PER_DAY + 1
    assert not security.is_valid_session(cookie)


def test_api_key_check():
    config = ServerConfig(api_key="key")
    security = SecurityService(config)
    assert security.is_valid_api_key(config.api_key)
    assert not security.is_valid_api_key("wrong")
    assert not security.is_valid_api_key(None)


def test_log_cache_attaches_once_and_detaches():
    logger = logging.getLogger("pyjackett.test-injection")
    handler = LogCache(logger=logger)
    handler.attach()
    handler.attach()
    assert logger.handlers.count(handler) == 1
    handler.set_debug(True)
    assert logger.level == logging.DEBUG
    handler.set_debug(False)
    assert logger.level == logging.INFO
    handler.detach()
    assert handler not in logger.handlers


def test_context_takes_the_environment_and_clock_from_its_caller(tmp_path):
    from pyjackett.app_context import build_context

    clock = FakeClock()
    context = build_context(
        tmp_path,
        include_bundled=False,
        environ={"PYJACKETT_KEY": "secret"},
        clock=clock,
    )
    assert context.clock is clock
    assert context.protector.unprotect(context.protector.protect("a")) == "a"
    assert not (tmp_path / "protection.key").exists()
    assert context.cache.ttl == timedelta(seconds=context.config.cache_ttl)


@pytest.mark.parametrize("found", [True, False])
async def test_indexer_verify_raises_a_domain_error(found):
    from pyjackett.core.exceptions import IndexerTestFailedError
    from pyjackett.indexers.base import BaseIndexer
    from pyjackett.indexers.result import IndexerResult

    class Stub(BaseIndexer):
        id = name = "stub"

        async def apply_configuration(self, config):
            raise NotImplementedError

        async def perform_query(self, query):
            return []

        async def results_for_query(self, query, is_meta_indexer=False):
            return IndexerResult(self, [object()] if found else [])

    indexer = Stub(None)
    if found:
        await indexer.verify()
    else:
        with pytest.raises(IndexerTestFailedError):
            await indexer.verify()
