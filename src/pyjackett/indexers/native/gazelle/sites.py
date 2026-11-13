"""Trackers built on Gazelle."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any

from pyjackett.config.items import BoolItem, DisplayInfoItem
from pyjackett.core import category_catalog as cat
from pyjackett.core.query import TorznabQuery
from pyjackett.core.release import ReleaseInfo
from pyjackett.core.search_modes import SearchMode
from pyjackett.indexers.native.categories import add_categories
from pyjackett.indexers.native.forms import flag
from pyjackett.indexers.native.gazelle import categories
from pyjackett.indexers.native.gazelle.tracker import (
    FREELOAD_ONLY,
    GazelleTracker,
)
from pyjackett.utils.numbers import parse_imdb_id

ACTIVITY = "accountinactivity"
MUSIC_PARAMETERS = ["q", "album", "artist", "label", "year"]
RATIO_NOTE_MINIMUM = 0.6  # the proportional ratio system, worst case
YEAR = re.compile(r"(\b|[-._ ])((?:19|20)\d{2})(\b|[-._ ])")


def _inactivity(days: int, extra: str = "") -> str:
    return (
        f"To keep your account active, sign in and browse the site at least "
        f"once every {days} days. Seeding torrents does not count as "
        f"account activity, so in order to remain active you need to sign "
        f"in and browse the site. {extra}"
    ).strip()


class BrokenStones(GazelleTracker):
    id = "brokenstones"
    name = "BrokenStones"
    description = (
        "Broken Stones is a Private site for MacOS and iOS APPS / GAMES"
    )
    default_site_link = "https://brokenstones.is/"
    legacy_site_links = (
        "https://brokenstones.club/",
        "https://broken-stones.club/",
    )
    supports_freeleech_tokens = True
    has_two_factor = True

    def build_capabilities(self) -> None:
        add_categories(self.torznab_caps.categories, categories.BROKEN_STONES)


class DicMusic(GazelleTracker):
    id = "dicmusic"
    name = "DICMusic"
    description = "DICMusic is a CHINESE Private Torrent Tracker for MUSIC"
    default_site_link = "https://dicmusic.com/"
    legacy_site_links = ("https://dicmusic.club/",)
    language = "zh-CN"
    supports_freeleech_tokens = True
    supports_freeleech_only = True
    has_two_factor = True

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.MUSIC, MUSIC_PARAMETERS)
        add_categories(caps.categories, categories.DIC_MUSIC)

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        return [r for r in releases if query.match_query_string_and(r.title)]


class Orpheus(GazelleTracker):
    id = "orpheus"
    name = "Orpheus"
    description = "Orpheus is a Private MUSIC tracker"
    default_site_link = "https://orpheus.network/"
    supports_freeleech_tokens = True
    use_api_key = True
    authorization_format = "token {}"
    api_key_length = 116
    api_key_length_legacy = 118
    instructions = (
        "<ol><li>Go to Orpheus's site and open your account settings.</li>"
        "<li>Under <b>Access Settings</b> click on 'Create a new token'</li>"
        "<li>Give it a name you like and click <b>Generate</b>.</li>"
        "<li>Copy the generated API Key and paste it in the above text "
        "field.</li></ol>"
    )

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.MUSIC, [*MUSIC_PARAMETERS, "genre"])
        caps.set_parameters(SearchMode.BOOK, ["q", "genre"])
        add_categories(caps.categories, categories.ORPHEUS)

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                _inactivity(
                    120,
                    "Power Users (and above) are immune to the inactivity "
                    "timer, but logging in regularly is recommended to "
                    "learn about special events and new features. Donors "
                    "are exempt from automatic account disabling due to "
                    "inactivity. If you wish to always maintain an active "
                    "account consider donating.",
                ),
            ),
        )

    def download_url(self, torrent_id: int, can_use_token: bool) -> str:
        token = "&usetoken=1" if self._use_tokens and can_use_token else ""
        return (
            f"{self.site_link}ajax.php?action=download{token}&id={torrent_id}"
        )

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        for release in releases:
            release.minimum_ratio = RATIO_NOTE_MINIMUM
        return releases


class Redacted(GazelleTracker):
    id = "redacted"
    name = "Redacted"
    description = "Redacted is a Private site for MUSIC"
    default_site_link = "https://redacted.sh/"
    legacy_site_links = ("https://redacted.ch/",)
    replaces = ("passtheheadphones",)
    supports_freeleech_tokens = True
    supports_freeload_only = True
    use_api_key = True
    instructions = (
        "<ol><li>Go to Redacted's site and open your account settings."
        "</li><li>Go to <b>Access Settings</b> tab and copy the API Key."
        "</li><li>Ensure that you've checked <b>Confirm API Key</b>.</li>"
        "<li>Finally, click <b>Save Profile</b>.</li></ol>"
    )

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.MOVIE, ["q", "genre"])
        caps.set_parameters(SearchMode.MUSIC, [*MUSIC_PARAMETERS, "genre"])
        caps.set_parameters(SearchMode.BOOK, ["q", "genre"])
        add_categories(caps.categories, categories.REDACTED)

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                _inactivity(
                    120,
                    "Some scripts or automated tools may be detected as "
                    "activity on your account, but it is best to sign in "
                    "with a browser from time to time just to make sure "
                    "you will not be flagged as inactive. Donors and "
                    "certain user classes (Power User+) are exempt from "
                    "automatic account disabling due to inactivity. If "
                    "you wish to always maintain an active account "
                    "consider donating or reaching a higher user class.",
                ),
            ),
        )

    def download_url(self, torrent_id: int, can_use_token: bool) -> str:
        token = "&usetoken=1" if self._use_tokens and can_use_token else ""
        return (
            f"{self.site_link}ajax.php?action=download{token}&id={torrent_id}"
        )

    def should_skip(self, torrent: dict[str, Any]) -> bool:
        is_freeload = str(torrent.get("isFreeload")).lower() == "true"
        if flag(self.config_data, FREELOAD_ONLY) and not is_freeload:
            return True
        return super().should_skip(torrent)

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        releases = [
            r for r in releases if query.match_query_string_and(r.title)
        ]
        for release in releases:
            release.minimum_ratio = RATIO_NOTE_MINIMUM
        return releases


class AlphaRatio(GazelleTracker):
    id = "alpharatio"
    name = "AlphaRatio"
    description = (
        "AlphaRatio (AR) is a Private Torrent Tracker for 0DAY / GENERAL"
    )
    default_site_link = "https://alpharatio.cc/"
    supports_freeleech_tokens = True
    supports_freeleech_only = True
    imdb_in_tags = True

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.TV, ["q", "season", "ep"])
        caps.set_parameters(SearchMode.MOVIE, ["q", "imdbid"])
        add_categories(caps.categories, categories.ALPHA_RATIO)

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                "Users must login to the site at least once every 90 days. "
                "Failure to do so results in the user account being "
                "suspended and automatically demoted to Exiled user class.",
            ),
        )

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        for release in releases:
            release.minimum_ratio = 1
            release.minimum_seed_time = 259200
        return releases


class GreatPosterWall(GazelleTracker):
    id = "greatposterwall"
    name = "GreatPosterWall"
    description = "GreatPosterWall (GPW) is a CHINESE Private site for MOVIES"
    default_site_link = "https://greatposterwall.com/"
    replaces = ("seals",)
    language = "zh-CN"
    supports_freeleech_tokens = True
    supports_freeleech_only = True
    has_two_factor = True
    # factors of the "freeType" field
    free_types = {"11": 0.75, "12": 0.5, "13": 0.25, "1": 0.0, "2": 0.0}

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.MOVIE, ["q", "imdbid", "genre"])
        add_categories(caps.categories, categories.GREAT_POSTER_WALL)

    def build_configuration(self) -> None:
        super().build_configuration()
        data = self.config_data
        data.add_dynamic(
            "showfilename",
            BoolItem("Use the first torrent filename as the title", False),
        )
        data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                "To keep your account active, you should log in and browse "
                "the site at least once every 120 days. Simply seeding is "
                "not currently considered an active feature of your "
                "account, so to keep your account active you can only log "
                "in and browse the site. Some scripts or automated tools "
                "may help keep your account active, but it's best to log "
                "in via your browser from time to time to ensure your "
                "account isn't marked as inactive.",
            ),
        )

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        if query.is_imdb_query:  # GPW searches the imdb id as text
            query.search_term = query.imdb_id
            query.imdb_id = None
        return await super().perform_query(query)

    def post_parse(
        self,
        release: ReleaseInfo,
        torrent: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        release.title = _poster_wall_title(torrent, result)
        if flag(self.config_data, "showfilename"):
            release.title = html.unescape(torrent.get("fileName") or "")
        digits = str(result.get("doubanId") or "")
        release.douban_id = int(digits) if digits.isdigit() else None
        self._apply_free_type(release, torrent)
        if result.get("imdbId"):
            release.imdb = parse_imdb_id(result["imdbId"])
        release.minimum_ratio = 1
        release.minimum_seed_time = 172800  # 48 hours
        release.category = [cat.MOVIES.id]
        sub_name = html.unescape(result.get("groupSubName") or "")
        if sub_name:
            release.description = sub_name
        when = torrent.get("time")
        if when:  # Chinese time, 8 hours ahead of UTC
            release.publish_date = datetime.strptime(
                f"{when} +0800", "%Y-%m-%d %H:%M:%S %z"
            )
        return True

    def _apply_free_type(
        self, release: ReleaseInfo, torrent: dict[str, Any]
    ) -> None:
        free_type = str(torrent.get("freeType"))
        if free_type in self.free_types:
            release.download_volume_factor = self.free_types[free_type]
        if free_type == "2":
            release.upload_volume_factor = 0
        if torrent.get("isPersonalFreeleech") is True:
            release.download_volume_factor = 0


def _poster_wall_title(torrent: dict[str, Any], result: dict[str, Any]) -> str:
    title = html.unescape(result.get("groupName") or "")
    year = result.get("groupYear")
    if year and str(year) != "0":
        title += f" [{year}]"
    flags = [
        torrent.get(key)
        for key in ("codec", "source", "resolution", "container", "processing")
        if torrent.get(key)
    ]
    return f"{title} {' / '.join(flags)}" if flags else title


class SecretCinema(GazelleTracker):
    id = "secretcinema"
    name = "Secret Cinema"
    description = "Secret Cinema is a Private ratioless site for rare MOVIES."
    default_site_link = "https://secret-cinema.pw/"

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.MOVIE, ["q", "imdbid"])
        caps.set_parameters(SearchMode.MUSIC, MUSIC_PARAMETERS)
        add_categories(caps.categories, categories.SECRET_CINEMA)

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        return [r for r in releases if query.match_query_string_and(r.title)]

    def post_parse(
        self,
        release: ReleaseInfo,
        torrent: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        media = torrent.get("media")
        self._recategorise(release, media)
        if _is_movie(release.category):
            release.title = _movie_title(torrent, result, media)
        when = torrent.get("time")
        if when:
            release.publish_date = datetime.strptime(
                f"{when} +0200", "%Y-%m-%d %H:%M:%S %z"
            )
        return True

    @staticmethod
    def _recategorise(release: ReleaseInfo, media: str | None) -> None:
        by_media = {
            "SD": cat.MOVIES_SD,
            "720p": cat.MOVIES_HD,
            "1080p": cat.MOVIES_HD,
            "2160p": cat.MOVIES_HD,
            "4k": cat.MOVIES_HD,
            "DVD-R": cat.MOVIES_DVD,
            "BDMV": cat.MOVIES_BLURAY,
        }
        target = by_media.get(media or "")
        if target is not None:
            release.category = [
                c for c in release.category if c != cat.MOVIES.id
            ] + [target.id]


def _is_movie(category: list[int]) -> bool:
    movies = {cat.MOVIES.id, *(c.id for c in cat.MOVIES.subcategories)}
    return bool(movies & set(category))


def _movie_title(
    torrent: dict[str, Any], result: dict[str, Any], media: str | None
) -> str:
    name = (torrent.get("releaseName") or "").strip()
    if name and YEAR.search(name):
        return html.unescape(name)
    title = html.unescape(result.get("groupName") or "")
    title = f"{title} ({result.get('groupYear')}) {media or ''}".strip()
    remaster = (torrent.get("remasterTitle") or "").strip()
    if remaster:
        title += f" / {html.unescape(remaster)}"
    title = re.sub(r"\bBDMV\b", "COMPLETE BLURAY", title, flags=re.I)
    return re.sub(r"\bSD\b", "DVDRip", title, flags=re.I)


class Simurg(GazelleTracker):
    id = "simurg"
    name = "Simurg"
    description = (
        "Simurg is a Private Torrent Tracker for EBOOKS and AUDIOBOOKS"
    )
    default_site_link = "https://simurg.world/"
    supports_freeleech_tokens = True
    use_api_key = True
    authorization_format = "token {}"
    api_key_length = 116
    # the formats that tell the kind of a release without a category
    format_categories = {
        "PDF": cat.BOOKS_E_BOOK,
        "MOBI": cat.BOOKS_E_BOOK,
        "EPUB": cat.BOOKS_E_BOOK,
        "AZW3": cat.BOOKS_E_BOOK,
        "CBR": cat.BOOKS_COMICS,
        "CBZ": cat.BOOKS_COMICS,
        "MP3": cat.AUDIO_AUDIOBOOK,
        "M4B": cat.AUDIO_AUDIOBOOK,
    }

    def build_capabilities(self) -> None:
        add_categories(self.torznab_caps.categories, categories.SIMURG)

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                "To keep your account active, sign in and browse the site "
                "at least once every 90 days. Seeding torrents does not "
                "count as account activity.",
            ),
        )

    def download_url(self, torrent_id: int, can_use_token: bool) -> str:
        token = "&usetoken=1" if self._use_tokens and can_use_token else ""
        return (
            f"{self.site_link}ajax.php?action=download{token}&id={torrent_id}"
        )

    def post_parse(
        self,
        release: ReleaseInfo,
        torrent: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        # Content categories are authoritative: a PDF can be a book, comic
        # or magazine. Older grouped responses omit them.
        label = torrent.get("category") or result.get("category")
        mapped = self.torznab_caps.categories.to_torznab_by_description(label)
        if mapped:
            release.category = mapped
            return True
        by_format = self.format_categories.get(torrent.get("format"))
        if by_format is not None:
            release.category = [by_format.id]
        return True

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        for release in releases:
            release.minimum_ratio = RATIO_NOTE_MINIMUM
            release.minimum_seed_time = 259200
        return releases


class DesiGaane(GazelleTracker):
    id = "desigaane"
    name = "DesiGaane"
    description = "DesiGaane is a Private Torrent Tracker for DESI MUSIC"
    default_site_link = "https://desigaane.rocks/"
    supports_freeleech_tokens = True
    use_api_key = True
    api_key_length = 116

    def build_capabilities(self) -> None:
        add_categories(self.torznab_caps.categories, categories.DESI_GAANE)

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            ACTIVITY,
            DisplayInfoItem(
                "Account Inactivity",
                "To keep your account active, sign in and browse the site "
                "at least once every 90 days. Seeding torrents does not "
                "count as account activity.",
            ),
        )

    def download_url(self, torrent_id: int, can_use_token: bool) -> str:
        token = "&usetoken=1" if self._use_tokens and can_use_token else ""
        return (
            f"{self.site_link}ajax.php?action=download{token}&id={torrent_id}"
        )

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        releases = await super().perform_query(query)
        for release in releases:
            release.minimum_ratio = RATIO_NOTE_MINIMUM
            release.minimum_seed_time = 259200
        return releases
