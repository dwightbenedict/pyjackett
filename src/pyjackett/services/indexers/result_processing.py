"""Validation and normalisation of the releases an indexer returned."""

from __future__ import annotations

import logging
from datetime import datetime

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.dates import local_now
from pyjackett.domain.magnet import (
    info_hash_to_public_magnet,
    magnet_to_info_hash,
)
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.text import is_blank

logger = logging.getLogger(__name__)

PRIVATE_TYPE = "private"


def is_valid_release(release: ReleaseInfo, interactive_search: bool, indexer_id: str) -> bool:
    """A release needs a title; normal searches also size and category."""
    if is_blank(release.title):
        logger.error(
            "[%s] Invalid Release: '%s'. No title provided.",
            indexer_id,
            release.details,
        )
        return False
    if interactive_search:
        return True  # show releases with issues in the manual search
    if release.size is None:
        logger.warning(
            "[%s] Invalid Release: '%s'. No size provided.",
            indexer_id,
            release.details,
        )
        return False
    if not release.category:
        logger.warning(
            "[%s] Invalid Release: '%s'. No categories provided.",
            indexer_id,
            release.details,
        )
        return False
    return True


def filter_results(
    releases: list[ReleaseInfo],
    query: TorznabQuery,
    caps: TorznabCapabilities,
    indexer_id: str,
) -> list[ReleaseInfo]:
    """Drop invalid releases and those outside the requested categories."""
    kept = [
        release
        for release in releases
        if is_valid_release(release, query.interactive_search, indexer_id)
    ]
    if query.categories:
        wanted = set(caps.categories.expand_query_categories(query))
        kept = [
            release
            for release in kept
            if not release.category or wanted.intersection(release.category)
        ]
    return kept[: query.limit] if query.limit > 0 else kept


def _clamp_future_date(release: ReleaseInfo, now: datetime) -> None:
    """Some trackers keep their clocks ~20 minutes ahead."""
    if release.publish_date is not None and release.publish_date > now:
        release.publish_date = now


def _complete_links(release: ReleaseInfo, indexer_type: str | None) -> None:
    if (
        release.magnet_uri is None
        and not is_blank(release.info_hash)
        and indexer_type != PRIVATE_TYPE
    ):
        release.magnet_uri = info_hash_to_public_magnet(release.info_hash, release.title)
    if release.magnet_uri is not None and is_blank(release.info_hash):
        release.info_hash = magnet_to_info_hash(release.magnet_uri)


def _ensure_guid(release: ReleaseInfo) -> None:
    if release.guid is None:
        release.guid = release.link or release.magnet_uri or release.details


def fix_results(
    releases: list[ReleaseInfo], indexer, now: datetime | None = None
) -> list[ReleaseInfo]:
    """Attach the origin, repair dates and fill links/guid."""
    now = now or local_now()
    for release in releases:
        release.origin = indexer
        _clamp_future_date(release, now)
        _complete_links(release, indexer.type)
        _ensure_guid(release)
    return releases


def deduplicate_by_guid(releases: list[ReleaseInfo]) -> list[ReleaseInfo]:
    """Keep the first release of each guid."""
    unique: dict[str | None, ReleaseInfo] = {}
    for release in releases:
        unique.setdefault(release.guid, release)
    return list(unique.values())
