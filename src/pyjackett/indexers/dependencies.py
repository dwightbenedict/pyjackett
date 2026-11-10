"""The collaborators every indexer is built with."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol

from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.client import WebClient
from pyjackett.utils.clock import SYSTEM_CLOCK, Clock

if TYPE_CHECKING:
    from pyjackett.indexers.base import BaseIndexer


class SecretProtector(Protocol):
    """Encrypts and decrypts the secrets stored in configuration files."""

    def protect(self, plain_text: str | None) -> str:
        """Protocol method."""

    def unprotect(self, token: str | None) -> str:
        """Protocol method."""


class SearchCache(Protocol):
    """What an indexer needs from the results cache."""

    @property
    def ttl(self) -> timedelta:
        """Protocol method."""

    def search(
        self, indexer: BaseIndexer, query: TorznabQuery
    ) -> list[ReleaseInfo] | None:
        """Protocol method."""

    def cache_results(
        self,
        indexer: BaseIndexer,
        query: TorznabQuery,
        releases: list[ReleaseInfo],
    ) -> None:
        """Protocol method."""


@dataclass
class IndexerDependencies:
    protector: SecretProtector
    cache: SearchCache
    client_factory: Callable[[], WebClient]
    trusted_certificates: TrustedCertificates
    clock: Clock = SYSTEM_CLOCK
