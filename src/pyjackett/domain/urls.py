"""URL helpers that mimic the lenient behaviour of .NET's ``Uri``."""

from __future__ import annotations

import base64
from collections.abc import Iterable
from urllib.parse import (
    parse_qsl,
    quote,
    quote_plus,
    unquote_plus,
    urljoin,
    urlsplit,
)

_SAFE_CHARS = "!#$%&'()*+,-./:;=?@[]_~"
_FORM_SAFE_CHARS = "!*()"


def url_encode(text: str | None, encoding: str = "utf-8") -> str:
    """Form-encode ``text`` like .NET's ``WebUtility.UrlEncode``."""
    if not text:
        return ""
    return quote_plus(text, safe=_FORM_SAFE_CHARS, encoding=encoding).replace("~", "%7E")


def url_decode(text: str | None, encoding: str = "utf-8") -> str:
    if not text:
        return ""
    return unquote_plus(text, encoding=encoding, errors="replace")


def build_query_string(
    pairs: Iterable[tuple[str, str]],
    encoding: str = "utf-8",
    separator: str = "&",
) -> str:
    """Join ``key=value`` pairs; only the values are encoded."""
    return separator.join(f"{key}={url_encode(value, encoding)}" for key, value in pairs)


def encode_url(url: str) -> str:
    """Percent-encode spaces and non ASCII characters, keep the rest."""
    return quote(url, safe=_SAFE_CHARS)


def resolve_url(path: str, base: str) -> str:
    """Resolve ``path`` against ``base`` and return an encoded URL."""
    return encode_url(urljoin(base, path))


def get_query_argument(url: str | None, argument: str | None) -> str | None:
    """Return one query string value of ``url`` (None when absent)."""
    if url is None or argument is None or "?" not in url:
        return None
    query = url.split("?", 1)[1].split("#", 1)[0]
    for key, value in parse_qsl(query, keep_blank_values=True):
        if key == argument:
            return value
    return None


def url_host(url: str) -> str:
    return urlsplit(url).hostname or ""


def url_scheme(url: str) -> str:
    return urlsplit(url).scheme


def url_authority(url: str) -> str:
    return urlsplit(url).netloc


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def base64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
