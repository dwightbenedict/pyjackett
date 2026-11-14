"""The public URL clients use to reach this server."""

from __future__ import annotations

from fastapi import Request

from pyjackett.wiring import AppContext

HTTPS_DEFAULT_PORT = 443


def _scheme(request: Request) -> str:
    """Honour the headers reverse proxies add."""
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.headers.get("front-end-https") == "on":
        return "https"
    return request.url.scheme


def server_url(context: AppContext, request: Request) -> str:
    """Base URL ending with a slash, including any base path."""
    base_path = context.server_service.base_path()
    override = (context.config.base_url_override or "").strip()
    if override:
        return f"{override}{base_path}/"
    scheme = _scheme(request)
    host_header = request.headers.get("host", "")
    host, _, port = host_header.partition(":")
    if not port:
        port = str(HTTPS_DEFAULT_PORT if scheme == "https" else request.url.port or 80)
    return f"{scheme}://{host}:{port}{base_path}/"
