"""The sites of the AvistaZ network."""

from __future__ import annotations

from typing import Any

from pyjackett.domain import category_catalog as cat
from pyjackett.domain.config_items import DisplayInfoItem, MultiSelectItem
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.search_modes import SearchMode
from pyjackett.services.indexers.native.avistaz import categories
from pyjackett.services.indexers.native.avistaz.languages import (
    AUDIO_LANGUAGES,
    SUBTITLE_LANGUAGES,
)
from pyjackett.services.indexers.native.avistaz.tracker import (
    FREELEECH,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AvistazTracker,
    QueryParameters,
)
from pyjackett.services.indexers.native.categories import add_categories
from pyjackett.services.indexers.native.forms import flag
from pyjackett.services.indexers.native.support import first_if_single

AUDIO_KEY = "searchaudiolanguages"
SUBTITLE_KEY = "searchsubtitlelanguages"
LANGUAGE_HELP = (
    "The audio and subtitle language settings are AND searches, e.g. "
    "selecting English audio with Basque and Catalan subtitles, will only "
    "return results with all three of these."
)
INACTIVITY_HELP = (
    "To avoid account deletion you must login at least 1 time every 90 "
    "days, and you must download at least 1 torrent every 6 months. Simply "
    "keeping torrents seeding long term will not protect your account"
)


class VideoTracker(AvistazTracker):
    """The movie and TV sites share one category tree."""

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(
            SearchMode.TV,
            ["q", "season", "ep", "imdbid", "tvdbid", "genre"],
        )
        caps.set_parameters(
            SearchMode.MOVIE, ["q", "imdbid", "tmdbid", "genre"]
        )
        caps.tv_search_imdb_available = True
        for tracker_id, group in (
            (1, (cat.MOVIES, cat.MOVIES_UHD, cat.MOVIES_HD, cat.MOVIES_SD)),
            (2, (cat.TV, cat.TVUHD, cat.TVHD, cat.TVSD)),
        ):
            for category in group:
                caps.categories.add(tracker_id, category)


class AvistaZ(VideoTracker):
    id = "avistaz"
    name = "AvistaZ"
    description = (
        "AvistaZ (AsiaTorrents) is a Private Torrent Tracker for ASIAN "
        "MOVIES / TV / GENERAL"
    )
    default_site_link = "https://avistaz.to/"

    def build_capabilities(self) -> None:
        super().build_capabilities()
        self.torznab_caps.supports_raw_search = True
        self.torznab_caps.categories.add(3, cat.AUDIO)

    def build_configuration(self) -> None:
        super().build_configuration()
        data = self.config_data
        data.add_dynamic(
            AUDIO_KEY,
            MultiSelectItem("Search Audio Languages", AUDIO_LANGUAGES),
        )
        data.add_dynamic(
            SUBTITLE_KEY,
            MultiSelectItem("Search Subtitle Languages", SUBTITLE_LANGUAGES),
        )
        data.add_dynamic(
            "infosearchlanguages",
            DisplayInfoItem("Info Search Languages", LANGUAGE_HELP),
        )

    def search_parameters(self, query: TorznabQuery) -> QueryParameters:
        parameters = super().search_parameters(query)
        for key, field in (
            (AUDIO_KEY, "language[]"),
            (SUBTITLE_KEY, "subtitle[]"),
        ):
            for language_id in dict.fromkeys(
                self.config_data.get_dynamic(key).values
            ):
                parameters.append((field, language_id))
        return parameters

    def episode_term(self, query: TorznabQuery) -> str:
        """AvistaZ has episodes without season, e.g. Running Man E323."""
        if not query.season and (query.episode or "").strip():
            return f"E{query.episode}"
        return query.episode_search_string()


class CinemaZ(VideoTracker):
    id = "cinemaz"
    name = "CinemaZ"
    description = (
        "CinemaZ (EuTorrents) is a Private Torrent Tracker for FOREIGN "
        "NON-ASIAN MOVIES / TV"
    )
    default_site_link = "https://cinemaz.to/"


