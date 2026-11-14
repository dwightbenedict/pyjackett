"""Rewrites result links so downloads go through this server."""

from __future__ import annotations

from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.text import make_valid_file_name
from pyjackett.domain.tracker_result import TrackerCacheResult
from pyjackett.wiring import AppContext

DOWNLOAD_ACTION = "dl"
IMAGE_ACTION = "img"
BLACKHOLE_ACTION = "bh"


def proxy_release(context: AppContext, release: ReleaseInfo, server_url: str) -> ReleaseInfo:
    """A copy of ``release`` with proxied link and poster."""
    proxied = release.clone()
    service = context.server_service
    indexer_id = release.origin.id
    proxied.link = service.convert_to_proxy_link(
        release.link, server_url, indexer_id, DOWNLOAD_ACTION, release.title
    )
    proxied.poster = service.convert_to_proxy_link(
        release.poster, server_url, indexer_id, IMAGE_ACTION, "poster"
    )
    return proxied


def proxy_tracker_result(context: AppContext, result: TrackerCacheResult, server_url: str) -> None:
    """Rewrite links of a dashboard result in place."""
    service = context.server_service
    original = result.link or result.magnet_uri
    file_name = make_valid_file_name(result.title or "", "_", False)
    result.link = service.convert_to_proxy_link(
        result.link, server_url, result.tracker_id, DOWNLOAD_ACTION, file_name
    )
    result.poster = service.convert_to_proxy_link(
        result.poster, server_url, result.tracker_id, IMAGE_ACTION, "poster"
    )
    if context.config.blackhole_dir and original:
        result.blackhole_link = service.convert_to_proxy_link(
            original,
            server_url,
            result.tracker_id,
            BLACKHOLE_ACTION,
            file_name,
        )
