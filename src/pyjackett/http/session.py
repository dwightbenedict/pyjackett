"""Shared HTTP connection pool, proxy and certificate pinning."""

from __future__ import annotations

import logging
from collections.abc import Callable
from http.cookiejar import CookieJar
from typing import Any
from urllib.parse import urlsplit

import httpx

from pyjackett.config.server_config import ProxyType, ServerConfig
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.flaresolverr import (
    ChallengeSolver,
    FlareSolverrClient,
    SolverFactory,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 100.0
MAX_CONNECTIONS_PER_HOST = 20


class PinnedCertificateError(Exception):
    """The server presented a certificate that is not pinned for the host."""


class _NullCookieJar(CookieJar):
    """Cookie jar that never stores anything.

    Cookies are managed by the indexers themselves (as header strings), so
    httpx must not keep any state between requests.
    """

    def set_cookie(self, cookie) -> None:
        return None

    def extract_cookies(self, response, request) -> None:
        return None


def _proxy_settings(config: ServerConfig) -> str | None:
    """Proxy URL for httpx (httpcore has no SOCKS4 support)."""
    if config.proxy_type is ProxyType.SOCKS4 and config.proxy_address():
        raise ValueError("SOCKS4 proxies are not supported, use SOCKS5")
    return config.proxy_address()


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
    """Owns the httpx clients used by every indexer's web client."""

    def __init__(
        self,
        config: ServerConfig,
        trusted_certificates: TrustedCertificates | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        solver_factory: SolverFactory = FlareSolverrClient,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._config = config
        self._certificates = trusted_certificates or TrustedCertificates()
        self._transport = transport
        self._timeout = timeout
        self._solver_factory = solver_factory
        self._client_factory = client_factory
        self._proxy_address = config.proxy_address()
        self._flaresolverr_key = self._flaresolverr_settings()
        self._flaresolverr: ChallengeSolver | None = None
        self._clients: dict[bool, httpx.AsyncClient] = {}
        config.subscribe(self._on_config_changed)

    # ---- clients ----------------------------------------------------------

    def _client(self, verify: bool) -> httpx.AsyncClient:
        if verify not in self._clients:
            self._clients[verify] = self._build_client(verify)
        return self._clients[verify]

    def _build_client(self, verify: bool) -> httpx.AsyncClient:
        options: dict[str, Any] = {
            "verify": verify,
            "timeout": self._timeout,
            "follow_redirects": False,
            "cookies": httpx.Cookies(_NullCookieJar()),
            "limits": httpx.Limits(
                max_connections=MAX_CONNECTIONS_PER_HOST * 5,
                max_keepalive_connections=MAX_CONNECTIONS_PER_HOST,
            ),
        }
        if self._transport is not None:
            options["transport"] = self._transport
        else:
            options["proxy"] = _proxy_settings(self._config)
        return self._client_factory(**options)

    # ---- sending ----------------------------------------------------------

    async def send(self, request_kwargs: dict[str, Any]) -> httpx.Response:
        """Send one request; pinned hosts get certificate verification."""
        host = urlsplit(request_kwargs["url"]).hostname or ""
        pinned = self._certificates.has_pins_for(host)
        client = self._client(verify=not pinned)
        async with client.stream(**request_kwargs) as response:
            if pinned:
                self._assert_pinned(host, response)
            await response.aread()
        return response

    def _assert_pinned(self, host: str, response: httpx.Response) -> None:
        stream = response.extensions.get("network_stream")
        ssl_object = stream.get_extra_info("ssl_object") if stream else None
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
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
        """Drop pooled clients when the proxy or solver settings changed."""
        if config.proxy_address() != self._proxy_address:
            self._proxy_address = config.proxy_address()
            self._discard_clients()
        if self._flaresolverr_settings() != self._flaresolverr_key:
            self._flaresolverr_key = self._flaresolverr_settings()
            self._flaresolverr = None
            self._discard_clients()

    def _discard_clients(self) -> None:
        # connections are closed lazily by garbage collection
        self._clients = {}

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients = {}
        if self._flaresolverr is not None:
            await self._flaresolverr.aclose()
