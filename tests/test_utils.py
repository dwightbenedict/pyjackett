"""Parsing and formatting helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pyjackett.domain import bencode, cookies, dates, numbers
from pyjackett.domain.date_formats import net_format_to_strptime
from pyjackett.domain.magnet import (
    info_hash_to_public_magnet,
    magnet_to_info_hash,
)
from pyjackett.domain.urls import get_query_argument, resolve_url


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.5 GB", int(1.5 * 1024**3)),
        ("700 MB", 700 * 1024**2),
        ("1.018,29 MB", int(1018.29 * 1024**2)),
        ("3,5GB", int(3.5 * 1024**3)),
        ("10 KiB", 10 * 1024),
        ("-", 0),
        ("512", 512),
    ],
)
def test_parse_size(text, expected):
    assert numbers.parse_size(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1,234", 1234), ("12", 12), ("-", 0), ("5 seeders", 5)],
)
def test_coerce_int(text, expected):
    assert numbers.coerce_int(text) == expected


def test_imdb_ids():
    assert numbers.format_imdb_id("tt133093") == "tt0133093"
    assert numbers.format_imdb_id("0133093") == "tt0133093"
    assert numbers.format_imdb_id("nonsense") is None
    assert numbers.format_imdb_id("tt0") is None


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        ("yyyy-MM-dd HH:mm:ss", "%Y-%m-%d %H:%M:%S"),
        ("dd/MM/yyyy", "%d/%m/%Y"),
        ("MMM d yyyy hh:mm tt", "%b %d %Y %I:%M %p"),
        ("yyyy-MM-dd HH:mm zzz", "%Y-%m-%d %H:%M %z"),
    ],
)
def test_dotnet_format_conversion(layout, expected):
    assert net_format_to_strptime(layout) == expected


def test_time_ago():
    now = datetime(2024, 5, 10, 12, 0).astimezone()
    assert dates.from_time_ago("2 hours 30 minutes ago", now) == now - timedelta(
        hours=2, minutes=30
    )
    assert dates.from_time_ago("1 day ago", now) == now - timedelta(days=1)


def test_unknown_formats():
    now = datetime(2024, 5, 10, 12, 0).astimezone()
    assert dates.from_unknown("1700000000").timestamp() == 1700000000
    yesterday = dates.from_unknown("Yesterday at 10:30", relative_from=now)
    assert (yesterday.day, yesterday.hour, yesterday.minute) == (9, 10, 30)
    assert dates.from_unknown("2024-03-01 10:00").year == 2024


def test_cookie_merge_and_expiry():
    merged = cookies.merge_headers("a=1; b=2", "b=3")
    assert cookies.header_to_dict(merged) == {"a": "1", "b": "3"}
    expired = cookies.set_cookie_to_pair("a=gone; Max-Age=0")
    assert cookies.header_to_dict("a=1 " + expired) == {}
    assert cookies.set_cookie_to_pair("a=1; Path=/") == "a=1;"


def test_magnet_roundtrip():
    magnet = info_hash_to_public_magnet("ABCDEF", "My Title")
    assert magnet.startswith("magnet:?xt=urn:btih:ABCDEF&dn=My+Title&tr=")
    assert magnet_to_info_hash(magnet) == "ABCDEF"


def test_urls():
    assert get_query_argument("http://x/?a=1&b=2", "b") == "2"
    assert resolve_url("../x y", "http://h/a/b/") == "http://h/a/x%20y"


def test_bencode_sorts_keys():
    assert bencode.normalize(b"d1:bi1e1:ai2ee") == b"d1:ai2e1:bi1ee"
    with pytest.raises(bencode.BencodeError):
        bencode.decode(b"not bencode")
