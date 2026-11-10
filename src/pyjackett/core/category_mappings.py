"""Mapping between tracker categories and Torznab categories."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pyjackett.core.category import TorznabCategory
from pyjackett.core.category_catalog import PARENT_CATEGORIES
from pyjackett.core.query import TorznabQuery

CUSTOM_CATEGORY_OFFSET = 100000


@dataclass(frozen=True)
class CategoryMapping:
    tracker_category: str
    tracker_category_desc: str | None
    torznab_category: int


def _custom_category_number(tracker_category: str) -> int:
    """Stable number for a tracker category (hashed when not numeric)."""
    if tracker_category.lstrip("-").isdigit():
        return int(tracker_category)
    digest = hashlib.sha1(tracker_category.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "little")


def _find_parent(category: TorznabCategory) -> TorznabCategory | None:
    return next((p for p in PARENT_CATEGORIES if p.contains(category)), None)


class CategoryMappings:
    """Holds the mappings plus the tree of categories an indexer exposes."""

    def __init__(self) -> None:
        self._mappings: list[CategoryMapping] = []
        self._tree: list[TorznabCategory] = []

    # ---- building ------------------------------------------------------

    def add(
        self,
        tracker_category: str | int,
        torznab_category: TorznabCategory,
        tracker_category_desc: str | None = None,
    ) -> None:
        """Register a mapping; a description also creates a custom category.

        Custom categories (id >= 100000) expose the tracker's own category
        1:1 to Torznab clients.
        """
        tracker_category = str(tracker_category)
        self._mappings.append(
            CategoryMapping(
                tracker_category, tracker_category_desc, torznab_category.id
            )
        )
        self._add_to_tree(torznab_category)
        if tracker_category_desc is None:
            return
        custom = TorznabCategory(
            _custom_category_number(tracker_category) + CUSTOM_CATEGORY_OFFSET,
            tracker_category_desc,
        )
        self._mappings.append(
            CategoryMapping(tracker_category, tracker_category_desc, custom.id)
        )
        self._add_to_tree(custom)

    def _add_to_tree(self, category: TorznabCategory) -> None:
        if category in PARENT_CATEGORIES:
            self._add_parent(category)
            return
        parent = _find_parent(category)
        if parent is None:
            self._tree.append(category)  # custom category
            return
        self._add_child(parent, category)

    def _add_parent(self, category: TorznabCategory) -> None:
        if category not in self._tree:
            self._tree.append(category.copy_without_subcategories())

    def _add_child(
        self, parent: TorznabCategory, child: TorznabCategory
    ) -> None:
        node = next((c for c in self._tree if c == parent), None)
        if node is None:
            node = parent.copy_without_subcategories()
            self._tree.append(node)
        if not node.contains(child):
            node.subcategories.append(child)

    def merge(self, other: CategoryMappings) -> None:
        """Add the standard categories of ``other`` (custom ones excluded)."""
        for category in other.category_list():
            if category.id < CUSTOM_CATEGORY_OFFSET:
                self._add_to_tree(category)

    # ---- reading ---------------------------------------------------------

    def tracker_categories(self) -> list[str]:
        names = (
            m.tracker_category
            for m in self._mappings
            if m.torznab_category < CUSTOM_CATEGORY_OFFSET
        )
        return list(dict.fromkeys(names))

    def category_tree(self, sort: bool = False) -> list[TorznabCategory]:
        if not sort:
            return self._tree
        sorted_tree = []
        for category in self._tree:
            copy = category.copy_without_subcategories()
            copy.subcategories.extend(
                sorted(category.subcategories, key=lambda c: c.id)
            )
            sorted_tree.append(copy)
        return sorted(sorted_tree, key=_tree_sort_key)

    def category_list(self, sort: bool = False) -> list[TorznabCategory]:
        """Flat list: every parent followed by its children."""
        flat: list[TorznabCategory] = []
        for category in self.category_tree(sort):
            flat.append(category.copy_without_subcategories())
            flat.extend(category.subcategories)
        return flat

    def supported_categories(self, categories: list[int]) -> list[int]:
        if not categories:
            return []
        children = [c for p in self._tree for c in p.subcategories]
        return [c.id for c in self._tree + children if c.id in categories]

    # ---- mapping ------------------------------------------------------------

    def expand_query_categories(
        self, query: TorznabQuery, map_children_to_parent: bool = False
    ) -> list[int]:
        """Add the children of requested parents (and optionally parents)."""
        expanded: list[int] = []
        for category_id in query.categories:
            expanded.append(category_id)
            if category_id >= CUSTOM_CATEGORY_OFFSET:
                continue
            parent = next((c for c in self._tree if c.id == category_id), None)
            if parent is not None:
                expanded.extend(c.id for c in parent.subcategories)
            elif map_children_to_parent:
                probe = TorznabCategory(category_id, "")
                owner = next(
                    (c for c in self._tree if c.contains(probe)), None
                )
                if owner is not None:
                    expanded.append(owner.id)
        return list(dict.fromkeys(expanded))

    def to_tracker_categories(
        self, query: TorznabQuery, map_children_to_parent: bool = False
    ) -> list[str]:
        wanted = self.expand_query_categories(query, map_children_to_parent)
        matches = (
            m.tracker_category
            for m in self._mappings
            if m.torznab_category in wanted
        )
        return list(dict.fromkeys(matches))

    def to_torznab(self, tracker_category: str | None) -> list[int]:
        if not tracker_category or not tracker_category.strip():
            return []
        needle = tracker_category.lower()
        return [
            m.torznab_category
            for m in self._mappings
            if m.tracker_category and m.tracker_category.lower() == needle
        ]

    def to_torznab_by_description(self, description: str | None) -> list[int]:
        if not description or not description.strip():
            return []
        needle = description.lower()
        return [
            m.torznab_category
            for m in self._mappings
            if m.tracker_category_desc
            and m.tracker_category_desc.lower() == needle
        ]


def _tree_sort_key(category: TorznabCategory) -> str:
    if category.id >= CUSTOM_CATEGORY_OFFSET:
        return "zzz" + category.name
    return str(category.id)
