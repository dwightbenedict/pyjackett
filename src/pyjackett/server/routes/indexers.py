"""Management API for indexers (dashboard backend)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from pyjackett.indexers.base import ConfigurationStatus
from pyjackett.server.auth import require_dashboard_user
from pyjackett.server.deps import get_context as _context
from pyjackett.server.proxy_links import proxy_tracker_result
from pyjackett.server.serialization import indexer_json, release_json
from pyjackett.server.urls import server_url

router = APIRouter(
    prefix="/api/v2.0/indexers", dependencies=[Depends(require_dashboard_user)]
)


@router.get("")
async def list_indexers(request: Request, configured: bool = False):
    indexers = _context(request).indexers.all_indexers()
    if configured:
        indexers = [i for i in indexers if i.is_configured]
    return [indexer_json(i) for i in indexers]


# declared before ``/{indexer_id}`` routes so "cache" is not an indexer id
@router.get("/cache")
async def cached_results(request: Request):
    context = _context(request)
    url = server_url(context, request)
    results = context.cache.cached_results()
    for result in results:
        proxy_tracker_result(context, result, url)
    return [release_json(r) for r in results]


@router.get("/{indexer_id}/config")
async def get_config(request: Request, indexer_id: str):
    indexer = _context(request).indexers.get_indexer(indexer_id)
    form = await indexer.get_configuration_for_setup()
    return form.to_json(None)


@router.post("/{indexer_id}/config")
async def update_config(request: Request, indexer_id: str):
    context = _context(request)
    indexer = context.indexers.get_indexer(indexer_id)
    context.cache.clean_indexer_cache(indexer)
    posted: list[dict[str, Any]] = await request.json()
    try:
        status = await indexer.apply_configuration(posted)
        if status is ConfigurationStatus.REQUIRES_TESTING:
            await context.indexers.test_indexer(indexer.id)
    except Exception:
        indexer.reset_base_config()
        raise
    return Response(status_code=204)


@router.post("/{indexer_id}/test")
async def test_indexer(request: Request, indexer_id: str):
    context = _context(request)
    indexer = context.indexers.get_indexer(indexer_id)
    try:
        await context.indexers.test_indexer(indexer.id)
    except Exception as error:
        indexer.last_error = _describe(error)
        raise
    indexer.last_error = None
    return Response(status_code=204)


def _describe(error: Exception) -> str:
    cause = error.__cause__
    return f"{error}: {cause}" if cause else str(error)


@router.delete("/{indexer_id}")
async def delete_indexer(request: Request, indexer_id: str):
    _context(request).indexers.delete_indexer(indexer_id)
    return Response(status_code=204)
