"""The versioned API: discovery, bulk operations, keys, stats and bundles."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from tests.conftest import FIXTURES, fake_tracker, sign_in_as_admin

import fakes
from pyjackett.errors import IndexerTestFailedError
from pyjackett.interfaces.api import create_app
from pyjackett.services.stats import SearchRecorder
from pyjackett.wiring import build_context

V1 = "/api/v1"
PRIVATE_DEFINITION = (
    (FIXTURES / "faketracker.yml")
    .read_text()
    .replace("id: faketracker", "id: privatetracker")
    .replace("type: public", "type: private")
)


@pytest.fixture
def configured(client):
    assert client.post(f"{V1}/indexers/faketracker/add").status_code == 204
    return client


def log_in_as_admin(client, password="secret"):
    """Secrets are only served to a logged-in admin with a password set."""
    client.post(f"{V1}/server/adminpassword", json=password)
    client.post("/UI/Login", data={"password": password})


def search(client, api_key, **params):
    return client.get(
        f"{V1}/indexers/faketracker/results/torznab/api",
        params={"apikey": api_key, "t": "search", **params},
    )


def test_both_prefixes_serve_torznab(configured, api_key):
    for path in (
        "/api/v1/indexers/faketracker/results/torznab/api",
        "/api/v2.0/indexers/faketracker/results/torznab/api",
        "/torznab/faketracker/api",
        "/torznab/faketracker",
    ):
        reply = configured.get(path, params={"apikey": api_key, "t": "caps"})
        assert "<caps>" in reply.text, path


def test_info_is_public(client):
    body = client.get(f"{V1}/server/info").json()
    assert body["name"] == "PyJackett"
    assert body["api_version"] == "1"


def test_update_check_accepts_the_api_key_only_when_protected(client, api_key):
    assert client.get(f"{V1}/server/updatecheck").status_code == 200
    client.post(f"{V1}/server/adminpassword", json="secret")
    client.cookies.clear()
    assert client.get(f"{V1}/server/updatecheck").status_code == 401
    reply = client.get(f"{V1}/server/updatecheck", params={"apikey": api_key})
    assert reply.json()["update_available"] is False


def test_listing_filters(client):
    everything = client.get(f"{V1}/indexers").json()
    assert "faketracker" in [i["id"] for i in everything]
    nothing = client.get(f"{V1}/indexers", params={"q": "no-such-thing"})
    assert nothing.json() == []
    configured = client.get(f"{V1}/indexers", params={"configured": True})
    assert "faketracker" not in [i["id"] for i in configured.json()]
    private = client.get(f"{V1}/indexers", params={"type": "private"})
    assert "faketracker" not in [i["id"] for i in private.json()]
    public = client.get(f"{V1}/indexers", params={"type": "public"})
    assert "faketracker" in [i["id"] for i in public.json()]


def test_capabilities_as_json(client):
    caps = client.get(f"{V1}/indexers/faketracker/caps").json()
    assert caps["search_modes"]["movie-search"]["available"] is True
    assert "imdbid" in caps["search_modes"]["movie-search"]["parameters"]
    assert caps["search_modes"]["music-search"]["available"] is False
    names = {c["name"] for c in caps["categories"]}
    assert {"Movies", "TV"} <= names


def test_category_catalog(client):
    names = [c["name"] for c in client.get(f"{V1}/categories").json()]
    assert "Movies" in names
    assert "TV" in names


def test_unknown_indexer_is_a_404(client):
    reply = client.get(f"{V1}/indexers/nope/caps")
    assert reply.status_code == 404
    assert reply.json()["result"] == "error"


def test_adding_a_public_indexer_is_idempotent(client):
    assert client.post(f"{V1}/indexers/faketracker/add").status_code == 204
    assert client.post(f"{V1}/indexers/faketracker/add").status_code == 204
    listing = client.get(f"{V1}/indexers", params={"configured": True})
    assert [i["id"] for i in listing.json()] == ["faketracker"]


def test_private_indexer_cannot_be_added_with_defaults(tmp_path):
    definitions = tmp_path / "definitions"
    definitions.mkdir()
    (definitions / "privatetracker.yml").write_text(PRIVATE_DEFINITION)
    context = build_context(
        tmp_path / "data",
        extra_definition_dirs=[definitions],
        client_factory=fakes.mock_network(fake_tracker),
        include_bundled=False,
    )
    with TestClient(create_app(context)) as client:
        sign_in_as_admin(client)
        reply = client.post(f"{V1}/indexers/privatetracker/add")
    assert reply.status_code == 409


def test_bulk_operations_report_each_indexer(client):
    ids = ["faketracker", "missing"]
    added = client.post(f"{V1}/indexers/bulk/add", json={"ids": ids}).json()
    assert [(o["id"], o["status"]) for o in added] == [
        ("faketracker", "ok"),
        ("missing", "error"),
    ]
    tested = client.post(f"{V1}/indexers/bulk/test", json={"ids": ids}).json()
    assert [o["status"] for o in tested] == ["ok", "error"]
    deleted = client.post(f"{V1}/indexers/bulk/delete", json={"ids": ["faketracker"]}).json()
    assert deleted[0]["status"] == "ok"
    listing = client.get(f"{V1}/indexers", params={"configured": True})
    assert listing.json() == []


def test_bulk_needs_at_least_one_id(client):
    reply = client.post(f"{V1}/indexers/bulk/test", json={"ids": []})
    assert reply.status_code == 422


def test_cache_can_be_cleared(configured, api_key):
    search(configured, api_key)
    assert configured.get(f"{V1}/indexers/cache").json()
    assert configured.delete(f"{V1}/indexers/cache").status_code == 204
    assert configured.get(f"{V1}/indexers/cache").json() == []


def test_listing_reports_the_last_search_latency(configured, api_key):
    def latency():
        listed = configured.get(f"{V1}/indexers").json()
        return next(i for i in listed if i["id"] == "faketracker")["latency_ms"]

    assert latency() is None
    search(configured, api_key)
    assert isinstance(latency(), int)


def test_recorder_keeps_the_last_successful_latency():
    recorder = SearchRecorder()
    assert recorder.last_elapsed_ms("a") is None
    recorder.record_success("a", "", 1, 120)
    recorder.record_success("a", "", 1, 45)
    recorder.record_failure("a", "", "boom", rate_limited=False)
    assert recorder.last_elapsed_ms("a") == 45


def test_testing_one_indexer_answers_with_its_latency(configured):
    reply = configured.post(f"{V1}/indexers/faketracker/test")
    assert reply.status_code == 200
    assert isinstance(reply.json()["latency_ms"], int)


def test_a_failed_test_still_reports_its_latency(context, configured):
    async def nothing_found():
        raise IndexerTestFailedError("No results.", 87)

    indexer = context.indexers.get_indexer("faketracker")
    indexer.verify = nothing_found
    app = create_app(context)
    with TestClient(app, raise_server_exceptions=False) as browser:
        sign_in_as_admin(browser)
        reply = browser.post(f"{V1}/indexers/faketracker/test")
    assert reply.status_code == 500
    assert reply.json()["latency_ms"] == 87


def test_a_test_that_never_answers_times_out(tmp_path):
    async def never_answers():
        await asyncio.Event().wait()

    context = build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(fake_tracker),
        include_bundled=False,
    )
    context.config.test_timeout = 0.05  # shorter than the setting allows
    with TestClient(create_app(context), raise_server_exceptions=False) as web:
        sign_in_as_admin(web)
        web.post(f"{V1}/indexers/faketracker/add")
        context.indexers.get_indexer("faketracker").verify = never_answers
        reply = web.post(f"{V1}/indexers/faketracker/test")
        outcome = web.post(f"{V1}/indexers/bulk/test", json={"ids": ["faketracker"]}).json()[0]
    assert reply.status_code == 500
    assert "No answer within 0.05 seconds" in reply.json()["error"]
    assert outcome["status"] == "error"
    assert "No answer within" in outcome["error"]


def test_statistics_and_history(configured, api_key):
    search(configured, api_key)
    search(configured, api_key)  # answered from the cache
    stats = configured.get(f"{V1}/server/stats", params={"apikey": api_key})
    body = stats.json()
    assert body["indexers"]["faketracker"]["successes"] == 1
    assert body["indexers"]["faketracker"]["cache_hits"] == 1
    assert body["totals"]["searches"] == 2
    history = configured.get(f"{V1}/server/history").json()
    assert [h["outcome"] for h in history] == ["cache", "ok"]
    assert configured.delete(f"{V1}/server/stats").status_code == 204
    assert configured.get(f"{V1}/server/history").json() == []


def test_api_key_can_be_read_and_rotated(client, context, api_key):
    log_in_as_admin(client)
    assert client.get(f"{V1}/server/apikey").json() == {"api_key": api_key}
    reply = client.post(f"{V1}/server/apikey/rotate", json={"password": "secret"})
    new_key = reply.json()["api_key"]
    assert new_key != api_key
    assert context.config.api_key == new_key
    assert not context.security.is_valid_api_key(api_key)
    assert context.security.is_valid_api_key(new_key)
    assert context.security.check_authorised("secret")


def test_rotation_keeps_the_admin_password_working(client, context):
    log_in_as_admin(client)
    assert context.security.check_authorised("secret")
    wrong = client.post(f"{V1}/server/apikey/rotate", json={"password": "no"})
    assert wrong.status_code == 403
    right = client.post(f"{V1}/server/apikey/rotate", json={"password": "secret"})
    assert right.status_code == 200
    assert context.security.check_authorised("secret")
    # the reply renewed the session, so the dashboard stays reachable
    assert client.get(f"{V1}/server/apikey").status_code == 200


SECRET_ROUTES = (
    ("GET", "/server/apikey"),
    ("POST", "/server/apikey/rotate"),
    ("GET", "/server/config/export"),
    ("POST", "/server/config/import"),
)


@pytest.mark.parametrize(("method", "path"), SECRET_ROUTES)
def test_secrets_need_a_dashboard_session(client, api_key, method, path):
    client.post(f"{V1}/server/adminpassword", json="secret")
    client.cookies.clear()
    reply = client.request(method, V1 + path, params={"apikey": api_key}, json={})
    assert reply.status_code == 401
    assert api_key not in reply.text


def test_export_and_import_round_trip(configured, context):
    log_in_as_admin(configured)
    bundle = configured.get(f"{V1}/server/config/export").json()
    assert bundle["format"] == "pyjackett-config"
    assert "faketracker" in bundle["indexers"]
    assert "APIKey" not in bundle["server"]
    assert "AdminPassword" not in bundle["server"]
    bundle["server"]["CacheTtl"] = 99
    bundle["indexers"]["ghost"] = []
    configured.delete(f"{V1}/indexers/faketracker")
    reply = configured.post(f"{V1}/server/config/import", json=bundle)
    assert reply.json() == {
        "imported": ["faketracker"],
        "skipped": ["ghost"],
        "restart_required": False,
    }
    assert context.config.cache_ttl == 99
    assert context.indexers.get_indexer("faketracker").is_configured


def test_import_flags_a_restart_for_network_changes(client):
    log_in_as_admin(client)
    bundle = client.get(f"{V1}/server/config/export").json()
    bundle["server"]["Port"] = 9999
    reply = client.post(f"{V1}/server/config/import", json=bundle)
    assert reply.json()["restart_required"] is True


def test_import_rejects_foreign_documents(client):
    log_in_as_admin(client)
    reply = client.post(f"{V1}/server/config/import", json={"format": "x"})
    assert reply.status_code == 400


def test_openapi_documents_v1_and_the_jackett_prefix(client):
    spec = client.get(f"{V1}/openapi.json").json()
    assert f"{V1}/indexers/{{indexer_id}}/results/torznab" in spec["paths"]
    assert "/api/v2.0/indexers/{indexer_id}/results/torznab" in spec["paths"]
    assert "ErrorResponse" in spec["components"]["schemas"]


def test_spec_covers_search_and_discovery_only(client):
    paths = client.get(f"{V1}/openapi.json").json()["paths"]
    suffixes = [
        "/categories",
        "/indexers",
        "/indexers/{indexer_id}/caps",
        "/indexers/{indexer_id}/results",
        "/indexers/{indexer_id}/results/potato",
        "/indexers/{indexer_id}/results/stream",
        "/indexers/{indexer_id}/results/torznab",
    ]
    assert sorted(paths) == sorted(f"{prefix}{s}" for prefix in (V1, "/api/v2.0") for s in suffixes)
    # management stays reachable: the dashboard and scripts call it
    assert client.get(f"{V1}/server/config").status_code == 200
    assert client.get(f"{V1}/server/logs").status_code == 200
