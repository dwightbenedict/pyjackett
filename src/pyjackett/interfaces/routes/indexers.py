"""Management API for indexers (dashboard backend)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from pyjackett.interfaces.auth import require_dashboard_user
from pyjackett.interfaces.deps import Context
from pyjackett.interfaces.proxy_links import proxy_tracker_result
from pyjackett.interfaces.schemas import (
    ERROR_RESPONSES,
    BulkOutcome,
    IndexerIds,
)
from pyjackett.interfaces.serialization import release_json
from pyjackett.interfaces.urls import server_url
from pyjackett.services.indexers.base import ConfigurationStatus

router = APIRouter(
    prefix="/indexers",
    tags=["indexers"],
    dependencies=[Depends(require_dashboard_user)],
    responses=ERROR_RESPONSES,
)


# the fixed paths are declared before the ``/{indexer_id}`` routes so that
# "cache" and "bulk" are not taken for indexer ids
@router.get("/cache")
async def cached_results(request: Request, context: Context):
    url = server_url(context, request)
    results = context.cache.cached_results()
    for result in results:
        proxy_tracker_result(context, result, url)
    return [release_json(r) for r in results]


@router.delete("/cache", status_code=204, summary="Clear the results cache")
async def clear_cache(context: Context) -> None:
    context.cache.clean_cache()


@router.post(
    "/bulk/add",
    response_model=list[BulkOutcome],
    summary="Add several public indexers with their defaults",
)
async def bulk_add(context: Context, body: IndexerIds):
    return await context.bulk.add(body.ids)


@router.post(
    "/bulk/test",
    response_model=list[BulkOutcome],
    summary="Test several indexers at once",
)
async def bulk_test(context: Context, body: IndexerIds):
    return await context.bulk.test(body.ids)


@router.post(
    "/bulk/delete",
    response_model=list[BulkOutcome],
    summary="Remove the configuration of several indexers",
)
async def bulk_delete(context: Context, body: IndexerIds):
    return await context.bulk.delete(body.ids)


@router.post(
    "/{indexer_id}/add",
    status_code=204,
    summary="Add a public indexer with its default configuration",
)
async def add_indexer(context: Context, indexer_id: str) -> None:
    """Indexers that need credentials answer 409: use ``/config``."""
    context.indexers.add_indexer(indexer_id)


@router.delete("/{indexer_id}/cache", status_code=204)
async def clear_indexer_cache(context: Context, indexer_id: str) -> None:
    context.cache.clean_indexer_cache(context.indexers.get_indexer(indexer_id))


@router.get("/{indexer_id}/config")
async def get_config(context: Context, indexer_id: str):
    indexer = context.indexers.get_indexer(indexer_id)
    form = await indexer.get_configuration_for_setup()
    return form.to_json(None)


@router.post("/{indexer_id}/config")
async def update_config(request: Request, context: Context, indexer_id: str):
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
async def test_indexer(context: Context, indexer_id: str):
    indexer = context.indexers.get_indexer(indexer_id)
    await context.test_runner.run(indexer.id)
    return {"latency_ms": context.stats.last_elapsed_ms(indexer.id)}


@router.delete("/{indexer_id}")
async def delete_indexer(context: Context, indexer_id: str):
    context.indexers.delete_indexer(indexer_id)
    return Response(status_code=204)
