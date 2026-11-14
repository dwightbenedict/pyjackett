"""Runs a search against a tracker as described by a definition."""

from __future__ import annotations

import json
import logging

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.cardigann import html_dom
from pyjackett.domain.cardigann.definition import SearchPathBlock
from pyjackett.domain.cardigann.filters import apply_filters
from pyjackett.domain.cardigann.headers import parse_custom_headers
from pyjackett.domain.cardigann.html_results import parse_html_results
from pyjackett.domain.cardigann.json_results import parse_json_results
from pyjackett.domain.cardigann.result_context import ResultContext
from pyjackett.domain.cardigann.row_fields import RowParser, field_specs
from pyjackett.domain.cardigann.template import Variables
from pyjackett.domain.cardigann.variables import (
    add_keyword_variables,
    add_query_variables,
)
from pyjackett.domain.http_models import WebResult
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.release import ReleaseInfo
from pyjackett.services.cardigann.host import CardigannHost
from pyjackett.services.cardigann.login import CardigannLogin
from pyjackett.services.cardigann.search_request import (
    SearchRequest,
    build_search_request,
    restrict_categories,
)

logger = logging.getLogger(__name__)

HTTP_OK = 200


class CardigannSearch:
    """Builds requests for every search path and parses the responses."""

    def __init__(
        self,
        host: CardigannHost,
        login: CardigannLogin,
        caps: TorznabCapabilities,
        default_categories: list[str],
        max_rows: int | None = None,
    ) -> None:
        self._host = host
        self._max_rows = max_rows
        self._login = login
        self._caps = caps
        self._default_categories = default_categories
        self._search = host.definition.search
        self._row_parser = RowParser(field_specs(self._search), caps.categories, host.id)

    # ---- entry point --------------------------------------------------------

    async def perform_query(self, query: TorznabQuery) -> list[ReleaseInfo]:
        host = self._host
        variables = host.base_variables()
        add_query_variables(variables, query)
        add_keyword_variables(
            variables,
            self._search.keywordsfilters,
            host.filter_context(variables),
        )
        mapped = self._caps.categories.to_tracker_categories(query) or self._default_categories
        releases: list[ReleaseInfo] = []
        visited: set[str] = set()
        for path in self._search.paths:
            variables[".Categories"] = mapped
            categories = restrict_categories(mapped, path)
            if categories is None:
                continue
            variables[".Categories"] = categories
            request = build_search_request(host, self._search, path, variables)
            if request.is_get and request.url in visited:
                logger.debug("Skipping duplicated request: %s", request.url)
                continue
            visited.add(request.url)
            releases += await self._search_path(path, request, variables, query)
        return releases[: query.limit] if query.limit > 0 else releases

    # ---- one path -----------------------------------------------------------

    async def _fetch(
        self,
        path: SearchPathBlock,
        request: SearchRequest,
        variables: Variables,
    ) -> WebResult:
        requester = self._host.requester
        headers = parse_custom_headers(self._search.headers, variables)
        response = await requester.request(
            request.url,
            method=request.method,
            headers=headers,
            data=request.inputs,
        )
        if response.is_redirect and path.followredirect:
            response = await requester.follow_if_redirect(response)
        return response

    async def _fetch_logged_in(
        self,
        path: SearchPathBlock,
        request: SearchRequest,
        variables: Variables,
    ) -> WebResult:
        """Fetch, logging in again once if the session expired."""
        response = await self._fetch(path, request, variables)
        if self._login.check_if_login_is_needed(response):
            await self._login.relogin(response)
            response = await self._fetch(path, request, variables)
        return response

    async def _search_path(
        self,
        path: SearchPathBlock,
        request: SearchRequest,
        variables: Variables,
        query: TorznabQuery,
    ) -> list[ReleaseInfo]:
        response_type = path.response.type if path.response else None
        context = self._result_context(variables)
        if response_type == "json":
            return await self._search_json(path, request, variables, query, context)
        return await self._search_markup(
            path, request, variables, query, context, response_type == "xml"
        )

    def _result_context(self, variables: Variables) -> ResultContext:
        return ResultContext(
            self._search,
            self._row_parser,
            self._caps,
            self._host.id,
            self._host.filter_context(variables),
            self._max_rows,
        )

    # ---- JSON ---------------------------------------------------------------

    async def _search_json(self, path, request, variables, query, context) -> list[ReleaseInfo]:
        response = await self._fetch_logged_in(path, request, variables)
        text = response.content_string
        if response.status != HTTP_OK:
            raise RuntimeError(
                f"Error Parsing Json Response: Status={response.status} Response={text}"
            )
        if self._declares_no_results(path, text):
            return []
        try:
            parsed = json.loads(text)
        except ValueError as error:
            logger.warning(
                "Unexpected response content (%d bytes): %s",
                len(response.content_bytes),
                text,
            )
            raise RuntimeError("Error Parsing Json Response") from error
        return parse_json_results(parsed, context, variables, query, request.url)

    @staticmethod
    def _declares_no_results(path: SearchPathBlock, text: str) -> bool:
        """The tracker's own "nothing found" answer (text or empty body)."""
        message = path.response.no_results_message if path.response else None
        if message is None:
            return False
        return message in text if message else text == ""

    # ---- HTML / XML ---------------------------------------------------------

    async def _search_markup(
        self, path, request, variables, query, context, is_xml
    ) -> list[ReleaseInfo]:
        if is_xml:
            response = await self._fetch(path, request, variables)
        else:
            response = await self._fetch_logged_in(path, request, variables)
        text = response.content_string
        try:
            document = self._parse_document(response, text, variables, is_xml)
            return parse_html_results(document, context, variables, query, request.url)
        except Exception as error:
            raise self._parse_error(text, error) from error

    def _parse_document(self, response, text, variables, is_xml):
        parse = html_dom.parse_xml if is_xml else html_dom.parse_html
        if not is_xml:
            self._login.check_for_error(response, self._search.error)
        filters = self._search.preprocessingfilters
        if filters:
            text = apply_filters(text, filters, self._host.filter_context(variables))
        return parse(text)

    def _parse_error(self, text: str, error: Exception) -> Exception:
        logger.error(
            "CardigannIndexer (%s) parse error: %s\n\n\n\n\n%s",
            self._host.id,
            error,
            text,
        )
        return RuntimeError(f"Parse error: {error}")
