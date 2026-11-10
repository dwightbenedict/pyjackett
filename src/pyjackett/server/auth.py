"""FastAPI glue for dashboard sessions and API key checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from pyjackett.server.deps import Context
from pyjackett.services.security import SecurityService

COOKIE_NAME = "PyJackett"


def get_security(context: Context) -> SecurityService:
    return context.security


Security = Annotated[SecurityService, Depends(get_security)]


def is_authenticated(security: SecurityService, request: Request) -> bool:
    return security.is_authenticated(request.cookies.get(COOKIE_NAME))


def require_dashboard_user(security: Security, request: Request) -> None:
    """FastAPI dependency protecting the management API."""
    if not is_authenticated(security, request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def has_valid_api_key(security: SecurityService, request: Request) -> bool:
    params = request.query_params
    key = params.get("apikey") or params.get("passkey")
    return security.is_valid_api_key(key)
