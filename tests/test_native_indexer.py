"""A native (Python) indexer working through the same server."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from tests.conftest import sign_in_as_admin

import fakes
from pyjackett.app_context import build_context
from pyjackett.server.app import create_app

API_RESPONSE = {
    "torrents": [
        {
            "infohash": "a" * 40,
            "name": "Old Film",
            "size_bytes": 1000,
            "created_unix": 1_600_000_000,
            "seeders": 5,
            "leechers": 2,
            "completed": 9,
        },
        {
            "infohash": "b" * 40,
            "name": "New Film",
            "size_bytes": 2000,
            "created_unix": 1_700_000_000,
            "seeders": None,
            "leechers": None,
            "completed": None,
        },
    ]
}


def handler(request: fakes.Request) -> fakes.Response:
    assert request.url.path == "/service/search"
    return fakes.Response(200, text=json.dumps(API_RESPONSE))


@pytest.fixture
def client(tmp_path):
    context = build_context(
        tmp_path,
        client_factory=fakes.mock_network(handler),
        include_bundled=False,
    )
    with TestClient(create_app(context)) as test_client:
        sign_in_as_admin(test_client)
        test_client.api_key = context.config.api_key
        yield test_client


def test_native_indexer_is_registered_and_configurable(client):
    ids = [i["id"] for i in client.get("/api/v2.0/indexers").json()]
    assert "torrentscsv" in ids
    reply = client.post("/api/v2.0/indexers/torrentscsv/config", json=[])
    # the empty-search notice counts as a result, as in upstream Jackett
    assert reply.status_code == 204


def test_search_orders_newest_first_and_builds_magnets(client):
    client.post("/api/v2.0/indexers/torrentscsv/config", json=[])
    reply = client.get(
        "/api/v2.0/indexers/torrentscsv/results/torznab/api",
        params={"apikey": client.api_key, "t": "search", "q": "film"},
    )
    items = list(ET.fromstring(reply.text).iter("item"))
    assert [i.findtext("title") for i in items] == ["New Film", "Old Film"]
    assert items[0].findtext("link").startswith("magnet:?xt=urn:btih:bbbb")
