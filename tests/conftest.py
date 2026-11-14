"""Shared fixtures: an app wired to a fake tracker instead of the network."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import fakes
from pyjackett.interfaces.api import create_app
from pyjackett.wiring import build_context

FIXTURES = Path(__file__).parent / "fixtures"

SEARCH_PAGE = """
<html><body><table class="results"><tbody>
<tr><td class="cat">1</td>
    <td class="name"><a href="/details/1">Big Movie 2020 1080p</a></td>
    <td class="size">1.5 GB</td><td class="seeds">42</td>
    <td class="leech">7</td>
    <td class="date">2024-03-01 12:00:00</td></tr>
<tr><td class="cat">2</td>
    <td class="name"><a href="/details/2">Other Show S01E01</a></td>
    <td class="size">700 MB</td><td class="seeds">3</td>
    <td class="leech">1</td>
    <td class="date">2024-03-02 08:30:00</td></tr>
</tbody></table></body></html>
"""
DETAILS_PAGE = '<html><body><a class="dl" href="/file/1.torrent">get</a></body></html>'
# keys deliberately unsorted: the server must normalise them
UNSORTED_TORRENT = b"d4:name3:foo4:infod6:lengthi3eee"


def fake_tracker(request: fakes.Request) -> fakes.Response:
    path = request.url.path
    if path == "/search":
        return fakes.Response(200, text=SEARCH_PAGE)
    if path.startswith("/torrent/"):
        return fakes.Response(200, text=DETAILS_PAGE)
    if path == "/file/1.torrent":
        return fakes.Response(200, content=UNSORTED_TORRENT)
    return fakes.Response(404)


def sign_in_as_admin(client: TestClient) -> None:
    """Log in with the default credentials every fresh install starts with."""
    client.post("/UI/Login", data={"username": "admin", "password": "admin"})


@pytest.fixture
def context(tmp_path):
    return build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(fake_tracker),
        include_bundled=False,
    )


@pytest.fixture
def client(context):
    with TestClient(create_app(context)) as test_client:
        sign_in_as_admin(test_client)
        yield test_client


@pytest.fixture
def api_key(context):
    return context.config.api_key
