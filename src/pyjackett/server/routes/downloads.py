"""Torrent, blackhole and image proxy endpoints."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from pyjackett.app_context import AppContext
from pyjackett.indexers.web import BaseWebIndexer
from pyjackett.server.deps import Context
from pyjackett.utils import bencode
from pyjackett.utils.text import make_valid_file_name
from pyjackett.utils.urls import base64url_decode

logger = logging.getLogger(__name__)
router = APIRouter()

MAGNET_PREFIX = b"magnet:"
IMAGE_OK_STATUSES = frozenset({100, 200, 206})


def _query_value(request: Request, name: str) -> str | None:
    """Query parameter; tolerates ``&amp;`` left by lenient RSS readers."""
    value = request.query_params.get(name)
    if value is not None:
        return value
    raw = request.url.query.replace("&amp;", "&")
    values = parse_qs(raw).get(name)
    return values[0] if values else None


def _decode_target(context: AppContext, encoded: str) -> str:
    token = base64url_decode(encoded).decode("utf-8")
    return context.protector.unprotect(token)


def _web_indexer(context: AppContext, indexer_id: str) -> BaseWebIndexer:
    indexer = context.indexers.get_web_indexer(indexer_id)
    if not indexer.is_configured:
        logger.warning(
            "Rejected a request to %s which is unconfigured.", indexer.name
        )
        raise PermissionError("This indexer is not configured.")
    return indexer


def _authorized(context: AppContext, request: Request) -> bool:
    return context.security.is_valid_api_key(
        _query_value(request, "jackett_apikey")
    )


@router.get("/dl/{indexer_id}")
@router.get("/dl/{indexer_id}/")
async def download(request: Request, context: Context, indexer_id: str):
    if not _authorized(context, request):
        return Response(status_code=401)
    try:
        indexer = _web_indexer(context, indexer_id)
        target = _decode_target(context, _query_value(request, "path"))
        data = await indexer.download(target)
        if data.startswith(MAGNET_PREFIX):
            return Response(
                status_code=302, headers={"Location": data.decode("utf-8")}
            )
        name = make_valid_file_name(
            _query_value(request, "file") or "", "_", False
        )
        return Response(
            bencode.normalize(data),
            media_type="application/x-bittorrent",
            headers={
                "Content-Disposition": f'attachment; filename="{name}.torrent"'
            },
        )
    except Exception:
        logger.exception("Error downloading. indexer: %s", indexer_id)
        return Response(status_code=404)


def _blackhole_file_name(
    stamp_ns: int, indexer_name: str, file: str, extension: str
) -> str:
    stamp = f"{stamp_ns}-{make_valid_file_name(indexer_name, '_', False)}"
    if not file.strip():
        return stamp + extension
    return f"{stamp}-{make_valid_file_name(file + extension, '_', False)}"


def _write_blackhole(
    directory: Path, name: str, data: bytes, ext: str
) -> None:
    try:
        (directory / name).write_bytes(data)
    except OSError:
        # very long torrent names can fail to be written: use a GUID
        (directory / f"{uuid.uuid4()}{ext}").write_bytes(data)


@router.get("/bh/{indexer_id}")
@router.get("/bh/{indexer_id}/")
async def blackhole(request: Request, context: Context, indexer_id: str):
    if not _authorized(context, request):
        return Response(status_code=401)
    try:
        indexer = _web_indexer(context, indexer_id)
        target = _decode_target(context, _query_value(request, "path"))
        data = (
            target.encode("utf-8")
            if target.startswith("magnet")
            else await indexer.download(target)
        )
        extension = ".magnet" if data.startswith(MAGNET_PREFIX) else ".torrent"
        directory = _blackhole_directory(context)
        name = _blackhole_file_name(
            int(context.clock.time() * 1e9),
            indexer.name,
            _query_value(request, "file") or "",
            extension,
        )
        _write_blackhole(directory, name, data, extension)
        return JSONResponse({"result": "success"})
    except Exception as error:
        logger.exception(
            "Error downloading to blackhole. indexer: %s", indexer_id
        )
        return JSONResponse({"result": "error", "error": str(error)})


def _blackhole_directory(context: AppContext) -> Path:
    configured = context.config.blackhole_dir
    if not (configured or "").strip():
        raise RuntimeError("Blackhole directory not set!")
    directory = Path(configured)
    if not directory.is_dir():
        raise RuntimeError(f"Blackhole directory does not exist: {configured}")
    return directory


@router.get("/img/{indexer_id}")
@router.get("/img/{indexer_id}/")
async def image(request: Request, context: Context, indexer_id: str):
    if not _authorized(context, request):
        return Response(status_code=401)
    try:
        indexer = _web_indexer(context, indexer_id)
        target = _decode_target(context, _query_value(request, "path"))
        result = await indexer.download_image(target)
        if result.status not in IMAGE_OK_STATUSES:
            return Response(status_code=result.status)
        return Response(
            result.content_bytes,
            media_type=result.header("content-type") or "image/jpeg",
        )
    except Exception:
        logger.debug(
            "Error downloading image. indexer: %s", indexer_id, exc_info=True
        )
        return Response(status_code=500)
