"""Lookups over the static Torznab category catalog."""

from __future__ import annotations

from pyjackett.domain.category import TorznabCategory
from pyjackett.domain.category_catalog import ALL_CATEGORIES

_BY_NAME = {category.name: category for category in ALL_CATEGORIES}
_BY_ID = {category.id: category for category in ALL_CATEGORIES}


def get_category_by_name(name: str) -> TorznabCategory | None:
    return _BY_NAME.get(name)


def get_category_description(category_id: int) -> str:
    category = _BY_ID.get(category_id)
    return category.name if category else ""
