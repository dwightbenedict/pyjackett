"""Retry policy for tracker requests."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from pyjackett.adapters.clock import SYSTEM_CLOCK, Clock
from pyjackett.domain.http_models import WebResult
from pyjackett.errors import (
    ConfigurationError,
    TooManyRequestsError,
)

logger = logging.getLogger(__name__)

BASE_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_STATUS = 408
# retrying cannot fix a bad configuration or a rate limit
PERMANENT_ERRORS = (ConfigurationError, TooManyRequestsError)


def _should_retry(result: WebResult) -> bool:
    return result.has_http_server_error or result.status == (REQUEST_TIMEOUT_STATUS)


def _backoff_seconds(attempt: int, clock: Clock) -> float:
    """Exponential delay with jitter: ~2s, ~4s, ~8s ..."""
    delay = BASE_DELAY_SECONDS * 2**attempt
    return delay * clock.jitter(0.75, 1.25)


async def retry_request(
    operation: Callable[[], Awaitable[WebResult]],
    retries: int,
    name: str,
    clock: Clock = SYSTEM_CLOCK,
) -> WebResult:
    """Call ``operation`` until it succeeds or ``retries`` are used up.

    Server errors, request timeouts and exceptions are retried; the last
    outcome (result or exception) is then returned/raised.
    """
    for attempt in range(retries + 1):
        last_attempt = attempt == retries
        try:
            result = await operation()
        except PERMANENT_ERRORS:
            raise
        except Exception as error:
            if last_attempt:
                raise
            reason = f"exception '{error}'"
        else:
            if last_attempt or not _should_retry(result):
                return result
            reason = f"status {result.status}"
        delay = _backoff_seconds(attempt, clock)
        logger.warning(
            "Request to %s failed with %s. Retrying in %.1fs.",
            name,
            reason,
            delay,
        )
        await clock.sleep(delay)
    raise AssertionError("unreachable")
