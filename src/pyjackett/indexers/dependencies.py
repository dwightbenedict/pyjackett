"""The collaborators every indexer is built with."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyjackett.config.protection import ProtectionService
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.client import WebClient
from pyjackett.services.cache import ResultsCache


@dataclass
class IndexerDependencies:
    protector: ProtectionService
    cache: ResultsCache
    client_factory: Callable[[], WebClient]
    trusted_certificates: TrustedCertificates
