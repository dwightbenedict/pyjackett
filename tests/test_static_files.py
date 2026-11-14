"""Static assets are served so that browsers revalidate them."""

from __future__ import annotations


def test_static_files_must_be_revalidated(client):
    reply = client.get("/static/js/app.js")

    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-cache"


def test_unchanged_static_file_answers_not_modified(client):
    etag = client.get("/static/js/app.js").headers["etag"]

    reply = client.get("/static/js/app.js", headers={"If-None-Match": etag})

    assert reply.status_code == 304
