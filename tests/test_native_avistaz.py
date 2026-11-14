"""The AvistaZ network trackers: login, search and result mapping."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from tests.conftest import sign_in_as_admin

import fakes
from pyjackett.interfaces.api import create_app
from pyjackett.wiring import build_context

ROW = {
    "url": "https://avistaz.to/torrent/1-film",
    "download": "https://avistaz.to/download/1.torrent",
    "category": {"1": "Movie"},
    "movie_tv": {"imdb": "tt0075998", "tmdb": "12", "tvdb": ""},
    "created_at_iso": "2024-01-02T03:04:05.000000Z",
    "file_name": "Film.2024.1080p",
    "info_hash": "a" * 40,
    "leech": 2,
    "completed": 9,
    "seed": 5,
    "file_size": 2 * 1024**3,
    "file_count": 3,
    "download_multiply": 0,
    "upload_multiply": 1,
    "video_quality": "1080p",
    "type": "Movie",
    "audio": [{"id": 1, "language": "English"}],
    "subtitle": [{"id": 2, "language": "French"}],
}
FORM = [
    {"id": "username", "value": "me"},
    {"id": "password", "value": "secret"},
    {"id": "pid", "value": "abc"},
]


class Tracker:
    """Records the requests and answers like the AvistaZ API."""

    def __init__(self) -> None:
        self.requests: list[fakes.Request] = []
        self.search_status = 200
        self.logins = 0

    def __call__(self, request: fakes.Request) -> fakes.Response:
        self.requests.append(request)
        if request.url.path.endswith("/auth"):
            self.logins += 1
            return fakes.Response(200, text=json.dumps({"token": "t0k"}))
        if self.search_status != 200:
            status, self.search_status = self.search_status, 200
            return fakes.Response(status)
        assert request.headers["Authorization"] == "Bearer t0k"
        return fakes.Response(200, text=json.dumps({"data": [ROW]}))


@pytest.fixture
def tracker():
    return Tracker()


@pytest.fixture
def client(tmp_path, tracker):
    context = build_context(
        tmp_path,
        client_factory=fakes.mock_network(tracker),
        include_bundled=False,
    )
    with TestClient(create_app(context)) as test_client:
        sign_in_as_admin(test_client)
        test_client.api_key = context.config.api_key
        yield test_client


def search(client, indexer: str = "avistaz", **params):
    reply = client.get(
        f"/api/v2.0/indexers/{indexer}/results/torznab/api",
        params={"apikey": client.api_key, "t": "search", **params},
    )
    return reply, list(ET.fromstring(reply.text).iter("item"))


def test_the_four_sites_are_registered(client):
    ids = {i["id"] for i in client.get("/api/v2.0/indexers").json()}
    assert {"avistaz", "cinemaz", "exoticaz", "privatehd"} <= ids


def test_configuring_logs_in_and_runs_a_test_search(client, tracker):
    reply = client.post("/api/v2.0/indexers/avistaz/config", json=FORM)
    assert reply.status_code == 204
    login = tracker.requests[0]
    assert json.loads(login.content) == {
        "username": "me",
        "password": "secret",
        "pid": "abc",
    }


def test_a_search_is_mapped_to_torznab_items(client, tracker):
    client.post("/api/v2.0/indexers/avistaz/config", json=FORM)
    _, items = search(client, q="film")
    assert [i.findtext("title") for i in items] == ["Film.2024.1080p"]
    request = tracker.requests[-1]
    assert "search=film" in request.url.query
    assert "in=1" in request.url.query
    attrs = {
        a.get("name"): a.get("value")
        for a in items[0].iter("{http://torznab.com/schemas/2015/feed}attr")
    }
    assert attrs["seeders"] == "5"
    assert attrs["peers"] == "7"
    assert attrs["downloadvolumefactor"] == "0"
    assert attrs["imdbid"] == "tt0075998"


def test_an_expired_token_is_renewed_once(client, tracker):
    client.post("/api/v2.0/indexers/avistaz/config", json=FORM)
    tracker.search_status = 401
    _, items = search(client, q="film")
    assert len(items) == 1
    assert tracker.logins == 2


def test_a_search_without_results_is_empty(client, tracker):
    client.post("/api/v2.0/indexers/avistaz/config", json=FORM)
    tracker.search_status = 404
    reply, items = search(client, q="film")
    assert reply.status_code == 200
    assert items == []
