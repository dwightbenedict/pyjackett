"""An indexer driven entirely by a Cardigann YAML definition."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from pyjackett.cardigann.caps_builder import build_capabilities
from pyjackett.cardigann.config_form import build_configuration
from pyjackett.cardigann.definition import (
    IndexerDefinition,
    LoginBlock,
    SearchBlock,
    SearchPathBlock,
    SettingsField,
)
from pyjackett.cardigann.download import CardigannDownload
from pyjackett.cardigann.filters import FilterContext
from pyjackett.cardigann.login import CardigannLogin
from pyjackett.cardigann.methods import LoginMethod
from pyjackett.cardigann.search import CardigannSearch
from pyjackett.cardigann.template import Variables
from pyjackett.cardigann.variables import base_variables
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.http.models import lookup_encoding
from pyjackett.indexers.base import ConfigurationStatus
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.web import BaseWebIndexer
from pyjackett.utils.urls import resolve_url, url_host

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "UTF-8"
DEFAULT_LOGIN_METHOD = LoginMethod.FORM


def _with_defaults(definition: IndexerDefinition) -> IndexerDefinition:
    """A copy of ``definition`` with the optional parts the engine needs."""
    settings = definition.settings
    if settings is None:
        settings = [
            SettingsField(name="username", label="Username", type="text"),
            SettingsField(name="password", label="Password", type="password"),
        ]
    return replace(
        definition,
        settings=settings,
        encoding=definition.encoding or DEFAULT_ENCODING,
        login=_login_with_defaults(definition.login),
        search=_search_with_defaults(definition.search),
    )


def _login_with_defaults(login: LoginBlock | None) -> LoginBlock | None:
    if login is None or login.method is not None:
        return login
    return replace(login, method=DEFAULT_LOGIN_METHOD)


def _search_with_defaults(search: SearchBlock) -> SearchBlock:
    """A lone ``search.path`` is just a one entry ``paths`` list."""
    paths = list(search.paths or [])
    if search.path is not None:
        paths.append(SearchPathBlock(path=search.path))
    return replace(search, paths=paths)


def _site_link(link: str) -> str:
    return link if link.endswith("/") else link + "/"


class CardigannIndexer(BaseWebIndexer):
    """Searches, logs in and downloads as the definition describes."""

    def __init__(
        self, dependencies: IndexerDependencies, definition: IndexerDefinition
    ) -> None:
        self.definition = _with_defaults(definition)
        self.id = definition.id
        self.name = definition.name
        self.description = definition.description or ""
        self.type = definition.type
        self.language = definition.language or "en-US"
        self.replaces = tuple(definition.replaces)
        self.encoding = lookup_encoding(definition.encoding)
        if self.encoding is None:
            raise LookupError(f"unknown encoding: {definition.encoding}")
        self.default_site_link = _site_link(definition.links[0])
        if len(definition.links) > 1:
            self.alternative_site_links = tuple(definition.links)
        self.legacy_site_links = tuple(definition.legacylinks or ())
        super().__init__(dependencies, build_configuration(definition))
        if definition.request_delay is not None:
            self.client.set_request_delay(definition.request_delay)
        self.torznab_caps, default_categories = build_capabilities(
            definition.caps, self.id
        )
        self._login = CardigannLogin(self)
        self._search = CardigannSearch(
            self, self._login, self.torznab_caps, default_categories
        )
        self._download = CardigannDownload(self, self.download_with)
        self.load_values_from_json(None)

    # ---- CardigannHost interface --------------------------------------------

    def base_variables(self) -> Variables:
        return base_variables(
            self.site_link, self.definition.settings, self.config_data
        )

    def filter_context(self, variables: Variables) -> FilterContext:
        return FilterContext(self.id, self.encoding, variables)

    def resolve_path(self, path: str, current_url: str | None = None) -> str:
        return resolve_url(path, current_url or self.site_link)

    def set_site_link(self, link: str) -> None:
        self.config_data.site_link.value = link
        self.site_link = link
        self.config_changed()

    # ---- configuration ------------------------------------------------------

    def load_values_from_json(
        self, stored: list[dict[str, Any]] | None, use_protection=False
    ) -> None:
        super().load_values_from_json(stored, use_protection)
        host = url_host(self.site_link)
        for fingerprint in self.definition.certificates or []:
            self._deps.trusted_certificates.add(host, fingerprint)

    async def get_configuration_for_setup(self):
        try:
            return await self._login.get_configuration_for_setup(False)
        except Exception:
            logger.exception(
                "Exception in get_configuration_for_setup (%s)", self.id
            )
            return self.config_data

    async def apply_configuration(
        self, config: list[dict[str, Any]]
    ) -> ConfigurationStatus:
        self.load_values_from_json(config)
        await self._login.do_login()
        await self._login.test_login()
        self.is_configured = True
        self.config_changed()
        return ConfigurationStatus.COMPLETED

    # ---- searching and downloading ------------------------------------------

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        return await self._search.perform_query(query)

    async def download(self, link: str) -> bytes:
        return await self._download.download(self.unclean_link(link))
