"""Shared HTTP connection pool, proxy and certificate pinning."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from curl_cffi.requests import AsyncSession, Response

from pyjackett.adapters.http.certificates import (
    CertificateProbe,
    TrustedCertificates,
    fetch_peer_certificate,
)
from pyjackett.adapters.http.flaresolverr import (
    ChallengeSolver,
    FlareSolverrClient,
    SolverFactory,
)
from pyjackett.domain.server_config import ServerConfig

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 100.0
MAX_CONNECTIONS_PER_HOST = 20
HTTPS_PORT = 443
IMPERSONATE_ENV = "PYJACKETT_IMPERSONATE"
DEFAULT_IMPERSONATION = "chrome"
IMPERSONATION_OFF = {"", "none", "off", "false", "0"}


def impersonation_from(environ: Mapping[str, str]) -> str | None:
    """The browser to impersonate; unset means Chrome, "none" turns it off."""
    value = environ.get(IMPERSONATE_ENV)
    if value is None:
        return DEFAULT_IMPERSONATION
    value = value.strip()
    return None if value.lower() in IMPERSONATION_OFF else value


class PinnedCertificateError(Exception):
    """The server presented a certificate that is not pinned for the host."""


def _flaresolverr_proxy(config: ServerConfig) -> dict[str, str] | None:
    url = config.proxy_address(with_credentials=False)
    if url is None:
        return None
    proxy = {"url": url}
    if not config.proxy_is_anonymous:
        proxy["username"] = config.proxy_username or ""
        proxy["password"] = config.proxy_password or ""
    return proxy


class HttpSession:
    """Owns the curl_cffi session used by every indexer's web client."""

    def __init__(
        self,
        config: ServerConfig,
        trusted_certificates: TrustedCertificates | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        solver_factory: SolverFactory = FlareSolverrClient,
        client_factory: Callable[..., AsyncSession] = AsyncSession,
        certificate_probe: CertificateProbe = fetch_peer_certificate,
        impersonate: str | None = DEFAULT_IMPERSONATION,
    ) -> None:
        self._config = config
        self._impersonate = impersonate
        self._certificates = trusted_certificates or TrustedCertificates()
        self._timeout = timeout
        self._solver_factory = solver_factory
        self._client_factory = client_factory
        self._certificate_probe = certificate_probe
        self._proxy_address = config.proxy_address()
        self._flaresolverr_key = self._flaresolverr_settings()
        self._flaresolverr: ChallengeSolver | None = None
        self._client: AsyncSession | None = None
        config.subscribe(self._on_config_changed)

    @property
    def impersonating(self) -> bool:
        """Whether curl_cffi presents itself as a real browser."""
        return self._impersonate is not None

    # ---- client -----------------------------------------------------------

    def _session(self) -> AsyncSession:
        if self._client is None:
            self._client = self._client_factory(
                timeout=self._timeout,
                allow_redirects=False,
                discard_cookies=True,  # indexers manage cookies themselves
                max_clients=MAX_CONNECTIONS_PER_HOST * 5,
                proxy=self._config.proxy_address(),
                impersonate=self._impersonate,
            )
        return self._client

    # ---- sending ----------------------------------------------------------

    async def send(self, request_kwargs: dict[str, Any]) -> Response:
        """Send one request; pinned hosts get certificate verification."""
        url = urlsplit(request_kwargs["url"])
        host = url.hostname or ""
        pinned = self._certificates.has_pins_for(host)
        if pinned:
            await self._assert_pinned(host, url.port or HTTPS_PORT)
        return await self._session().request(
            verify=not pinned, **request_kwargs
        )

    async def _assert_pinned(self, host: str, port: int) -> None:
        der = await self._certificate_probe(host, port, self._timeout)
        if not der or not self._certificates.is_trusted(host, der):
            raise PinnedCertificateError(
                f"certificate validation failed for {host}"
            )

    # ---- FlareSolverr -------------------------------------------------------

    def _flaresolverr_settings(self) -> tuple:
        config = self._config
        return (config.flaresolverr_url, config.flaresolverr_max_timeout)

    @property
    def flaresolverr(self) -> ChallengeSolver | None:
        """A solver client when FlareSolverr is configured, else None."""
        url = (self._config.flaresolverr_url or "").strip()
        if not url:
            return None
        if self._flaresolverr is None:
            self._flaresolverr = self._solver_factory(
                url,
                self._config.flaresolverr_max_timeout,
                _flaresolverr_proxy(self._config),
            )
        return self._flaresolverr

    # ---- lifecycle ----------------------------------------------------------

    def _on_config_changed(self, config: ServerConfig) -> None:
        """Drop the pooled session when proxy or solver settings changed."""
        if config.proxy_address() != self._proxy_address:
            self._proxy_address = config.proxy_address()
            self._discard_client()
        if self._flaresolverr_settings() != self._flaresolverr_key:
            self._flaresolverr_key = self._flaresolverr_settings()
            self._flaresolverr = None
            self._discard_client()

    def _discard_client(self) -> None:
        # connections are closed lazily by garbage collection
        self._client = None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._client = None
        if self._flaresolverr is not None:
            await self._flaresolverr.aclose()
