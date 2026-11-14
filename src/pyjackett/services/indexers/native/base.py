"""Shared behaviour of indexers written in Python instead of YAML."""

from __future__ import annotations

from typing import Any

from pyjackett.domain.query import TorznabQuery
from pyjackett.services.indexers.base import ConfigurationStatus
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.web import BaseWebIndexer


class NativeIndexer(BaseWebIndexer):
    """Subclasses set the class attributes and implement ``perform_query``.

    ``default_site_link`` must end with a slash. Capabilities are filled in
    by overriding :meth:`build_capabilities` and the configuration form by
    overriding :meth:`build_configuration`. ``request_delay`` is the minimum
    number of seconds between two requests.
    """

    request_delay: float = 0.0
    limits_default: int | None = None
    limits_max: int | None = None

    def __init__(self, dependencies: IndexerDependencies) -> None:
        super().__init__(dependencies)
        if self.request_delay:
            self.client.set_request_delay(self.request_delay)
        if self.limits_default is not None:
            self.torznab_caps.limits_default = self.limits_default
            self.torznab_caps.limits_max = self.limits_max
        self.build_capabilities()
        self.build_configuration()
        self.load_values_from_json(None)

    def build_capabilities(self) -> None:
        """Populate ``self.torznab_caps``."""

    def build_configuration(self) -> None:
        """Add the indexer specific items to ``self.config_data``."""

    async def apply_configuration(
        self, config: list[dict[str, Any]]
    ) -> ConfigurationStatus:
        """Accept the configuration if a test search returns releases."""
        self.load_values_from_json(config)
        await self.authenticate()
        releases = await self.perform_query(TorznabQuery(query_type="search"))
        if not releases:
            raise RuntimeError("Error: 0 results found!")
        self.is_configured = True
        self.config_changed()
        return ConfigurationStatus.COMPLETED

    async def authenticate(self) -> None:
        """Log in before the configuration test; most indexers need none."""
