"""The browse API shared by the Gazelle based trackers."""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from typing import Any

from pyjackett.domain.cardigann.html_dom import (
    parse_html,
    query_selector,
    text_content,
)
from pyjackett.domain.config_items import (
    BoolItem,
    DisplayInfoItem,
    PasswordItem,
    StringItem,
)
from pyjackett.domain.dates import from_fuzzy_time, from_unix_timestamp
from pyjackett.domain.http_models import RequestType
from pyjackett.domain.numbers import parse_imdb_id
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.urls import build_query_string
from pyjackett.errors import ConfigurationError
from pyjackett.services.indexers.base import ConfigurationStatus
from pyjackett.services.indexers.native.base import NativeIndexer
from pyjackett.services.indexers.native.forms import (
    add_instructions,
    flag,
    text,
)

USERNAME = "username"
PASSWORD = "password"
API_KEY = "apikey"
COOKIE = "cookie"
PASSKEY = "passkey"
AUTHKEY = "authkey"
USE_TOKENS = "usefreeleechtokenswhenavailable"
FREELEECH_ONLY = "searchfreeleechonly"
FREELOAD_ONLY = "searchfreeloadonly"
TOKEN_ARGUMENT = "&usetoken=1"
OUT_OF_TOKENS = (
    "You do not have any freeleech tokens left.",
    "You do not have enough freeleech tokens",
    "This torrent is too large.",
    "You cannot use tokens here",
)
COOKIE_HELP = (
    "Use the Cookie field only if 2FA is enabled for your account, or the "
    "tracker requests your email at login; leave it empty otherwise."
    "<ol><li>Login to this tracker with your browser"
    "<li>Open the <b>DevTools</b> panel by pressing <b>F12</b>"
    "<li>Select the <b>Network</b> tab"
    "<li>Click on the <b>Doc</b> button"
    "<li>Refresh the page by pressing <b>F5</b>"
    "<li>Select the <b>Headers</b> tab"
    "<li>Find 'cookie:' in the <b>Request Headers</b> section"
    "<li>Copy & paste the whole cookie string to here.</ol>"
)
HTTP_ERROR = 400
RSS_LIMIT = 50
Parameters = list[tuple[str, str]]


