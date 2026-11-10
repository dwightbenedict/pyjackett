"""Turns an httpx response into a :class:`WebResult`."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx

from pyjackett.http.models import WebRequest, WebResult
from pyjackett.utils.cookies import set_cookie_to_pair

_REFRESH_URL = re.compile(r"^(.*?url)=(.*?)(?:;|$)", re.IGNORECASE)


def _collect_headers(response: httpx.Response) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for name, value in response.headers.multi_items():
        headers.setdefault(name.lower(), []).append(value)
    return headers


def flatten_set_cookies(set_cookies: list[str]) -> str | None:
    """Reduce Set-Cookie headers to one ``name=value; ...`` string.

    When a cookie is set several times the last occurrence wins.
    """
    pairs: dict[str, str] = {}
    for value in set_cookies:
        name, separator, _ = value.partition("=")
        if separator:
            pairs[name] = set_cookie_to_pair(value)
    return " ".join(pairs.values()) if pairs else None


def _refresh_target(refresh_header: str | None) -> str | None:
    if not refresh_header:
        return None
    match = _REFRESH_URL.match(refresh_header)
    return match.group(2) if match else None


def _redirect_target(headers: dict[str, list[str]]) -> str | None:
    location = (headers.get("location") or [None])[0]
    refresh = (headers.get("refresh") or [None])[0]
    return location or _refresh_target(refresh)


def build_web_result(response: httpx.Response, request: WebRequest):
    """Convert ``response``; relative redirects become absolute."""
    headers = _collect_headers(response)
    target = _redirect_target(headers)
    return WebResult(
        status=response.status_code,
        content_bytes=response.content,
        headers=headers,
        cookies=flatten_set_cookies(headers.get("set-cookie", [])),
        redirecting_to=urljoin(request.url, target) if target else None,
        request=request,
    )


def refresh_delay_seconds(result: WebResult) -> float:
    """Seconds announced by a ``Refresh: N; url=...`` challenge header."""
    refresh = result.header("refresh") or ""
    head = refresh.split(";", 1)[0].strip()
    try:
        return float(head)
    except ValueError:
        return 0.0
