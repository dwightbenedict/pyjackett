"""Sites whose address rotates are followed using the injected clock."""

from __future__ import annotations

import shutil

import fakes
from pyjackett.adapters.paths import BUNDLED_DEFINITIONS_DIR
from pyjackett.domain.cardigann import rotating_links
from pyjackett.domain.cardigann.rotating_links import AddressPageLinks
from pyjackett.wiring import build_context
from test_injection import FakeClock

BUNDLED = BUNDLED_DEFINITIONS_DIR
PAGE = AddressPageLinks("529075.xyz", salt="address-page-2026")
SLOT_SECONDS = 30 * 60


def indexer_52bt(tmp_path, clock):
    definitions = tmp_path / "definitions"
    definitions.mkdir()
    shutil.copy(BUNDLED / "52bt.yml", definitions)
    context = build_context(
        tmp_path,
        extra_definition_dirs=[definitions],
        include_bundled=False,
        client_factory=fakes.mock_network(lambda request: fakes.Response(404)),
        clock=clock,
    )
    context.indexers.init_indexers()
    return context.indexers.get_indexer("52bt")


def test_codes_match_the_address_page():
    # values computed by the page's own script
    assert PAGE.link_at(1_700_000_000) == "https://xc5vurd3.529075.xyz/"
    assert PAGE.link_at(1_700_001_800) == "https://hysq5on3.529075.xyz/"


def test_every_rotating_indexer_is_a_bundled_definition():
    for indexer_id in rotating_links.ROTATING_LINKS:
        assert (BUNDLED / f"{indexer_id}.yml").is_file()


def test_link_is_stable_inside_a_slot():
    start = 1_700_000_000 // SLOT_SECONDS * SLOT_SECONDS
    assert PAGE.link_at(start) == PAGE.link_at(start + SLOT_SECONDS - 1)


def test_owns_only_its_domain():
    assert PAGE.owns("https://abcd1234.529075.xyz/")
    assert not PAGE.owns("https://example.com/529075.xyz")


def test_indexer_starts_on_the_current_address(tmp_path):
    indexer = indexer_52bt(tmp_path, FakeClock())
    assert indexer.site_link == "https://xc5vurd3.529075.xyz/"


async def test_indexer_follows_the_rotation(tmp_path):
    clock = FakeClock()
    indexer = indexer_52bt(tmp_path, clock)
    clock.seconds += SLOT_SECONDS
    await indexer.follow_site_address()
    assert indexer.site_link == PAGE.link_at(clock.seconds)
    assert indexer.config_data.site_link.value == indexer.site_link


async def test_indexer_follows_a_stale_configured_address(tmp_path):
    clock = FakeClock()
    indexer = indexer_52bt(tmp_path, clock)
    indexer.site_link = "https://jsrtlgzx.529075.xyz/"
    await indexer.follow_site_address()
    assert indexer.site_link == PAGE.link_at(clock.seconds)


async def test_indexer_keeps_an_address_the_user_typed(tmp_path):
    indexer = indexer_52bt(tmp_path, FakeClock())
    indexer.site_link = "https://my-mirror.example/"
    await indexer.follow_site_address()
    assert indexer.site_link == "https://my-mirror.example/"
