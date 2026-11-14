"""Magnet link construction and parsing."""

from __future__ import annotations

from urllib.parse import quote

from pyjackett.domain.urls import get_query_argument, url_encode

_PUBLIC_TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://vito-tracker.space:6969/announce",
    "udp://vito-tracker.duckdns.org:6969/announce",
    "udp://tracker.theoks.net:6969/announce",
    "udp://tracker.srv00.com:6969/announce",
    "udp://tracker.qu.ax:6969/announce",
    "udp://tracker.corpscorp.online:80/announce",
)
_TRACKERS_QUERY = "&".join(f"tr={quote(tracker, safe='')}" for tracker in _PUBLIC_TRACKERS)


def info_hash_to_public_magnet(info_hash: str, title: str) -> str | None:
    """Build a magnet link carrying a list of well known public trackers."""
    if not info_hash or not info_hash.strip():
        return None
    if not title or not title.strip():
        return None
    name = url_encode(title)
    return f"magnet:?xt=urn:btih:{info_hash}&dn={name}&{_TRACKERS_QUERY}"


def magnet_to_info_hash(magnet: str) -> str | None:
    exact_topic = get_query_argument(magnet, "xt")
    return exact_topic.split(":")[-1] if exact_topic else None
