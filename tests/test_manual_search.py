"""The manual search answers even when some trackers never respond."""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient
from tests.conftest import FIXTURES

import fakes
from pyjackett.interfaces import routes
from pyjackett.interfaces.api import create_app
from pyjackett.wiring import build_context

API_RESPONSE = {
    "torrents": [
        {
            "infohash": "a" * 40,
            "name": "Quick Film",
            "size_bytes": 1000,
            "created_unix": 1_700_000_000,
            "seeders": 1,
            "leechers": 1,
            "completed": 1,
        }
    ]
}


async def hanging_site(request: fakes.Request) -> fakes.Response:
    if request.url.path == "/service/search":
        return fakes.Response(200, text=json.dumps(API_RESPONSE))
    await asyncio.Event().wait()  # never answers
    raise AssertionError("unreachable")


def test_slow_tracker_does_not_block_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.results, "MANUAL_SEARCH_TIMEOUT", 0.2)
    context = build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(hanging_site),
        include_bundled=False,
        configure_public=True,
    )
    with TestClient(create_app(context)) as client:
        reply = client.get(
            "/api/v2.0/indexers/all/results",
            params={"apikey": context.config.api_key, "query": "film"},
        )
    assert reply.status_code == 200
    body = reply.json()
    statuses = {s["id"]: s for s in body["indexers"]}
    assert statuses["torrentscsv"]["status"] == "ok"
    assert statuses["faketracker"]["status"] == "error"
    assert statuses["faketracker"]["error"] == "Timed out"
    assert [r["title"] for r in body["results"]] == ["Quick Film"]


def test_stream_yields_each_tracker_as_it_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.results, "MANUAL_SEARCH_TIMEOUT", 0.2)
    context = build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(hanging_site),
        include_bundled=False,
        configure_public=True,
    )
    with TestClient(create_app(context)) as client:
        reply = client.get(
            "/api/v2.0/indexers/all/results/stream",
            params={"apikey": context.config.api_key, "query": "film"},
        )
    assert reply.status_code == 200
    chunks = [json.loads(line) for line in reply.text.splitlines()]
    assert [c["indexer"]["id"] for c in chunks] == [
        "torrentscsv",
        "faketracker",
    ]
    assert [r["title"] for r in chunks[0]["results"]] == ["Quick Film"]
    assert chunks[1]["indexer"]["error"] == "Timed out"
    assert chunks[1]["results"] == []
