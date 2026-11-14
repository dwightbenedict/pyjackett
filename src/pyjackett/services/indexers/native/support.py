"""Small helpers shared by the native indexers."""

from __future__ import annotations

from datetime import timedelta

from pyjackett.domain.http_models import WebResult
from pyjackett.errors import TooManyRequestsError

TOO_MANY_REQUESTS = 429
DEFAULT_RETRY_AFTER = timedelta(minutes=5)


def retry_after(response: WebResult) -> timedelta:
    """How long the tracker asked us to wait (``Retry-After`` seconds)."""
    value = response.header("retry-after")
    if value and value.strip().isdigit():
        return timedelta(seconds=int(value))
    return DEFAULT_RETRY_AFTER


def raise_if_rate_limited(response: WebResult) -> None:
    if response.status == TOO_MANY_REQUESTS:
        raise TooManyRequestsError("Rate limited", retry_after(response))


def first_if_single(values: list[str], default: str) -> str:
    """The only value, else ``default`` (several categories mean "any")."""
    return values[0] if len(values) == 1 else default
