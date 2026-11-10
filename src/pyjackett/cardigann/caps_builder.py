"""Builds Torznab capabilities from a definition's ``caps`` block."""

from __future__ import annotations

import logging

from pyjackett.cardigann.definition import (
    CapabilitiesBlock,
    CategoryMappingBlock,
)
from pyjackett.core.capabilities import TorznabCapabilities
from pyjackett.core.category_lookup import get_category_by_name
from pyjackett.core.search_modes import SearchMode

logger = logging.getLogger(__name__)


def _apply_search_modes(
    caps: TorznabCapabilities, modes: dict[str, list[str]] | None
) -> None:
    """Validate the declared modes and copy their parameters."""
    if not modes:
        raise ValueError("At least one search mode is required")
    if "search" not in modes:
        raise ValueError("The search mode 'search' is mandatory")
    for name, parameters in modes.items():
        try:
            mode = SearchMode(name)
        except ValueError:
            raise ValueError(f"Unsupported search mode: {name}") from None
        if mode is SearchMode.SEARCH:
            if parameters != ["q"]:
                raise ValueError(
                    "In search mode 'search' only 'q' parameter is "
                    "supported and it's mandatory"
                )
            continue
        caps.set_parameters(mode, parameters)


def _add_simple_categories(
    caps: TorznabCapabilities, categories: dict[str, str], indexer_id: str
) -> None:
    for tracker_id, name in categories.items():
        category = get_category_by_name(name)
        if category is None:
            logger.error(
                "CardigannIndexer (%s): invalid Torznab category for id "
                "%s: %s",
                indexer_id,
                tracker_id,
                name,
            )
            continue
        caps.categories.add(tracker_id, category)


def _add_category_mapping(
    caps: TorznabCapabilities, mapping: CategoryMappingBlock, indexer_id: str
) -> bool:
    """Register one mapping; False if its Torznab category is unknown."""
    category = get_category_by_name(mapping.cat) if mapping.cat else None
    if category is None:
        logger.error(
            "CardigannIndexer (%s): invalid Torznab category for id %s: %s",
            indexer_id,
            mapping.id,
            mapping.cat,
        )
        return False
    caps.categories.add(mapping.id, category, mapping.desc)
    return True


def build_capabilities(
    block: CapabilitiesBlock, indexer_id: str
) -> tuple[TorznabCapabilities, list[str]]:
    """Return the capabilities and the default tracker categories."""
    caps = TorznabCapabilities()
    _apply_search_modes(caps, block.modes)
    caps.supports_raw_search = block.allowrawsearch
    caps.tv_search_imdb_available = block.allowtvsearchimdb
    _add_simple_categories(caps, block.categories or {}, indexer_id)
    defaults = []
    for mapping in block.categorymappings or []:
        if (
            _add_category_mapping(caps, mapping, indexer_id)
            and mapping.default
        ):
            defaults.append(mapping.id)
    return caps, defaults
