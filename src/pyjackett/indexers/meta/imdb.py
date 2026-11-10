"""Optional IMDb title lookup (OMDb) to improve meta indexer searches.

When an OMDb key is configured, an IMDb search is repeated as a title
search on indexers without IMDb support, and results are checked against
the title so wrong matches are dropped.
"""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import urljoin

from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.http.client import WebClient
from pyjackett.http.models import WebRequest
from pyjackett.utils.text import contains_ignore_case

logger = logging.getLogger(__name__)

DEFAULT_OMDB_URL = "https://omdbapi.com"


class ImdbResolver(Protocol):
    async def title_for_id(self, imdb_id: str) -> str | None:
        """Protocol method."""


class OmdbResolver:
    """Looks up movie titles on the OMDb API."""

    def __init__(
        self, client: WebClient, api_key: str, api_url: str | None
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._api_url = api_url or DEFAULT_OMDB_URL

    async def title_for_id(self, imdb_id: str) -> str | None:
        if not imdb_id.startswith("tt"):
            imdb_id = f"tt{imdb_id}"
        url = urljoin(self._api_url, f"/?apikey={self._api_key}&i={imdb_id}")
        result = await self._client.get_result(
            WebRequest(url=url, encoding="utf-8")
        )
        try:
            return result.json().get("Title")
        except (ValueError, AttributeError):
            logger.warning("Unexpected OMDb response for %s", imdb_id)
            return None


def title_variants(title: str) -> list[str]:
    """The title with spaces, dots and underscores as word separators."""
    plain = title.replace(":", "")
    return [plain, plain.replace(" ", "."), plain.replace(" ", "_")]


class ImdbSupport:
    """Fallback queries and result filtering based on the IMDb title."""

    def __init__(self, resolver: ImdbResolver | None) -> None:
        self._resolver = resolver

    async def fallback_queries(self, query: TorznabQuery):
        """A title based query for indexers lacking IMDb search."""
        if self._resolver is None or not query.imdb_id:
            return []
        title = await self._resolver.title_for_id(query.imdb_id)
        return [query.create_fallback(title)] if title else []

    async def filter_results(
        self, query: TorznabQuery, results: list[ReleaseInfo]
    ) -> list[ReleaseInfo]:
        if self._resolver is None or not query.imdb_id:
            return results
        wanted = int("".join(c for c in query.imdb_id if c.isdigit()) or 0)
        with_id = [r for r in results if r.imdb is not None]
        perfect = [r for r in with_id if r.imdb == wanted]
        wrong = [r for r in with_id if r.imdb != wanted]
        remaining = [r for r in results if r not in perfect + wrong]
        title = await self._resolver.title_for_id(query.imdb_id)
        if title is None:
            return perfect
        variants = title_variants(title)
        matched = [
            r
            for r in remaining
            if any(contains_ignore_case(r.title, v) for v in variants)
        ]
        return perfect + matched
