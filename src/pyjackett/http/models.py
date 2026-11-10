"""Value objects describing one HTTP exchange with a tracker."""

from __future__ import annotations

import codecs
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CHARSET = re.compile(r"charset=([\w-]+)", re.IGNORECASE)


class RequestType(StrEnum):
    GET = "GET"
    POST = "POST"


# .NET encoding names Python spells differently
_ENCODING_ALIASES = {"windows-874": "cp874"}


def lookup_encoding(name: str | None) -> str | None:
    """Return a Python codec name for ``name`` (None if unknown)."""
    if not name:
        return None
    try:
        return codecs.lookup(_ENCODING_ALIASES.get(name.lower(), name)).name
    except LookupError:
        return None


@dataclass
class WebRequest:
    """Everything needed to issue one request."""

    url: str
    type: RequestType = RequestType.GET
    post_data: list[tuple[str, str]] = field(default_factory=list)
    cookies: str | None = None
    referer: str | None = None
    raw_body: str | None = None
    emulate_browser: bool | None = None
    encoding: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup."""
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return None


@dataclass
class WebResult:
    """The response of a tracker, with cookies already flattened."""

    status: int = 0
    content_bytes: bytes = b""
    headers: dict[str, list[str]] = field(default_factory=dict)
    cookies: str | None = None
    redirecting_to: str | None = None
    request: WebRequest | None = None
    _text: str | None = field(default=None, repr=False)

    @property
    def encoding(self) -> str:
        """Request encoding, then the response charset, then UTF-8."""
        if self.request is not None:
            requested = lookup_encoding(self.request.encoding)
            if requested:
                return requested
        content_type = (self.headers.get("content-type") or [""])[0]
        match = _CHARSET.search(content_type)
        return (match and lookup_encoding(match.group(1))) or "utf-8"

    @property
    def content_string(self) -> str:
        if self._text is None:
            self._text = self.content_bytes.decode(
                self.encoding, errors="replace"
            )
        return self._text

    @content_string.setter
    def content_string(self, value: str) -> None:
        self._text = value

    def json(self) -> Any:
        """The body decoded as JSON."""
        return json.loads(self.content_string)

    def header(self, name: str) -> str | None:
        values = self.headers.get(name.lower())
        return values[0] if values else None

    @property
    def has_http_error(self) -> bool:
        return self.status >= 400

    @property
    def has_http_server_error(self) -> bool:
        return self.status >= 500

    @property
    def is_redirect(self) -> bool:
        return self.status in REDIRECT_STATUSES or "refresh" in self.headers
