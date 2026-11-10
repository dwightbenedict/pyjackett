"""The per-indexer web client: throttling, Cloudflare handling, parsing."""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlsplit

from pyjackett.http.flaresolverr import is_cloudflare_challenge
from pyjackett.http.models import WebRequest, WebResult
from pyjackett.http.request_builder import build_request_kwargs
from pyjackett.http.response_parser import (
    build_web_result,
    refresh_delay_seconds,
)
from pyjackett.http.session import HttpSession
from pyjackett.utils.cookies import merge_headers

logger = logging.getLogger(__name__)

MAX_REFRESH_WAIT_SECONDS = 5.0
_REFRESH_STATUS = 503


class WebClient:
    """Sends requests for one indexer.

    Several indexers share one :class:`HttpSession`; this class adds what is
    specific to an indexer: the minimum delay between requests and the
    Cloudflare clearance obtained from FlareSolverr.
    """

    def __init__(self, session: HttpSession) -> None:
        self._session = session
        self.request_delay = 0.0  # seconds between two requests
        self.emulate_browser = True
        self._last_request = 0.0
        self._clearance: dict[str, tuple[str, str | None]] = {}

    # ---- public API ----------------------------------------------------

    async def get_result(self, request: WebRequest) -> WebResult:
        if request.emulate_browser is None:
            request.emulate_browser = self.emulate_browser
        await self._wait_for_request_delay(request)
        result = await self._fetch(request)
        self._last_request = time.monotonic()
        result.request = request
        return result

    # ---- throttling --------------------------------------------------------

    async def _wait_for_request_delay(self, request: WebRequest) -> None:
        if not self.request_delay:
            return
        remaining = self.request_delay - (
            time.monotonic() - self._last_request
        )
        if remaining > 0:
            logger.debug(
                "delaying request for %s by %.1f seconds",
                request.url,
                remaining,
            )
            await asyncio.sleep(remaining)

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
        kwargs = build_request_kwargs(request, user_agent)
        response = await self._session.send(kwargs)
        return build_web_result(response, request)

    @staticmethod
    def _with_cookies(request: WebRequest, cookies: str) -> WebRequest:
        merged = merge_headers(request.cookies, cookies)
        return WebRequest(**{**vars(request), "cookies": merged})

    async def _follow_refresh_challenge(self, result: WebResult) -> WebResult:
        """Some Cloudflare setups answer 503 with a ``Refresh`` header."""
        if result.status == _REFRESH_STATUS and "refresh" in result.headers:
            wait = min(refresh_delay_seconds(result), MAX_REFRESH_WAIT_SECONDS)
            await asyncio.sleep(wait)
            result.status = 302
        return result

    # ---- Cloudflare / FlareSolverr ------------------------------------------

    def _needs_solving(self, result: WebResult) -> bool:
        return (
            self._session.flaresolverr is not None
            and is_cloudflare_challenge(result)
        )

    async def _solve(self, request: WebRequest) -> WebResult:
        solver = self._session.flaresolverr
        solution = await solver.solve(request)
        host = urlsplit(request.url).hostname or ""
        self._clearance[host] = (solution.cookies, solution.user_agent)
        return solution.result

    def _clearance_for(self, url: str) -> tuple[str | None, str | None]:
        host = urlsplit(url).hostname or ""
        return self._clearance.get(host, (None, None))
