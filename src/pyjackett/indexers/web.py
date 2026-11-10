"""Base class for indexers that talk to a tracker over HTTP."""

from __future__ import annotations

import logging

from pyjackett.config.indexer_config import ConfigurationData
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.http.models import RequestType, WebResult
from pyjackett.indexers.base import BaseIndexer
from pyjackett.indexers.dependencies import IndexerDependencies
from pyjackett.indexers.downloader import TorrentDownloader
from pyjackett.indexers.requester import WebRequester

logger = logging.getLogger(__name__)

DEFAULT_RETRY_ATTEMPTS = 2


class BaseWebIndexer(BaseIndexer):
    """Adds a web client, cookie handling and torrent downloads."""

    def __init__(
        self,
        dependencies: IndexerDependencies,
        config_data: ConfigurationData | None = None,
        download_base: str = "",
    ) -> None:
        super().__init__(dependencies, config_data)
        self.client = dependencies.client_factory()
        self.requester = WebRequester(
            self.client, self, self.retry_attempts, self._clock
        )
        self._downloader = TorrentDownloader(self.requester)
        self.download_url_base = download_base

    # ---- retries ------------------------------------------------------------

    @property
    def default_retry_attempts(self) -> int:
        return DEFAULT_RETRY_ATTEMPTS

    def retry_attempts(self) -> int:
        """User configured number of retries, else the indexer default."""
        item = self.config_data.get_dynamic("retryAttempts")
        value = getattr(item, "value", None)
        if value is not None and str(value).isdigit() and int(value) > 0:
            return int(value)
        return self.default_retry_attempts

    # ---- downloads ----------------------------------------------------------

    def unclean_link(self, link: str) -> str:
        """Re-attach the base removed from links before they were exposed."""
        base = self.download_url_base
        if not base or link.startswith(base):
            return link
        return base + link

    def clean_link(self, link: str | None) -> str | None:
        """Strip the download base from links to shorten the exposed URL."""
        base = self.download_url_base
        if link and base and link.startswith(base):
            return link[len(base) :]
        return link

    def _post_process(
        self, query: TorznabQuery, releases: list[ReleaseInfo]
    ) -> list[ReleaseInfo]:
        releases = super()._post_process(query, releases)
        for release in releases:
            release.link = self.clean_link(release.link)
        return releases

    async def download(self, link: str) -> bytes:
        return await self._downloader.download(self.unclean_link(link))

    async def download_image(self, link: str) -> WebResult:
        return await self._downloader.download_image(
            self.unclean_link(link), self.site_link
        )

    async def download_with(
        self,
        link: str,
        method: RequestType,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Download with an explicit HTTP method (used by Cardigann)."""
        return await self._downloader.download(link, method, referer, headers)
