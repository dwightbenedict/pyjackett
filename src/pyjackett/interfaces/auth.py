"""FastAPI glue for dashboard sessions and API key checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from pyjackett.interfaces.deps import Context
from pyjackett.services.security import (
    SECONDS_PER_DAY,
    SESSION_DAYS,
    SecurityService,
)

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


def require_protected_session(security: Security, request: Request) -> None:
    """Dependency for routes that hand out or replace secrets.

    A dashboard without a password is open to anyone who can reach the
    server, so these routes stay closed until an admin password is set and
    the caller has logged in with it.
    """
    if not security.has_admin_password:
        raise HTTPException(
            status_code=403,
            detail="Set an admin password in the dashboard first",
        )
    require_dashboard_user(security, request)


def has_valid_api_key(security: SecurityService, request: Request) -> bool:
    params = request.query_params
    key = params.get("apikey") or params.get("passkey")
    return security.is_valid_api_key(key)


def require_api_access(security: Security, request: Request) -> None:
    """FastAPI dependency: a valid API key or a dashboard session."""
    if has_valid_api_key(security, request) or is_authenticated(
        security, request
    ):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def set_session_cookie(response: Response, security: SecurityService) -> None:
    """Log the caller in to the dashboard for the usual session length."""
    response.set_cookie(
        COOKIE_NAME,
        security.create_session_cookie(),
        max_age=SESSION_DAYS * SECONDS_PER_DAY,
        httponly=True,
        samesite="lax",
    )
