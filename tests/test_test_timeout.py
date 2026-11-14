"""The time an indexer test may take is a saved, validated setting."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.conftest import sign_in_as_admin

from pyjackett.server.app import create_app

V2 = "/api/v2.0"


def test_the_form_shows_and_saves_the_timeout(client, context):
    form = client.get(f"{V2}/server/config").json()
    assert form["test_timeout"] == 30
    reply = client.post(
        f"{V2}/server/config", json={**form, "test_timeout": 45}
    )
    assert reply.status_code == 200
    assert reply.json()["test_timeout"] == 45
    assert context.config.test_timeout == 45


@pytest.mark.parametrize("seconds", [0, 301])
def test_the_timeout_must_be_within_range(context, seconds):
    app = create_app(context)
    with TestClient(app, raise_server_exceptions=False) as web:
        sign_in_as_admin(web)
        form = web.get(f"{V2}/server/config").json()
        reply = web.post(
            f"{V2}/server/config", json={**form, "test_timeout": seconds}
        )
    assert reply.status_code >= 400
    assert "between 1 and 300 seconds" in reply.json()["error"]
    assert context.config.test_timeout == 30
