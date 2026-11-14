"""The category tree an indexer exposes, built from tracker categories."""

from __future__ import annotations

from pyjackett.core.category_catalog import (
    MOVIES,
    MOVIES_HD,
    MOVIES_SD,
    TV,
)
from pyjackett.core.category_mappings import (
    CUSTOM_CATEGORY_OFFSET,
    CategoryMappings,
)


def tree_of(mappings: CategoryMappings) -> list[tuple[int, list[int]]]:
    return [
        (node.id, [child.id for child in node.subcategories])
        for node in mappings.category_tree()
    ]


def test_a_child_gets_its_parent_with_the_child_once():
    mappings = CategoryMappings()
    mappings.add("1", MOVIES_HD)
    mappings.add("2", MOVIES_HD)
    mappings.add("3", MOVIES_SD)
    assert tree_of(mappings) == [(MOVIES.id, [MOVIES_HD.id, MOVIES_SD.id])]


def test_a_parent_is_listed_once_and_keeps_later_children():
    mappings = CategoryMappings()
    mappings.add("1", MOVIES)
    mappings.add("2", MOVIES)
    mappings.add("3", MOVIES_HD)
    assert tree_of(mappings) == [(MOVIES.id, [MOVIES_HD.id])]


def test_parents_keep_the_order_they_were_first_seen_in():
    mappings = CategoryMappings()
    mappings.add("1", TV)
    mappings.add("2", MOVIES_HD)
    assert [parent for parent, _ in tree_of(mappings)] == [TV.id, MOVIES.id]


def test_a_described_mapping_adds_a_custom_category():
    mappings = CategoryMappings()
    mappings.add("7", MOVIES_HD, "Films 1080p")
    custom = [
        node
        for node in mappings.category_tree()
        if node.id >= CUSTOM_CATEGORY_OFFSET
    ]
    assert [(c.id, c.name) for c in custom] == [(100007, "Films 1080p")]
    assert mappings.to_torznab("7") == [MOVIES_HD.id, 100007]


def test_merge_copies_only_standard_categories():
    source = CategoryMappings()
    source.add("7", MOVIES_HD, "Films 1080p")
    target = CategoryMappings()
    target.merge(source)
    assert tree_of(target) == [(MOVIES.id, [MOVIES_HD.id])]
