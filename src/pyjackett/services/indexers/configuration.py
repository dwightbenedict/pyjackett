"""Loads and saves the configuration of indexers (encrypting secrets)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pyjackett.services.ports import IndexerConfigRepository, SecretProtector

if TYPE_CHECKING:
    from pyjackett.services.indexers.base import BaseIndexer

logger = logging.getLogger(__name__)


class IndexerConfigurationService:
    """Bridge between an indexer's form data and its JSON file."""

    def __init__(self, store: IndexerConfigRepository, protector: SecretProtector) -> None:
        self._store = store
        self._protector = protector

    @property
    def store(self) -> IndexerConfigRepository:
        return self._store

    def load(self, indexer: BaseIndexer) -> None:
        stored = self._store.load(indexer.id)
        if stored is not None:
            indexer.load_from_saved_configuration(stored)

    def save(self, indexer: BaseIndexer) -> None:
        data = indexer.config_data.to_json(self._protector, for_display=False)
        self._store.save(indexer.id, data)

    def delete(self, indexer: BaseIndexer) -> None:
        self._store.delete(indexer.id)
