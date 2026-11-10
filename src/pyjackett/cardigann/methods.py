"""The ``method`` values a definition may use, parsed once into enums."""

from __future__ import annotations

from enum import StrEnum

from pyjackett.http.models import RequestType


class LoginMethod(StrEnum):
    POST = "post"
    FORM = "form"
    COOKIE = "cookie"
    GET = "get"
    ONEURL = "oneurl"


def request_type(method: str | None) -> RequestType:
    """POST when the definition says so (any case), else GET."""
    if (method or "").lower() == "post":
        return RequestType.POST
    return RequestType.GET
