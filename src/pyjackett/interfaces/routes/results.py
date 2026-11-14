"""Search endpoints: Torznab, TorrentPotato and the manual search."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pyjackett.adapters.clock import Stopwatch
from pyjackett.domain.numbers import format_imdb_id
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.tracker_result import TrackerCacheResult
from pyjackett.errors import (
    IndexerError,
    IndexerRateLimitedError,
)
from pyjackett.interfaces import torznab_xml
from pyjackett.interfaces.api_docs import (
    MANUAL_PARAMETERS,
    NDJSON_RESPONSE,
    PLAIN_ERRORS,
    POTATO_PARAMETERS,
    TORZNAB_PARAMETERS,
    TORZNAB_RESPONSES,
    IndexerId,
    api_key_query,
)
from pyjackett.interfaces.auth import has_valid_api_key
from pyjackett.interfaces.deps import Context
from pyjackett.interfaces.errors import GuardFailureError
from pyjackett.interfaces.proxy_links import (
    proxy_release,
    proxy_tracker_result,
)
from pyjackett.interfaces.query_parsing import (
    manual_search_query,
    potato_query,
    torznab_query,
)
from pyjackett.interfaces.schemas import ManualSearchResponse, PotatoResponse
from pyjackett.interfaces.serialization import release_json
from pyjackett.interfaces.torznab_validation import validate_query
from pyjackett.interfaces.urls import server_url
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.manager import UnknownIndexerError

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/indexers/{indexer_id}/results",
    tags=["search"],
    dependencies=[Depends(api_key_query)],
)
# the paths older Jackett setups still call, mounted without the API prefix
legacy = APIRouter(include_in_schema=False)

XML_TYPE = "application/xml; charset=utf-8"
MANUAL_SEARCH_TIMEOUT = 30.0  # seconds before slow trackers are given up
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
        request: Request, indexer_id: IndexerId, context: Context
    ) -> BaseIndexer:
        if not has_valid_api_key(context.security, request):
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


def _log_search(kind, indexer, query, count, from_cache, elapsed) -> None:
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
        "Torznab",
        indexer,
        query,
        len(releases),
        result.is_from_cache,
        result.elapsed_ms,
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


@router.get(
    "/torznab",
    operation_id="searchTorznab",
    summary="Search with the Torznab protocol",
    description=(
        "The endpoint for Sonarr, Radarr, Lidarr, Readarr and Prowlarr. "
        "Add `/api` to the path if your client insists on it. "
        "Releases link to this server (`/dl/...`), which fetches the "
        "torrent for the client, so tracker credentials never leave it."
    ),
    responses=TORZNAB_RESPONSES,
    openapi_extra={"parameters": TORZNAB_PARAMETERS},
)
@router.get("/torznab/{ignored:path}", include_in_schema=False)
@legacy.get("/torznab/{indexer_id}")
@legacy.get("/torznab/{indexer_id}/api")
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


@router.get(
    "/potato",
    operation_id="searchTorrentPotato",
    summary="Search movies with the TorrentPotato protocol",
    description=(
        "For CouchPotato-style clients. Only indexers with movie "
        "categories answer (`potatoenabled` in the indexer listing)."
    ),
    response_model=PotatoResponse,
    responses=PLAIN_ERRORS,
    openapi_extra={"parameters": POTATO_PARAMETERS},
)
@router.get("/potato/{ignored:path}", include_in_schema=False)
@legacy.get("/potato/{indexer_id}")
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


async def _as_completed(
    searches: dict[asyncio.Task, BaseIndexer],
) -> AsyncIterator[tuple[asyncio.Task, BaseIndexer]]:
    """Yield each search as soon as it finishes.

    Searches still running at the deadline are cancelled and yielded last,
    so one slow tracker never holds back the results of the others.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + MANUAL_SEARCH_TIMEOUT
    pending = set(searches)
    while pending:
        done, pending = await asyncio.wait(
            pending,
            timeout=max(deadline - loop.time(), 0),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            break
        for task in done:
            yield task, searches[task]
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in pending:
        yield task, searches[task]


def _outcome_json(task: asyncio.Task, indexer: BaseIndexer) -> dict:
    """Status entry of one tracker in the manual search response."""
    if task.cancelled():
        return _failed_outcome(indexer, "Timed out")
    error = task.exception()
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
    return _failed_outcome(indexer, str(error))


def _failed_outcome(indexer: BaseIndexer, message: str) -> dict:
    return {
        "id": indexer.id,
        "name": indexer.name,
        "status": "error",
        "results": 0,
        "elapsed_ms": 0,
        "error": message,
    }


def _start_searches(
    request: Request, indexer: BaseIndexer
) -> tuple[TorznabQuery, dict[asyncio.Task, BaseIndexer]]:
    """Start the selected trackers' searches in parallel."""
    query = manual_search_query(_manual_parameters(request))
    requested = [
        t for t in request.query_params.get("Tracker[]", "").split(",") if t
    ]
    trackers = _selected_trackers(indexer, requested, query)
    query.interactive_search = True
    is_meta = not requested or len(requested) > 1
    searches = {
        asyncio.ensure_future(t.results_for_query(query, is_meta)): t
        for t in trackers
    }
    return query, searches


def _tracker_results(
    context, task: asyncio.Task, url: str
) -> list[TrackerCacheResult]:
    """Releases of one finished search, newest first."""
    if task.cancelled() or task.exception() is not None:
        return []
    result = task.result()
    found: list[TrackerCacheResult] = []
    for release in result.releases:
        tracker = TrackerCacheResult.from_release(
            release,
            result.indexer.name,
            result.indexer.id,
            result.indexer.type,
        )
        proxy_tracker_result(context, tracker, url)
        found.append(tracker)
    return _newest_first(found)


def _newest_first(
    releases: list[TrackerCacheResult],
) -> list[TrackerCacheResult]:
    return sorted(
        releases,
        key=lambda r: r.publish_date.timestamp() if r.publish_date else 0,
        reverse=True,
    )


@router.get(
    "",
    operation_id="searchAll",
    response_model=ManualSearchResponse,
    summary="Search and get every tracker's results as JSON",
    description=(
        "Searches the selected trackers in parallel and answers once they "
        "all finished or after 30 seconds, whichever comes first. Trackers "
        "that failed or timed out are reported in `indexers`; the others "
        "still deliver their `results`. Use `/stream` to receive trackers "
        "as they finish."
    ),
    responses=PLAIN_ERRORS,
    openapi_extra={"parameters": MANUAL_PARAMETERS},
)
async def manual_search(
    request: Request, context: Context, indexer: PlainIndexer
):
    stopwatch = Stopwatch(context.clock)
    query, searches = _start_searches(request, indexer)
    url = server_url(context, request)
    statuses: list[dict] = []
    found: list[TrackerCacheResult] = []
    async for task, tracker in _as_completed(searches):
        statuses.append(_outcome_json(task, tracker))
        found += _tracker_results(context, task, url)
    _log_manual(
        list(searches.values()), query, len(found), stopwatch.elapsed_ms
    )
    return JSONResponse(
        {
            "indexers": statuses,
            "results": [release_json(r) for r in _newest_first(found)],
        }
    )


@router.get(
    "/stream",
    operation_id="searchStream",
    summary="Search and receive each tracker's results as it finishes",
    response_class=StreamingResponse,
    responses={**NDJSON_RESPONSE, **PLAIN_ERRORS},
    openapi_extra={"parameters": MANUAL_PARAMETERS},
)
async def manual_search_stream(
    request: Request, context: Context, indexer: PlainIndexer
):
    """Newline-delimited JSON: one line per tracker, as it finishes."""
    stopwatch = Stopwatch(context.clock)
    query, searches = _start_searches(request, indexer)
    url = server_url(context, request)

    async def lines() -> AsyncIterator[str]:
        count = 0
        try:
            async for task, tracker in _as_completed(searches):
                found = _tracker_results(context, task, url)
                count += len(found)
                chunk = {
                    "indexer": _outcome_json(task, tracker),
                    "results": [release_json(r) for r in found],
                }
                yield json.dumps(chunk) + "\n"
        finally:
            for task in searches:
                task.cancel()  # a client that went away stops the work
        _log_manual(
            list(searches.values()), query, count, stopwatch.elapsed_ms
        )

    # already encoded: gzip would hold lines back until the buffer fills
    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Content-Encoding": "identity"},
    )


def _log_manual(trackers, query, count, elapsed) -> None:
    names = ", ".join(sorted(t.name for t in trackers))
    term = query.query_string()
    where = f" for {term}" if term else ""
    logger.info(
        "Manual search in %s%s => Found %d releases [%.0fms]",
        names,
        where,
        count,
        elapsed,
    )
