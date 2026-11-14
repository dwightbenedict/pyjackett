"""A minimal JSONPath, enough for ``JToken.SelectToken`` style selectors.

Supported: optional leading ``$``, ``.name``, ``['name']``, ``[n]`` (also
negative), ``[*]``, ``.*`` and recursive descent ``..name``.
"""

from __future__ import annotations

import json
import re
from typing import Any

MISSING: Any = object()  # distinguishes "not found" from a JSON null

_SEGMENT = re.compile(
    r"""
    (?P<recursive>\.\.)(?P<rname>[^.\[]+|\*)
    |\.(?P<name>[^.\[]+)
    |\[\s*'(?P<squote>[^']*)'\s*\]
    |\[\s*"(?P<dquote>[^"]*)"\s*\]
    |\[\s*(?P<index>-?\d+)\s*\]
    |\[\s*(?P<wild>\*)\s*\]
    """,
    re.VERBOSE,
)


def _tokenize(path: str) -> list[tuple[str, str]]:
    """Split ``path`` into (kind, value) segments."""
    path = path.strip()
    if path.startswith("$"):
        path = path[1:]
    if path and not path.startswith((".", "[")):
        path = "." + path
    segments: list[tuple[str, str]] = []
    position = 0
    while position < len(path):
        match = _SEGMENT.match(path, position)
        if match is None:
            raise ValueError(f"Unexpected character in JSONPath: {path!r}")
        position = match.end()
        segments.append(_segment_of(match))
    return segments


def _segment_of(match: re.Match) -> tuple[str, str]:
    if match.group("recursive"):
        return ("recursive", match.group("rname"))
    for kind in ("name", "squote", "dquote", "index", "wild"):
        value = match.group(kind)
        if value is not None:
            return ("name" if kind in ("squote", "dquote") else kind, value)
    raise ValueError("Empty JSONPath segment")


def _descendants(value: Any):
    """Yield ``value`` and everything below it."""
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _descendants(child)
    elif isinstance(value, list):
        for child in value:
            yield from _descendants(child)


def _children(value: Any, kind: str, key: str):
    if kind == "name":
        if isinstance(value, dict) and key in value:
            yield value[key]
    elif kind == "index":
        if isinstance(value, list) and -len(value) <= int(key) < len(value):
            yield value[int(key)]
    elif kind == "wild":
        if isinstance(value, dict):
            yield from value.values()
        elif isinstance(value, list):
            yield from value
    elif kind == "recursive":
        for node in _descendants(value):
            if key == "*":
                yield from _children(node, "wild", "")
            else:
                yield from _children(node, "name", key)


def select_tokens(root: Any, path: str) -> list[Any]:
    """Every value matched by ``path`` (JSON nulls included)."""
    current = [root]
    for kind, key in _tokenize(path):
        if kind == "name" and key == "*":
            kind = "wild"
        current = [
            child for node in current for child in _children(node, kind, key)
        ]
    return current


def select_token(root: Any, path: str) -> Any:
    """First value matched by ``path`` or :data:`MISSING`."""
    matches = select_tokens(root, path)
    return matches[0] if matches else MISSING


def token_to_string(value: Any) -> str | None:
    """Text of a JSON value the way ``JToken.ToString()`` renders it."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)
