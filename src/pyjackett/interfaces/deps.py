"""FastAPI dependencies shared by the route modules."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from pyjackett.wiring import AppContext


def get_context(request: Request) -> AppContext:
    return request.app.state.context


Context = Annotated[AppContext, Depends(get_context)]
