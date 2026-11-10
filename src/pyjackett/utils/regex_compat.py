"""Regular expressions with .NET semantics.

Indexer definitions were written against .NET's regex engine: they use
Unicode properties (``\\p{L}``), atomic groups and ``$1`` style replacement
strings. The third party ``regex`` module understands the pattern syntax;
this module adds the replacement syntax.
"""

from __future__ import annotations

import functools

import regex

_REPLACEMENT_TOKEN = regex.compile(r"\$(?:(\$)|(&)|(\d+)|\{(\w+)\})")


@functools.lru_cache(maxsize=2048)
def compile_pattern(pattern: str) -> regex.Pattern:
    return regex.compile(pattern)


def _group_text(match: regex.Match, key: int | str) -> str | None:
    """Text of a group, or None if the pattern has no such group."""
    try:
        return match.group(key) or ""
    except (IndexError, regex.error):
        return None


def _expand_token(replacement_match: regex.Match, match: regex.Match) -> str:
    dollar, ampersand, number, name = replacement_match.groups()
    literal = replacement_match.group(0)
    if dollar:
        return "$"
    if ampersand:
        return match.group(0)
    if number is not None:
        text = _group_text(match, int(number))
    else:
        key = int(name) if name.isdigit() else name
        text = _group_text(match, key)
    return literal if text is None else text


def expand_replacement(match: regex.Match, replacement: str) -> str:
    """Expand ``$1``, ``${name}``, ``$&`` and ``$$`` in ``replacement``."""
    if "$" not in replacement:
        return replacement
    return _REPLACEMENT_TOKEN.sub(
        lambda token: _expand_token(token, match), replacement
    )


def replace_all(pattern: str, replacement: str, text: str) -> str:
    """``Regex.Replace`` equivalent."""
    compiled = compile_pattern(pattern)
    return compiled.sub(lambda m: expand_replacement(m, replacement), text)


def first_group(pattern: str, text: str) -> str:
    """Value of group 1 of the first match, or "" when nothing matched."""
    match = compile_pattern(pattern).search(text)
    if match is None:
        return ""
    return _group_text(match, 1) or ""
