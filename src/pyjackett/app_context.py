"""Composition root: builds and wires every long-lived service."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from curl_cffi.requests import AsyncSession

from pyjackett.cardigann.definition_cache import DefinitionCache
from pyjackett.config.environment import (
    DEFINITION_CACHE_ENV,
    MAX_CONCURRENCY_ENV,
    MAX_ROWS_ENV,
    RETRIES_ENV,
    apply_credentials,
    cache_limit_from,
    non_negative_int,
    positive_int,
    public_indexers_from,
    skip_failing_from,
)
from pyjackett.config.indexer_config_store import IndexerConfigStore
from pyjackett.config.paths import (
    BUNDLED_DEFINITIONS_DIR,
    DEFINITION_CACHE_FILE,
    resolve_data_dir,
)
from pyjackett.config.protection import KEY_ENV, ProtectionService
from pyjackett.config.server_config import ServerConfig
from pyjackett.config.server_config_store import (
    ServerConfigStore,
    generate_api_key,
)
from pyjackett.definition_sync.feed import GitHubDefinitionFeed
from pyjackett.definition_sync.store import DefinitionStore
from pyjackett.definition_sync.task import DefinitionSyncTask
from pyjackett.definition_sync.updater import DefinitionUpdater
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.client import WebClient
from pyjackett.http.session import HttpSession, impersonation_from
from pyjackett.indexers.bulk import BulkIndexerOperations
from pyjackett.indexers.configuration import IndexerConfigurationService
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.manager import IndexerManager
from pyjackett.indexers.meta.factory import MetaIndexerFactory
from pyjackett.indexers.provisioning import PublicIndexerProvisioner
from pyjackett.indexers.registry import IndexerRegistry
from pyjackett.indexers.search_limit import SearchLimit
from pyjackett.indexers.sources import CardigannSource, NativeSource
from pyjackett.indexers.test_runner import IndexerTestRunner
from pyjackett.services.cache import ResultsCache
from pyjackett.services.config_transfer import ConfigTransfer
from pyjackett.services.log_cache import LogCache
from pyjackett.services.security import SecurityService
from pyjackett.services.server_service import ServerService
from pyjackett.services.stats import SearchRecorder
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
    stats: SearchRecorder
    test_runner: IndexerTestRunner
    bulk: BulkIndexerOperations
    config_transfer: ConfigTransfer
    clock: Clock = SYSTEM_CLOCK
    definition_sync: DefinitionSyncTask | None = None

    def save_config(self) -> None:
        self.config_store.save(self.config)

    async def close(self) -> None:
        await self.test_runner.close()
        await self.http_session.aclose()


def build_context(
    data_dir: str | Path | None = None,
    extra_definition_dirs: list[Path] | None = None,
    client_factory: Callable[..., AsyncSession] = AsyncSession,
    include_bundled: bool = True,
    environ: Mapping[str, str] = os.environ,
    clock: Clock = SYSTEM_CLOCK,
    configure_public: bool = False,
    sync_definitions: bool = False,
    default_public: frozenset[str] | None = None,
) -> AppContext:
    """Create all services; ``client_factory`` lets tests fake the network.

    ``configure_public`` makes startup configure the public indexers
    (``default_public``, unless ``PYJACKETT_INDEXERS`` says otherwise;
    None means every one of them);
    ``sync_definitions`` keeps the definitions up to date from upstream.
    """
    data_path = resolve_data_dir(data_dir, environ)
    data_path.mkdir(parents=True, exist_ok=True)
    config_store = ServerConfigStore(data_path)
    config = config_store.load()
    security = SecurityService(config, clock, generate_api_key)
    changed = apply_credentials(config, security, environ)
    if security.ensure_default_credentials() or changed:
        config_store.save(config)
    protector = ProtectionService.for_data_dir(data_path, environ.get(KEY_ENV))
    certificates = TrustedCertificates()
    session = HttpSession(
        config,
        certificates,
        client_factory=client_factory,
        impersonate=impersonation_from(environ),
    )
    cache = ResultsCache(config, clock, cache_limit_from(environ))
    stats = SearchRecorder(clock)
    config_service = IndexerConfigurationService(
        IndexerConfigStore(data_path), protector
    )
    dependencies = IndexerDependencies(
        protector=protector,
        cache=cache,
        client_factory=lambda: WebClient(session, clock),
        trusted_certificates=certificates,
        clock=clock,
        stats=stats,
        search_limit=SearchLimit(positive_int(environ, MAX_CONCURRENCY_ENV)),
        max_rows=positive_int(environ, MAX_ROWS_ENV),
        skip_failing=skip_failing_from(environ),
        retries=non_negative_int(environ, RETRIES_ENV),
    )
    downloaded_dir = data_path / "Definitions"
    definition_dirs = [downloaded_dir]
    if include_bundled:
        definition_dirs.insert(0, BUNDLED_DEFINITIONS_DIR)
    definition_dirs += extra_definition_dirs or []
    definitions = DefinitionCache(
        Path(
            environ.get(DEFINITION_CACHE_ENV)
            or data_path / DEFINITION_CACHE_FILE
        )
    )
    registry = IndexerRegistry()
    manager = IndexerManager(
        dependencies,
        config_service,
        [NativeSource(), CardigannSource(definition_dirs, definitions)],
        registry,
        MetaIndexerFactory(dependencies, config, registry.values()),
        PublicIndexerProvisioner(
            configure_public, public_indexers_from(environ, default_public)
        ),
        config,
    )
    test_runner = IndexerTestRunner(manager)
    definition_sync = None
    if sync_definitions:
        definition_sync = DefinitionSyncTask(
            DefinitionUpdater(
                GitHubDefinitionFeed(session), DefinitionStore(downloaded_dir)
            ),
            config,
            clock,
            manager.reload_definitions,
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
        security=security,
        log_cache=LogCache(),
        stats=stats,
        test_runner=test_runner,
        bulk=BulkIndexerOperations(manager, test_runner),
        config_transfer=ConfigTransfer(config, config_store, manager, cache),
        clock=clock,
        definition_sync=definition_sync,
    )
