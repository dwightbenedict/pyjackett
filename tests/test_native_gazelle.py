"""The Gazelle based trackers: API key and login flows, result mapping."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from tests.conftest import sign_in_as_admin

import fakes
from pyjackett.interfaces.api import create_app
from pyjackett.wiring import build_context

TORRENT = {
    "torrentId": 10,
    "time": "2020-01-02 03:04:05",
    "format": "FLAC",
    "encoding": "Lossless",
    "media": "CD",
    "hasLog": True,
    "logScore": 100,
    "hasCue": True,
    "remastered": True,
    "remasterYear": 1999,
    "remasterTitle": "Deluxe",
    "size": 1000,
    "seeders": 3,
    "leechers": 1,
    "snatches": 5,
    "fileCount": 8,
    "isFreeleech": True,
    "isNeutralLeech": False,
    "isPersonalFreeleech": False,
    "category": "Music",
}
GROUP = {
    "groupName": "Album &amp; More",
    "artist": "Band",
    "tags": ["rock", "indie"],
    "groupYear": 2020,
    "releaseType": "Album",
    "groupTime": "1600000000",
    "cover": "",
    "torrents": [TORRENT],
}
API_KEY = "k" * 116


class Site:
    """Answers the browse API and the login form."""

    def __init__(self) -> None:
        self.requests: list[fakes.Request] = []
        self.payload = {"status": "success", "response": {"results": [GROUP]}}

    def __call__(self, request: fakes.Request) -> fakes.Response:
        self.requests.append(request)
        if request.url.path.endswith("login.php"):
            return fakes.Response(
                200,
                text="<a href='logout.php'>Logout</a>",
                headers={"Set-Cookie": "session=abc; Path=/"},
            )
        return fakes.Response(200, text=json.dumps(self.payload))


@pytest.fixture
def site():
    return Site()


@pytest.fixture
def client(tmp_path, site):
    context = build_context(
        tmp_path,
        client_factory=fakes.mock_network(site),
        include_bundled=False,
    )
    with TestClient(
        create_app(context), raise_server_exceptions=False
    ) as test_client:
        sign_in_as_admin(test_client)
        test_client.api_key = context.config.api_key
        yield test_client


def search(client, indexer: str, **params):
    reply = client.get(
        f"/api/v2.0/indexers/{indexer}/results/torznab/api",
        params={"apikey": client.api_key, "t": "search", **params},
    )
    return list(ET.fromstring(reply.text).iter("item"))


def test_an_api_key_of_the_wrong_length_is_rejected(client):
    reply = client.post(
        "/api/v2.0/indexers/orpheus/config",
        json=[{"id": "apikey", "value": "short"}],
    )
    assert reply.status_code != 204


def test_api_key_trackers_send_the_key_and_map_results(client, site):
    form = [{"id": "apikey", "value": API_KEY}]
    assert (
        client.post("/api/v2.0/indexers/orpheus/config", json=form).status_code
        == 204
    )
    items = search(client, "orpheus", q="album")
    assert [i.findtext("title") for i in items] == [
        "Band - Album & More [2020] [Album] FLAC / Lossless / Log (100%) "
        "/ Cue / CD / 1999 Deluxe"
    ]
    request = site.requests[-1]
    assert request.headers["Authorization"] == f"token {API_KEY}"
    assert "action=browse" in request.url.query
    assert "searchstr=album" in request.url.query


def test_a_failure_message_of_the_api_is_reported(client, site):
    form = [{"id": "apikey", "value": API_KEY}]
    client.post("/api/v2.0/indexers/orpheus/config", json=form)
    site.payload = {"status": "failure", "error": "bad key"}
    reply = client.get(
        "/api/v2.0/indexers/orpheus/results/torznab/api",
        params={"apikey": client.api_key, "t": "search", "q": "x"},
    )
    assert "bad key" in reply.text


def test_login_trackers_log_in_and_search_with_the_cookie(client, site):
    form = [
        {"id": "username", "value": "me"},
        {"id": "password", "value": "secret"},
    ]
    reply = client.post("/api/v2.0/indexers/alpharatio/config", json=form)
    assert reply.status_code == 204
    login = site.requests[0]
    assert login.url.path == "/login.php"
    assert b"username=me" in login.content
    items = search(client, "alpharatio", q="album")
    assert items
    assert "session=abc" in site.requests[-1].headers.get("Cookie", "")