class PrivateHD(VideoTracker):
    id = "privatehd"
    name = "PrivateHD"
    description = (
        "PrivateHD is a Private BitTorrent site for High Quality, High "
        "Definition (HD) MOVIES and TV Shows"
    )
    default_site_link = "https://privatehd.to/"

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            "accountinactivity",
            DisplayInfoItem("Account Inactivity", INACTIVITY_HELP),
        )


class ExoticaZ(AvistazTracker):
    id = "exoticaz"
    name = "ExoticaZ"
    description = "ExoticaZ (YourExotic) is a Private Torrent Tracker for 3X"
    default_site_link = "https://exoticaz.to/"
    legacy_site_links = ("https://torrents.yourexotic.com/",)
    replaces = ("yourexotic",)

    def build_capabilities(self) -> None:
        add = self.torznab_caps.categories.add
        add(1, cat.XX_XX_264, "Video Clip")
        add(2, cat.XXX_PACK, "Video Pack")
        add(3, cat.XXX_PACK, "Siterip Pack")
        add(4, cat.XXX_PACK, "Pornstar Pack")
        add(5, cat.XXXDVD, "DVD")
        add(6, cat.XX_XX_264, "BluRay")
        add(7, cat.XXX_IMAGE_SET, "Photo Pack")
        add(8, cat.XXX_IMAGE_SET, "Books & Magazines")

    def search_parameters(self, query: TorznabQuery) -> QueryParameters:
        mapped = self.torznab_caps.categories.to_tracker_categories(query)
        parameters: QueryParameters = [
            ("in", "1"),
            ("category", first_if_single(mapped, "0")),
            ("limit", "50"),
            ("search", self.search_term(query)),
        ]
        parameters += self._page_parameters(query)
        if flag(self.config_data, FREELEECH):
            parameters.append(("discount[]", "1"))
        return parameters

    def parse_categories(self, row: dict[str, Any]) -> list[int]:
        categories = self.torznab_caps.categories
        return [
            torznab
            for tracker_id in (row.get("category") or {})
            for torznab in categories.to_torznab(str(tracker_id))
        ]


class AnimeZ(AvistazTracker):
    id = "animez"
    name = "AnimeZ"
    description = (
        "AnimeZ (ex-AnimeTorrents) is a Private Torrent Tracker for "
        "ANIME / MANGA"
    )
    default_site_link = "https://animez.to/"
    legacy_site_links = ("https://animetorrents.me/",)
    replaces = ("animetorrents",)

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.TV, ["q", "season", "ep"])
        caps.set_parameters(SearchMode.MOVIE, ["q"])
        caps.set_parameters(SearchMode.BOOK, ["q"])
        add_categories(caps.categories, categories.ANIME_Z)

    def search_parameters(self, query: TorznabQuery) -> QueryParameters:
        parameters: QueryParameters = [("limit", "50")]
        mapped = self.torznab_caps.categories.to_tracker_categories(query)
        parameters += [("format[]", category) for category in mapped]
        parameters.append(("search", self.search_term(query)))
        parameters += self._page_parameters(query)
        if flag(self.config_data, FREELEECH):
            parameters.append(("freeleech", "1"))
        return parameters

    def parse_categories(self, row: dict[str, Any]) -> list[int]:
        return self.torznab_caps.categories.to_torznab(row.get("format"))

    def parse_title(self, row: dict[str, Any]) -> str | None:
        return row.get("release_title") or row.get("file_name")

    async def download(self, link: str) -> bytes:
        if not self._token:
            await self._renew_token()
        response = await self._download_response(link)
        if response.status == HTTP_UNAUTHORIZED:
            await self._renew_token()
            response = await self._download_response(link)
        if response.status != HTTP_OK:
            raise RuntimeError(f"Unknown error in download: {response.status}")
        return response.content_bytes

    async def _download_response(self, link: str):
        return await self.requester.request(
            self.unclean_link(link), headers=self._search_headers()
        )
