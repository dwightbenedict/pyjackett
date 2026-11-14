"""Plain string helpers."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_INVALID_FILENAME_CHARS = '<>:"/\\|?*' + "".join(map(chr, range(32)))
_FANCY_REPLACEMENTS = {'"': "”", "'": "’", "/": "⁄"}
_COMMON_WORDS = frozenset({"and", "the", "an"})


def is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def normalize_space(value: str | None) -> str:
    """Trim a value; ``None`` becomes the empty string."""
    return value.strip() if value else ""


def normalize_multi_spaces(value: str | None) -> str:
    return _WHITESPACE.sub(" ", normalize_space(value))


def strip_diacritics(value: str) -> str:
    """Replace accented characters by their base character."""
    decomposed = unicodedata.normalize("NFD", value)
    kept = (c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", "".join(kept))


def contains_ignore_case(haystack: str, needle: str) -> bool:
    """Case and diacritic insensitive substring test."""
    return strip_diacritics(needle).casefold() in strip_diacritics(haystack).casefold()


def _replace_invalid_char(char: str, replacement: str | None, fancy: bool):
    if fancy and char in _FANCY_REPLACEMENTS:
        return _FANCY_REPLACEMENTS[char]
    return replacement or ""


def make_valid_file_name(text: str, replacement: str | None = "_", fancy: bool = True) -> str:
    """Replace characters that are not allowed in file names."""
    out = [
        _replace_invalid_char(char, replacement, fancy) if char in _INVALID_FILENAME_CHARS else char
        for char in text
    ]
    return "".join(out) or "_"


def significant_words(text: str) -> list[str]:
    """Split ``text`` into search words, dropping noise words."""
    parts = re.split(r"[^\w]+", text)
    return [part for part in parts if len(part) > 1 and part.lower() not in _COMMON_WORDS]
