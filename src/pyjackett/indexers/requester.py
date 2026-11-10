"""Cookie-aware requests on behalf of one indexer."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Protocol

from pyjackett.http.client import WebClient
from pyjackett.http.models import RequestType, WebRequest, WebResult
from pyjackett.indexers.retry import retry_request
from pyjackett.utils.clock import SYSTEM_CLOCK, Clock
from pyjackett.utils.cookies import dict_to_header, header_to_dict
from pyjackett.utils.text import is_blank

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
SITE_DOWN_STATUSES = frozenset({502, 504, 521, 522, 523})
# these cookies cause bad gateway errors (upstream issue #2306)
DROPPED_COOKIES = ("cf_use_ob", "cf_ob_info")

PostData = Iterable[tuple[str, str]]


class CookieOwner(Protocol):
    """The indexer whose cookie header the requester keeps up to date."""

    name: str
    encoding: str
    is_configured: bool
    cookie_header: str | None

    def config_changed(self) -> None:
        """Protocol method."""


def check_site_down(response: WebResult) -> None:
    if response.status in SITE_DOWN_STATUSES:
        url = response.request.url if response.request else "tracker"
        raise RuntimeError(
            f"Request to {url} failed (Error {response.status}) "
            "- The tracker seems to be down."
        )


def _join(*cookie_parts: str | None) -> str:
    return " ".join(part for part in cookie_parts if part)


class WebRequester:
    """Sends requests with the indexer's cookies and stores new ones."""

    def __init__(
        self,
        client: WebClient,
        owner: CookieOwner,
        retries: Callable[[], int],
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._client = client
        self._owner = owner
        self._retries = retries
        self._clock = clock

    # ---- cookies ----------------------------------------------------------

    def resolve_cookies(self, incoming: str = "") -> str:
        """Merge the stored cookies with ``incoming`` (newest value wins)."""
        stored = self._owner.cookie_header
        merged = incoming if is_blank(stored) else f"{stored} {incoming}"
        cookies = header_to_dict(merged)
        for name in DROPPED_COOKIES:
            cookies.pop(name, None)
        return dict_to_header(cookies)

    def update_cookie_header(
        self, new_cookies: str | None, cookie_override: str | None = None
    ) -> None:
        """Adopt new cookies and persist them if something changed."""
        updated = self.resolve_cookies(_join(cookie_override, new_cookies))
        if self._owner.cookie_header != updated:
            logger.debug(
                "updating Cookies %s => %s", self._owner.cookie_header, updated
            )
            self._owner.cookie_header = updated
            if self._owner.is_configured:
                self._owner.config_changed()

    # ---- plain requests -----------------------------------------------------

    async def request(
        self,
        url: str,
        cookie_override: str | None = None,
        method: RequestType = RequestType.GET,
        referer: str | None = None,
        data: PostData | None = None,
        headers: dict[str, str] | None = None,
        raw_body: str | None = None,
        emulate_browser: bool | None = None,
    ) -> WebResult:
        request = WebRequest(
            url=url,
            type=method,
            cookies=(
                cookie_override
                if cookie_override is not None
                else self._owner.cookie_header
            ),
            post_data=list(data or []),
            referer=referer,
            headers=dict(headers or {}),
            raw_body=raw_body,
            emulate_browser=emulate_browser,
            encoding=self._owner.encoding,
        )
        return await self.send(request, cookie_override)

    async def send(
        self, request: WebRequest, cookie_override: str | None = None
    ) -> WebResult:
        request.encoding = self._owner.encoding
        result = await self._client.get_result(request)
        check_site_down(result)
        self.update_cookie_header(result.cookies, cookie_override)
        return result

    async def request_with_retry(self, *args, **kwargs) -> WebResult:
        return await retry_request(
            lambda: self.request(*args, **kwargs),
            self._retries(),
            self._owner.name,
            self._clock,
        )

    async def send_with_retry(self, request: WebRequest) -> WebResult:
        return await retry_request(
            lambda: self.send(request),
            self._retries(),
            self._owner.name,
            self._clock,
        )

    # ---- redirects ----------------------------------------------------------

    async def follow_if_redirect(
        self,
        response: WebResult,
        referrer: str | None = None,
        override_redirect_url: str | None = None,
        override_cookies: str | None = None,
        accumulate_cookies: bool = False,
        max_redirects: int = MAX_REDIRECTS,
    ) -> WebResult:
        """Follow up to ``max_redirects`` redirects (not magnet links)."""
        for _ in range(max_redirects):
            if not response.is_redirect:
                break
            if (response.redirecting_to or "").startswith("magnet:"):
                break
            response = await self._follow_once(
                response,
                referrer,
                override_redirect_url,
                override_cookies,
                accumulate_cookies,
            )
            if accumulate_cookies:
                accumulated = self.resolve_cookies(
                    _join(override_cookies, response.cookies)
                )
                self._owner.cookie_header = accumulated
                override_cookies = response.cookies = accumulated
            if override_cookies is not None and response.cookies is None:
                response.cookies = override_cookies
        return response

    async def _follow_once(
        self,
        response: WebResult,
        referrer: str | None,
        override_url: str | None,
        override_cookies: str | None,
        accumulate_cookies: bool,
    ) -> WebResult:
        cookies = override_cookies or ""
        if accumulate_cookies:
            cookies = self.resolve_cookies(cookies)
        request = WebRequest(
            url=override_url or response.redirecting_to,
            referer=referrer,
            cookies=cookies,
            encoding=self._owner.encoding,
        )
        return await self._client.get_result(request)

    async def login_and_follow_redirect(
        self,
        url: str,
        data: PostData,
        cookies: str | None,
        return_cookies_from_first_call: bool,
        redirect_url_override: str | None = None,
        referer: str | None = None,
        accumulate_cookies: bool = False,
        headers: dict[str, str] | None = None,
    ) -> WebResult:
        """POST a login form and follow the redirects that come back."""
        request = WebRequest(
            url=url,
            type=RequestType.POST,
            cookies=cookies
            if cookies is not None
            else self._owner.cookie_header,
            referer=referer,
            post_data=list(data),
            encoding=self._owner.encoding,
            headers=dict(headers or {}),
        )
        response = await self._client.get_result(request)
        check_site_down(response)
        if accumulate_cookies:
            response.cookies = self.resolve_cookies(
                _join(request.cookies, response.cookies)
            )
        first_call_cookies = response.cookies
        if response.is_redirect:
            response = await self.follow_if_redirect(
                response,
                request.url,
                redirect_url_override,
                response.cookies,
                accumulate_cookies,
            )
        if return_cookies_from_first_call:
            later = response.cookies if accumulate_cookies else None
            response.cookies = self.resolve_cookies(
                _join(first_call_cookies, later)
            )
        return response
