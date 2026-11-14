"""Text normalisation for search terms and episode strings."""

from __future__ import annotations

import re
from datetime import datetime

from pyjackett.domain.numbers import coerce_int
from pyjackett.domain.text import is_blank

# Unicode "Pd" (dash punctuation) category
_DASHES = re.compile("[-֊־᐀᠆‐-―⸗⸚⸺⸻⹀〜〰゠︱︲﹘﹣－]+")
_SINGLE_QUOTES = re.compile("[`´‘’]")
_ALLOWED_PUNCTUATION = frozenset("-._()@/'[]+%")


def _is_safe_char(char: str) -> bool:
    return char.isalnum() or char.isspace() or char in _ALLOWED_PUNCTUATION


def sanitize_search_term(term: str | None) -> str:
    """Standardize dashes/quotes and drop characters trackers choke on."""
    term = _DASHES.sub("-", term or "")
    term = _SINGLE_QUOTES.sub("'", term)
    return "".join(char for char in term if _is_safe_char(char))


def _daily_show_date(season: int, episode: str | None) -> str | None:
    """Season ``2024`` + episode ``03/15`` is a daily show air date."""
    try:
        aired = datetime.strptime(f"{season} {episode}", "%Y %m/%d")
    except ValueError:
        return None
    return aired.strftime("%Y.%m.%d")


def episode_search_string(season: int | None, episode: str | None) -> str:
    """Build ``S01E02``-style text from season and episode values."""
    if not season:
        return ""
    daily = _daily_show_date(season, episode)
    if daily:
        return daily
    if is_blank(episode):
        return f"S{season:02d}"
    try:
        return f"S{season:02d}E{coerce_int(episode):02d}"
    except ValueError:  # e.g. searching for S01E01A
        return f"S{season:02d}E{episode}"
