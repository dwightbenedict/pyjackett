"""Server configuration, logs and admin password endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from fastapi import APIRouter, Depends, Request, Response

from pyjackett.server.auth import has_valid_api_key, require_dashboard_user
from pyjackett.server.config_update import (
    ServerConfigPayload,
    apply_server_config,
    config_json,
)
from pyjackett.server.deps import get_context as _context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2.0/server")
protected = APIRouter(
    prefix="/api/v2.0/server", dependencies=[Depends(require_dashboard_user)]
)


@protected.get("/config")
async def get_config(request: Request):
    return config_json(_context(request))


@protected.post("/config")
async def update_config(request: Request, payload: ServerConfigPayload):
    context = _context(request)
    restart = apply_server_config(context, payload)
    context.save_config()
    context.indexers.init_meta_indexers()
    context.config.notify_changed()
    logging.getLogger("pyjackett").setLevel(
        logging.DEBUG if payload.logging else logging.INFO
    )
    result = config_json(context)
    result["restart_required"] = restart
    return result


@protected.post("/adminpassword")
async def set_admin_password(request: Request):
    context = _context(request)
    password = await request.json() or None
    hashed = context.security.hash_password(password)
    if hashed != context.config.admin_password:
        context.config.admin_password = hashed
        context.save_config()
    return Response(status_code=204)


@protected.get("/logs")
async def logs(request: Request):
    return _context(request).log_cache.logs


@protected.post("/update")
async def update(request: Request):
    """Updates are delivered through pip; nothing to do here."""
    return Response(status_code=204)


@router.post("/shutdown")
async def shutdown(request: Request):
    context = _context(request)
    if not has_valid_api_key(context, request):
        return Response(status_code=401)
    logger.warning("Shutdown requested via API")
    asyncio.get_running_loop().call_later(
        0.2, os.kill, os.getpid(), signal.SIGINT
    )
    return {"ShuttingDown": True}
