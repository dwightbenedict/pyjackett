"""Exceptions raised by indexers and the services around them."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyjackett.services.indexers.base import BaseIndexer


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


def describe_failure(error: Exception) -> str:
    """The short reason shown on an indexer card after a failed test."""
    reason = error.__cause__ or error
    text = str(reason).split(" For more information")[0].strip()
    return text or type(reason).__name__


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

    def __init__(self, message: str, latency_ms: int | None = None) -> None:
        super().__init__(message)
        self.latency_ms = latency_ms


class IndexerTestTimeoutError(IndexerTestFailedError):
    """A test search did not answer within the time allowed for tests."""


class InvalidPasswordError(Exception):
    """The admin password needed to authorise the action is wrong."""


class InvalidCredentialsError(ValueError):
    """The new admin username or password is empty."""


class IndexerConfigurationRequiredError(Exception):
    """The indexer needs credentials, so it cannot be added with defaults."""


class ConfigBundleError(ValueError):
    """An exported configuration bundle is malformed or unsupported."""


class DefinitionFeedError(Exception):
    """The upstream definitions cannot be listed or downloaded."""
