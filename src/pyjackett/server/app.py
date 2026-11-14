"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from pyjackett import __version__
from pyjackett.app_context import AppContext
from pyjackett.config.paths import BUNDLED_WEB_DIR
from pyjackett.server.api_docs import (
    API_DESCRIPTION,
    API_SUMMARY,
    API_TAGS,
    API_TITLE,
    finish_openapi,
)
from pyjackett.server.errors import (
    CLIENT_ERRORS,
    GuardFailureError,
    client_error_handler,
    handle_exception,
    handle_guard_failure,
)
from pyjackett.server.routes import (
    catalog,
    downloads,
    indexers,
    results,
    server_config,
    system,
    ui,
)
from pyjackett.server.static_files import RevalidatingStaticFiles

logger = logging.getLogger(__name__)

# PyJackett's own versioned API; v2.0 is Jackett's, kept so that Sonarr,
# Radarr, Prowlarr and the dashboard keep working (and left out of the docs)
API_PREFIX = "/api/v1"
JACKETT_API_PREFIX = "/api/v2.0"
# The documented API is for searching: the search endpoints and the
# read-only discovery needed to use them. Everything that manages indexers
# or the server belongs to the dashboard and stays out of the spec.
# Fixed paths first: ``/indexers/cache`` must not match ``/{indexer_id}``.
SEARCH_ROUTERS = (results.router, catalog.router)
MANAGEMENT_ROUTERS = (
    indexers.router,
    server_config.router,
    server_config.protected,
    system.router,
    system.protected,
)


def _lifespan(context: AppContext, load_indexers: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context.log_cache.attach()
        sync = context.definition_sync if load_indexers else None
        if load_indexers:
            await asyncio.to_thread(context.indexers.init_indexers)
        if sync is not None:
            sync.attach()
        yield
        if sync is not None:
            await sync.detach()
        await context.close()
        context.log_cache.detach()

    return lifespan


def _add_routers(app: FastAPI, base_path: str) -> None:
    for router in (ui.router, downloads.router, results.legacy):
        app.include_router(router, prefix=base_path, include_in_schema=False)
    for router in (*SEARCH_ROUTERS, *MANAGEMENT_ROUTERS):
        documented = router in SEARCH_ROUTERS
        app.include_router(
            router,
            prefix=base_path + API_PREFIX,
            include_in_schema=documented,
        )
        app.include_router(
            router,
            prefix=base_path + JACKETT_API_PREFIX,
            include_in_schema=False,
        )
    app.mount(
        f"{base_path}/static",
        RevalidatingStaticFiles(directory=BUNDLED_WEB_DIR / "static"),
        name="static",
    )


def _finish_openapi(app: FastAPI) -> None:
    """Post-process the generated OpenAPI document (it is built lazily)."""
    generate = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            finish_openapi(generate(), API_PREFIX, JACKETT_API_PREFIX)
        return app.openapi_schema

    app.openapi = openapi


def create_app(context: AppContext, load_indexers: bool = True) -> FastAPI:
    """Build the application around an already wired ``context``."""
    base_path = context.server_service.base_path()
    app = FastAPI(
        title=API_TITLE,
        version=__version__,
        summary=API_SUMMARY,
        description=API_DESCRIPTION,
        openapi_tags=API_TAGS,
        license_info={"name": "GPL-2.0-only", "identifier": "GPL-2.0-only"},
        lifespan=_lifespan(context, load_indexers),
        docs_url=f"{base_path}{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{base_path}{API_PREFIX}/openapi.json",
    )
    app.state.context = context
    _finish_openapi(app)
    app.add_exception_handler(Exception, handle_exception)
    app.add_exception_handler(GuardFailureError, handle_guard_failure)
    for error_type, status_code in CLIENT_ERRORS.items():
        app.add_exception_handler(
            error_type, client_error_handler(status_code)
        )
    if context.config.allow_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    # the indexer listing alone is ~2 MB of JSON; level 5 is the sweet spot
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    _add_routers(app, base_path)
    return app
