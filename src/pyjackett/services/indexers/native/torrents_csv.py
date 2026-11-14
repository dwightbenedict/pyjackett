"""Torrents.csv: an open source torrent search engine (JSON API)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import quote

from pyjackett.domain.category_catalog import OTHER
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.search_modes import SearchMode
from pyjackett.domain.urls import build_query_string
from pyjackett.services.indexers.native.base import NativeIndexer

MIN_SEARCH_LENGTH = 3
PAGE_SIZE = "100"
EMPTY_SEARCH_MAGNET = "magnet:?xt=urn:btih:" + "3" * 40


class TorrentsCsv(NativeIndexer):
    id = "torrentscsv"
    name = "Torrents.csv"
    description = "Torrents.csv is a self-hostable, open source torrent search engine and database"
    default_site_link = "https://torrents-csv.com/"
    legacy_site_links = ("https://torrents-csv.ml/",)
    language = "en-US"
    type = "public"

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.TV, ["q", "season", "ep"])
        caps.set_parameters(SearchMode.MOVIE, ["q"])
        caps.categories.add(1, OTHER)  # the site returns no categories

    @property
    def _search_endpoint(self) -> str:
        return self.site_link + "service/search"

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        text = query.query_string()
        if not text.strip():
            return [self._empty_search_notice()]
        if len(text) < MIN_SEARCH_LENGTH:
            return []
        parameters = build_query_string([("size", PAGE_SIZE), ("q", text)])
        response = await self.requester.request_with_retry(f"{self._search_endpoint}?{parameters}")
        try:
            torrents = json.loads(response.content_string)["torrents"]
            releases = [self._to_release(torrent) for torrent in torrents]
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError(f"Parse error: {error}") from error
        return sorted(releases, key=lambda r: r.publish_date, reverse=True)

    def _to_release(self, torrent: dict) -> ReleaseInfo:
        seeders = torrent.get("seeders") or 0
        leechers = torrent.get("leechers") or 0
        info_hash = torrent["infohash"]
        return ReleaseInfo(
            guid=f"magnet:?xt=urn:btih:{info_hash}",
            details=f"{self.site_link}search?q={quote(torrent['name'])}",
            title=torrent["name"],
            info_hash=info_hash,  # the magnet link is generated from it
            category=[OTHER.id],
            publish_date=datetime.fromtimestamp(torrent["created_unix"], UTC),
            size=torrent["size_bytes"],
            grabs=torrent.get("completed") or 0,
            seeders=seeders,
            peers=leechers + seeders,
            download_volume_factor=0,
            upload_volume_factor=1,
        )

    def _empty_search_notice(self) -> ReleaseInfo:
        """The API cannot list recent torrents; explain it as a result."""
        return ReleaseInfo(
            title="[NOT IMPLEMENTED] Empty search is unsupported in this indexer",
            guid=self.site_link,
            details=self.site_link,
            magnet_uri=EMPTY_SEARCH_MAGNET,
            category=[OTHER.id],
            publish_date=datetime.fromtimestamp(0, UTC),
            size=0,
            grabs=0,
            seeders=0,
            peers=0,
            download_volume_factor=0,
            upload_volume_factor=1,
        )
