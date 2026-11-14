"""Turns a :class:`WebRequest` into keyword arguments for curl_cffi."""

from __future__ import annotations

import sys
from typing import Any
from urllib.parse import quote_plus

from pyjackett import __version__
from pyjackett.http.models import RequestType, WebRequest, lookup_encoding

CHROME_USER_AGENT_LINUX = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)
CHROME_USER_AGENT_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def encode_form(pairs: list[tuple[str, str]], encoding: str | None) -> bytes:
    """URL-encode form data with a tracker specific character set."""
    codec = lookup_encoding(encoding) or "utf-8"
    text = "&".join(
        f"{quote_plus(key, encoding=codec)}="
        f"{quote_plus(value, encoding=codec)}"
        for key, value in pairs
    )
    return text.encode("ascii")


def _default_headers(request: WebRequest) -> dict[str, str]:
    """Accept headers some trackers insist on, unless the indexer set them."""
    headers = dict(request.headers)
    names = {name.lower() for name in headers}
    if "accept" not in names:
        headers["Accept"] = "*/*"
    if "accept-language" not in names:
        headers["Accept-Language"] = "*"
    return headers


def _user_agent(emulate_browser: bool) -> str:
    if not emulate_browser:
        return f"PyJackett/{__version__}"
    if sys.platform == "win32":
        return CHROME_USER_AGENT_WINDOWS
    return CHROME_USER_AGENT_LINUX


def _body(request: WebRequest, headers: dict[str, str]) -> bytes | None:
    if request.raw_body:
        return request.raw_body.encode(
            lookup_encoding(request.encoding) or "utf-8"
        )
    if request.type is RequestType.POST:
        headers.setdefault("Content-Type", FORM_CONTENT_TYPE)
        return encode_form(request.post_data or [], request.encoding)
    return None


def build_request_kwargs(
    request: WebRequest,
    user_agent: str | None = None,
    impersonating: bool = False,
) -> dict[str, Any]:
    """Return ``method``, ``url``, ``headers`` and ``content`` (curl_cffi).

    When ``impersonating``, browser requests keep only the headers the
    indexer or a Cloudflare clearance asked for; curl_cffi sends the
    User-Agent and Accept headers that match its TLS fingerprint.
    """
    client_sets_headers = impersonating and bool(request.emulate_browser)
    if client_sets_headers:
        headers = dict(request.headers)
    else:
        headers = _default_headers(request)
    lowered = {name.lower() for name in headers}
    if "user-agent" not in lowered and (user_agent or not client_sets_headers):
        headers["User-Agent"] = user_agent or _user_agent(
            bool(request.emulate_browser)
        )
    if request.cookies and request.cookies.strip():
        headers["Cookie"] = request.cookies
    if request.referer:
        headers["Referer"] = request.referer
    body = _body(request, headers)
    is_post = body is not None
    return {
        "method": "POST" if is_post else "GET",
        "url": request.url,
        "headers": headers,
        "content": body,
    }
