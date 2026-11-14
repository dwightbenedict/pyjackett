"""Behaviour introduced by the strategy / template-method refactors."""

from __future__ import annotations

import pytest

from pyjackett.domain.cardigann.methods import LoginMethod, request_type
from pyjackett.domain.http_models import RequestType
from pyjackett.domain.server_config import ServerConfig
from pyjackett.services.cardigann.login import CardigannLogin
from pyjackett.services.indexers.meta.factory import (
    MAX_EXPRESSION_FILTERS,
    MetaIndexerFactory,
)
from pyjackett.services.indexers.meta.meta_indexer import AggregateIndexer
from pyjackett.services.indexers.registry import IndexerRegistry


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("post", RequestType.POST),
        ("POST", RequestType.POST),
        ("get", RequestType.GET),
        (None, RequestType.GET),
    ],
)
def test_request_type_is_case_insensitive(value, expected):
    assert request_type(value) is expected


def test_every_login_method_has_a_strategy():
    login = CardigannLogin(host=None)
    for method in LoginMethod:
        assert callable(login._strategy_for(method.value))


def test_unknown_login_method_is_not_implemented():
    with pytest.raises(NotImplementedError, match="carrier-pigeon"):
        CardigannLogin(host=None)._strategy_for("carrier-pigeon")


def test_meta_indexer_derives_its_state_and_rejects_assignment():
    aggregate = AggregateIndexer(None, _NoImdb(), [])
    assert aggregate.is_meta
    assert aggregate.is_configured
    assert aggregate.members() == []
    with pytest.raises(AttributeError):
        aggregate.is_configured = False
    with pytest.raises(AttributeError):
        aggregate.torznab_caps = None


class _NoImdb:
    """Stand-in for ImdbSupport; the aggregate never queries it here."""


class _Stub:
    """Just enough of an indexer for the registry and factory."""

    def __init__(self, indexer_id, replaces=()):
        self.id = indexer_id
        self.name = indexer_id
        self.replaces = replaces
        self.tags = []
        self.is_configured = True


def test_registry_rejects_duplicates_and_resolves_renamed_ids():
    registry = IndexerRegistry()
    assert registry.register(_Stub("new", replaces=("old",)))
    assert not registry.register(_Stub("new"))
    assert dict(registry.build_aliases()) == {"old": "new"}
    assert registry.resolve("old") == "new"
    assert registry.resolve("other") == "other"
    assert len(registry) == 1


def test_expression_filters_are_cached_with_a_bound():
    config = ServerConfig()
    factory = MetaIndexerFactory(None, config, [])
    factory.rebuild()
    assert factory.find("all").id == "all"
    assert factory.find("nonsense") is None
    for number in range(MAX_EXPRESSION_FILTERS + 10):
        assert factory.find(f"tag:t{number}") is not None
    assert len(factory._expressions) == MAX_EXPRESSION_FILTERS


def test_plain_routes_answer_with_http_errors(client, api_key):
    base = "/api/v2.0/indexers"
    assert client.get(f"{base}/faketracker/results/potato").status_code == 401
    unknown = client.get(f"{base}/nope/results/potato", params={"apikey": api_key})
    assert unknown.status_code == 404
    assert unknown.text == "Indexer is not supported"


def test_torznab_routes_answer_with_xml_errors(client, api_key):
    base = "/api/v2.0/indexers"
    reply = client.get(f"{base}/nope/results/torznab/api", params={"apikey": api_key})
    assert reply.status_code == 200
    assert 'code="201"' in reply.text


def test_rate_limit_is_its_own_error_type():
    from datetime import timedelta

    from pyjackett.errors import (
        IndexerError,
        IndexerRateLimitedError,
        TooManyRequestsError,
    )

    cause = TooManyRequestsError("slow down", timedelta(seconds=30))
    error = IndexerRateLimitedError(_Stub("x"), cause)
    assert isinstance(error, IndexerError)
    assert error.retry_after == timedelta(seconds=30)
    assert error.__cause__ is cause


def test_health_uses_the_injected_clock():
    from pyjackett.services.indexers.health import IndexerHealth

    now = [100.0]
    health = IndexerHealth(clock=lambda: now[0])
    health.record_success(10)
    assert health.is_healthy
    now[0] = 111.0
    assert not health.is_healthy
    health.record_failure()
    assert health.is_failing


async def test_retry_does_not_repeat_configuration_errors():
    from pyjackett.errors import ConfigurationError
    from pyjackett.services.indexers.retry import retry_request

    calls = []

    async def operation():
        calls.append(1)
        raise ConfigurationError("bad credentials")

    with pytest.raises(ConfigurationError):
        await retry_request(operation, retries=3, name="x")
    assert len(calls) == 1


def test_filters_register_under_every_alias():
    from pyjackett.domain.cardigann.filters import FILTERS

    assert FILTERS["timeparse"] is FILTERS["dateparse"]
    assert FILTERS["reltime"] is FILTERS["timeago"]
    assert len(FILTERS) == 27
