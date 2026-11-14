"""The set of known indexers and the old ids that still resolve to them."""

from __future__ import annotations

import logging
from collections.abc import ItemsView, ValuesView

from pyjackett.services.indexers.base import BaseIndexer

logger = logging.getLogger(__name__)


class IndexerRegistry:
    """Indexers by id, plus aliases for indexers that were renamed."""

    def __init__(self) -> None:
        self._indexers: dict[str, BaseIndexer] = {}
        self._aliases: dict[str, str] = {}

    # ---- registration -------------------------------------------------------

    def register(self, indexer: BaseIndexer) -> bool:
        """Add ``indexer``; False when its id is already taken."""
        if indexer.id in self._indexers:
            logger.warning("Ignoring indexer ID %s: it already exists", indexer.id)
            return False
        self._indexers[indexer.id] = indexer
        return True

    def replace(self, indexer: BaseIndexer) -> None:
        """Swap in ``indexer`` for the one that has its id."""
        self._indexers[indexer.id] = indexer

    def build_aliases(self) -> ItemsView[str, str]:
        """(Re)learn which old id belongs to which indexer; returns them."""
        aliases: dict[str, str] = {}
        for indexer in self._indexers.values():
            for old_id in filter(None, indexer.replaces):
                if old_id in aliases:
                    logger.warning(
                        "Duplicate replacement mapping: %s is replaced by "
                        "both %s and %s. Keeping %s.",
                        old_id,
                        aliases[old_id],
                        indexer.id,
                        aliases[old_id],
                    )
                else:
                    aliases[old_id] = indexer.id
        self._aliases = aliases
        return aliases.items()

    # ---- lookup -------------------------------------------------------------

    def resolve(self, name: str) -> str:
        """The current id for ``name`` (old ids of renamed indexers too)."""
        real_name = self._aliases.get(name, name)
        if real_name != name:
            logger.warning(
                "Indexer %s has been renamed to %s. Please update the URL "
                "of the feeds. This may stop working in the future.",
                name,
                real_name,
            )
        return real_name

    def find(self, indexer_id: str) -> BaseIndexer | None:
        return self._indexers.get(indexer_id)

    def __contains__(self, indexer_id: str) -> bool:
        return indexer_id in self._indexers

    def __len__(self) -> int:
        return len(self._indexers)

    def values(self) -> ValuesView[BaseIndexer]:
        """A live view of every indexer (meta indexers keep one)."""
        return self._indexers.values()

    def sorted_by_name(self) -> list[BaseIndexer]:
        return sorted(self._indexers.values(), key=lambda i: i.name)
