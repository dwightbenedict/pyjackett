"""What the services need from the outside world; adapters implement these."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from pyjackett.domain.cardigann.definition import IndexerDefinition
from pyjackett.domain.http_models import WebRequest, WebResult
from pyjackett.domain.server_config import ServerConfig


class Clock(Protocol):
    """Everything the code needs to know about, or wait for, time."""

    def now(self) -> datetime:
        """Wall clock time in the local zone."""
        ...

    def time(self) -> float:
        """Seconds since the epoch."""
        ...

    def monotonic(self) -> float:
        """Seconds from an arbitrary origin; never goes backwards."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Wait without blocking the event loop."""

    def jitter(self, low: float, high: float) -> float:
        """A random factor between ``low`` and ``high``."""
        ...


class HttpClient(Protocol):
    """Sends the requests of one indexer."""

    def set_request_delay(self, seconds: float) -> None:
        """Minimum time between two requests."""

    async def get_result(self, request: WebRequest) -> WebResult:
        """Send ``request`` and return what the site answered."""
        ...


class CertificateTrust(Protocol):
    """Where indexers pin the self-signed certificates of their sites."""

    def add(self, host: str, fingerprint: str) -> None:
        """Allow ``host`` to present the certificate with ``fingerprint``."""


class SecretProtector(Protocol):
    """Encrypts and decrypts the secrets stored in configuration files."""

    def protect(self, plain_text: str | None) -> str:
        """Protocol method."""
        ...

    def unprotect(self, token: str | None) -> str:
        """Protocol method."""
        ...


class IndexerConfigRepository(Protocol):
    """The saved configuration of every indexer, by indexer id."""

    def load(self, indexer_id: str) -> list[dict[str, Any]] | None:
        """The stored values, or None when nothing was saved."""
        ...

    def save(self, indexer_id: str, data: list[dict[str, Any]]) -> None:
        """Protocol method."""

    def delete(self, indexer_id: str) -> None:
        """Protocol method."""

    def rename(self, old_id: str, new_id: str) -> bool:
        """Move a configuration to a new id; True if it was moved."""
        ...

    def stored_ids(self) -> list[str]:
        """The id of every indexer with a saved configuration."""
        ...


class ServerConfigRepository(Protocol):
    """Where the server configuration is persisted."""

    def save(self, config: ServerConfig) -> None:
        """Protocol method."""


class DefinitionFeed(Protocol):
    """A published set of definitions."""

    async def list_files(self) -> dict[str, str]:
        """The current revision of every definition, by file name."""
        ...

    async def fetch(self, name: str) -> str:
        """The text of one definition."""
        ...


@dataclass(frozen=True)
class Download:
    """One definition fetched from the feed."""

    text: str
    revision: str


class DefinitionRepository(Protocol):
    """The downloaded definitions and their revisions."""

    def revisions(self) -> dict[str, str]:
        """Revision of every downloaded definition that is still stored."""
        ...

    def save(self, downloads: Mapping[str, Download], removed: Iterable[str]) -> None:
        """Write the downloads and delete the removed."""


class DefinitionParser(Protocol):
    """Parses definitions, remembering the ones it has seen."""

    def parse(self, text: str) -> IndexerDefinition:
        """Protocol method."""
        ...

    def save(self) -> None:
        """Persist what was parsed since the last save."""
