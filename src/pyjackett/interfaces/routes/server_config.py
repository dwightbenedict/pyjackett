"""Server configuration, logs and admin password endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from pyjackett.interfaces.auth import (
    has_valid_api_key,
    require_dashboard_user,
    require_protected_session,
    set_session_cookie,
)
from pyjackett.interfaces.config_update import (
    ServerConfigPayload,
    apply_server_config,
    config_json,
)
from pyjackett.interfaces.deps import Context
from pyjackett.interfaces.schemas import (
    ERROR_RESPONSES,
    ApiKeyResponse,
    ImportOutcome,
    RotateApiKeyRequest,
)

logger = logging.getLogger(__name__)
SECRETS = [Depends(require_protected_session)]
router = APIRouter(prefix="/server", tags=["server"])
protected = APIRouter(
    prefix="/server",
    tags=["server"],
    dependencies=[Depends(require_dashboard_user)],
    responses=ERROR_RESPONSES,
)


@protected.get("/config")
async def get_config(context: Context):
    return config_json(context)


@protected.post("/config")
async def update_config(context: Context, payload: ServerConfigPayload):
    restart = apply_server_config(context, payload)
    context.save_config()
    context.indexers.init_meta_indexers()
    context.config.notify_changed()
    context.log_cache.set_debug(payload.logging)
    result = config_json(context)
    result["restart_required"] = restart
    return result


@protected.post("/adminpassword")
async def set_admin_password(request: Request, context: Context):
    context.security.set_password(await request.json())
    context.save_config()
    return Response(status_code=204)


@protected.post("/adminusername")
async def set_admin_username(request: Request, context: Context):
    context.security.set_username(await request.json())
    context.save_config()
    return Response(status_code=204)


@protected.get(
    "/apikey",
    response_model=ApiKeyResponse,
    summary="Read the API key",
    dependencies=SECRETS,
)
async def get_api_key(context: Context):
    return ApiKeyResponse(api_key=context.config.api_key)


@protected.post(
    "/apikey/rotate",
    response_model=ApiKeyResponse,
    summary="Generate a new API key",
    dependencies=SECRETS,
)
async def rotate_api_key(
    context: Context, response: Response, body: RotateApiKeyRequest
):
    """Every URL using the old key stops working; sessions are renewed."""
    api_key = context.security.rotate_api_key(body.password)
    context.save_config()
    set_session_cookie(response, context.security)
    return ApiKeyResponse(api_key=api_key)


@protected.get(
    "/config/export",
    summary="Export settings and indexers",
    dependencies=SECRETS,
)
async def export_config(context: Context):
    """A JSON bundle with indexer passwords in clear text: keep it safe."""
    return context.config_transfer.export_bundle()


@protected.post(
    "/config/import",
    response_model=ImportOutcome,
    summary="Import a bundle made by the export endpoint",
    dependencies=SECRETS,
)
async def import_config(context: Context, bundle: dict[str, Any]):
    return context.config_transfer.import_bundle(bundle)


@protected.get("/logs")
async def logs(context: Context):
    return context.log_cache.logs


@protected.delete("/logs", summary="Clear the collected log entries")
async def clear_logs(context: Context):
    context.log_cache.clear()
    return Response(status_code=204)


@protected.post("/update")
async def update(request: Request):
    """Updates are delivered through pip; nothing to do here."""
    return Response(status_code=204)


@router.post("/shutdown")
async def shutdown(request: Request, context: Context):
    if not has_valid_api_key(context.security, request):
        return Response(status_code=401)
    logger.warning("Shutdown requested via API")
    asyncio.get_running_loop().call_later(
        0.2, os.kill, os.getpid(), signal.SIGINT
    )
    return {"ShuttingDown": True}
