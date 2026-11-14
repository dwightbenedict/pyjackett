"""Resolves the real torrent link of a result (the ``download`` block)."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, urlsplit

from pyjackett.domain.cardigann import html_dom
from pyjackett.domain.cardigann.definition import (
    BeforeBlock,
    DownloadBlock,
    RequestBlock,
    SelectorField,
)
from pyjackett.domain.cardigann.filters import apply_filters
from pyjackett.domain.cardigann.headers import parse_custom_headers
from pyjackett.domain.cardigann.methods import request_type
from pyjackett.domain.cardigann.template import Variables, apply_template
from pyjackett.domain.http_models import RequestType, WebResult
from pyjackett.domain.magnet import info_hash_to_public_magnet
from pyjackett.domain.urls import build_query_string
from pyjackett.services.cardigann.host import CardigannHost

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
TORRENT_FILE_START = 0x64  # "d": a bencoded dictionary

Downloader = Callable[[str, RequestType, str | None, dict[str, str] | None], Awaitable[bytes]]


def uri_variables(url: str, prefix: str) -> Variables:
    """Expose the parts of ``url`` as ``<prefix>.Host``, ``.Query.x``..."""
    parts = urlsplit(url)
    default_port = 443 if parts.scheme == "https" else 80
    variables: Variables = {
        f"{prefix}.AbsoluteUri": url,
        f"{prefix}.AbsolutePath": parts.path or "/",
        f"{prefix}.Scheme": parts.scheme,
        f"{prefix}.Host": parts.hostname or "",
        f"{prefix}.Port": str(parts.port or default_port),
        f"{prefix}.PathAndQuery": (parts.path or "/") + (f"?{parts.query}" if parts.query else ""),
        f"{prefix}.Query": f"?{parts.query}" if parts.query else "",
    }
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        variables.setdefault(f"{prefix}.Query.{key}", value)  # first wins
    return variables


class CardigannDownload:
    """Follows ``before``/``selectors``/``infohash`` rules to get a file."""

    def __init__(self, host: CardigannHost, download: Downloader) -> None:
        self._host = host
        self._download = download

    # ---- public -------------------------------------------------------------

    async def download(self, link: str) -> bytes:
        block = self._host.definition.download
        if block is None:
            return await self._plain_download(link, RequestType.GET)
        variables = self._host.base_variables()
        variables.update(uri_variables(link, ".DownloadUri"))
        headers = self._headers(block, variables)
        response = await self._run_before(block, link, variables, headers)
        method = request_type(block.method)
        if block.infohash is not None:
            result = await self._download_by_infohash(
                block, link, variables, headers, response, method
            )
            if result is not None:
                return result
        elif block.selectors:
            return await self._download_by_selectors(
                block, link, variables, headers, response, method
            )
        return await self._plain_download(link, method)

    def _headers(self, block: DownloadBlock, variables: Variables):
        search = self._host.definition.search
        source = block.headers or (search.headers if search else None)
        return parse_custom_headers(source, variables)

    async def _plain_download(self, link: str, method: RequestType) -> bytes:
        definition = self._host.definition
        block = definition.download
        search = definition.search
        source = (block.headers if block else None) or (search.headers if search else None)
        headers = parse_custom_headers(source, self._host.base_variables())
        return await self._download(link, method, link, headers)

    # ---- requests -----------------------------------------------------------

    async def _redirectable_request(self, url: str, headers: dict[str, str]) -> WebResult:
        requester = self._host.requester
        response = await requester.request(url, headers=headers)
        for _ in range(MAX_REDIRECTS):
            if not response.is_redirect:
                break
            response = await requester.request(response.redirecting_to, headers=headers)
        return response

    async def _request_block(
        self,
        block: RequestBlock,
        variables: Variables,
        referer: str,
        headers: dict[str, str],
    ) -> WebResult:
        host = self._host
        url = host.resolve_path(apply_template(block.path, variables))
        method = request_type(block.method)
        pairs = [
            (key, apply_template(value, variables)) for key, value in (block.inputs or {}).items()
        ]
        if pairs and method is RequestType.GET:
            url += "?" if "?" not in url else ""
            url += build_query_string(pairs, host.encoding, block.queryseparator)
            pairs = []
        return await host.requester.request_with_retry(url, None, method, referer, pairs, headers)

    async def _run_before(
        self,
        block: DownloadBlock,
        link: str,
        variables: Variables,
        headers: dict[str, str],
    ) -> WebResult | None:
        before = block.before
        if before is None:
            return None
        if before.pathselector is not None:
            page = await self._redirectable_request(link, headers)
            path = self._match_selector(page, before.pathselector, variables)
            before = dataclasses.replace(before, path=path)
        return await self._request_block(before, variables, link, headers)

    # ---- selector matching --------------------------------------------------

    def _match_selector(
        self,
        response: WebResult,
        selector: SelectorField,
        variables: Variables,
    ) -> str | None:
        text = apply_template(selector.selector, variables)
        document = html_dom.parse_html(response.content_string)
        element = html_dom.query_selector(document, text)
        if element is None:
            logger.debug(
                "CardigannIndexer (%s): Selector %s could not match any elements.",
                self._host.id,
                text,
            )
            return None
        if selector.attribute is None:
            value = html_dom.text_content(element)
        else:
            value = html_dom.attribute_value(element, selector.attribute)
            if value is None:
                raise ValueError(
                    f'Attribute "{selector.attribute}" is not set for '
                    f"element {html_dom.to_html(element)}"
                )
        return apply_filters(value, selector.filters, self._host.filter_context(variables))

    # ---- strategies ---------------------------------------------------------

    async def _page_for(
        self,
        use_before: bool,
        before: BeforeBlock | None,
        response: WebResult | None,
        link: str,
        headers: dict[str, str],
    ) -> WebResult:
        if use_before and before is not None and response is not None:
            return response
        return await self._redirectable_request(link, headers)

    async def _download_by_infohash(
        self, block, link, variables, headers, response, method
    ) -> bytes | None:
        infohash = block.infohash
        try:
            page = await self._page_for(
                infohash.usebeforeresponse,
                block.before,
                response,
                link,
                headers,
            )
            info_hash = self._match_selector(page, infohash.hash, variables)
            if info_hash is None:
                raise ValueError("InfoHash selectors didn't match hash.")
            title = self._match_selector(page, infohash.title, variables)
            if title is None:
                raise ValueError("InfoHash selectors didn't match title.")
            magnet = info_hash_to_public_magnet(info_hash, title)
            return await self._download(magnet, method, magnet, None)
        except Exception:
            logger.exception(
                "CardigannIndexer (%s): An exception occurred while trying Infohash block",
                self._host.id,
            )
            return None

    async def _download_by_selectors(
        self, block, link, variables, headers, response, method
    ) -> bytes:
        for selector in block.selectors:
            try:
                page = await self._page_for(
                    selector.usebeforeresponse,
                    block.before,
                    response,
                    link,
                    headers,
                )
                result = await self._try_selector(selector, page, link, variables, headers, method)
            except Exception:
                logger.exception(
                    "CardigannIndexer (%s): An exception occurred while "
                    "trying selector %s, retrying with next available "
                    "selector",
                    self._host.id,
                    selector.selector,
                )
                continue
            if result is not None:
                return result
        logger.error(
            "CardigannIndexer (%s): Download selectors didn't match",
            self._host.id,
        )
        raise RuntimeError("Download selectors didn't match")

    async def _try_selector(self, selector, page, link, variables, headers, method) -> bytes | None:
        """Bytes behind the link the selector found, or None to move on."""
        href = self._match_selector(page, selector, variables)
        if href is None:
            return None
        torrent_link = self._host.resolve_path(href, link)
        if (
            not torrent_link.startswith("magnet:")
            and self._host.definition.testlinktorrent
            and not await self._looks_like_torrent(torrent_link, headers)
        ):
            logger.debug(
                "CardigannIndexer (%s): Download selector %s's torrent file "
                "is invalid, retrying with next available selector",
                self._host.id,
                selector.selector,
            )
            return None
        return await self._download(torrent_link, method, torrent_link, headers)

    async def _looks_like_torrent(self, url: str, headers: dict[str, str]) -> bool:
        response = await self._redirectable_request(url, headers)
        content = response.content_bytes
        return len(content) < 1 or content[0] == TORRENT_FILE_START
