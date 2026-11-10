"""Dashboard pages, login/logout and the health check."""

from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from pyjackett.app_context import AppContext
from pyjackett.config.paths import BUNDLED_WEB_DIR
from pyjackett.server.auth import COOKIE_NAME, is_authenticated
from pyjackett.server.deps import Context
from pyjackett.services.security import SECONDS_PER_DAY, SESSION_DAYS

router = APIRouter()
BASE_PATH_PLACEHOLDER = "__BASE_PATH__"


def _page(name: str, base_path: str) -> HTMLResponse:
    text = (BUNDLED_WEB_DIR / name).read_text(encoding="utf-8")
    return HTMLResponse(
        text.replace(BASE_PATH_PLACEHOLDER, base_path),
        headers={"Cache-Control": "no-store"},
    )


def _redirect(context: AppContext, path: str) -> RedirectResponse:
    return RedirectResponse(
        f"{context.server_service.base_path()}{path}", status_code=303
    )


def _with_session(context: AppContext, response: RedirectResponse):
    response.set_cookie(
        COOKIE_NAME,
        context.security.create_session_cookie(),
        max_age=SESSION_DAYS * SECONDS_PER_DAY,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/health")
@router.head("/health")
async def health():
    return JSONResponse({"status": "OK"})


@router.get("/")
async def root(context: Context):
    return _redirect(context, "/UI/Dashboard")


@router.get("/UI/Login")
async def login_page(request: Request, context: Context):
    if is_authenticated(context.security, request):
        return _with_session(context, _redirect(context, "/UI/Dashboard"))
    return _page("login.html", context.server_service.base_path())


@router.post("/UI/Login")
@router.post("/UI/Dashboard")
async def login(request: Request, context: Context):
    form = parse_qs((await request.body()).decode("utf-8"))
    password = (form.get("password") or [""])[0]
    if context.security.check_authorised(password):
        return _with_session(context, _redirect(context, "/UI/Dashboard"))
    return _redirect(context, "/UI/Login?error=1")


@router.get("/UI/Dashboard")
async def dashboard(request: Request, context: Context):
    if request.query_params.get("logout", "").lower() == "true":
        return _redirect(context, "/UI/Logout")
    if not is_authenticated(context.security, request):
        return _redirect(context, "/UI/Login")
    return _page("index.html", context.server_service.base_path())


@router.get("/UI/Logout")
async def logout(context: Context):
    response = _redirect(context, "/UI/Login")
    response.delete_cookie(COOKIE_NAME)
    return response
