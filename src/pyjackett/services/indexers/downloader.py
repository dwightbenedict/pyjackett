"""Downloads torrent files and images through an indexer's session."""

from __future__ import annotations

import logging

from pyjackett.domain.http_models import RequestType, WebResult
from pyjackett.services.indexers.requester import WebRequester

logger = logging.getLogger(__name__)

OK_STATUSES = frozenset({100, 200, 206})
_ESCAPES = {"(": "%28", ")": "%29", "'": "%27"}  # needed by HD-Torrents


def _is_magnet(url: str | None) -> bool:
    return bool(url) and url.startswith("magnet:")


def _escape_link(link: str) -> str:
    return "".join(_ESCAPES.get(char, char) for char in link)


class TorrentDownloader:
    """Fetches the bytes behind a result link, resolving redirects."""

    def __init__(self, requester: WebRequester) -> None:
        self._requester = requester

    async def download(
        self,
        link: str,
        method: RequestType = RequestType.GET,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Return the .torrent bytes (or the magnet link as text)."""
        if _is_magnet(link):
            return link.encode("utf-8")
        response = await self._requester.request_with_retry(
            _escape_link(link), None, method, referer, None, headers
        )
        response = await self._resolve_redirects(response)
        if _is_magnet(response.redirecting_to):
            return response.redirecting_to.encode("utf-8")
        if response.status not in OK_STATUSES:
            raise RuntimeError(self._failure_message(response))
        return response.content_bytes

    async def _resolve_redirects(self, response: WebResult) -> WebResult:
        response = await self._requester.follow_if_redirect(response)
        if response.is_redirect and not _is_magnet(response.redirecting_to):
            response = await self._requester.follow_if_redirect(response)
        return response

    @staticmethod
    def _failure_message(response: WebResult) -> str:
        if response.content_bytes:
            logger.error(
                "Failed download response:\n%s",
                response.content_bytes.decode("utf-8", errors="replace"),
            )
        target = f" => {response.redirecting_to}" if response.is_redirect else ""
        return f"Remote server returned {response.status}{target}"

    async def download_image(self, link: str, referer: str) -> WebResult:
        response = await self._requester.request(link, None, RequestType.GET, referer)
        if response.is_redirect:
            response = await self._requester.follow_if_redirect(response)
        return response
