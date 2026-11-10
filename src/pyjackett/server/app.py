"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pyjackett import __version__
from pyjackett.app_context import AppContext
from pyjackett.config.paths import BUNDLED_WEB_DIR
from pyjackett.server.errors import (
    GuardFailureError,
    handle_exception,
    handle_guard_failure,
)
from pyjackett.server.routes import (
    downloads,
    indexers,
    results,
    server_config,
    ui,
)

logger = logging.getLogger(__name__)


def _lifespan(context: AppContext, load_indexers: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context.log_cache.attach()
        if load_indexers:
            await asyncio.to_thread(context.indexers.init_indexers)
        yield
        await context.close()
        context.log_cache.detach()

    return lifespan


def _add_routers(app: FastAPI, base_path: str) -> None:
    for router in (
        ui.router,
        results.router,
        indexers.router,
        server_config.router,
        server_config.protected,
        downloads.router,
    ):
        app.include_router(router, prefix=base_path)
    app.mount(
        f"{base_path}/static",
        StaticFiles(directory=BUNDLED_WEB_DIR / "static"),
        name="static",
    )


def create_app(context: AppContext, load_indexers: bool = True) -> FastAPI:
    """Build the application around an already wired ``context``."""
    app = FastAPI(
        title="PyJackett",
        version=__version__,
        lifespan=_lifespan(context, load_indexers),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.context = context
    app.add_exception_handler(Exception, handle_exception)
    app.add_exception_handler(GuardFailureError, handle_guard_failure)
    if context.config.allow_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    _add_routers(app, context.server_service.base_path())
    return app
