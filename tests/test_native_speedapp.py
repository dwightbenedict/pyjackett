"""The SpeedApp trackers: login, search and result mapping."""

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
    "id": 7,
    "name": "[REQUESTED] Some.Film.2020.",
    "url": "https://speedapp.io/browse/7",
    "created_at": "2024-01-02T03:04:05+00:00",
    "category": {"id": 401},
    "short_description": "Action, Drama/Thriller",
    "poster": "https://speedapp.io/p.jpg",
    "size": 1000,
    "times_completed": 4,
    "seeders": 3,
    "leechers": 1,
    "download_volume_factor": 0,
    "upload_volume_factor": 1,
}
FORM = [
    {"id": "email", "value": "me@example.com"},
    {"id": "password", "value": "secret"},
]


class Site:
    def __init__(self) -> None:
        self.requests: list[fakes.Request] = []
        self.logins = 0

    def __call__(self, request: fakes.Request) -> fakes.Response:
        self.requests.append(request)
        if request.url.path == "/api/login":
            self.logins += 1
            return fakes.Response(200, text=json.dumps({"token": "tok"}))
        assert request.headers["Authorization"] == "Bearer tok"
        return fakes.Response(200, text=json.dumps([ROW]))


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
    with TestClient(create_app(context)) as test_client:
        sign_in_as_admin(test_client)
        test_client.api_key = context.config.api_key
        yield test_client


def test_configuring_logs_in_with_the_email(client, site):
    reply = client.post("/api/v2.0/indexers/speedapp/config", json=FORM)
    assert reply.status_code == 204
    assert json.loads(site.requests[0].content) == {
        "username": "me@example.com",
        "password": "secret",
    }


def test_results_are_cleaned_and_mapped(client, site):
    client.post("/api/v2.0/indexers/retroflix/config", json=FORM)
    reply = client.get(
        "/api/v2.0/indexers/retroflix/results/torznab/api",
        params={"apikey": client.api_key, "t": "search", "q": "some film"},
    )
    items = list(ET.fromstring(reply.text).iter("item"))
    assert [i.findtext("title") for i in items] == ["Some.Film.2020"]
    assert "search=some+film" in site.requests[-1].url.query or (
        "search=some%20film" in site.requests[-1].url.query
    )
