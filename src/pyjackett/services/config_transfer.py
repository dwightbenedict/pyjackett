"""Exports and imports the server settings and indexer configurations."""

from __future__ import annotations

import logging
from typing import Any

from pyjackett import __version__
from pyjackett.adapters.server_config_store import ServerConfigStore
from pyjackett.domain.server_config import JSON_KEYS, ServerConfig
from pyjackett.errors import ConfigBundleError
from pyjackett.services.cache import ResultsCache
from pyjackett.services.indexers.manager import (
    IndexerManager,
    UnknownIndexerError,
)

logger = logging.getLogger(__name__)

BUNDLE_FORMAT = "pyjackett-config"
BUNDLE_VERSION = 1
# identity and credentials of this installation never travel in a bundle
EXCLUDED_ATTRIBUTES = frozenset(
    {"api_key", "admin_password", "admin_username", "instance_id"}
)
NETWORK_ATTRIBUTES = (
    "port",
    "allow_external",
    "local_bind_address",
    "allow_cors",
    "base_path_override",
)


class ConfigTransfer:
    """Moves a configuration between installations as one JSON document.

    The bundle holds indexer passwords in clear text, so it is only handed
    to callers that are logged in to the dashboard.
    """

    def __init__(
        self,
        config: ServerConfig,
        config_store: ServerConfigStore,
        indexers: IndexerManager,
        cache: ResultsCache,
    ) -> None:
        self._config = config
        self._store = config_store
        self._indexers = indexers
        self._cache = cache

    # ---- export -------------------------------------------------------------

    def export_bundle(self) -> dict[str, Any]:
        return {
            "format": BUNDLE_FORMAT,
            "version": BUNDLE_VERSION,
            "app_version": __version__,
            "server": self._exported_server(),
            "indexers": self._exported_indexers(),
        }

    def _exported_server(self) -> dict[str, Any]:
        data = self._config.to_json()
        return {
            key: data[key]
            for attribute, key in JSON_KEYS.items()
            if attribute not in EXCLUDED_ATTRIBUTES
        }

    def _exported_indexers(self) -> dict[str, list[dict[str, Any]]]:
        return {
            indexer.id: indexer.config_data.to_json(None, for_display=False)
            for indexer in self._indexers.all_indexers()
            if indexer.is_configured and not indexer.is_meta
        }

    # ---- import -------------------------------------------------------------

    def import_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Apply ``bundle``; reports what was imported and what was not."""
        self._check_format(bundle)
        restart = self._import_server(bundle.get("server") or {})
        imported, skipped = self._import_indexers(bundle.get("indexers") or {})
        self._indexers.init_meta_indexers()
        self._config.notify_changed()
        return {
            "imported": imported,
            "skipped": skipped,
            "restart_required": restart,
        }

    @staticmethod
    def _check_format(bundle: dict[str, Any]) -> None:
        if bundle.get("format") != BUNDLE_FORMAT:
            raise ConfigBundleError("Not a PyJackett configuration bundle")
        if bundle.get("version") != BUNDLE_VERSION:
            raise ConfigBundleError(
                f"Unsupported bundle version: {bundle.get('version')}"
            )

    def _import_server(self, section: dict[str, Any]) -> bool:
        """Copy the settings of ``section``; True if a restart is needed."""
        accepted = {
            attribute: key
            for attribute, key in JSON_KEYS.items()
            if attribute not in EXCLUDED_ATTRIBUTES and key in section
        }
        if not accepted:
            return False
        posted = {key: section[key] for key in accepted.values()}
        merged = ServerConfig.from_json({**self._config.to_json(), **posted})
        before = self._network_state()
        for attribute in accepted:
            setattr(self._config, attribute, getattr(merged, attribute))
        self._store.save(self._config)
        return self._network_state() != before

    def _network_state(self) -> tuple:
        return tuple(getattr(self._config, a) for a in NETWORK_ATTRIBUTES)

    def _import_indexers(
        self, section: dict[str, list[dict[str, Any]]]
    ) -> tuple[list[str], list[str]]:
        imported: list[str] = []
        skipped: list[str] = []
        for indexer_id, values in section.items():
            if self._import_indexer(indexer_id, values):
                imported.append(indexer_id)
            else:
                skipped.append(indexer_id)
        return imported, skipped

    def _import_indexer(self, indexer_id: str, values: Any) -> bool:
        try:
            indexer = self._indexers.get_indexer(indexer_id)
        except UnknownIndexerError:
            return False
        if indexer.is_meta or not isinstance(values, list):
            return False
        indexer.load_values_from_json(values)
        indexer.is_configured = True
        self._cache.clean_indexer_cache(indexer)
        indexer.config_changed()  # persists (and encrypts) the values
        return True
