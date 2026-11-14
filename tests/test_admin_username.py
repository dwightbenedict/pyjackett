"""Sign-in always needs a username and password; admin/admin by default."""

from __future__ import annotations

import pytest

from pyjackett.wiring import build_context

V2 = "/api/v2.0"


def sign_in(client, username="admin", password="admin"):
    reply = client.post(
        "/UI/Login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    return reply.headers["location"]


def change_credentials(client, username, password):
    client.post(f"{V2}/server/adminusername", json=username)
    client.post(f"{V2}/server/adminpassword", json=password)
    client.cookies.clear()


def test_fresh_install_gets_admin_admin(context):
    assert context.config.admin_username == "admin"
    assert context.security.check_credentials("admin", "admin")


def test_defaults_are_persisted_and_not_regenerated(tmp_path):
    first = build_context(tmp_path, include_bundled=False)
    first.security.set_password("changed")
    first.save_config()
    second = build_context(tmp_path, include_bundled=False)
    assert second.security.check_credentials("admin", "changed")
    assert not second.security.check_credentials("admin", "admin")


def test_config_flags_the_default_credentials(client):
    assert client.get(f"{V2}/server/config").json()["default_credentials"]
    client.post(f"{V2}/server/adminpassword", json="secret")
    config = client.get(f"{V2}/server/config").json()
    assert config["username"] == "admin"
    assert not config["default_credentials"]


def test_dashboard_needs_a_session(client):
    client.cookies.clear()
    assert client.get(f"{V2}/server/config").status_code == 401


def test_sign_in_checks_both_fields(client):
    change_credentials(client, " alice ", "secret")
    assert sign_in(client, "admin", "secret").endswith("/UI/Login?error=1")
    assert sign_in(client, "alice", "wrong").endswith("/UI/Login?error=1")
    assert sign_in(client, "", "secret").endswith("/UI/Login?error=1")
    assert sign_in(client, "alice", "secret").endswith("/UI/Dashboard")


@pytest.mark.parametrize(
    ("route", "value"),
    [
        ("adminusername", ""),
        ("adminusername", "   "),
        ("adminpassword", ""),
    ],
)
def test_credentials_cannot_be_blank(client, route, value):
    reply = client.post(f"{V2}/server/{route}", json=value)
    assert reply.status_code == 400
    assert client.get(f"{V2}/server/config").json()["username"] == "admin"


def test_login_page_always_asks_for_a_username(client):
    client.cookies.clear()
    assert 'name="username"' in client.get("/UI/Login").text
