"""The sites running SpeedApp."""

from __future__ import annotations

from pyjackett.config.items import DisplayInfoItem
from pyjackett.core.search_modes import SearchMode
from pyjackett.indexers.native.categories import add_categories
from pyjackett.indexers.native.speedapp import categories
from pyjackett.indexers.native.speedapp.tracker import SpeedAppTracker

REQUEST_DELAY = 2.1  # the API allows one request per two seconds


class SpeedAppSite(SpeedAppTracker):
    """Capabilities every SpeedApp site shares."""

    request_delay = REQUEST_DELAY
    category_table: categories.CategoryTable = []

    def build_capabilities(self) -> None:
        caps = self.torznab_caps
        caps.set_parameters(SearchMode.TV, ["q", "season", "ep", "imdbid"])
        caps.set_parameters(SearchMode.MOVIE, ["q", "imdbid"])
        caps.set_parameters(SearchMode.MUSIC, ["q"])
        caps.set_parameters(SearchMode.BOOK, ["q"])
        add_categories(caps.categories, self.category_table)


class SpeedApp(SpeedAppSite):
    id = "speedapp"
    name = "SpeedApp"
    description = (
        "SpeedApp is a ROMANIAN Private Torrent Tracker for MOVIES / TV / "
        "GENERAL"
    )
    default_site_link = "https://speedapp.io/"
    legacy_site_links = (
        "https://www.icetorrent.org/",
        "https://icetorrent.org/",
        "https://scenefz.me/",
        "https://www.scenefz.me/",
        "https://www.u-torrents.ro/",
        "https://myxz.eu/",
        "https://www.myxz.eu/",
        "https://www.myxz.org/",
    )
    replaces = ("icetorrent", "scenefz", "xtremezone")
    language = "ro-RO"
    category_table = categories.SPEED_APP


class RetroFlix(SpeedAppSite):
    id = "retroflix"
    name = "RetroFlix"
    description = (
        "RetroFlix is a Private site for Classic Movies / TV / General "
        "Releases"
    )
    default_site_link = "https://retroflix.net/"
    alternative_site_links = (
        "https://retroflix.net/",
        "https://retroflix.club/",
    )
    language = "en-US"
    minimum_seed_time = 432000  # 120 hours
    category_table = categories.RETRO_FLIX

    def build_configuration(self) -> None:
        super().build_configuration()
        self.config_data.add_dynamic(
            "accountinactivity",
            DisplayInfoItem(
                "Account Inactivity",
                "Any account not logged into after 150 days will be "
                "deleted. Parked accounts will be deleted after 150 days "
                "of inactivity.",
            ),
        )
