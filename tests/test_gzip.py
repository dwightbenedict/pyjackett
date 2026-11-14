"""Large responses are gzipped, except the line-by-line search stream."""

from __future__ import annotations

GZIP = {"Accept-Encoding": "gzip"}


def test_large_json_is_gzipped(client):
    response = client.get("/api/v1/openapi.json", headers=GZIP)

    assert response.headers["content-encoding"] == "gzip"
    assert response.json()["paths"]


def test_search_stream_is_left_uncompressed(client, api_key):
    response = client.get(
        "/api/v2.0/indexers/all/results/stream",
        params={"apikey": api_key, "query": "ubuntu"},
        headers=GZIP,
    )

    assert response.headers["content-encoding"] == "identity"
