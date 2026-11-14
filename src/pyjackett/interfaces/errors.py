"""Error responses of the management API."""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from pyjackett.errors import (
    ConfigBundleError,
    ConfigurationError,
    IndexerConfigurationRequiredError,
    IndexerTestFailedError,
    InvalidCredentialsError,
    InvalidPasswordError,
)
from pyjackett.services.indexers.manager import UnknownIndexerError

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
    if isinstance(error, IndexerTestFailedError):
        body["latency_ms"] = error.latency_ms
    return JSONResponse(body, status_code=500)


# domain failures that are the caller's fault, not the server's
CLIENT_ERRORS: dict[type[Exception], int] = {
    UnknownIndexerError: 404,
    IndexerConfigurationRequiredError: 409,
    InvalidPasswordError: 403,
    ConfigBundleError: 400,
    InvalidCredentialsError: 400,
}


def client_error_handler(status_code: int):
    """Handler answering with the same JSON shape at a 4xx status."""

    async def handler(request: Request, error: Exception):
        message = error.args[0] if isinstance(error, KeyError) else error
        return JSONResponse(
            {"result": "error", "error": str(message)},
            status_code=status_code,
        )

    return handler