class GazelleTracker(NativeIndexer):
    """Searches ``ajax.php?action=browse`` with a key, cookie or login."""

    language = "en-US"
    type = "private"
    # ---- what a site supports (the former constructor arguments) ------------
    supports_freeleech_tokens = False
    supports_freeleech_only = False
    supports_freeload_only = False
    imdb_in_tags = False
    has_two_factor = False
    use_api_key = False
    use_passkey = False
    use_authkey = False
    instructions: str | None = None
    # ---- API conventions ----------------------------------------------------
    api_path = "ajax.php"
    authorization_name = "Authorization"
    authorization_format = "{}"
    api_key_length = 41
    api_key_length_legacy = 0

    # ---- configuration ------------------------------------------------------

    def build_configuration(self) -> None:
        data = self.config_data
        if self.use_api_key:
            data.add_dynamic(API_KEY, StringItem("APIKey"))
        else:
            data.add_dynamic(USERNAME, StringItem("Username"))
            data.add_dynamic(PASSWORD, PasswordItem("Password"))
        if self.has_two_factor:
            data.add_dynamic("cookiehint", DisplayInfoItem("CookieHint", COOKIE_HELP))
            data.add_dynamic(COOKIE, StringItem("Cookie", ""))
        if self.use_passkey:
            data.add_dynamic(PASSKEY, StringItem("Passkey"))
        if self.use_authkey:
            data.add_dynamic(AUTHKEY, StringItem("Authkey"))
        if self.supports_freeleech_tokens:
            data.add_dynamic(
                USE_TOKENS,
                BoolItem("Use Freeleech Tokens when Available", False),
            )
        if self.supports_freeleech_only:
            data.add_dynamic(FREELEECH_ONLY, BoolItem("Search freeleech only", False))
        if self.supports_freeload_only:
            data.add_dynamic(FREELOAD_ONLY, BoolItem("Search freeload only", False))
        add_instructions(data, self.instructions)

    @property
    def _cookie(self) -> str:
        return text(self.config_data, COOKIE)

    @property
    def _use_tokens(self) -> bool:
        return flag(self.config_data, USE_TOKENS)

    @property
    def _api_url(self) -> str:
        return self.site_link + self.api_path

    @property
    def _poster_url(self) -> str:
        return self.site_link

    # ---- authentication -----------------------------------------------------

    async def apply_configuration(self, config) -> ConfigurationStatus:
        self.load_values_from_json(config)
        if self.use_api_key:
            self._check_api_key()
            await self._test_search("Your API Key did not work")
            return ConfigurationStatus.COMPLETED
        if self._cookie:
            self.cookie_header = self._cookie
            await self._test_search("Your cookie did not work")
            return ConfigurationStatus.COMPLETED
        await self._log_in()
        return ConfigurationStatus.REQUIRES_TESTING

    def _check_api_key(self) -> None:
        key = text(self.config_data, API_KEY)
        if not key:
            raise ConfigurationError("Invalid API Key configured", self.config_data)
        allowed = {self.api_key_length, self.api_key_length_legacy} - {0}
        if len(key) not in allowed:
            expected = " or ".join(str(n) for n in sorted(allowed))
            raise ConfigurationError(
                f"Invalid API Key configured: expected length: {expected}, got {len(key)}",
                self.config_data,
            )

    async def _test_search(self, failure: str) -> None:
        try:
            releases = await self.perform_query(TorznabQuery(query_type="search"))
            if not releases:
                raise RuntimeError("Found 0 results in the tracker")
        except Exception as error:
            self.is_configured = False
            raise ConfigurationError(f"{failure}: {error}", self.config_data) from error
        self.is_configured = True
        self.config_changed()

    async def _log_in(self) -> None:
        form = [
            ("username", text(self.config_data, USERNAME)),
            ("password", text(self.config_data, PASSWORD)),
            ("keeplogged", "1"),
        ]
        response = await self.requester.login_and_follow_redirect(
            self.site_link + "login.php",
            form,
            "",
            True,
            self.site_link,
        )
        if "logout.php" not in (response.content_string or ""):
            raise ConfigurationError(_login_error(response.content_string), self.config_data)
        self.requester.update_cookie_header(response.cookies)
        self.is_configured = True
        self.config_changed()

    # ---- hooks --------------------------------------------------------------

    def search_term(self, query: TorznabQuery) -> str:
        return query.query_string()

    def should_skip(self, torrent: dict[str, Any]) -> bool:
        """Non freeleech results are dropped when searching freeleech only."""
        is_freeleech = _as_bool(torrent.get("isFreeleech"))
        return flag(self.config_data, FREELEECH_ONLY) and not is_freeleech

    def post_parse(
        self,
        release: ReleaseInfo,
        torrent: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        """Adjust a release; return False to leave it out."""
        return True

    def info_url(self, torrent_id: int, group_id: int | None = None) -> str:
        group = f"&id={group_id}" if group_id and group_id > 0 else ""
        return f"{self.site_link}torrents.php?torrentid={torrent_id}{group}"

    def download_url(self, torrent_id: int, can_use_token: bool) -> str:
        token = TOKEN_ARGUMENT if self._use_tokens and can_use_token else ""
        passkey = f"&torrent_pass={text(self.config_data, PASSKEY)}" if self.use_passkey else ""
        authkey = f"&authkey={text(self.config_data, AUTHKEY)}" if self.use_authkey else ""
        return (
            f"{self.site_link}torrents.php?action=download{token}{passkey}{authkey}&id={torrent_id}"
        )

    def strip_token(self, link: str) -> str:
        return link.replace(TOKEN_ARGUMENT, "")

    # ---- searching ----------------------------------------------------------

    def browse_parameters(self, query: TorznabQuery) -> Parameters:
        parameters: dict[str, str] = {
            "action": "browse",
            "order_by": "time",
            "order_way": "desc",
        }
        if query.genre and query.genre.strip():
            parameters["taglist"] = query.genre
        search = self.search_term(query)
        if query.imdb_id and query.imdb_id.strip():
            key = "taglist" if self.imdb_in_tags else "cataloguenumber"
            parameters[key] = query.imdb_id
        elif search.strip():
            parameters["searchstr"] = search
        if query.artist and query.artist.strip() and query.artist != "VA":
            parameters["artistname"] = query.artist
        if query.label and query.label.strip():
            parameters["recordlabel"] = query.label
        if query.year:
            parameters["year"] = str(query.year)
        if query.album and query.album.strip():
            parameters["groupname"] = query.album
        for category in self._tracker_categories(query):
            parameters[f"filter_cat[{category}]"] = "1"
        if flag(self.config_data, FREELEECH_ONLY):
            parameters["freetorrent"] = "1"
        elif flag(self.config_data, FREELOAD_ONLY):
            parameters["freetorrent"] = "4"
        return list(parameters.items())

    def _tracker_categories(self, query: TorznabQuery) -> list[str]:
        return self.torznab_caps.categories.to_tracker_categories(query)

    def _auth_headers(self) -> dict[str, str] | None:
        if not self.use_api_key:
            return None
        key = text(self.config_data, API_KEY)
        return {self.authorization_name: self.authorization_format.format(key)}

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        # a dot is not used in titles
        parameters = build_query_string(self.browse_parameters(query))
        url = f"{self._api_url}?{parameters.replace('.', ' ')}"
        response = await self._browse(url)
        no_manual_cookie = not self._cookie
        if response.is_redirect and not self.use_api_key and no_manual_cookie:
            await self._log_in()  # the cookie expired
            response = await self._browse(url)
        self._raise_api_error(response.content_string)
        if response.status >= HTTP_ERROR:
            raise RuntimeError(f"Invalid status code {response.status} received from indexer")
        try:
            releases = self._parse(json.loads(response.content_string))
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError(f"Parse error: {error}") from error
        releases.sort(key=lambda r: r.publish_date, reverse=True)
        return releases[:RSS_LIMIT] if query.is_rss_search else releases

    async def _browse(self, url: str):
        return await self.requester.request_with_retry(url, headers=self._auth_headers())

    def _raise_api_error(self, content: str | None) -> None:
        if not (content and "failure" in content and self.use_api_key):
            return
        reason = json.loads(content).get("error")
        if reason and str(reason).strip():
            raise RuntimeError(f'Unexpected response from indexer request: "{reason}"')

    def _parse(self, payload: dict[str, Any]) -> list[ReleaseInfo]:
        releases: list[ReleaseInfo] = []
        for result in payload["response"]["results"]:
            base = self._group_release(result)
            torrents = result.get("torrents")
            for torrent in torrents if isinstance(torrents, list) else [result]:
                if self.should_skip(torrent):
                    continue
                release = base.clone()
                self._fill_release(release, torrent)
                if self.post_parse(release, torrent, result):
                    releases.append(release)
        return releases

    def _group_release(self, result: dict[str, Any]) -> ReleaseInfo:
        tags = [str(tag) for tag in result.get("tags") or []]
        has_tags = bool(tags) and bool(tags[0])
        release = ReleaseInfo(
            publish_date=_group_time(result.get("groupTime")),
            title=_group_title(result),
            description=f"Tags: {', '.join(tags)}\n" if has_tags else None,
            poster=self._poster(result.get("cover")),
            genres=tags if has_tags else [],
        )
        if self.imdb_in_tags:
            ids = {parse_imdb_id(tag) for tag in tags} - {None}
            release.imdb = ids.pop() if len(ids) == 1 else None
        return release

    def _poster(self, cover: str | None) -> str | None:
        if not cover:
            return None
        return cover if cover.startswith("http") else self._poster_url + cover

    def _fill_release(self, release: ReleaseInfo, torrent: dict[str, Any]) -> None:
        torrent_id = int(torrent["torrentId"])
        when = torrent.get("time")
        if when:
            release.publish_date = datetime.strptime(f"{when} +0000", "%Y-%m-%d %H:%M:%S %z")
        flags = _release_flags(torrent)
        if flags:
            release.title += " " + " / ".join(flags)
        release.size = int(torrent["size"])
        release.seeders = int(torrent["seeders"])
        release.peers = int(torrent["leechers"]) + release.seeders
        release.details = self.info_url(torrent_id)
        release.guid = release.details
        release.files = int(torrent["fileCount"])
        release.grabs = int(torrent["snatches"])
        self._set_volume_factors(release, torrent)
        release.link = self.download_url(torrent_id, release.download_volume_factor != 0)
        release.category = self._categories(torrent.get("category"))

    def _categories(self, description: str | None) -> list[int]:
        mappings = self.torznab_caps.categories
        if description is None or "Select Category" in description:
            return mappings.to_torznab("1")
        return mappings.to_torznab_by_description(description)

    @staticmethod
    def _set_volume_factors(release: ReleaseInfo, torrent: dict[str, Any]) -> None:
        release.download_volume_factor = 1
        release.upload_volume_factor = 1
        if _as_bool(torrent.get("isFreeleech")) or _as_bool(torrent.get("isPersonalFreeleech")):
            release.download_volume_factor = 0
        if _as_bool(torrent.get("isNeutralLeech")) or _as_bool(torrent.get("isFreeload")):
            release.download_volume_factor = 0
            release.upload_volume_factor = 0

    # ---- downloading --------------------------------------------------------

    async def download(self, link: str) -> bytes:
        link = self.unclean_link(link)
        headers = self._auth_headers()
        response = await self.requester.request(link, headers=headers)
        content = response.content_bytes
        # most trackers return the torrent anyway, Redacted an error page
        if content[:1] not in (b"", b"d") and TOKEN_ARGUMENT in link:
            page = content.decode("utf-8", errors="replace")
            if any(message in page for message in OUT_OF_TOKENS):
                return await self.download_with(
                    self.strip_token(link),
                    RequestType.GET,
                    headers=headers,
                )
        return content


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _group_time(value: Any) -> datetime:
    raw = str(value or "")
    if raw.isdigit():
        return from_unix_timestamp(int(raw))
    return from_fuzzy_time(raw) if raw else datetime.fromtimestamp(0, UTC)


def _group_title(result: dict[str, Any]) -> str:
    artist = html.unescape(result.get("artist") or "")
    year = result.get("groupYear")
    release_type = result.get("releaseType")
    title = f"{artist} - " if artist else ""
    title += html.unescape(result.get("groupName") or "")
    if year and str(year) != "0":
        title += f" [{year}]"
    if release_type and release_type != "Unknown":
        title += f" [{release_type}]"
    return title


def _release_flags(torrent: dict[str, Any]) -> list[str]:
    """The format, media and remaster details appended to the title."""
    flags: list[str] = []

    def add(value: Any, skip: str = "") -> None:
        if value and value != skip:
            flags.append(str(value))

    add(html.unescape(torrent.get("format") or ""))
    add(torrent.get("encoding"))
    if torrent.get("hasLog"):
        flags.append(f"Log ({torrent.get('logScore')}%)")
    if torrent.get("hasCue"):
        flags.append("Cue")
    add(torrent.get("lang"), "---")
    for key in ("media", "resolution", "container", "codec", "audio"):
        add(torrent.get(key))
    add(torrent.get("subbing"), "---")
    if torrent.get("remastered"):
        year = str(torrent.get("remasterYear"))
        title = html.unescape(torrent.get("remasterTitle") or "")
        remastered = f"{year if year != '0' else ''} {title}".strip()
        add(remastered)
    return flags


def _login_error(page: str | None) -> str:
    document = parse_html(page or "")
    form = query_selector(document, "#loginform")
    if form is None:
        return "Unexpected response during login, see log for HTML response."
    table = query_selector(form, "table")
    if table is not None:
        table.decompose()
    return text_content(form).replace("\n\t", " ").strip()
