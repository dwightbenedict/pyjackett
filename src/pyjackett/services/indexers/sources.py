"""Where indexers come from: each source builds its own kind."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from pyjackett.adapters.definition_cache import DefinitionCache
from pyjackett.services.cardigann.indexer import CardigannIndexer
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.native import NATIVE_INDEXERS

logger = logging.getLogger(__name__)


class IndexerSource(Protocol):
    """Builds indexers; a new kind of indexer is a new source."""

    name: str

    def load(self, dependencies: IndexerDependencies) -> Iterable[BaseIndexer]:
        """Every indexer this source can create (failures are skipped)."""


class NativeSource:
    """Indexers implemented in Python (``indexers/native``)."""

    name = "native"

    def load(self, dependencies: IndexerDependencies) -> list[BaseIndexer]:
        indexers = []
        for indexer_class in NATIVE_INDEXERS:
            try:
                indexers.append(indexer_class(dependencies))
            except Exception:
                logger.exception(
                    "Cannot instantiate native indexer %s",
                    indexer_class.__name__,
                )
        return indexers


class CardigannSource:
    """Indexers described by the YAML files of some directories."""

    name = "Cardigann"

    def __init__(
        self,
        definition_dirs: Iterable[Path],
        cache: DefinitionCache | None = None,
    ) -> None:
        self._definition_dirs = list(definition_dirs)
        self._cache = cache or DefinitionCache()

    def load(self, dependencies: IndexerDependencies) -> list[BaseIndexer]:
        created = (self._create(dependencies, path) for path in self._files())
        indexers = [indexer for indexer in created if indexer is not None]
        self._cache.save()
        return indexers

    def _files(self) -> list[Path]:
        """Every definition file; a later directory overrides an earlier."""
        by_name = {
            file.name: file
            for directory in self._definition_dirs
            if directory.is_dir()
            for file in directory.glob("*.yml")
        }
        return [by_name[name] for name in sorted(by_name)]

    def _create(self, dependencies: IndexerDependencies, path: Path) -> CardigannIndexer | None:
        try:
            definition = self._cache.parse(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Error while parsing definition %s", path)
            return None
        try:
            return CardigannIndexer(dependencies, definition)
        except Exception:
            logger.exception(
                "Error while creating indexer from definition %s",
                definition.id,
            )
            return None
