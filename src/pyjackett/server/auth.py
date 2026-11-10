"""Dashboard sessions (signed cookie) and API key checks."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from pyjackett.app_context import AppContext

COOKIE_NAME = "PyJackett"
SESSION_DAYS = 14
_SECONDS_PER_DAY = 86400


def _signature(context: AppContext, expires: str) -> str:
    secret = f"{context.config.api_key}{context.config.instance_id}"
    return hmac.new(
        secret.encode(), expires.encode(), hashlib.sha256
    ).hexdigest()


def create_session_cookie(context: AppContext) -> str:
    expires = str(int(time.time()) + SESSION_DAYS * _SECONDS_PER_DAY)
    return f"{expires}.{_signature(context, expires)}"


def is_valid_session(context: AppContext, cookie: str | None) -> bool:
    if not cookie or "." not in cookie:
        return False
    expires, signature = cookie.split(".", 1)
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(signature, _signature(context, expires))


def is_authenticated(context: AppContext, request: Request) -> bool:
    """True when no password is set or the session cookie is valid."""
    if not context.config.admin_password:
        return True
    return is_valid_session(context, request.cookies.get(COOKIE_NAME))


def require_dashboard_user(request: Request) -> None:
    """FastAPI dependency protecting the management API."""
    context: AppContext = request.app.state.context
    if not is_authenticated(context, request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def has_valid_api_key(context: AppContext, request: Request) -> bool:
    params = request.query_params
    key = params.get("apikey") or params.get("passkey")
    return bool(key) and hmac.compare_digest(key, context.config.api_key)
