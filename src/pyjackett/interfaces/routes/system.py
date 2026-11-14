"""Server information, update check and search statistics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pyjackett import __version__
from pyjackett.interfaces.auth import require_api_access
from pyjackett.interfaces.deps import Context
from pyjackett.interfaces.schemas import (
    ERROR_RESPONSES,
    ServerInfo,
    StatsResponse,
    UpdateCheck,
)

API_VERSION = "1"
MAX_HISTORY = 200

router = APIRouter(prefix="/server", tags=["server"])
protected = APIRouter(
    prefix="/server",
    tags=["server"],
    dependencies=[Depends(require_api_access)],
    responses=ERROR_RESPONSES,
)


@router.get("/info", response_model=ServerInfo, summary="Version of the API")
async def info():
    """Public: lets a client discover what it is talking to."""
    return ServerInfo(
        name="PyJackett",
        version=__version__,
        api_version=API_VERSION,
        update_channel="pip",
    )


@protected.get(
    "/updatecheck", response_model=UpdateCheck, summary="Check for updates"
)
async def update_check():
    """Updates are delivered through pip, so there is nothing to compare."""
    return UpdateCheck(
        current_version=__version__,
        update_available=False,
        managed_by="pip",
        detail="Upgrade with: pip install --upgrade pyjackett",
    )


@protected.get(
    "/stats", response_model=StatsResponse, summary="Per-indexer statistics"
)
async def stats(context: Context):
    """Counters since the server started: success, errors, cache hits."""
    return StatsResponse(
        totals=context.stats.totals(), indexers=context.stats.snapshot()
    )


@protected.get("/history", summary="Recent searches, newest first")
async def history(context: Context, limit: int = MAX_HISTORY):
    return context.stats.history(max(1, min(limit, MAX_HISTORY)))


@protected.delete("/stats", status_code=204, summary="Reset statistics")
async def reset_stats(context: Context) -> None:
    context.stats.reset()
