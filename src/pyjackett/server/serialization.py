"""JSON representations sent to the dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pyjackett.core.category_catalog import MOVIES
from pyjackett.core.tracker_result import TrackerCacheResult
from pyjackett.indexers.base import BaseIndexer

_RELEASE_FIELDS = (
    "title",
    "guid",
    "link",
    "magnet_uri",
    "details",
    "category",
    "category_desc",
    "size",
    "files",
    "grabs",
    "description",
    "seeders",
    "peers",
    "poster",
    "info_hash",
    "tracker",
    "tracker_id",
    "tracker_type",
    "blackhole_link",
    "imdb",
    "year",
    "minimum_ratio",
    "minimum_seed_time",
    "download_volume_factor",
    "upload_volume_factor",
)


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def release_json(result: TrackerCacheResult) -> dict[str, Any]:
    data = {name: getattr(result, name) for name in _RELEASE_FIELDS}
    data["publish_date"] = _iso(result.publish_date)
    data["first_seen"] = _iso(result.first_seen)
    data["gain"] = result.gain
    return data


def indexer_json(indexer: BaseIndexer) -> dict[str, Any]:
    """The listing entry of one indexer."""
    tree = indexer.torznab_caps.categories.category_tree()
    return {
        "id": indexer.id,
        "name": indexer.name,
        "description": indexer.description,
        "type": indexer.type,
        "configured": indexer.is_configured,
        "site_link": indexer.site_link,
        "alternativesitelinks": list(indexer.alternative_site_links),
        "language": indexer.language,
        "tags": list(indexer.tags),
        "last_error": indexer.last_error or "",
        "potatoenabled": any(MOVIES.contains(c) for c in tree),
        "healthy": indexer.is_healthy,
        "failing": indexer.is_failing,
        "caps": [
            {"ID": str(c.id), "Name": c.name}
            for c in indexer.torznab_caps.categories.category_list(True)
        ],
    }
