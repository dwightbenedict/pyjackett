"""Sites whose current address is published on a page we can read."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from pyjackett.domain.http_models import WebRequest
from pyjackett.domain.urls import url_host
from pyjackett.services.ports import Clock, HttpClient

logger = logging.getLogger(__name__)

RECHECK_SECONDS = 30 * 60
RETRY_SECONDS = 5 * 60
_NOT_FOUND = (404, 410)
_SERVER_ERROR = 500

Extractor = Callable[[str], list[str]]

_HREF = re.compile(r'href="(https?://[^"]+)"', re.IGNORECASE)
_NUMBERED = re.compile(r"^\s*\d+\)\s+(\S+)(.*)$", re.MULTILINE)


def hrefs_off_site(page_url: str) -> Extractor:
    """Links on the page that lead somewhere other than the page's site."""
    # the page also links to its own sister domains (.my, .cc, ...)
    site = (url_host(page_url) or "").split(".")[-2]

    def extract(text: str) -> list[str]:
        roots = (
            match.rstrip("/") + "/"
            for match in _HREF.findall(text)
            if urlsplit(match).path in ("", "/")  # not a stylesheet or such
        )
        return [link for link in roots if site not in url_host(link)]

    return extract


def numbered_domains(text: str) -> list[str]:
    """Lines such as ``1) example.to`` of an official domains list."""
    domains = []
    for host, note in _NUMBERED.findall(text):
        if "STOP USING" in note or host.endswith(".onion"):
            continue
        domains.append(f"https://{host}/")
    return domains


@dataclass(frozen=True)
class ListedLinks:
    """Where to read a site's current addresses, and which are its own."""

    pages: tuple[str, ...]
    extract: Extractor
    owned: re.Pattern[str] | None = None

    def owns(self, link: str) -> bool:
        return bool(self.owned and self.owned.search(url_host(link)))


# Indexer id -> the pages that list its current addresses.
LISTED_LINKS: dict[str, ListedLinks] = {
    "1337x": ListedLinks(
        pages=("https://1337x-status.org/",),
        extract=numbered_domains,
        owned=re.compile(r"(^|\.)x?1337x\."),
    ),
    "world-torrent": ListedLinks(
        pages=tuple(
            f"https://www.torrent-site.my/{name}"
            for name in (
                "Darkfox",
                "Workino",
                "Vidlox",
                "Wikibox",
                "Worldivx",
                "Sharkibox",
                "Oxtorrent",
                "Torrent911",
            )
        ),
        extract=hrefs_off_site("https://www.torrent-site.my/"),
    ),
}


def listed_links_for(indexer_id: str) -> ListedLinks | None:
    return LISTED_LINKS.get(indexer_id)


class ListedLinkFollower:
    """Finds a working address once the one in use stops answering."""

    def __init__(self, source: ListedLinks, client: HttpClient, clock: Clock) -> None:
        self._source = source
        self._client = client
        self._clock = clock
        self._next_check = 0.0

    def owns(self, link: str) -> bool:
        return self._source.owns(link)

    async def replacement_for(self, current: str) -> str | None:
        """A working address if ``current`` is down, else None."""
        now = self._clock.time()
        if now < self._next_check:
            return None
        self._next_check = now + RECHECK_SECONDS
        if await self._answers(current):
            return None
        for candidate in await self._candidates():
            if candidate != current and await self._answers(candidate):
                return candidate
        self._next_check = now + RETRY_SECONDS
        return None

    async def _candidates(self) -> list[str]:
        found: list[str] = []
        for page in self._source.pages:
            text = await self._read(page)
            for link in self._source.extract(text):
                if link not in found:
                    found.append(link)
        return found

    async def _read(self, url: str) -> str:
        try:
            result = await self._client.get_result(WebRequest(url=url))
        except Exception as error:
            logger.debug("could not read %s: %s", url, error)
            return ""
        return result.content_string if result.status < _SERVER_ERROR else ""

    async def _answers(self, link: str) -> bool:
        """True for anything but a dead host; a 403 is just Cloudflare."""
        try:
            result = await self._client.get_result(WebRequest(url=link))
        except Exception as error:
            logger.debug("%s does not answer: %s", urlsplit(link).hostname, error)
            return False
        return 0 < result.status < _SERVER_ERROR and (result.status not in _NOT_FOUND)
