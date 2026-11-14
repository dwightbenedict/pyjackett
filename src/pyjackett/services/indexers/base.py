"""Base class of every indexer (native, Cardigann or meta)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.indexer_config import ConfigurationData
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.text import is_blank
from pyjackett.errors import (
    IndexerError,
    IndexerRateLimitedError,
    IndexerTestFailedError,
    TooManyRequestsError,
)
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.health import IndexerHealth
from pyjackett.services.indexers.query_support import (
    can_handle_categories,
    can_handle_query,
)
from pyjackett.services.indexers.result import IndexerResult
from pyjackett.services.indexers.result_processing import (
    deduplicate_by_guid,
    filter_results,
    fix_results,
)
from pyjackett.services.ports import Clock
from pyjackett.services.stopwatch import Stopwatch

logger = logging.getLogger(__name__)

HEALTHY_VALIDITY_FACTOR = 2  # healthy for two cache lifetimes


class ConfigurationStatus(StrEnum):
    COMPLETED = "completed"
    REQUIRES_TESTING = "requires_testing"


class BaseIndexer(ABC):
    """Identity, configuration, health and the common search pipeline."""

    id: str = ""
    name: str = ""
    description: str = ""
    type: str | None = None
    language: str = "en-US"
    encoding: str = "utf-8"
    replaces: tuple[str, ...] = ()
    default_site_link: str = ""
    alternative_site_links: tuple[str, ...] = ()
    legacy_site_links: tuple[str, ...] = ()
    supports_pagination: bool = False
    caches_results: bool = True  # meta indexers leave this to their members
    limits_concurrency = True  # meta indexers only wait for their members

    def __init__(
        self,
        dependencies: IndexerDependencies,
        config_data: ConfigurationData | None = None,
    ) -> None:
        self._deps = dependencies
        self._clock: Clock = dependencies.clock
        self.config_data = config_data or ConfigurationData()
        self._torznab_caps = TorznabCapabilities()
        self.health = IndexerHealth(self._clock.monotonic)
        self.site_link = self.default_site_link
        self.tags: list[str] = []
        self._is_configured = False
        self._config_listeners: list[Callable[[BaseIndexer], None]] = []

    # ---- state --------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    @is_configured.setter
    def is_configured(self, value: bool) -> None:
        self._is_configured = value

    @property
    def torznab_caps(self) -> TorznabCapabilities:
        return self._torznab_caps

    @torznab_caps.setter
    def torznab_caps(self, value: TorznabCapabilities) -> None:
        self._torznab_caps = value

    @property
    def is_meta(self) -> bool:
        """True for indexers that only forward queries to other indexers."""
        return False

    def members(self) -> list[BaseIndexer]:
        """The configured indexers a query to this one is answered by."""
        return [self]

    # ---- configuration ------------------------------------------------------

    @property
    def cookie_header(self) -> str | None:
        return self.config_data.cookie_header.value

    @cookie_header.setter
    def cookie_header(self, value: str | None) -> None:
        self.config_data.cookie_header.value = value

    @property
    def last_error(self) -> str | None:
        return self.config_data.last_error.value

    @last_error.setter
    def last_error(self, value: str | None) -> None:
        changed = self.config_data.last_error.value != value
        self.config_data.last_error.value = value
        if changed and self.is_configured:
            self.config_changed()

    async def get_configuration_for_setup(self) -> ConfigurationData:
        return self.config_data

    def load_values_from_json(
        self, stored: list[dict[str, Any]] | None, use_protection=False
    ) -> None:
        """Copy saved values into the form and normalise the site link."""
        protector = self._deps.protector if use_protection else None
        self.config_data.load_values(stored, protector)
        link = self.config_data.site_link
        if is_blank(link.value):
            link.value = self.default_site_link
        if not link.value.endswith("/"):
            link.value += "/"
        if link.value in self.legacy_site_links:
            logger.debug(
                "changing legacy site link from %s to %s",
                link.value,
                self.default_site_link,
            )
            link.value = self.default_site_link
        self.site_link = link.value
        self.tags = [tag.lower() for tag in self.config_data.tags.values]

    def load_from_saved_configuration(self, stored: Any) -> None:
        if isinstance(stored, list):
            self.load_values_from_json(stored, use_protection=True)
            self.is_configured = True
        else:
            logger.warning(
                "Configuration of %s is in an old format; configure it again",
                self.id,
            )

    def subscribe_config_changes(self, listener: Callable[[BaseIndexer], None]) -> None:
        """Call ``listener(self)`` whenever the configuration changes."""
        self._config_listeners.append(listener)

    def config_changed(self) -> None:
        """Tell the subscribers (who persist it) to pick up the change."""
        for listener in self._config_listeners:
            listener(self)

    def reset_base_config(self) -> None:
        self.cookie_header = ""
        self.is_configured = False
        self.health.reset()

    def unconfigure(self) -> None:
        self.is_configured = False
        self.site_link = self.default_site_link
        self.cookie_header = ""

    def same_definition_as(self, other: BaseIndexer) -> bool:
        """Whether ``other`` behaves like this one (no reload needed)."""
        return True

    @abstractmethod
    async def apply_configuration(self, config: list[dict[str, Any]]) -> ConfigurationStatus:
        """Validate posted form values (usually logs in) and save them."""

    # ---- health -------------------------------------------------------------

    @property
    def is_healthy(self) -> bool:
        return self.health.is_healthy

    @property
    def is_failing(self) -> bool:
        return self.health.is_failing

    def _healthy_validity_seconds(self) -> float:
        ttl = self._deps.cache.ttl.total_seconds()
        return ttl * HEALTHY_VALIDITY_FACTOR

    # ---- searching ----------------------------------------------------------

    def can_handle_query(self, query: TorznabQuery | None) -> bool:
        return can_handle_query(self.torznab_caps, query)

    @abstractmethod
    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        """Fetch raw releases from the tracker."""

    async def results_for_query(
        self, query: TorznabQuery, is_meta_indexer: bool = False
    ) -> IndexerResult:
        """Run a search through cache, tracker, filtering and clean-up."""
        query = query.clone()  # indexers may modify the query
        if not self._accepts(query, is_meta_indexer):
            logger.debug(
                "%s skipped query %r: not supported",
                self.name,
                query.query_string(),
            )
            return IndexerResult(self)
        cached = self._cached_result(query)
        if cached is not None:
            logger.info(
                "%s served %d cached releases for %r",
                self.name,
                len(cached.releases),
                query.query_string(),
            )
            self._deps.stats.record_cache_hit(self.id, query.query_string(), len(cached.releases))
            return cached
        return await self._deps.single_flight.run(
            f"{self.id}:{query.cache_key()}",
            lambda: self._search_once(query),
            self._copy_of,
        )

    async def _search_once(self, query: TorznabQuery) -> IndexerResult:
        """Search the tracker; failures are recorded once per search, not
        once per client waiting for it."""
        try:
            return await self._search_in_slot(query)
        except TooManyRequestsError as error:
            self.health.record_rate_limit(error.retry_after.total_seconds())
            self._record_failure(query, error, rate_limited=True)
            raise IndexerRateLimitedError(self, error) from error
        except Exception as error:
            self.health.record_failure()
            self._record_failure(query, error, rate_limited=False)
            raise IndexerError(self, error) from error

    async def _search_in_slot(self, query: TorznabQuery) -> IndexerResult:
        if not self.limits_concurrency:
            return await self._search_tracker(query)
        async with self._deps.search_limit.slot():
            return await self._search_tracker(query)

    @staticmethod
    def _copy_of(result: IndexerResult) -> IndexerResult:
        """What a client that shared a search gets, free to be changed."""
        return IndexerResult(
            result.indexer,
            [release.clone() for release in result.releases],
            result.elapsed_ms,
            result.is_from_cache,
        )

    async def verify(self) -> None:
        """Run a blank search; fails when the tracker returns nothing."""
        query = TorznabQuery(query_type="search", search_term="", is_test=True)
        result = await self.results_for_query(query)
        logger.info(
            "Test search in %s => Found %d releases [%dms]",
            self.name,
            len(result.releases),
            result.elapsed_ms,
        )
        if not result.releases:
            raise IndexerTestFailedError(
                "No results. Check the indexer settings, e.g. freeleech only.",
                result.elapsed_ms,
            )

    # ---- steps subclasses may specialise ------------------------------------

    def _accepts(self, query: TorznabQuery, is_meta_indexer: bool) -> bool:
        if not self.can_handle_query(query):
            return False
        if not can_handle_categories(
            self.torznab_caps,
            query,
            self.name,
            is_meta_indexer or self.is_meta,
        ):
            return False
        return self.supports_pagination or query.offset <= 0

    def _cached_result(self, query: TorznabQuery) -> IndexerResult | None:
        if not self.caches_results or not query.cache:
            return None
        releases = self._deps.cache.search(self, query)
        if releases is None:
            return None
        return IndexerResult(self, releases, 0, True)

    async def _search_tracker(self, query: TorznabQuery) -> IndexerResult:
        logger.info("%s searching for %r", self.name, query.query_string())
        stopwatch = Stopwatch(self._clock)
        releases = await self.perform_query(query)
        elapsed_ms = stopwatch.elapsed_ms
        raw_count = len(releases)
        releases = self._post_process(query, releases)
        logger.info(
            "%s found %d releases (%d before filtering) in %dms",
            self.name,
            len(releases),
            raw_count,
            elapsed_ms,
        )
        self._record_outcome(query, releases)
        self._deps.stats.record_success(self.id, query.query_string(), len(releases), elapsed_ms)
        return IndexerResult(self, releases, elapsed_ms, False)

    def _record_failure(self, query: TorznabQuery, error: Exception, rate_limited: bool) -> None:
        if rate_limited:
            logger.warning("%s was rate limited: %s", self.name, error)
        else:
            logger.error(
                "%s search for %r failed: %s",
                self.name,
                query.query_string(),
                error,
            )
        self._deps.stats.record_failure(self.id, query.query_string(), str(error), rate_limited)

    def _record_outcome(self, query: TorznabQuery, releases: list[ReleaseInfo]) -> None:
        """Remember a successful search: cache it and mark us healthy."""
        self._deps.cache.cache_results(self, query, releases)
        self.health.record_success(self._healthy_validity_seconds())

    def _post_process(self, query: TorznabQuery, releases: list[ReleaseInfo]) -> list[ReleaseInfo]:
        """Validate and normalise what the tracker returned."""
        releases = filter_results(releases, query, self.torznab_caps, self.id)
        return deduplicate_by_guid(fix_results(releases, self, self._clock.now()))
