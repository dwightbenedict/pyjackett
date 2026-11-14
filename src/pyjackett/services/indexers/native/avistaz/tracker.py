"""The API shared by AvistaZ, CinemaZ, ExoticaZ and PrivateHD."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from pyjackett.domain import category_catalog as cat
from pyjackett.domain.category import TorznabCategory
from pyjackett.domain.config_items import BoolItem, DisplayInfoItem
from pyjackett.domain.http_models import RequestType
from pyjackett.domain.numbers import parse_imdb_id
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.urls import build_query_string
from pyjackett.services.indexers.native.base import NativeIndexer
from pyjackett.services.indexers.native.forms import (
    PASSWORD,
    PID,
    USERNAME,
    add_basic_login_with_pid,
    flag,
    text,
)
from pyjackett.services.indexers.native.support import (
    first_if_single,
    raise_if_rate_limited,
)

FREELEECH = "searchfreeleechonly"
HD_RESOLUTIONS = frozenset({"1080p", "1080i", "720p"})
MIN_SEED_SECONDS = 259200  # 72 hours
HTTP_UNAUTHORIZED = 401
HTTP_PRECONDITION_FAILED = 412
HTTP_NOT_FOUND = 404
HTTP_OK = 200
JSON_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
LOGIN_HELP = (
    "You have to check 'Enable RSS Feed' in 'My Account', without this "
    "configuration the torrent download does not work.<br/>You can find "
    "the PID in 'My profile'."
)
ACTIVITY_HELP = (
    "To avoid account deletion you must login at least 1 time every 60 "
    "days, and you must download at least 1 torrent every 90 days. Simply "
    "keeping torrents seeding long term will not protect your account. Do "
    "not rely on inactivity emails, we often do not send them."
)

QueryParameters = list[tuple[str, str]]


def minimum_seed_seconds(size: int | None) -> int:
    """Seed time grows with the size of the torrent (hit and run rules)."""
    if not size:
        return MIN_SEED_SECONDS
    gigabytes = size / 1024**3
    if gigabytes > 50.0:
        return int(100 * math.log(gigabytes) - 219.2023) * 3600
    return MIN_SEED_SECONDS + int(gigabytes * 7200)


class AvistazTracker(NativeIndexer):
    """Logs in for a bearer token and searches the ``jackett`` API."""

    language = "en-US"
    type = "private"
    request_delay = 6.0
    limits_default = 50
    limits_max = 50

    def __init__(self, dependencies) -> None:
        self._token: str | None = None
        super().__init__(dependencies)

    # ---- configuration ------------------------------------------------------

    def build_configuration(self) -> None:
        data = self.config_data
        add_basic_login_with_pid(data, LOGIN_HELP)
        data.add_dynamic(FREELEECH, BoolItem("Search freeleech only", False))
        data.add_dynamic(
            "accountinactivity",
            DisplayInfoItem("Account Inactivity", ACTIVITY_HELP),
        )

    @property
    def _auth_url(self) -> str:
        return self.site_link + "api/v1/jackett/auth"

    @property
    def _search_url(self) -> str:
        return self.site_link + "api/v1/jackett/torrents"

    # ---- authentication -----------------------------------------------------

    async def authenticate(self) -> None:
        await self._renew_token()

    async def _renew_token(self) -> None:
        body = {
            "username": text(self.config_data, USERNAME),
            "password": text(self.config_data, PASSWORD),
            "pid": text(self.config_data, PID),
        }
        response = await self.requester.request(
            self._auth_url,
            method=RequestType.POST,
            headers=JSON_HEADERS,
            raw_body=json.dumps(body),
        )
        raise_if_rate_limited(response)
        try:
            reply = response.json()
        except ValueError as error:
            raise RuntimeError(
                "Invalid response from AvistaZ, the response is not valid JSON"
            ) from error
        self._token = reply.get("token")
        if self._token is None:
            raise RuntimeError(reply.get("message") or "Unauthorized request to indexer")

    def _search_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

    # ---- hooks --------------------------------------------------------------

    def episode_term(self, query: TorznabQuery) -> str:
        return query.episode_search_string().strip()

    def search_term(self, query: TorznabQuery) -> str:
        return f"{query.search_term or ''} {self.episode_term(query)}".strip()

    def search_parameters(self, query: TorznabQuery) -> QueryParameters:
        """Category, quality, id and search filters of one query."""
        mapped = self.torznab_caps.categories.to_tracker_categories(query)
        parameters: QueryParameters = [
            ("in", "1"),
            ("type", first_if_single(mapped, "0")),
            ("limit", "50"),
        ]
        parameters += self._page_parameters(query)
        parameters += self._quality_parameters(query)
        parameters += self._id_parameters(query)
        if query.genre and query.genre.strip():
            parameters.append(("tags", query.genre))
        if flag(self.config_data, FREELEECH):
            parameters.append(("discount[]", "1"))
        return parameters

    @staticmethod
    def _page_parameters(query: TorznabQuery) -> QueryParameters:
        if query.limit > 0 and query.offset > 0:
            return [("page", str(query.offset // query.limit + 1))]
        return []

    @staticmethod
    def _quality_parameters(query: TorznabQuery) -> QueryParameters:
        """Resolution filters narrow searches in the sub categories."""
        wanted = set(query.categories)
        if wanted & {cat.MOVIES.id, cat.TV.id, cat.AUDIO.id}:
            return []
        qualities: list[str] = []
        if wanted & {cat.MOVIES_UHD.id, cat.TVUHD.id}:
            qualities.append("6")  # 2160p
        if wanted & {cat.MOVIES_HD.id, cat.TVHD.id}:
            qualities += ["2", "7", "3"]  # 720p, 1080i, 1080p
        if wanted & {cat.MOVIES_SD.id, cat.TVSD.id}:
            qualities.append("1")
        return [("video_quality[]", quality) for quality in qualities]

    def _id_parameters(self, query: TorznabQuery) -> QueryParameters:
        episode = ("search", self.episode_term(query))
        if query.is_imdb_query:
            return [("imdb", query.imdb_id or ""), episode]
        if query.is_tmdb_query:
            return [("tmdb", str(query.tmdb_id)), episode]
        if query.is_tvdb_query:
            return [("tvdb", str(query.tvdb_id)), episode]
        return [("search", self.search_term(query))]

    def parse_categories(self, row: dict[str, Any]) -> list[int]:
        quality = row.get("video_quality") or ""
        kind = (row.get("type") or "").upper()
        if kind == "MOVIE":
            return [_video_category(quality, cat.MOVIES_HD, cat.MOVIES_UHD, cat.MOVIES_SD)]
        if kind == "TV-SHOW":
            return [_video_category(quality, cat.TVHD, cat.TVUHD, cat.TVSD)]
        if kind == "MUSIC":
            return [cat.AUDIO.id]
        raise RuntimeError("Error parsing category!")

    def parse_title(self, row: dict[str, Any]) -> str | None:
        return row.get("file_name")

    # ---- searching ----------------------------------------------------------

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        parameters = build_query_string(self.search_parameters(query))
        url = f"{self._search_url}?{parameters}"
        response = await self._search(url)
        if response.status in (HTTP_UNAUTHORIZED, HTTP_PRECONDITION_FAILED):
            await self._renew_token()
            response = await self._search(url)
        if response.status == HTTP_NOT_FOUND:
            return []  # a search without results, e.g. CinemaZ: tt0075998
        raise_if_rate_limited(response)
        if response.status != HTTP_OK:
            raise RuntimeError(f"Invalid status code {response.status} received from indexer")
        try:
            rows = json.loads(response.content_string)["data"]
            return [self._to_release(row) for row in rows]
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError(f"Parse error: {error}") from error

    async def _search(self, url: str):
        return await self.requester.request_with_retry(url, headers=self._search_headers())

    def _to_release(self, row: dict[str, Any]) -> ReleaseInfo:
        audio = [tag["language"] for tag in row.get("audio") or []]
        subtitles = [tag["language"] for tag in row.get("subtitle") or []]
        seeders = row.get("seed")
        size = row.get("file_size")
        release = ReleaseInfo(
            title=self.parse_title(row),
            link=row["download"],
            info_hash=row.get("info_hash"),
            details=row["url"],
            guid=row["url"],
            category=self.parse_categories(row),
            publish_date=_parse_date(row["created_at_iso"]),
            description=_describe(audio, subtitles),
            size=size,
            files=row.get("file_count"),
            grabs=row.get("completed"),
            seeders=seeders,
            peers=(row.get("leech") or 0) + (seeders or 0),
            download_volume_factor=row.get("download_multiply"),
            upload_volume_factor=row.get("upload_multiply"),
            minimum_ratio=1,
            minimum_seed_time=minimum_seed_seconds(size),
            languages=audio,
            subs=subtitles,
        )
        _add_ids(release, row.get("movie_tv"))
        return release


def _video_category(
    quality: str,
    hd: TorznabCategory,
    uhd: TorznabCategory,
    sd: TorznabCategory,
) -> int:
    if quality in HD_RESOLUTIONS:
        return hd.id
    return uhd.id if quality == "2160p" else sd.id


def _add_ids(release: ReleaseInfo, ids: dict[str, Any] | None) -> None:
    if not ids:
        return
    release.imdb = parse_imdb_id(ids.get("imdb"))
    release.tmdb = _to_int(ids.get("tmdb"))
    release.tvdb_id = _to_int(ids.get("tvdb"))


def _to_int(value: Any) -> int:
    digits = str(value or "").strip()
    return int(digits) if digits.isdigit() else 0


def _parse_date(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _describe(audio: list[str], subtitles: list[str]) -> str:
    description = f"Audio: {', '.join(audio)}" if audio else ""
    if subtitles:
        description += f"<br/>Subtitles: {', '.join(subtitles)}"
    return description
