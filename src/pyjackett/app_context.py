"""Composition root: builds and wires every long-lived service."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

from pyjackett.config.indexer_config_store import IndexerConfigStore
from pyjackett.config.paths import BUNDLED_DEFINITIONS_DIR, resolve_data_dir
from pyjackett.config.protection import KEY_ENV, ProtectionService
from pyjackett.config.server_config import ServerConfig
from pyjackett.config.server_config_store import ServerConfigStore
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.client import WebClient
from pyjackett.http.session import HttpSession
from pyjackett.indexers.configuration import IndexerConfigurationService
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.manager import IndexerManager
from pyjackett.indexers.meta.factory import MetaIndexerFactory
from pyjackett.indexers.registry import IndexerRegistry
from pyjackett.indexers.sources import CardigannSource, NativeSource
from pyjackett.services.cache import ResultsCache
from pyjackett.services.log_cache import LogCache
from pyjackett.services.security import SecurityService
from pyjackett.services.server_service import ServerService
from pyjackett.utils.clock import SYSTEM_CLOCK, Clock

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
    clock: Clock = SYSTEM_CLOCK

    def save_config(self) -> None:
        self.config_store.save(self.config)

    async def close(self) -> None:
        await self.http_session.aclose()


def build_context(
    data_dir: str | Path | None = None,
    extra_definition_dirs: list[Path] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    include_bundled: bool = True,
    environ: Mapping[str, str] = os.environ,
    clock: Clock = SYSTEM_CLOCK,
) -> AppContext:
    """Create all services; ``transport`` lets tests fake the network."""
    data_path = resolve_data_dir(data_dir, environ)
    data_path.mkdir(parents=True, exist_ok=True)
    config_store = ServerConfigStore(data_path)
    config = config_store.load()
    protector = ProtectionService.for_data_dir(data_path, environ.get(KEY_ENV))
    certificates = TrustedCertificates()
    session = HttpSession(config, certificates, transport)
    cache = ResultsCache(config, clock)
    config_service = IndexerConfigurationService(
        IndexerConfigStore(data_path), protector
    )
    dependencies = IndexerDependencies(
        protector=protector,
        cache=cache,
        client_factory=lambda: WebClient(session, clock),
        trusted_certificates=certificates,
        clock=clock,
    )
    definition_dirs = [data_path / "Definitions"]
    if include_bundled:
        definition_dirs.insert(0, BUNDLED_DEFINITIONS_DIR)
    definition_dirs += extra_definition_dirs or []
    registry = IndexerRegistry()
    manager = IndexerManager(
        dependencies,
        config_service,
        [NativeSource(), CardigannSource(definition_dirs)],
        registry,
        MetaIndexerFactory(dependencies, config, registry.values()),
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
        security=SecurityService(config, clock),
        log_cache=LogCache(),
        clock=clock,
    )
