"""The clock, session signer and logging seams can be driven from tests."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import fakes
from pyjackett.adapters.clock import SYSTEM_CLOCK
from pyjackett.adapters.http.client import WebClient
from pyjackett.adapters.http.session import HttpSession
from pyjackett.adapters.server_config_store import generate_api_key
from pyjackett.domain.http_models import WebRequest, WebResult
from pyjackett.domain.server_config import ServerConfig
from pyjackett.services.cache import ResultsCache
from pyjackett.services.indexers.retry import retry_request
from pyjackett.services.log_cache import LogCache
from pyjackett.services.security import (
    SECONDS_PER_DAY,
    SESSION_DAYS,
    SecurityService,
)
from pyjackett.services.stopwatch import Stopwatch


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
    client_factory = fakes.mock_network(lambda request: fakes.Response(200))
    session = HttpSession(ServerConfig(), client_factory=client_factory)
    client = WebClient(session, clock, request_delay=5.0)
    request = WebRequest(url="http://tracker.test/")
    await client.get_result(request)
    assert clock.slept == []  # nothing to wait for on the first request
    clock.seconds += 2
    await client.get_result(request)
    assert clock.slept == [3.0]
    await session.aclose()


def test_cache_expires_entries_by_the_injected_clock():
    from pyjackett.domain.query import TorznabQuery

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
    security = SecurityService(config, clock, generate_api_key)
    cookie = security.create_session_cookie()
    assert security.is_valid_session(cookie)
    assert not security.is_valid_session(cookie + "x")
    clock.seconds += SESSION_DAYS * SECONDS_PER_DAY + 1
    assert not security.is_valid_session(cookie)


def test_api_key_check():
    config = ServerConfig(api_key="key")
    security = SecurityService(config, SYSTEM_CLOCK, generate_api_key)
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


def test_log_cache_clear_drops_collected_entries():
    logger = logging.getLogger("pyjackett.test-clear")
    handler = LogCache(logger=logger)
    handler.attach()
    logger.warning("something happened")
    assert len(handler.logs) == 1
    handler.clear()
    assert handler.logs == []
    handler.detach()


def test_context_takes_the_environment_and_clock_from_its_caller(tmp_path):
    from pyjackett.wiring import build_context

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
    from pyjackett.errors import IndexerTestFailedError
    from pyjackett.services.indexers.base import BaseIndexer
    from pyjackett.services.indexers.result import IndexerResult

    class Stub(BaseIndexer):
        id = name = "stub"

        async def apply_configuration(self, config):
            raise NotImplementedError

        async def perform_query(self, query):
            return []

        async def results_for_query(self, query, is_meta_indexer=False):
            return IndexerResult(self, [object()] if found else [])

    indexer = Stub(SimpleNamespace(clock=SYSTEM_CLOCK))
    if found:
        await indexer.verify()
    else:
        with pytest.raises(IndexerTestFailedError):
            await indexer.verify()


def test_log_cache_entries_carry_a_short_source_and_plain_message():
    logger = logging.getLogger("pyjackett.indexers.demo")
    handler = LogCache(logger=logging.getLogger("pyjackett"))
    handler.attach()
    logger.warning("hello %s", "world")
    entry = handler.logs[0]
    handler.detach()
    assert entry["Source"] == "indexers.demo"
    assert entry["Message"] == "hello world"
    assert entry["Level"] == "Warning"


def test_impersonation_defaults_to_chrome_and_can_be_switched_off():
    from pyjackett.adapters.http.session import impersonation_from

    assert impersonation_from({}) == "chrome"
    assert impersonation_from({"PYJACKETT_IMPERSONATE": "safari"}) == "safari"
    assert impersonation_from({"PYJACKETT_IMPERSONATE": "none"}) is None
    assert impersonation_from({"PYJACKETT_IMPERSONATE": " "}) is None


async def test_session_opens_its_connection_with_the_impersonation():
    opened = []

    def factory(**options):
        opened.append(options)
        return fakes.mock_network(lambda request: fakes.Response(200))(**options)

    session = HttpSession(ServerConfig(), client_factory=factory, impersonate="chrome")
    await session.send({"method": "GET", "url": "http://tracker.test/"})
    assert opened[0]["impersonate"] == "chrome"
    await session.aclose()


def test_impersonated_browser_requests_leave_headers_to_the_client():
    from pyjackett.adapters.http.request_builder import build_request_kwargs

    request = WebRequest(url="http://tracker.test/", emulate_browser=True)
    headers = build_request_kwargs(request, impersonating=True)["headers"]
    assert headers == {}


def test_impersonated_requests_keep_site_and_clearance_headers():
    from pyjackett.adapters.http.request_builder import build_request_kwargs

    request = WebRequest(
        url="http://tracker.test/",
        emulate_browser=True,
        headers={"Accept": "application/json"},
    )
    kwargs = build_request_kwargs(request, impersonating=True)
    assert kwargs["headers"] == {"Accept": "application/json"}
    cleared = build_request_kwargs(request, "Solved/1.0", impersonating=True)
    assert cleared["headers"]["User-Agent"] == "Solved/1.0"


def test_api_requests_and_unimpersonated_sessions_keep_the_defaults():
    from pyjackett.adapters.http.request_builder import build_request_kwargs

    api = WebRequest(url="http://tracker.test/", emulate_browser=False)
    api_headers = build_request_kwargs(api, impersonating=True)["headers"]
    assert api_headers["User-Agent"].startswith("PyJackett/")
    browser = WebRequest(url="http://tracker.test/", emulate_browser=True)
    plain = build_request_kwargs(browser, impersonating=False)["headers"]
    assert "Chrome" in plain["User-Agent"]
    assert plain["Accept"] == "*/*"
