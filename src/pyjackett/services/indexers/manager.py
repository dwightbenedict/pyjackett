"""Loads, finds, tests and removes indexers.

The manager is a facade: sources create indexers, the registry stores them,
the meta factory builds "all" and the filter groups.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from pyjackett.domain.server_config import ServerConfig
from pyjackett.errors import (
    IndexerConfigurationRequiredError,
    IndexerTestTimeoutError,
)
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.configuration import (
    IndexerConfigurationService,
)
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.meta.factory import MetaIndexerFactory
from pyjackett.services.indexers.provisioning import PublicIndexerProvisioner
from pyjackett.services.indexers.registry import IndexerRegistry
from pyjackett.services.indexers.sources import IndexerSource

logger = logging.getLogger(__name__)


class UnknownIndexerError(KeyError):
    """No indexer, meta indexer or filter matches the requested name."""


class IndexerManager:
    """Registry of every indexer plus the meta indexers built on them."""

    def __init__(
        self,
        dependencies: IndexerDependencies,
        config_service: IndexerConfigurationService,
        sources: Iterable[IndexerSource],
        registry: IndexerRegistry,
        meta_factory: MetaIndexerFactory,
        provisioner: PublicIndexerProvisioner,
        config: ServerConfig,
    ) -> None:
        self._config = config
        self._deps = dependencies
        self._config_service = config_service
        self._sources = list(sources)
        self._registry = registry
        self._meta = meta_factory
        self._provisioner = provisioner

    # ---- startup ----------------------------------------------------------

    def init_indexers(self) -> None:
        for source in self._sources:
            self._load_source(source)
        logger.info("Loaded %d indexers in total", len(self._registry))
        self._migrate_renamed_indexers()
        self._load_configurations()
        self._provisioner.provision(self._registry.values())
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

    async def reload_definitions(self) -> int:
        """Add new and swap changed indexers without a restart.

        Returns how many changed. Indexers whose definition disappeared stay
        until the next restart.
        """
        fresh = await asyncio.to_thread(self._load_all)
        changed = [i for i in fresh if self._apply_definition(i)]
        if changed:
            self._migrate_renamed_indexers()
            self._provisioner.provision(changed)
            self.init_meta_indexers()
        logger.info("Reloaded definitions: %d changed", len(changed))
        return len(changed)

    def _load_all(self) -> list[BaseIndexer]:
        return [i for source in self._sources for i in source.load(self._deps)]

    def _apply_definition(self, indexer: BaseIndexer) -> bool:
        current = self._registry.find(indexer.id)
        if current is None:
            self._register(indexer)
        elif current.same_definition_as(indexer):
            return False
        else:
            self._registry.replace(indexer)
            indexer.subscribe_config_changes(self._config_service.save)
        self._config_service.load(indexer)
        return True

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
        """Run a blank search; fails when the tracker returns nothing.

        A tracker that does not answer within the test timeout fails too.
        """
        indexer = self.get_indexer(name)
        seconds = self._config.test_timeout
        limit = asyncio.timeout(seconds)
        try:
            async with limit:
                await indexer.verify()
        except TimeoutError:
            if not limit.expired():
                raise
            raise IndexerTestTimeoutError(
                f"No answer within {seconds:g} seconds"
            ) from None

    def add_indexer(self, name: str) -> BaseIndexer:
        """Configure a public indexer with its defaults (idempotent).

        Indexers that need credentials must be configured with their form.
        """
        found = self._registry.find(self._registry.resolve(name))
        if found is None:
            raise UnknownIndexerError(f"Unknown indexer: {name}")
        if not found.is_configured and not self._provisioner.provision_one(
            found
        ):
            raise IndexerConfigurationRequiredError(
                f"{found.name} needs credentials: configure it with its form"
            )
        return found

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
