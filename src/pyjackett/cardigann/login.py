"""Login, login test and re-login for Cardigann indexers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from bs4 import BeautifulSoup

from pyjackett.cardigann import html_dom
from pyjackett.cardigann.definition import ErrorBlock, LoginBlock
from pyjackett.cardigann.headers import parse_custom_headers
from pyjackett.cardigann.host import CardigannHost
from pyjackett.cardigann.html_selectors import handle_selector
from pyjackett.cardigann.login_captcha import (
    add_captcha_items,
    captcha_answer_fields,
    simple_captcha_fields,
)
from pyjackett.cardigann.login_form import (
    apply_configured_inputs,
    build_multipart,
    form_fields,
    selector_values,
)
from pyjackett.cardigann.methods import LoginMethod
from pyjackett.cardigann.redirects import (
    result_domain_hint,
)
from pyjackett.cardigann.template import Variables, apply_template
from pyjackett.config.indexer_config import ConfigurationData
from pyjackett.core.exceptions import ConfigurationError
from pyjackett.http.models import RequestType, WebRequest, WebResult
from pyjackett.utils.urls import build_query_string

logger = logging.getLogger(__name__)

UNAUTHORIZED = 401

LoginStrategy = Callable[..., Awaitable[bool]]


class CardigannLogin:
    """Implements the login methods: post, form, cookie, get and oneurl."""

    def __init__(self, host: CardigannHost) -> None:
        self._host = host
        self._landing_result: WebResult | None = None
        self._landing_document: BeautifulSoup | None = None
        self._strategies: dict[LoginMethod, LoginStrategy] = {
            LoginMethod.POST: self._post_strategy,
            LoginMethod.FORM: self._login_form,
            LoginMethod.COOKIE: self._cookie_strategy,
            LoginMethod.GET: self._get_strategy,
            LoginMethod.ONEURL: self._oneurl_strategy,
        }

    # ---- shared helpers -----------------------------------------------------

    @property
    def _login(self) -> LoginBlock | None:
        return self._host.definition.login

    def _headers(self, variables: Variables) -> dict[str, str]:
        definition = self._host.definition
        source = self._login.headers if self._login else None
        if source is None and definition.search:
            source = definition.search.headers
        return parse_custom_headers(source, variables)

    def _config_error(self, message: str) -> ConfigurationError:
        return ConfigurationError(message, self._host.config_data)

    def _store_cookies(self, cookies: str | None) -> None:
        self._host.cookie_header = cookies

    # ---- error detection ----------------------------------------------------

    def check_for_error(
        self, result: WebResult, errors: list[ErrorBlock] | None
    ) -> bool:
        """Raise if the page shows one of the definition's error messages."""
        if result.status == UNAUTHORIZED:  # e.g. YGGtorrent
            raise self._config_error(
                "401 Unauthorized, check your credentials"
            )
        if not errors:
            return True
        document = html_dom.parse_html(result.content_string)
        variables = self._host.base_variables()
        context = self._host.filter_context(variables)
        for error in errors:
            element = html_dom.query_selector(document, error.selector)
            if element is None:
                continue
            message = html_dom.text_content(element)
            if error.message is not None:
                message = handle_selector(
                    error.message,
                    html_dom.root_element(document),
                    variables,
                    context,
                )
            raise self._config_error(f"Error: {message.strip()}")
        return True

    # ---- login methods ------------------------------------------------------

    async def do_login(self, cookies: str | None = None) -> bool:
        login = self._login
        if login is None:
            return True
        variables = self._host.base_variables()
        headers = self._headers(variables)
        strategy = self._strategy_for(login.method)
        if not await strategy(login, variables, headers, cookies):
            return False
        logger.debug(
            "CardigannIndexer (%s): Cookies after login: %s",
            self._host.id,
            self._host.cookie_header,
        )
        return True

    def _strategy_for(self, method: str | None) -> LoginStrategy:
        """The coroutine implementing ``method``; fails when unknown."""
        try:
            return self._strategies[LoginMethod(method)]
        except ValueError:
            raise NotImplementedError(
                f"Login method {method} not implemented"
            ) from None

    # Every strategy takes (login, variables, headers, cookies) and returns
    # False only when the login could not be completed automatically.

    async def _post_strategy(self, login, variables, headers, cookies):
        await self._login_post(login, variables, headers)
        return True

    async def _cookie_strategy(self, login, variables, headers, cookies):
        self._login_cookie()
        return True

    async def _get_strategy(self, login, variables, headers, cookies):
        await self._login_get(login, variables, headers)
        return True

    async def _oneurl_strategy(self, login, variables, headers, cookies):
        await self._login_oneurl(login, variables, headers)
        return True

    async def _login_post(
        self, login: LoginBlock, variables: Variables, headers: dict[str, str]
    ) -> None:
        pairs = [
            (key, apply_template(value, variables))
            for key, value in (login.inputs or {}).items()
        ]
        url = self._host.resolve_path(apply_template(login.path, variables))
        self._store_cookies(
            "; ".join(login.cookies) if login.cookies else None
        )
        result = await self._host.requester.login_and_follow_redirect(
            url, pairs, None, True, None, self._host.site_link, True, headers
        )
        self._store_cookies(result.cookies)
        self.check_for_error(result, login.error)

    def _login_cookie(self) -> None:
        item = self._host.config_data.get_dynamic("cookie")
        self._store_cookies(item.value)

    async def _login_get(
        self, login: LoginBlock, variables: Variables, headers: dict[str, str]
    ) -> None:
        pairs = [
            (key, apply_template(value, variables))
            for key, value in (login.inputs or {}).items()
        ]
        path = apply_template(login.path, variables)
        url = self._host.resolve_path(f"{path}?{build_query_string(pairs)}")
        await self._request_login_url(url, headers, login)

    async def _login_oneurl(
        self, login: LoginBlock, variables: Variables, headers: dict[str, str]
    ) -> None:
        suffix = apply_template(login.inputs["oneurl"], variables)
        path = apply_template(login.path, variables)
        url = self._host.resolve_path(path + suffix)
        await self._request_login_url(url, headers, login)

    async def _request_login_url(
        self, url: str, headers: dict[str, str], login: LoginBlock
    ) -> None:
        self._store_cookies(None)
        result = await self._host.requester.request(
            url, None, referer=self._host.site_link, headers=headers
        )
        self._store_cookies(result.cookies)
        self.check_for_error(result, login.error)

    # ---- form login ---------------------------------------------------------

    async def _login_form(
        self,
        login: LoginBlock,
        variables: Variables,
        headers: dict[str, str],
        cookies: str | None,
    ) -> bool:
        login_url = self._host.resolve_path(
            apply_template(login.path, variables)
        )
        if self._landing_document is None:
            setup = await self.get_configuration_for_setup(True, cookies)
            if setup is None:  # captcha during an automatic login
                return False
        page = self._landing_document
        form = html_dom.query_selector(page, login.form or "form")
        if form is None:
            raise self._config_error(
                f"Login failed: No form found on {login_url} using form "
                f"selector {login.form or 'form'}"
            )
        fields = await self._collect_fields(
            login, form, page, variables, headers, login_url
        )
        submit_url = self._submit_url(login, form, page, variables, login_url)
        # forget the landing page: a later re-login needs a fresh one
        self._landing_result = None
        self._landing_document = None
        result = await self._submit_form(
            form, fields, submit_url, login_url, headers
        )
        self._store_cookies(result.cookies)
        self.check_for_error(result, login.error)
        return True

    async def _collect_fields(
        self, login, form, page, variables, headers, login_url
    ) -> dict[str, str]:
        host = self._host
        root = html_dom.root_element(page)
        context = host.filter_context(variables)
        fields = form_fields(form)
        apply_configured_inputs(
            fields, login, page, variables, host.config_data
        )
        fields.update(
            selector_values(
                login.selectorinputs, root, variables, context, "input"
            )
        )
        fields.update(
            await simple_captcha_fields(host, page, login_url, headers)
        )
        if login.captcha is not None:
            fields.update(
                captcha_answer_fields(
                    host, login.captcha, page, login.selectors
                )
            )
        return fields

    def _submit_url(self, login, form, page, variables, login_url) -> str:
        context = self._host.filter_context(variables)
        query = selector_values(
            login.getselectorinputs,
            html_dom.root_element(page),
            variables,
            context,
            "get selector input",
        )
        action = login.submitpath or form.get("action") or ""
        if query:
            action += "?" + build_query_string(query.items())
        return self._host.resolve_path(action, login_url)

    async def _submit_form(
        self, form, fields, submit_url, login_url, headers
    ) -> WebResult:
        host = self._host
        if form.get("enctype") == "multipart/form-data":
            body, content_type = build_multipart(fields)
            headers = {**headers, "Content-Type": content_type}
            request = WebRequest(
                url=submit_url,
                type=RequestType.POST,
                cookies=host.cookie_header,
                referer=host.site_link,
                post_data=list(fields.items()),
                headers=headers,
                raw_body=body,
            )
            return await host.requester.send(request)
        return await host.requester.login_and_follow_redirect(
            submit_url,
            list(fields.items()),
            host.cookie_header,
            True,
            None,
            login_url,
            True,
            headers,
        )

    # ---- setup form ---------------------------------------------------------

    async def _load_landing_page(
        self, login: LoginBlock, login_url: str, headers, cookies
    ) -> WebResult:
        """Fetch the login page and remember its parsed document."""
        host = self._host
        self._store_cookies(
            "; ".join(login.cookies) if login.cookies else None
        )
        result = await host.requester.request(
            login_url, cookies, referer=host.site_link, headers=headers
        )
        if host.definition.followredirect:
            result = await host.requester.follow_if_redirect(
                result, login_url, None, result.cookies, True
            )
        self._landing_result = result
        self._landing_document = html_dom.parse_html(result.content_string)
        return result

    def _abort_on_captcha(self) -> None:
        """An automatic login cannot solve a captcha: report and give up."""
        self._host.config_data.last_error.value = (
            "Got captcha during automatic login, please reconfigure manually"
        )
        logger.error(
            "CardigannIndexer (%s): Found captcha during automatic "
            "login, aborting",
            self._host.id,
        )
        self._landing_document = None

    async def get_configuration_for_setup(
        self, automatic_login: bool = False, cookies: str | None = None
    ) -> ConfigurationData | None:
        """Load the login page, adding a captcha to the form if needed.

        Returns None when a captcha blocks an automatic login.
        """
        host, login = self._host, self._login
        if login is None or login.method != LoginMethod.FORM:
            return host.config_data
        variables = host.base_variables()
        headers = self._headers(variables)
        login_url = host.resolve_path(apply_template(login.path, variables))
        result = await self._load_landing_page(
            login, login_url, headers, cookies
        )
        has_captcha = login.captcha is not None and await add_captcha_items(
            host,
            login.captcha,
            self._landing_document,
            login_url,
            result.cookies,
            headers,
        )
        if has_captcha and automatic_login:
            self._abort_on_captcha()
            return None
        return host.config_data

    # ---- login test ---------------------------------------------------------

    async def test_login(self) -> bool:
        login = self._login
        if login is None or login.test is None:
            return False
        host = self._host
        url = host.resolve_path(login.test.path)
        headers = self._headers(host.base_variables())
        result = await host.requester.request(url, headers=headers)
        if (
            result.is_redirect
            and result_domain_hint(result, host.site_link) is None
        ):
            logger.warning(
                "Redirected to %s from test login request",
                result.redirecting_to,
            )
            result = await host.requester.follow_if_redirect(
                result, url, None, result.cookies, True, 1
            )
        if result.is_redirect:
            raise self._config_error(self._redirect_message(result))
        self._assert_test_selector(login, result)
        return True

    def _redirect_message(self, result: WebResult) -> str:
        message = f"Login Failed, got redirected to: {result.redirecting_to}"
        hint = result_domain_hint(result, self._host.site_link)
        if hint is None:
            return message
        message += f" Try changing the indexer URL to {hint}."
        if self._host.definition.followredirect:
            self._host.set_site_link(hint)
            message += " Updated site link, please try again."
        return message

    def _assert_test_selector(self, login: LoginBlock, result: WebResult):
        selector = login.test.selector
        if selector is None:
            return
        document = html_dom.parse_html(result.content_string)
        if not html_dom.query_selector_all(document, selector):
            raise self._config_error(
                f'Login failed: Selector "{selector}" didn\'t match'
            )

    # ---- re-login -----------------------------------------------------------

    def check_if_login_is_needed(self, response: WebResult) -> bool:
        """True if the response shows we are logged out."""
        host = self._host
        if response.is_redirect:
            hint = result_domain_hint(response, host.site_link)
            if hint is not None:
                raise self._config_error(self._domain_change_message(hint))
            logger.error("Redirected to: %s", response.redirecting_to)
            return True
        login = self._login
        if login is None or login.test is None:
            return False
        content_type = response.header("content-type")
        is_html = content_type is None or "text/html" in content_type
        if login.test.selector is not None and is_html:
            document = html_dom.parse_html(response.content_string)
            return not html_dom.query_selector_all(
                document, login.test.selector
            )
        return False

    def _domain_change_message(self, hint: str) -> str:
        message = (
            f"Got redirected to another domain. Try changing the indexer "
            f"URL to {hint}."
        )
        if self._host.definition.followredirect:
            self._host.set_site_link(hint)
            message += " Updated site link, please try again."
        return message

    async def relogin(self, response: WebResult) -> None:
        logger.info("CardigannIndexer(%s): Relogin required", self._host.id)
        if not await self.do_login(response.cookies):
            raise RuntimeError("Relogin failed")
        await self.test_login()
        # new cookies may not be saved if later responses set none
        if self._host.is_configured:
            self._host.config_changed()
