"""End to end: Torznab requests against a fake tracker."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

import pytest

TORZNAB = "{http://torznab.com/schemas/2015/feed}"


@pytest.fixture
def configured(client):
    """Configure the fake tracker (no login needed)."""
    reply = client.post("/api/v2.0/indexers/faketracker/config", json=[])
    assert reply.status_code == 204
    return client


def torznab(client, api_key, **params):
    params.setdefault("t", "search")
    return client.get(
        "/api/v2.0/indexers/faketracker/results/torznab/api",
        params={"apikey": api_key, **params},
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "OK"}


def test_indexer_listing_contains_fixture(client):
    listing = client.get("/api/v2.0/indexers").json()
    assert "faketracker" in [i["id"] for i in listing]
    assert all(i["configured"] is False for i in listing)


def test_unconfigured_indexer_is_rejected(client, api_key):
    reply = torznab(client, api_key)
    assert "Indexer is not configured" in reply.text


def test_invalid_api_key(configured):
    reply = torznab(configured, "wrong")
    assert 'code="100"' in reply.text


def test_caps(configured, api_key):
    reply = torznab(configured, api_key, t="caps")
    root = ET.fromstring(reply.text)
    modes = {e.tag: e.get("available") for e in root.find("searching")}
    assert modes["search"] == "yes"
    assert modes["tv-search"] == "yes"
    assert modes["book-search"] == "no"
    category_ids = {c.get("id") for c in root.find("categories")}
    assert {"2000", "5000"} <= category_ids


def test_search_returns_both_releases(configured, api_key):
    root = ET.fromstring(torznab(configured, api_key, q="").text)
    titles = [i.findtext("title") for i in root.iter("item")]
    assert titles == ["Big Movie 2020 1080p", "Other Show S01E01"]


def test_search_item_details(configured, api_key):
    root = ET.fromstring(torznab(configured, api_key, q="").text)
    item = next(root.iter("item"))
    attrs = {a.get("name"): a.get("value") for a in item.iter(TORZNAB + "attr")}
    assert attrs["seeders"] == "42"
    assert attrs["peers"] == "49"  # seeders + leechers
    assert item.findtext("size") == str(int(1.5 * 1024**3))
    assert "2040" in {c.text for c in item.findall("category")}
    assert item.findtext("pubDate").startswith("Fri, 01 Mar 2024")


def test_andmatch_filters_unrelated_titles(configured, api_key):
    root = ET.fromstring(torznab(configured, api_key, q="movie").text)
    assert [i.findtext("title") for i in root.iter("item")] == ["Big Movie 2020 1080p"]


def test_category_filter(configured, api_key):
    root = ET.fromstring(torznab(configured, api_key, q="", cat="5000").text)
    assert [i.findtext("title") for i in root.iter("item")] == ["Other Show S01E01"]


def test_unsupported_query_is_an_error(configured, api_key):
    reply = torznab(configured, api_key, t="music", q="x")
    assert 'code="201"' in reply.text


def test_download_goes_through_proxy_and_sorts_torrent(configured, api_key):
    root = ET.fromstring(torznab(configured, api_key, q="").text)
    link = next(root.iter("item")).findtext("link")
    parts = urlsplit(link)
    assert parts.path == "/dl/faketracker/"
    assert parse_qs(parts.query)["jackett_apikey"] == [api_key]
    download = configured.get(f"{parts.path}?{parts.query}")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/x-bittorrent"
    assert download.content == b"d4:infod6:lengthi3ee4:name3:fooe"


def test_download_requires_api_key(configured):
    assert configured.get("/dl/faketracker/?path=x&jackett_apikey=no").status_code == 401


def test_manual_search_lists_results_and_status(configured, api_key):
    reply = configured.get(
        "/api/v2.0/indexers/all/results",
        params={"apikey": api_key, "query": "movie"},
    ).json()
    assert reply["indexers"][0]["status"] == "ok"
    assert [r["title"] for r in reply["results"]] == ["Big Movie 2020 1080p"]
    assert "/dl/faketracker/" in reply["results"][0]["link"]


def test_results_are_cached(configured, api_key, context):
    torznab(configured, api_key, q="")
    cached = configured.get("/api/v2.0/indexers/cache").json()
    assert len(cached) == 2


def test_aggregate_caps_union(configured, api_key):
    reply = configured.get(
        "/api/v2.0/indexers/all/results/torznab/api",
        params={"apikey": api_key, "t": "caps"},
    )
    assert "<caps>" in reply.text
