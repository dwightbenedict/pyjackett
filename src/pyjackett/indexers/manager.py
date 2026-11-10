"""Loads, finds, tests and removes indexers.

The manager is a facade: sources create indexers, the registry stores them,
the meta factory builds "all" and the filter groups.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from pyjackett.config.server_config import ServerConfig
from pyjackett.core.query import TorznabQuery
from pyjackett.indexers.base import BaseIndexer
from pyjackett.indexers.configuration import IndexerConfigurationService
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.meta.factory import MetaIndexerFactory
from pyjackett.indexers.registry import IndexerRegistry
from pyjackett.indexers.sources import (
    CardigannSource,
    IndexerSource,
    NativeSource,
)

logger = logging.getLogger(__name__)


class UnknownIndexerError(KeyError):
    """No indexer, meta indexer or filter matches the requested name."""


class IndexerManager:
    """Registry of every indexer plus the meta indexers built on them."""

    def __init__(
        self,
        dependencies: IndexerDependencies,
        config_service: IndexerConfigurationService,
        server_config: ServerConfig,
        definition_dirs: list[Path],
        sources: Iterable[IndexerSource] | None = None,
    ) -> None:
        self._deps = dependencies
        self._config_service = config_service
        self._sources = list(
            sources or [NativeSource(), CardigannSource(definition_dirs)]
        )
        self._registry = IndexerRegistry()
        self._meta = MetaIndexerFactory(
            dependencies, server_config, self._registry.values()
        )

    # ---- startup ----------------------------------------------------------

    def init_indexers(self) -> None:
        for source in self._sources:
            self._load_source(source)
        logger.info("Loaded %d indexers in total", len(self._registry))
        self._migrate_renamed_indexers()
        self._load_configurations()
        self.init_meta_indexers()
        self._remove_legacy_configurations()

    def _load_source(self, source: IndexerSource) -> None:
        loaded = sum(
            self._register(indexer) for indexer in source.load(self._deps)
        )
        logger.info("Loaded %d %s indexers", loaded, source.name)

    def _register(self, indexer: BaseIndexer) -> bool:
        """Add the indexer and persist its configuration when it changes."""
        if not self._registry.register(indexer):
            return False
        indexer.subscribe_config_changes(self._config_service.save)
        return True

    def _load_configurations(self) -> None:
        for indexer in self._registry.values():
            self._config_service.load(indexer)

    def _migrate_renamed_indexers(self) -> None:
        """Keep old ids working and move their saved configuration."""
        store = self._config_service.store
        for old_id, new_id in self._registry.build_aliases():
            if store.rename(old_id, new_id):
                logger.info("Configuration renamed: %s => %s", old_id, new_id)

    def init_meta_indexers(self) -> None:
        """(Re)build the "all" indexer and the predefined filter groups."""
        self._meta.rebuild()

    # ---- lookup -------------------------------------------------------------

    def get_indexer(self, name: str) -> BaseIndexer:
        """Find by id (old ids of renamed indexers still work)."""
        return self.get_web_indexer(self._registry.resolve(name))

    def get_web_indexer(self, name: str) -> BaseIndexer:
        indexer = self._registry.find(name) or self._meta.find(name)
        if indexer is None:
            logger.error("Request for unknown indexer: %s", name)
            raise UnknownIndexerError(f"Unknown indexer: {name}")
        return indexer

    def all_indexers(self) -> list[BaseIndexer]:
        return self._registry.sorted_by_name()

    # ---- operations ---------------------------------------------------------

    async def test_indexer(self, name: str) -> None:
        """Run a blank search; fails when the tracker returns nothing."""
        indexer = self.get_indexer(name)
        query = TorznabQuery(query_type="search", search_term="", is_test=True)
        result = await indexer.results_for_query(query)
        logger.info(
            "Test search in %s => Found %d releases [%dms]",
            indexer.name,
            len(result.releases),
            result.elapsed_ms,
        )
        if not result.releases:
            raise RuntimeError(
                f"Test search in {indexer.name} => Found no results while "
                "trying to browse this tracker. This may be an issue with "
                "the indexer, or other indexer settings such as search "
                "freeleech only etc."
            )

    def delete_indexer(self, name: str) -> None:
        indexer = self.get_indexer(name)
        self._config_service.delete(indexer)
        indexer.unconfigure()

    # ---- cleanup ------------------------------------------------------------

    def _remove_legacy_configurations(self) -> None:
        """Delete saved configs of indexers that no longer exist."""
        store = self._config_service.store
        for indexer_id in store.stored_ids():
            if indexer_id not in self._registry:
                logger.info("Removing old configuration file: %s", indexer_id)
                store.delete(indexer_id)
