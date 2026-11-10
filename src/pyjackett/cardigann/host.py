"""What the login/search/download helpers need from the indexer."""

from __future__ import annotations

from typing import Protocol

from pyjackett.cardigann.definition import IndexerDefinition
from pyjackett.cardigann.filters import FilterContext
from pyjackett.cardigann.template import Variables
from pyjackett.config.indexer_config import ConfigurationData
from pyjackett.indexers.requester import WebRequester


class CardigannHost(Protocol):
    id: str
    definition: IndexerDefinition
    config_data: ConfigurationData
    requester: WebRequester
    site_link: str
    encoding: str
    is_configured: bool
    cookie_header: str | None

    def base_variables(self) -> Variables:
        """Protocol method."""

    def filter_context(self, variables: Variables) -> FilterContext:
        """Protocol method."""

    def resolve_path(self, path: str, current_url: str | None = None) -> str:
        """Protocol method."""

    def config_changed(self) -> None:
        """Protocol method."""

    def set_site_link(self, link: str) -> None:
        """Protocol method."""
