"""Indexers that fan a query out to other configured indexers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.indexer_config import ConfigurationData
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.services.indexers.base import BaseIndexer, ConfigurationStatus
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.meta.imdb import ImdbSupport
from pyjackett.services.indexers.result import IndexerResult

logger = logging.getLogger(__name__)

MEMBER_TIMEOUT_SECONDS = 40
META_LIMIT = 1000  # workaround until proper paging is supported
LOCAL_SITE_LINK = "http://127.0.0.1/"

Predicate = Callable[[BaseIndexer], bool]


class BaseMetaIndexer(BaseIndexer):
    """Queries every valid member indexer in parallel and merges results."""

    default_site_link = LOCAL_SITE_LINK
    caches_results = False
    limits_concurrency = False  # its members take the slots

    def __init__(
        self,
        dependencies: IndexerDependencies,
        imdb: ImdbSupport,
        member_filter: Predicate,
        indexers: Iterable[BaseIndexer],
    ) -> None:
        super().__init__(dependencies, ConfigurationData())
        self._imdb = imdb
        self._member_filter = member_filter
        self.indexers = indexers  # a live view of every known indexer
        self.site_link = LOCAL_SITE_LINK

    # ---- members ------------------------------------------------------------

    @property
    def valid_indexers(self) -> list[BaseIndexer]:
        return [
            indexer
            for indexer in self.indexers
            if indexer.is_configured and self._member_filter(indexer)
        ]

    @property
    def is_meta(self) -> bool:
        return True

    def members(self) -> list[BaseIndexer]:
        return self.valid_indexers

    # ---- derived state ------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def torznab_caps(self) -> TorznabCapabilities:
        merged = TorznabCapabilities()
        for indexer in self.valid_indexers:
            merged.merge(indexer.torznab_caps)
        merged.limits_default = merged.limits_max = META_LIMIT
        return merged

    def unconfigure(self) -> None:
        """Derived from its members: nothing to reset."""

    def reset_base_config(self) -> None:
        """Derived from its members: nothing to reset."""

    def can_handle_query(self, query: TorznabQuery | None) -> bool:
        if query is not None and query.query_type == "indexers":
            return True
        return super().can_handle_query(query)

    async def apply_configuration(self, config) -> ConfigurationStatus:
        return ConfigurationStatus.COMPLETED

    # ---- searching ----------------------------------------------------------

    def _post_process(self, query: TorznabQuery, releases: list[ReleaseInfo]) -> list[ReleaseInfo]:
        """Members already cleaned their own results."""
        return releases

    def _record_outcome(self, query: TorznabQuery, releases: list[ReleaseInfo]) -> None:
        """Members cache their results and track their own health."""

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        results = await self._query_members(query)
        releases = [r for result in results for r in result.releases]
        releases = await self._imdb.filter_results(query, releases)
        releases.sort(key=lambda release: release.gain, reverse=True)
        return releases[: query.limit] if query.limit > 0 else releases

    def _searchable_members(self) -> list[BaseIndexer]:
        """Members worth asking: failing ones wait out their back-off."""
        members = self.valid_indexers
        if not self._deps.skip_failing:
            return members
        working = [m for m in members if not m.is_failing]
        if len(working) < len(members):
            logger.info("Skipping %d failing indexers", len(members) - len(working))
        return working

    async def _query_members(self, query: TorznabQuery):
        members = self._searchable_members()
        searches = [m.results_for_query(query, True) for m in members if m.can_handle_query(query)]
        for fallback in await self._imdb.fallback_queries(query):
            searches += [
                m.results_for_query(fallback, True)
                for m in members
                if not m.can_handle_query(query) and m.can_handle_query(fallback)
            ]
        return await self._gather_within_timeout(searches)

    async def _gather_within_timeout(self, searches) -> list[IndexerResult]:
        """Results of the searches that finished before the deadline.

        Searches still waiting for a slot at the deadline are dropped, so
        a loaded server answers with partial results instead of piling up.
        """
        tasks = [asyncio.ensure_future(search) for search in searches]
        if not tasks:
            return []
        done, pending = await asyncio.wait(tasks, timeout=MEMBER_TIMEOUT_SECONDS)
        for task in pending:
            task.cancel()
        results = []
        for task in done:
            if task.exception() is not None:
                logger.error(
                    "Error during request in metaindexer %s: %s",
                    self.id,
                    task.exception(),
                )
            else:
                results.append(task.result())
        return results


class AggregateIndexer(BaseMetaIndexer):
    """The "all" indexer: every configured indexer."""

    id = "all"
    name = "AggregateSearch"
    description = "This feed includes all configured trackers"

    def __init__(
        self,
        dependencies: IndexerDependencies,
        imdb: ImdbSupport,
        indexers: Iterable[BaseIndexer],
    ) -> None:
        super().__init__(dependencies, imdb, lambda _: True, indexers)


class FilterIndexer(BaseMetaIndexer):
    """A group of indexers selected by a filter expression."""

    def __init__(
        self,
        filter_text: str,
        dependencies: IndexerDependencies,
        imdb: ImdbSupport,
        member_filter: Predicate,
        indexers: Iterable[BaseIndexer],
    ) -> None:
        super().__init__(dependencies, imdb, member_filter, indexers)
        self.id = filter_text
        self.name = filter_text
        self.description = f"This feed includes all configured trackers filter by {filter_text}"

    @property
    def is_configured(self) -> bool:
        return bool(self.valid_indexers)
