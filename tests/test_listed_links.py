"""Sites that publish their addresses move to one that still answers."""

from __future__ import annotations

import shutil

import fakes
from pyjackett.app_context import build_context
from pyjackett.cardigann import listed_links
from pyjackett.cardigann.listed_links import (
    RECHECK_SECONDS,
    hrefs_off_site,
    numbered_domains,
)
from test_injection import FakeClock

STATUS_PAGE = """
Official domains (May 2024):

1) 1337x.to
2) 1337x.st
3) x1337x.ws
7) l337xdarkkaqfwzntnfk5bmoaroivtl6xsbatabvlb52umg6v3ch44yd.onion *Beta*

X) 1337x.so !STOP USING! - Expired May 2024
"""
STOP_USING = "1) old.example !STOP USING!"


def indexer_for(tmp_path, clock, indexer_id, handler):
    definitions = tmp_path / "definitions"
    definitions.mkdir()
    bundled = listed_links.__file__.replace(
        r"cardigann\listed_links.py", "definitions"
    ).replace("cardigann/listed_links.py", "definitions")
    shutil.copy(f"{bundled}/{indexer_id}.yml", definitions)
    context = build_context(
        tmp_path,
        extra_definition_dirs=[definitions],
        include_bundled=False,
        client_factory=fakes.mock_network(handler),
        clock=clock,
    )
    context.indexers.init_indexers()
    return context.indexers.get_indexer(indexer_id)


def test_numbered_domains_skip_onion_and_retired_ones():
    assert numbered_domains(STATUS_PAGE) == [
        "https://1337x.to/",
        "https://1337x.st/",
        "https://x1337x.ws/",
    ]
    assert numbered_domains(STOP_USING) == []


def test_hrefs_off_site_ignore_the_pages_own_links():
    page = '<a href="https://www.torrent-site.cc">x</a>'
    page += '<a href="https://www.darkfox.ws">y</a>'
    extract = hrefs_off_site("https://www.torrent-site.my/")
    assert extract(page) == ["https://www.darkfox.ws/"]


async def test_a_working_address_is_kept(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.url.hostname)
        return fakes.Response(200, text="ok")

    indexer = indexer_for(tmp_path, FakeClock(), "1337x", handler)
    await indexer.follow_site_address()
    assert indexer.site_link == "https://1337x.to/"
    assert seen == ["1337x.to"]  # the status page was not needed


async def test_a_dead_address_is_replaced_from_the_status_page(tmp_path):
    def handler(request):
        host = request.url.hostname
        if host == "1337x-status.org":
            return fakes.Response(200, text=STATUS_PAGE)
        return fakes.Response(200 if host == "1337x.st" else 410)

    indexer = indexer_for(tmp_path, FakeClock(), "1337x", handler)
    await indexer.follow_site_address()
    assert indexer.site_link == "https://1337x.st/"


async def test_a_cloudflare_403_counts_as_alive(tmp_path):
    indexer = indexer_for(
        tmp_path, FakeClock(), "1337x", lambda r: fakes.Response(403)
    )
    await indexer.follow_site_address()
    assert indexer.site_link == "https://1337x.to/"


async def test_the_check_is_not_repeated_within_the_interval(tmp_path):
    clock = FakeClock()
    calls = []

    def handler(request):
        calls.append(request.url.hostname)
        return fakes.Response(410)

    indexer = indexer_for(tmp_path, clock, "1337x", handler)
    await indexer.follow_site_address()
    first = len(calls)
    await indexer.follow_site_address()
    assert len(calls) == first
    clock.seconds += RECHECK_SECONDS
    await indexer.follow_site_address()
    assert len(calls) > first


async def test_an_address_the_user_typed_is_left_alone(tmp_path):
    indexer = indexer_for(
        tmp_path, FakeClock(), "world-torrent", lambda r: fakes.Response(410)
    )
    indexer.site_link = "https://my-mirror.example/"
    await indexer.follow_site_address()
    assert indexer.site_link == "https://my-mirror.example/"


async def test_world_torrent_uses_the_address_pages(tmp_path):
    def handler(request):
        host = request.url.hostname
        if host == "www.torrent-site.my":
            return fakes.Response(
                200, text='<a href="https://www.newfox.ws">go</a>'
            )
        return fakes.Response(200 if host == "www.newfox.ws" else 410)

    indexer = indexer_for(tmp_path, FakeClock(), "world-torrent", handler)
    await indexer.follow_site_address()
    assert indexer.site_link == "https://www.newfox.ws/"
