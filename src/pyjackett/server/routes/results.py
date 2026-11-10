"""Search endpoints: Torznab, TorrentPotato and the manual search."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from pyjackett.core.exceptions import (
    IndexerError,
    IndexerRateLimitedError,
)
from pyjackett.core.query import TorznabQuery
from pyjackett.core.tracker_result import TrackerCacheResult
from pyjackett.indexers.base import BaseIndexer
from pyjackett.indexers.manager import UnknownIndexerError
from pyjackett.server import torznab_xml
from pyjackett.server.auth import has_valid_api_key
from pyjackett.server.deps import Context
from pyjackett.server.errors import GuardFailureError
from pyjackett.server.proxy_links import proxy_release, proxy_tracker_result
from pyjackett.server.query_parsing import (
    manual_search_query,
    potato_query,
    torznab_query,
)
from pyjackett.server.serialization import release_json
from pyjackett.server.torznab_validation import validate_query
from pyjackett.server.urls import server_url
from pyjackett.utils.numbers import format_imdb_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2.0/indexers/{indexer_id}/results")

XML_TYPE = "application/xml; charset=utf-8"
RSS_TYPE = "application/rss+xml; charset=utf-8"
DEFAULT_RETRY_AFTER = 60

INVALID_API_KEY = 100
INDEXER_UNSPECIFIED = 200
INDEXER_UNSUPPORTED = 201
GENERIC_ERROR = 900


def _error_response(
    code: int, description: str, status: int = 400
) -> Response:
    return Response(
        torznab_xml.error_xml(code, description),
        status_code=status,
        media_type=XML_TYPE,
    )


class TorznabErrors:
    """Torznab clients get XML errors (with a 200 status)."""

    @staticmethod
    def invalid_api_key() -> Response:
        return TorznabErrors._xml(INVALID_API_KEY, "Invalid API Key")

    @staticmethod
    def not_supported(description: str) -> Response:
        return TorznabErrors._xml(INDEXER_UNSUPPORTED, description)

    @staticmethod
    def _xml(code: int, description: str) -> Response:
        return Response(
            torznab_xml.error_xml(code, description),
            media_type="application/xml",
        )


class PlainErrors:
    """Everybody else gets plain HTTP errors."""

    @staticmethod
    def invalid_api_key() -> Response:
        return Response(status_code=401)

    @staticmethod
    def not_supported(description: str) -> Response:
        return Response(description, status_code=404)


def authorized_indexer(errors):
    """Dependency: the configured indexer, or a GuardFailureError response."""

    def dependency(
        request: Request, indexer_id: str, context: Context
    ) -> BaseIndexer:
        if not has_valid_api_key(context, request):
            raise GuardFailureError(errors.invalid_api_key())
        try:
            indexer = context.indexers.get_indexer(indexer_id)
        except UnknownIndexerError:
            raise GuardFailureError(
                errors.not_supported("Indexer is not supported")
            ) from None
        if not indexer.is_configured:
            raise GuardFailureError(
                errors.not_supported("Indexer is not configured")
            )
        return indexer

    return dependency


TorznabIndexer = Annotated[
    BaseIndexer, Depends(authorized_indexer(TorznabErrors))
]
PlainIndexer = Annotated[BaseIndexer, Depends(authorized_indexer(PlainErrors))]


# ---- Torznab ----------------------------------------------------------------


def _indexers_listing(indexer: BaseIndexer, configured: str | None):
    members = list(indexer.indexers)
    if (configured or "").lower() == "true":
        members = [m for m in members if m.is_configured]
    elif (configured or "").lower() == "false":
        members = [m for m in members if not m.is_configured]
    return Response(torznab_xml.indexers_xml(members), media_type=XML_TYPE)


def _log_search(kind, indexer, query, count, from_cache, started) -> None:
    elapsed = (time.monotonic() - started) * 1000
    cache = " (from cache)" if from_cache else ""
    term = query.query_string()
    where = f" for {term}" if term else ""
    logger.info(
        "%s search in %s%s => Found %d releases%s [%.0fms]",
        kind,
        indexer.name,
        where,
        count,
        cache,
        elapsed,
    )


async def _torznab_results(request, context, indexer, query) -> Response:
    started = time.monotonic()
    try:
        result = await indexer.results_for_query(query)
    except IndexerRateLimitedError as error:
        return _too_many_requests(error)
    except IndexerError as error:
        logger.error("%s", error)
        return _error_response(GENERIC_ERROR, str(error))
    url = server_url(context, request)
    releases = [proxy_release(context, r, url) for r in result.releases]
    _log_search(
        "Torznab", indexer, query, len(releases), result.is_from_cache, started
    )
    xml = torznab_xml.results_xml(
        releases, indexer.name, indexer.description, indexer.site_link, url
    )
    return Response(xml, media_type=RSS_TYPE)


def _too_many_requests(error: IndexerRateLimitedError) -> Response:
    retry = error.retry_after.total_seconds() or DEFAULT_RETRY_AFTER
    response = _error_response(GENERIC_ERROR, str(error), 429)
    response.headers["Retry-After"] = str(int(retry))
    return response


@router.get("/torznab")
@router.get("/torznab/{ignored:path}")
async def torznab(
    request: Request,
    context: Context,
    indexer: TorznabIndexer,
    ignored: str = "",
):
    query = torznab_query(request.query_params)
    if not indexer.can_handle_query(query):
        return TorznabErrors.not_supported(
            f"{indexer.id} does not support the requested query. Please "
            "check the capabilities (t=caps) and make sure the search mode "
            "and parameters are supported.",
        )
    if query.query_type.lower() == "caps":
        return Response(
            torznab_xml.capabilities_xml(indexer.torznab_caps),
            media_type=RSS_TYPE,
        )
    if query.query_type.lower() == "indexers":
        if not indexer.is_meta:
            return _error_response(
                203, "Function Not Available: this isn't a meta indexer"
            )
        return _indexers_listing(
            indexer, request.query_params.get("configured")
        )
    problem = validate_query(query, indexer)
    if problem:
        return _error_response(problem.code, problem.description)
    return await _torznab_results(request, context, indexer, query)


# ---- TorrentPotato ----------------------------------------------------------


def _potato_item(context, indexer, release, url) -> dict:
    link = context.server_service.convert_to_proxy_link(
        release.link, url, indexer.id, "dl", release.title
    )
    imdb = format_imdb_id(f"tt{release.imdb}") if release.imdb else None
    published = release.publish_date
    return {
        "release_name": f"{release.title}[{indexer.name}]",
        "torrent_id": release.guid,
        "details_url": release.details,
        "download_url": link or release.magnet_uri,
        "imdb_id": imdb,
        "freeleech": release.download_volume_factor == 0,
        "type": "movie",
        "size": (release.size or 0) // (1024 * 1024),
        "leechers": (release.peers if release.peers is not None else -1)
        - (release.seeders or 0),
        "seeders": release.seeders if release.seeders is not None else -1,
        "publish_date": (
            published.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
            if published
            else None
        ),
    }


@router.get("/potato")
@router.get("/potato/{ignored:path}")
async def potato(
    request: Request,
    context: Context,
    indexer: PlainIndexer,
    ignored: str = "",
):
    query = potato_query(request.query_params)
    result = await indexer.results_for_query(query)
    url = server_url(context, request)
    items = [
        _potato_item(context, indexer, release, url)
        for release in result.releases
        if release.link or release.magnet_uri
    ]
    return JSONResponse({"results": items})


# ---- manual search ----------------------------------------------------------


def _manual_parameters(request: Request) -> dict:
    params = request.query_params
    return {
        "query": params.get("query"),
        "categories": [
            int(c) for c in params.get("Category[]", "").split(",") if c
        ],
        "imdbid": params.get("imdbid"),
        "tmdbid": params.get("tmdbid"),
        "tvdbid": params.get("tvdbid"),
        "tvmazeid": params.get("tvmazeid"),
    }


def _selected_trackers(
    indexer: BaseIndexer, requested: list[str], query: TorznabQuery
) -> list[BaseIndexer]:
    members = indexer.members()
    if requested:
        members = [m for m in members if m.id in requested]
    return [m for m in members if m.can_handle_query(query)]


def _outcome_json(task: asyncio.Task, indexer: BaseIndexer) -> dict:
    """Status entry of one tracker in the manual search response."""
    error = task.exception() if task.done() and not task.cancelled() else None
    if error is None:
        result = task.result()
        return {
            "id": indexer.id,
            "name": indexer.name,
            "status": "ok",
            "results": len(result.releases),
            "elapsed_ms": result.elapsed_ms,
            "error": None,
        }
    return {
        "id": indexer.id,
        "name": indexer.name,
        "status": "error",
        "results": 0,
        "elapsed_ms": 0,
        "error": str(error),
    }


@router.get("")
async def manual_search(
    request: Request, context: Context, indexer: PlainIndexer
):
    started = time.monotonic()
    query = manual_search_query(_manual_parameters(request))
    requested = [
        t for t in request.query_params.get("Tracker[]", "").split(",") if t
    ]
    trackers = _selected_trackers(indexer, requested, query)
    query.interactive_search = True
    is_meta = not requested or len(requested) > 1
    tasks = [
        asyncio.ensure_future(t.results_for_query(query, is_meta))
        for t in trackers
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    url = server_url(context, request)
    statuses = [
        _outcome_json(t, i) for t, i in zip(tasks, trackers, strict=True)
    ]
    results = _collect_results(context, tasks, url)
    _log_manual(trackers, query, len(results), started)
    return JSONResponse({"indexers": statuses, "results": results})


def _collect_results(context, tasks, url) -> list[dict]:
    collected: list[TrackerCacheResult] = []
    for task in tasks:
        if task.exception() is not None:
            continue
        result = task.result()
        for release in result.releases:
            tracker = TrackerCacheResult.from_release(
                release,
                result.indexer.name,
                result.indexer.id,
                result.indexer.type,
            )
            proxy_tracker_result(context, tracker, url)
            collected.append(tracker)
    collected.sort(
        key=lambda r: r.publish_date.timestamp() if r.publish_date else 0,
        reverse=True,
    )
    return [release_json(r) for r in collected]


def _log_manual(trackers, query, count, started) -> None:
    names = ", ".join(sorted(t.name for t in trackers))
    elapsed = (time.monotonic() - started) * 1000
    term = query.query_string()
    where = f" for {term}" if term else ""
    logger.info(
        "Manual search in %s%s => Found %d releases [%.0fms]",
        names,
        where,
        count,
        elapsed,
    )
