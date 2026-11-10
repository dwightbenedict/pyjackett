"""Client for the FlareSolverr API (Cloudflare challenge solver)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Protocol

import httpx

from pyjackett.http.models import RequestType, WebRequest, WebResult

logger = logging.getLogger(__name__)

_CHALLENGE_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "attention required",
)
_CHALLENGE_STATUSES = (403, 503)
_TIMEOUT_MARGIN_SECONDS = 10


@dataclass
class Solution:
    """What FlareSolverr returned for a solved challenge."""

    result: WebResult
    cookies: str
    user_agent: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


def is_cloudflare_challenge(result: WebResult) -> bool:
    """True if ``result`` looks like a Cloudflare interstitial page."""
    server = (result.header("server") or "").lower()
    if "cloudflare" not in server or result.status not in _CHALLENGE_STATUSES:
        return False
    body = result.content_string.lower()
    return any(marker in body for marker in _CHALLENGE_MARKERS)


def _endpoint(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    return base_url if base_url.endswith("/v1") else f"{base_url}/v1"


def _cookie_list(header: str | None) -> list[dict[str, str]]:
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header or "")
    except Exception:  # malformed cookie headers are simply ignored
        return []
    return [
        {"name": name, "value": morsel.value} for name, morsel in jar.items()
    ]


def _payload(request: WebRequest, max_timeout: int, proxy: dict | None):
    command = (
        "request.post" if request.type is RequestType.POST else ("request.get")
    )
    payload: dict = {
        "cmd": command,
        "url": request.url,
        "maxTimeout": max_timeout,
    }
    if request.type is RequestType.POST:
        pairs = request.post_data or []
        payload["postData"] = "&".join(f"{k}={v}" for k, v in pairs)
    cookies = _cookie_list(request.cookies)
    if cookies:
        payload["cookies"] = cookies
    if proxy:
        payload["proxy"] = proxy
    return payload


def _solution_cookies(solution: dict) -> str:
    return "; ".join(
        f"{c['name']}={c['value']}" for c in solution.get("cookies", [])
    )


class ChallengeSolver(Protocol):
    """Gets a page past a Cloudflare challenge."""

    async def solve(self, request: WebRequest) -> Solution:
        """Protocol method."""

    async def aclose(self) -> None:
        """Protocol method."""


SolverFactory = Callable[[str, int, "dict | None"], ChallengeSolver]


class FlareSolverrClient:
    """Asks a FlareSolverr instance to fetch a page like a real browser."""

    def __init__(
        self,
        url: str,
        max_timeout: int = 55000,
        proxy: dict | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._endpoint = _endpoint(url)
        self._max_timeout = max_timeout
        self._proxy = proxy
        timeout = max_timeout / 1000 + _TIMEOUT_MARGIN_SECONDS
        self._http = client_factory(timeout=timeout, transport=transport)

    async def solve(self, request: WebRequest) -> Solution:
        payload = _payload(request, self._max_timeout, self._proxy)
        response = await self._http.post(self._endpoint, json=payload)
        body = response.json()
        if body.get("status") != "ok":
            raise RuntimeError(
                f"FlareSolverr failed: {body.get('message', 'unknown error')}"
            )
        return self._to_solution(body["solution"], request)

    @staticmethod
    def _to_solution(solution: dict, request: WebRequest) -> Solution:
        cookies = _solution_cookies(solution)
        text = solution.get("response", "")
        result = WebResult(
            status=int(solution.get("status", 200)),
            content_bytes=text.encode("utf-8"),
            headers={
                k.lower(): [v] for k, v in solution.get("headers", {}).items()
            },
            cookies=cookies or None,
            request=request,
        )
        result.content_string = text  # already decoded by the browser
        logger.debug("FlareSolverr solved %s (%s)", request.url, result.status)
        return Solution(result, cookies, solution.get("userAgent"))

    async def aclose(self) -> None:
        await self._http.aclose()
