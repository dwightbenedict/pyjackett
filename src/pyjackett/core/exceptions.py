"""Exceptions raised by indexers and the services around them."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyjackett.indexers.base import BaseIndexer


class TooManyRequestsError(Exception):
    """The tracker asked us to slow down (HTTP 429)."""

    def __init__(self, message: str, retry_after: timedelta) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class IndexerError(Exception):
    """Wraps any failure that happened while querying an indexer."""

    def __init__(self, indexer: BaseIndexer, cause: Exception) -> None:
        super().__init__(f"Exception ({indexer.id}): {cause}")
        self.indexer = indexer
        self.__cause__ = cause


class IndexerRateLimitedError(IndexerError):
    """The indexer's tracker answered 429; ``retry_after`` says when."""

    def __init__(self, indexer: BaseIndexer, cause: TooManyRequestsError):
        super().__init__(indexer, cause)
        self.retry_after = cause.retry_after


class ConfigurationError(Exception):
    """An indexer configuration is invalid; carries the form to re-show."""

    def __init__(self, message: str, config_data: Any = None) -> None:
        super().__init__(message)
        self.config_data = config_data


class IndexerTestFailedError(RuntimeError):
    """A test search found nothing: the indexer is probably misconfigured."""
