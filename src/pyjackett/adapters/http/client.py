"""The per-indexer web client: throttling, Cloudflare handling, parsing."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from pyjackett.adapters.clock import SYSTEM_CLOCK, Clock
from pyjackett.adapters.http.browser_profile import impersonation_for
from pyjackett.adapters.http.flaresolverr import is_cloudflare_challenge
from pyjackett.adapters.http.request_builder import build_request_kwargs
from pyjackett.adapters.http.response_parser import (
    build_web_result,
    refresh_delay_seconds,
)
from pyjackett.adapters.http.session import HttpSession
from pyjackett.domain.cookies import merge_headers
from pyjackett.domain.http_models import WebRequest, WebResult

logger = logging.getLogger(__name__)

MAX_REFRESH_WAIT_SECONDS = 5.0
_REFRESH_STATUS = 503


class WebClient:
    """Sends requests for one indexer.

    Several indexers share one :class:`HttpSession`; this class adds what is
    specific to an indexer: the minimum delay between requests and the
    Cloudflare clearance obtained from FlareSolverr.
    """

    def __init__(
        self,
        session: HttpSession,
        clock: Clock = SYSTEM_CLOCK,
        request_delay: float = 0.0,
        emulate_browser: bool = True,
    ) -> None:
        self._session = session
        self._clock = clock
        self._request_delay = request_delay  # seconds between two requests
        self._emulate_browser = emulate_browser
        self._last_request: float | None = None
        self._clearance: dict[str, tuple[str, str | None]] = {}

    @property
    def request_delay(self) -> float:
        return self._request_delay

    def set_request_delay(self, seconds: float) -> None:
        self._request_delay = seconds

    # ---- public API ----------------------------------------------------

    async def get_result(self, request: WebRequest) -> WebResult:
        if request.emulate_browser is None:
            request.emulate_browser = self._emulate_browser
        await self._wait_for_request_delay(request)
        result = await self._fetch(request)
        self._last_request = self._clock.monotonic()
        result.request = request
        return result

    # ---- throttling --------------------------------------------------------

    async def _wait_for_request_delay(self, request: WebRequest) -> None:
        if not self._request_delay or self._last_request is None:
            return
        remaining = self._request_delay - (self._clock.monotonic() - self._last_request)
        if remaining > 0:
            logger.debug(
                "delaying request for %s by %.1f seconds",
                request.url,
                remaining,
            )
            await self._clock.sleep(remaining)

    # ---- fetching -----------------------------------------------------------

    async def _fetch(self, request: WebRequest) -> WebResult:
        result = await self._send(request)
        result = await self._follow_refresh_challenge(result)
        if self._needs_solving(result):
            return await self._solve(request)
        return result

    async def _send(self, request: WebRequest) -> WebResult:
        cookies, user_agent = self._clearance_for(request.url)
        if cookies:
            request = self._with_cookies(request, cookies)
        kwargs = build_request_kwargs(request, user_agent, self._session.impersonating)
        profile = self._clearance_profile(user_agent)
        if profile:
            kwargs["impersonate"] = profile
        response = await self._session.send(kwargs)
        return build_web_result(response, request)

    def _clearance_profile(self, user_agent: str | None) -> str | None:
        """Match the TLS fingerprint to the browser that got the clearance."""
        if not (user_agent and self._session.impersonating):
            return None
        return impersonation_for(user_agent)

    @staticmethod
    def _with_cookies(request: WebRequest, cookies: str) -> WebRequest:
        merged = merge_headers(request.cookies, cookies)
        return WebRequest(**{**vars(request), "cookies": merged})

    async def _follow_refresh_challenge(self, result: WebResult) -> WebResult:
        """Some Cloudflare setups answer 503 with a ``Refresh`` header."""
        if result.status == _REFRESH_STATUS and "refresh" in result.headers:
            wait = min(refresh_delay_seconds(result), MAX_REFRESH_WAIT_SECONDS)
            await self._clock.sleep(wait)
            result.status = 302
        return result

    # ---- Cloudflare / FlareSolverr ------------------------------------------

    def _needs_solving(self, result: WebResult) -> bool:
        return self._session.flaresolverr is not None and is_cloudflare_challenge(result)

    async def _solve(self, request: WebRequest) -> WebResult:
        solver = self._session.flaresolverr
        solution = await solver.solve(request)
        host = urlsplit(request.url).hostname or ""
        self._clearance[host] = (solution.cookies, solution.user_agent)
        return solution.result

    def _clearance_for(self, url: str) -> tuple[str | None, str | None]:
        host = urlsplit(url).hostname or ""
        return self._clearance.get(host, (None, None))
