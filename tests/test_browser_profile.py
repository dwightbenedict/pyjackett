"""Clearance requests present the TLS fingerprint of the solving browser."""

from __future__ import annotations

import fakes
from pyjackett.config.server_config import ServerConfig
from pyjackett.http.browser_profile import impersonation_for
from pyjackett.http.client import WebClient
from pyjackett.http.flaresolverr import Solution
from pyjackett.http.models import WebRequest, WebResult
from pyjackett.http.session import HttpSession

PROFILES = ["chrome131", "chrome133a", "chrome142", "chrome152", "firefox144"]
SOLVED_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


def test_profile_is_the_newest_one_not_newer_than_the_browser():
    assert impersonation_for("x Chrome/145.0.0.0 y", PROFILES) == "chrome142"
    assert impersonation_for("x Chrome/152.0.0.0 y", PROFILES) == "chrome152"
    assert impersonation_for("x Chrome/200.0 y", PROFILES) == "chrome152"
    assert impersonation_for("Firefox/150.0", PROFILES) == "firefox144"


def test_profile_is_unknown_for_other_or_too_old_browsers():
    assert impersonation_for("Mozilla Safari/605", PROFILES) is None
    assert impersonation_for("Chrome/100.0.0.0", PROFILES) is None


class FakeSolver:
    def __init__(self, request_url: str) -> None:
        self.url = request_url

    async def solve(self, request: WebRequest) -> Solution:
        result = WebResult(status=200, content_bytes=b"solved")
        return Solution(result, "cf_clearance=abc", SOLVED_USER_AGENT)

    async def aclose(self) -> None:
        return None


async def test_requests_after_a_solve_match_the_solvers_browser():
    seen = []

    def handler(request: fakes.Request) -> fakes.Response:
        seen.append(request.headers)
        if len(seen) == 1:
            return fakes.Response(
                503,
                "<title>Just a moment...</title>",
                headers={"server": "cloudflare"},
            )
        return fakes.Response(200, "ok")

    profiles = []

    class RecordingSession(fakes.MockSession):
        async def request(self, method, url, **options):
            profiles.append(options.get("impersonate"))
            return await super().request(method, url, **options)

    def client_factory(**kwargs):
        return RecordingSession(handler, **kwargs)

    session = HttpSession(
        ServerConfig(flaresolverr_url="http://solver.test"),
        client_factory=client_factory,
        solver_factory=lambda url, timeout, proxy: FakeSolver(url),
    )
    client = WebClient(session)
    request = WebRequest(url="http://tracker.test/", emulate_browser=True)
    await client.get_result(request)
    await client.get_result(request)
    assert seen[1]["User-Agent"] == SOLVED_USER_AGENT
    assert seen[1]["Cookie"] == "cf_clearance=abc"
    assert "Accept" not in seen[1]
    assert profiles[0] is None  # the session default applies until a solve
    assert profiles[1] == "chrome145"
    await session.aclose()
