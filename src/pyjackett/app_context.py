"""Composition root: builds and wires every long-lived service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from pyjackett.config.indexer_config_store import IndexerConfigStore
from pyjackett.config.paths import BUNDLED_DEFINITIONS_DIR, resolve_data_dir
from pyjackett.config.protection import ProtectionService
from pyjackett.config.server_config import ServerConfig
from pyjackett.config.server_config_store import ServerConfigStore
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.client import WebClient
from pyjackett.http.session import HttpSession
from pyjackett.indexers.configuration import IndexerConfigurationService
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.manager import IndexerManager
from pyjackett.services.cache import ResultsCache
from pyjackett.services.log_cache import LogCache
from pyjackett.services.security import SecurityService
from pyjackett.services.server_service import ServerService

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Everything the web layer and the CLI need."""

    data_dir: Path
    config: ServerConfig
    config_store: ServerConfigStore
    protector: ProtectionService
    http_session: HttpSession
    cache: ResultsCache
    indexers: IndexerManager
    server_service: ServerService
    security: SecurityService
    log_cache: LogCache

    def save_config(self) -> None:
        self.config_store.save(self.config)

    async def close(self) -> None:
        await self.http_session.aclose()


def _attach_log_cache() -> LogCache:
    log_cache = LogCache()
    logging.getLogger("pyjackett").addHandler(log_cache)
    return log_cache


def build_context(
    data_dir: str | Path | None = None,
    extra_definition_dirs: list[Path] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    include_bundled: bool = True,
) -> AppContext:
    """Create all services; ``transport`` lets tests fake the network."""
    data_path = resolve_data_dir(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    config_store = ServerConfigStore(data_path)
    config = config_store.load()
    protector = ProtectionService.for_data_dir(data_path)
    certificates = TrustedCertificates()
    session = HttpSession(config, certificates, transport)
    cache = ResultsCache(config)
    config_service = IndexerConfigurationService(
        IndexerConfigStore(data_path), protector
    )
    dependencies = IndexerDependencies(
        protector=protector,
        cache=cache,
        client_factory=lambda: WebClient(session),
        trusted_certificates=certificates,
    )
    definition_dirs = [data_path / "Definitions"]
    if include_bundled:
        definition_dirs.insert(0, BUNDLED_DEFINITIONS_DIR)
    definition_dirs += extra_definition_dirs or []
    manager = IndexerManager(
        dependencies, config_service, config, definition_dirs
    )
    return AppContext(
        data_dir=data_path,
        config=config,
        config_store=config_store,
        protector=protector,
        http_session=session,
        cache=cache,
        indexers=manager,
        server_service=ServerService(config, protector),
        security=SecurityService(config),
        log_cache=_attach_log_cache(),
    )
