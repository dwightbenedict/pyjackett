"""Category tables written as data: ``(tracker id, Torznab name[, desc])``."""

from __future__ import annotations

from pyjackett.domain.category_lookup import get_category_by_name
from pyjackett.domain.category_mappings import CategoryMappings


def add_categories(
    mappings: CategoryMappings,
    table: list[tuple[str, str] | tuple[str, str, str]],
) -> None:
    """Register every row; Torznab names must exist in the catalog."""
    for tracker_id, torznab_name, *description in table:
        category = get_category_by_name(torznab_name)
        if category is None:
            raise KeyError(f"Unknown Torznab category: {torznab_name}")
        mappings.add(tracker_id, category, *description)
