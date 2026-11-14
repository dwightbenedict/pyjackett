"""Definitions are mirrored from upstream and reloaded without a restart."""

from __future__ import annotations

import asyncio
import json

import pytest

import fakes
from conftest import FIXTURES
from pyjackett.app_context import build_context
from pyjackett.config.server_config import ServerConfig
from pyjackett.core.exceptions import DefinitionFeedError
from pyjackett.definition_sync.feed import GitHubDefinitionFeed
from pyjackett.definition_sync.store import DefinitionStore
from pyjackett.definition_sync.task import (
    RETRY_SECONDS,
    SYNC_INTERVAL_SECONDS,
    DefinitionSyncTask,
)
from pyjackett.definition_sync.updater import (
    DefinitionChanges,
    DefinitionUpdater,
)
from pyjackett.http.session import HttpSession
from test_injection import FakeClock

TEMPLATE = (FIXTURES / "faketracker.yml").read_text("utf-8")
BROKEN = "name: [unclosed"


def definition(indexer_id: str, name: str = "Fake Tracker") -> str:
    return TEMPLATE.replace("id: faketracker", f"id: {indexer_id}").replace(
        "name: Fake Tracker", f"name: {name}"
    )


class FakeFeed:
    """name -> (revision, text); remembers what was downloaded."""

    def __init__(self, files: dict[str, tuple[str, str]]) -> None:
        self.files = files
        self.fetched: list[str] = []

    async def list_files(self) -> dict[str, str]:
        return {name: revision for name, (revision, _) in self.files.items()}

    async def fetch(self, name: str) -> str:
        self.fetched.append(name)
        return self.files[name][1]


@pytest.fixture
def downloaded(tmp_path):
    return tmp_path / "Definitions"


@pytest.fixture
def store(downloaded):
    return DefinitionStore(downloaded)


# ---- the update round -------------------------------------------------------


async def test_a_round_downloads_what_is_new_and_then_nothing(store):
    feed = FakeFeed(
        {"a.yml": ("1", definition("a")), "b.yml": ("1", definition("b"))}
    )
    updater = DefinitionUpdater(feed, store)
    first = await updater.update()
    assert first.added == ("a.yml", "b.yml")
    assert store.revisions() == {"a.yml": "1", "b.yml": "1"}
    second = await updater.update()
    assert not second.changed
    assert feed.fetched == ["a.yml", "b.yml"]


async def test_a_new_revision_is_downloaded_again(store, downloaded):
    feed = FakeFeed({"a.yml": ("1", definition("a"))})
    updater = DefinitionUpdater(feed, store)
    await updater.update()
    feed.files["a.yml"] = ("2", definition("a", "Renamed"))
    changes = await updater.update()
    assert changes.updated == ("a.yml",)
    assert "Renamed" in (downloaded / "a.yml").read_text("utf-8")


async def test_definitions_gone_upstream_are_removed(store):
    feed = FakeFeed(
        {"a.yml": ("1", definition("a")), "b.yml": ("1", definition("b"))}
    )
    updater = DefinitionUpdater(feed, store)
    await updater.update()
    del feed.files["b.yml"]
    changes = await updater.update()
    assert changes.removed == ("b.yml",)
    assert not store.has_file("b.yml")
    assert store.revisions() == {"a.yml": "1"}


async def test_a_definition_that_does_not_parse_keeps_the_working_one(
    store, downloaded
):
    feed = FakeFeed({"a.yml": ("1", definition("a"))})
    updater = DefinitionUpdater(feed, store)
    await updater.update()
    feed.files["a.yml"] = ("2", BROKEN)
    changes = await updater.update()
    assert changes.rejected == ("a.yml",)
    assert not changes.changed
    assert "id: a" in (downloaded / "a.yml").read_text("utf-8")
    await updater.update()
    assert feed.fetched.count("a.yml") == 3  # retried every round


async def test_upstream_overwrites_files_already_on_disk(store, downloaded):
    downloaded.mkdir()
    existing = downloaded / "a.yml"
    existing.write_text("old", encoding="utf-8")
    kept = downloaded / "mine.yml"
    kept.write_text("mine", encoding="utf-8")
    feed = FakeFeed({"a.yml": ("1", definition("a"))})
    changes = await DefinitionUpdater(feed, store).update()
    assert changes.added == ("a.yml",)
    assert existing.read_text("utf-8") == definition("a")
    assert kept.read_text("utf-8") == "mine"  # never deleted: not in manifest


async def test_an_empty_listing_never_wipes_the_store(store):
    feed = FakeFeed({"a.yml": ("1", definition("a"))})
    updater = DefinitionUpdater(feed, store)
    await updater.update()
    feed.files.clear()
    with pytest.raises(DefinitionFeedError):
        await updater.update()
    assert store.has_file("a.yml")


# ---- the GitHub feed --------------------------------------------------------


def github(handler):
    session = HttpSession(
        ServerConfig(), client_factory=fakes.mock_network(handler)
    )
    return GitHubDefinitionFeed(session, "o/r", "main", "defs")


async def test_the_feed_lists_definition_blobs_by_revision():
    seen = []

    def handler(request):
        seen.append(request.url.geturl())
        tree = [
            {"path": "a.yml", "type": "blob", "sha": "s1"},
            {"path": "notes.md", "type": "blob", "sha": "s2"},
            {"path": "nested.yml", "type": "tree", "sha": "s3"},
            {"path": "../evil.yml", "type": "blob", "sha": "s4"},
        ]
        return fakes.Response(200, text=json.dumps({"tree": tree}))

    files = await github(handler).list_files()
    assert files == {"a.yml": "s1"}
    assert seen == ["https://api.github.com/repos/o/r/git/trees/main:defs"]


