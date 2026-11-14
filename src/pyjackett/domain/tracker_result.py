"""A release annotated with where it came from (for the dashboard)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pyjackett.domain.category_lookup import get_category_description
from pyjackett.domain.release import ReleaseInfo


@dataclass(eq=False)
class TrackerCacheResult(ReleaseInfo):
    first_seen: datetime | None = None
    tracker: str | None = None
    tracker_id: str | None = None
    tracker_type: str | None = None
    category_desc: str = ""
    blackhole_link: str | None = None

    @classmethod
    def from_release(
        cls,
        release: ReleaseInfo,
        tracker: str | None = None,
        tracker_id: str | None = None,
        tracker_type: str | None = None,
        first_seen: datetime | None = None,
    ) -> TrackerCacheResult:
        """Copy ``release`` and describe its categories in words."""
        values = {
            name: getattr(release, name)
            for name in release.__dataclass_fields__
            if name != "origin"
        }
        result = cls(
            **values,
            first_seen=first_seen,
            tracker=tracker,
            tracker_id=tracker_id,
            tracker_type=tracker_type,
        )
        result.category_desc = ", ".join(
            description
            for description in map(get_category_description, result.category)
            if description
        )
        if result.peers is not None and result.seeders is not None:
            result.peers -= result.seeders  # dashboard shows leechers
        return result
