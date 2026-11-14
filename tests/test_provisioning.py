"""Public indexers are configured at startup, the others are not."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.conftest import sign_in_as_admin

import fakes
from pyjackett.app_context import build_context
from pyjackett.indexers.provisioning import PublicIndexerProvisioner
from pyjackett.server.app import create_app

PRIVATE_DEFINITION = """\
id: secretsite
name: Secret Site
description: A private tracker
language: en-US
type: private
encoding: UTF-8
links:
  - https://secret.example/
caps:
  categorymappings:
    - {id: 1, cat: Other}
  modes:
    search: [q]
login:
  path: login.php
  inputs: {}
search:
  paths:
    - path: search
  rows:
    selector: tr
  fields:
    title:
      selector: a
"""


class FakeIndexer:
    def __init__(self, type_: str | None, meta: bool = False) -> None:
        self.type = type_
        self.is_meta = meta
        self.is_configured = False
        self.saved = 0

    def config_changed(self) -> None:
        self.saved += 1


def unavailable(request: fakes.Request) -> fakes.Response:
    return fakes.Response(503)


@pytest.fixture
def definitions(tmp_path: Path) -> Path:
    directory = tmp_path / "definitions"
    directory.mkdir()
    (directory / "secretsite.yml").write_text(PRIVATE_DEFINITION)
    return directory


def make_client(tmp_path, definitions, configure_public):
    from tests.conftest import FIXTURES

    context = build_context(
        tmp_path / "data",
        extra_definition_dirs=[FIXTURES, definitions],
        client_factory=fakes.mock_network(unavailable),
        include_bundled=False,
        configure_public=configure_public,
    )
    return TestClient(create_app(context))


def test_provisioner_configures_and_persists_only_public():
    public, private, meta = (
        FakeIndexer("public"),
        FakeIndexer("private"),
        FakeIndexer("public", meta=True),
    )
    count = PublicIndexerProvisioner().provision([public, private, meta])
    assert count == 1
    assert public.is_configured and public.saved == 1
    assert not private.is_configured and not meta.is_configured


def test_provisioner_skips_already_configured():
    done = FakeIndexer("public")
    done.is_configured = True
    assert PublicIndexerProvisioner().provision([done]) == 0
    assert done.saved == 0


def test_disabled_provisioner_does_nothing():
    public = FakeIndexer("public")
    assert PublicIndexerProvisioner(enabled=False).provision([public]) == 0
    assert not public.is_configured


def test_startup_configures_public_indexers_without_network(
    tmp_path, definitions
):
    with make_client(tmp_path, definitions, True) as client:
        sign_in_as_admin(client)
        configured = client.get("/api/v2.0/indexers?configured=true").json()
        # the native Torrents.csv indexer is public as well
        assert [i["id"] for i in configured] == ["faketracker", "torrentscsv"]
        everything = {
            i["id"]: i["configured"]
            for i in client.get("/api/v2.0/indexers").json()
        }
        assert everything["secretsite"] is False
    saved = tmp_path / "data" / "Indexers" / "faketracker.json"
    assert saved.exists()


def test_startup_leaves_indexers_alone_by_default(tmp_path, definitions):
    with make_client(tmp_path, definitions, False) as client:
        sign_in_as_admin(client)
        assert client.get("/api/v2.0/indexers?configured=true").json() == []


class NamedIndexer(FakeIndexer):
    def __init__(self, id_: str, type_: str | None = "public") -> None:
        super().__init__(type_)
        self.id = id_


def test_provisioner_with_an_allowlist_configures_only_those():
    wanted, other = NamedIndexer("wanted"), NamedIndexer("other")
    provisioner = PublicIndexerProvisioner(only=frozenset({"wanted"}))
    assert provisioner.provision([wanted, other]) == 1
    assert wanted.is_configured and not other.is_configured


def test_allowlist_does_not_stop_adding_a_public_indexer_by_hand():
    other = NamedIndexer("other")
    provisioner = PublicIndexerProvisioner(only=frozenset({"wanted"}))
    assert provisioner.provision_one(other)
    assert other.is_configured


def test_allowlist_warns_about_unknown_and_private_ids(caplog):
    private = NamedIndexer("secret", "private")
    provisioner = PublicIndexerProvisioner(only=frozenset({"secret", "nope"}))
    with caplog.at_level("WARNING"):
        assert provisioner.provision([private]) == 0
    assert "nope, secret" in caplog.text
    assert not private.is_configured


DEFAULT = frozenset({"default"})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, DEFAULT),
        ("", DEFAULT),
        ("  ", DEFAULT),
        ("all", None),
        ("a", frozenset({"a"})),
        ("a, b,c  d", frozenset({"a", "b", "c", "d"})),
    ],
)
def test_public_indexers_from_the_environment(value, expected):
    from pyjackett.config.environment import (
        INDEXERS_ENV,
        public_indexers_from,
    )

    environ = {} if value is None else {INDEXERS_ENV: value}
    assert public_indexers_from(environ, DEFAULT) == expected


def test_default_indexers_are_all_real_public_indexers():
    from pyjackett.config.default_indexers import DEFAULT_PUBLIC_INDEXERS

    context = build_context(Path(__import__("tempfile").mkdtemp()), environ={})
    context.indexers.init_indexers()
    public = {
        i.id for i in context.indexers.all_indexers() if i.type == "public"
    }
    assert public >= DEFAULT_PUBLIC_INDEXERS


@pytest.mark.parametrize(
    ("environ", "configured"),
    [
        ({}, False),  # faketracker is not in the default list
        ({"PYJACKETT_INDEXERS": "all"}, True),
        ({"PYJACKETT_INDEXERS": "faketracker"}, True),
    ],
)
def test_startup_configures_the_default_list_unless_told_otherwise(
    tmp_path, environ, configured
):
    from tests.conftest import FIXTURES

    context = build_context(
        tmp_path,
        extra_definition_dirs=[FIXTURES],
        client_factory=fakes.mock_network(unavailable),
        include_bundled=False,
        configure_public=True,
        default_public=frozenset({"something-else"}),
        environ=environ,
    )
    context.indexers.init_indexers()
    assert context.indexers.get_indexer("faketracker").is_configured is (
        configured
    )
