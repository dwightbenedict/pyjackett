"""The API shared by SpeedApp and RetroFlix."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from pyjackett.config.items import BoolItem, DisplayInfoItem
from pyjackett.core.exceptions import ConfigurationError
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.http.models import RequestType, WebResult
from pyjackett.indexers.native.base import NativeIndexer
from pyjackett.indexers.native.forms import (
    PASSWORD,
    add_basic_login_with_email,
    flag,
    text,
)
from pyjackett.utils.urls import build_query_string

FREELEECH = "showfreeleechonly"
EMAIL = "email"
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
JSON_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
ACTIVITY_HELP = (
    "The accounts shall not be deleted or automatically deactivated. "
    "Inactive accounts, regardless of class, will have the invitations "
    "deleted after 180 days."
)
GENRE_DELIMITERS = re.compile(r"[,\s/)(.;\[\]\"|:]+")
REQUEST_TAG = re.compile(r"\[REQUEST(ED)?\]", re.IGNORECASE)


class SpeedAppTracker(NativeIndexer):
    """Logs in for a bearer token and searches ``api/torrent``."""

    type = "private"
    supports_pagination = True
    minimum_seed_time = 172800  # 48 hours

    def __init__(self, dependencies) -> None:
        self._token: str | None = None
        super().__init__(dependencies)

    # ---- configuration ------------------------------------------------------

    def build_configuration(self) -> None:
        data = self.config_data
        add_basic_login_with_email(data)
        data.add_dynamic(FREELEECH, BoolItem("Show freeleech only", False))
        data.add_dynamic(
            "accountinactivity",
            DisplayInfoItem("Account Inactivity", ACTIVITY_HELP),
        )

    # ---- authentication -----------------------------------------------------

    async def authenticate(self) -> None:
        await self._renew_token()

    async def _renew_token(self) -> None:
        email = text(self.config_data, EMAIL)
        password = text(self.config_data, PASSWORD)
        if not email or not password:
            raise ConfigurationError(
                "Please, check the indexer configuration.", self.config_data
            )
        response = await self.requester.request(
            self.site_link + "api/login",
            method=RequestType.POST,
            headers=JSON_HEADERS,
            raw_body=json.dumps({"username": email, "password": password}),
        )
        reply = response.json()
        self._token = reply.get("token")
        if self._token is None:
            raise ConfigurationError(
                str(reply.get("message")), self.config_data
            )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    # ---- searching ----------------------------------------------------------

    def search_parameters(self, query: TorznabQuery) -> list[tuple[str, str]]:
        parameters = [
            ("itemsPerPage", "100"),
            ("includingDead", "1"),
            ("sort", "torrent.createdAt"),
            ("direction", "desc"),
        ]
        if query.limit > 0 and query.offset > 0:
            parameters.append(("page", str(query.offset // query.limit + 1)))
        mapped = self.torznab_caps.categories.to_tracker_categories(query)
        parameters += [("categories[]", category) for category in mapped]
        if query.is_imdb_query:
            parameters.append(("imdbId", query.imdb_id or ""))
        else:
            parameters.append(("search", query.query_string()))
        return parameters

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        if not self._token:  # first time
            await self._renew_token()
        parameters = build_query_string(self.search_parameters(query))
        response = await self._authorised(
            f"{self.site_link}api/torrent?{parameters}"
        )
        if response.status != HTTP_OK:
            raise RuntimeError(
                f"Unknown error in search: {response.content_string}"
            )
        try:
            rows = json.loads(response.content_string)
            releases = [self._to_release(row, query) for row in rows]
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError(f"Parse error: {error}") from error
        return [release for release in releases if release is not None]

    async def _authorised(self, url: str) -> WebResult:
        response = await self.requester.request(url, headers=self._headers())
        if response.status == HTTP_UNAUTHORIZED:
            await self._renew_token()
            response = await self.requester.request(
                url, headers=self._headers()
            )
        return response

    def _to_release(
        self, row: dict[str, Any], query: TorznabQuery
    ) -> ReleaseInfo | None:
        download_factor = float(row["download_volume_factor"])
        if flag(self.config_data, FREELEECH) and download_factor != 0:
            return None
        title = REQUEST_TAG.sub("", row["name"]).strip(" .")
        if not query.is_imdb_query and not query.match_query_string_and(title):
            return None
        genres = [
            genre
            for genre in GENRE_DELIMITERS.split(row["short_description"] or "")
            if genre
        ]
        seeders = int(row["seeders"])
        poster = row.get("poster")
        return ReleaseInfo(
            title=title,
            link=f"{self.site_link}api/torrent/{row['id']}/download",
            details=row["url"],
            guid=row["url"],
            category=self.torznab_caps.categories.to_torznab(
                str(row["category"]["id"])
            ),
            publish_date=_parse_date(row["created_at"]),
            description=", ".join(genres),
            genres=genres,
            poster=poster if str(poster).startswith("http") else None,
            size=int(row["size"]),
            grabs=int(row["times_completed"]),
            seeders=seeders,
            peers=int(row["leechers"]) + seeders,
            download_volume_factor=download_factor,
            upload_volume_factor=float(row["upload_volume_factor"]),
            minimum_ratio=1,
            minimum_seed_time=self.minimum_seed_time,
        )

    # ---- downloading --------------------------------------------------------

    async def download(self, link: str) -> bytes:
        response = await self._authorised(self.unclean_link(link))
        if response.status != HTTP_OK:
            raise RuntimeError(f"Unknown error in download: {response.status}")
        return response.content_bytes


def _parse_date(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