async def test_the_feed_downloads_raw_text_and_reports_failures():
    def handler(request):
        if request.url.path == "/o/r/main/defs/a.yml":
            return fakes.Response(200, text="id: a")
        return fakes.Response(404)

    feed = github(handler)
    assert await feed.fetch("a.yml") == "id: a"
    with pytest.raises(DefinitionFeedError):
        await feed.fetch("missing.yml")
    with pytest.raises(DefinitionFeedError):
        await feed.list_files()


async def test_a_malformed_listing_is_a_feed_error():
    feed = github(lambda request: fakes.Response(200, text="[]"))
    with pytest.raises(DefinitionFeedError):
        await feed.list_files()


# ---- the background task ----------------------------------------------------


class FakeUpdater:
    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def update(self) -> DefinitionChanges:
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else NO_CHANGES
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


NO_CHANGES = DefinitionChanges()
SOME_CHANGES = DefinitionChanges(updated=("a.yml",))


class Reloads:
    def __init__(self, fail_first: bool = False) -> None:
        self.count = 0
        self._fail = fail_first

    async def __call__(self) -> int:
        self.count += 1
        if self._fail:
            self._fail = False
            raise RuntimeError("reload failed")
        return 1


def sync_task(updater, config=None, reloads=None):
    reloads = reloads or Reloads()
    task = DefinitionSyncTask(
        updater, config or ServerConfig(), FakeClock(), reloads
    )
    return task, reloads


async def test_a_round_that_changed_something_reloads_the_indexers():
    task, reloads = sync_task(FakeUpdater(SOME_CHANGES, NO_CHANGES))
    assert await task.sync_now() == SYNC_INTERVAL_SECONDS
    assert reloads.count == 1
    await task.sync_now()
    assert reloads.count == 1


async def test_disabling_update_checks_pauses_the_sync():
    updater = FakeUpdater(SOME_CHANGES)
    task, reloads = sync_task(updater, ServerConfig(update_disabled=True))
    assert await task.sync_now() == SYNC_INTERVAL_SECONDS
    assert updater.calls == 0
    assert reloads.count == 0


async def test_a_failed_round_is_retried_sooner():
    task, _ = sync_task(FakeUpdater(DefinitionFeedError("offline")))
    assert await task.sync_now() == RETRY_SECONDS
    task, _ = sync_task(FakeUpdater(RuntimeError("bug")))
    assert await task.sync_now() == RETRY_SECONDS


async def test_a_failed_reload_is_retried_even_without_new_changes():
    task, reloads = sync_task(
        FakeUpdater(SOME_CHANGES, NO_CHANGES),
        reloads=Reloads(fail_first=True),
    )
    assert await task.sync_now() == RETRY_SECONDS
    assert await task.sync_now() == SYNC_INTERVAL_SECONDS
    assert reloads.count == 2


class WaitingClock(FakeClock):
    """Sleeping really waits, so a loop can be observed between rounds."""

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        await asyncio.Event().wait()


async def test_the_loop_runs_once_per_interval_until_detached():
    updater = FakeUpdater()
    clock = WaitingClock()
    task = DefinitionSyncTask(updater, ServerConfig(), clock, Reloads())
    task.attach()
    task.attach()
    for _ in range(5):
        await asyncio.sleep(0)
    assert updater.calls == 1
    assert clock.slept == [SYNC_INTERVAL_SECONDS]
    await task.detach()
    await task.detach()


# ---- reloading indexers -----------------------------------------------------


def make_context(tmp_path, **options):
    return build_context(
        tmp_path,
        client_factory=fakes.mock_network(lambda request: fakes.Response(404)),
        include_bundled=False,
        **options,
    )


async def test_reload_adds_new_and_swaps_changed_definitions(
    tmp_path, downloaded
):
    downloaded.mkdir()
    (downloaded / "one.yml").write_text(definition("one"), "utf-8")
    context = make_context(tmp_path)
    manager = context.indexers
    manager.init_indexers()
    untouched = manager.get_indexer("one")
    assert await manager.reload_definitions() == 0
    assert manager.get_indexer("one") is untouched

    (downloaded / "two.yml").write_text(definition("two"), "utf-8")
    (downloaded / "one.yml").write_text(definition("one", "Renamed"), "utf-8")
    assert await manager.reload_definitions() == 2
    assert manager.get_indexer("one").name == "Renamed"
    assert manager.get_indexer("two").name == "Fake Tracker"
    assert await manager.reload_definitions() == 0
    await context.close()


async def test_reload_keeps_the_saved_configuration(tmp_path, downloaded):
    downloaded.mkdir()
    (downloaded / "one.yml").write_text(definition("one"), "utf-8")
    context = make_context(tmp_path, configure_public=True)
    manager = context.indexers
    manager.init_indexers()
    assert manager.get_indexer("one").is_configured
    (downloaded / "one.yml").write_text(definition("one", "Renamed"), "utf-8")
    await manager.reload_definitions()
    assert manager.get_indexer("one").is_configured
    await context.close()


def test_a_later_definition_folder_overrides_an_earlier_one(
    tmp_path, downloaded
):
    downloaded.mkdir()
    (downloaded / "one.yml").write_text(definition("one", "Old"), "utf-8")
    newer = tmp_path / "newer"
    newer.mkdir()
    (newer / "one.yml").write_text(definition("one", "New"), "utf-8")
    context = build_context(
        tmp_path, extra_definition_dirs=[newer], include_bundled=False
    )
    context.indexers.init_indexers()
    assert context.indexers.get_indexer("one").name == "New"


def test_syncing_is_opt_in(tmp_path):
    assert make_context(tmp_path).definition_sync is None
    assert make_context(tmp_path, sync_definitions=True).definition_sync
