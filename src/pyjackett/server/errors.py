"""Error responses of the management API."""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from pyjackett.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class GuardFailureError(Exception):
    """Stops a request early with a ready-made response."""

    def __init__(self, response: Response) -> None:
        super().__init__("request rejected")
        self.response = response


async def handle_guard_failure(request: Request, error: GuardFailureError):
    return error.response


def describe(error: BaseException) -> str:
    """Message of an error plus the message of its cause."""
    cause = error.__cause__ or error.__context__
    return f"{error}: {cause}" if cause else str(error)


async def handle_exception(request: Request, error: Exception):
    """JSON the dashboard understands (``result: error`` + message)."""
    logger.error("Unhandled error on %s: %s", request.url.path, error)
    body: dict = {
        "result": "error",
        "error": describe(error),
        "stacktrace": "".join(traceback.format_exception(error)),
    }
    if isinstance(error, ConfigurationError) and error.config_data:
        body["config"] = error.config_data.to_json(None, for_display=True)
    return JSONResponse(body, status_code=500)
