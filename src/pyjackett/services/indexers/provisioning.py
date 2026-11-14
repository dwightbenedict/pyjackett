"""Configures the indexers that need no credentials."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from pyjackett.services.indexers.base import BaseIndexer

logger = logging.getLogger(__name__)

PUBLIC_TYPE = "public"


class PublicIndexerProvisioner:
    """Marks every public indexer as configured with its default values.

    Public trackers have nothing to log in to, so no test search is run;
    a failing tracker shows up through its health instead.
    """

    def __init__(
        self,
        enabled: bool = True,
        only: frozenset[str] | None = None,
    ) -> None:
        self._enabled = enabled
        self._only = only  # ids to configure at startup; None means all

    def provision(self, indexers: Iterable[BaseIndexer]) -> int:
        """Configure the unconfigured public ones; returns how many.

        With an ``only`` list, just those: every configured indexer is one
        more site each search has to ask, which a small host cannot afford.
        """
        if not self._enabled:
            return 0
        candidates = list(indexers)
        self._warn_about_unknown(candidates)
        pending = [i for i in candidates if self._is_wanted(i) and self._needs_provisioning(i)]
        for indexer in pending:
            self._configure(indexer)
        logger.info("Configured %d public indexers", len(pending))
        return len(pending)

    def _is_wanted(self, indexer: BaseIndexer) -> bool:
        return self._only is None or indexer.id in self._only

    def _warn_about_unknown(self, indexers: list[BaseIndexer]) -> None:
        if self._only is None:
            return
        public = {i.id for i in indexers if i.type == PUBLIC_TYPE}
        unknown = sorted(self._only - public)
        if unknown:
            logger.warning(
                "Not configured (unknown or not public): %s",
                ", ".join(unknown),
            )

    def provision_one(self, indexer: BaseIndexer) -> bool:
        """Configure one public indexer on request; False if it can't be."""
        if not self._needs_provisioning(indexer):
            return False
        self._configure(indexer)
        return True

    @staticmethod
    def _configure(indexer: BaseIndexer) -> None:
        indexer.is_configured = True
        indexer.config_changed()  # persists the default configuration

    @staticmethod
    def _needs_provisioning(indexer: BaseIndexer) -> bool:
        return indexer.type == PUBLIC_TYPE and not indexer.is_meta and not indexer.is_configured
