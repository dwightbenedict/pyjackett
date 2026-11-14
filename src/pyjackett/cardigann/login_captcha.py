"""Captcha support for the ``form`` login method."""

from __future__ import annotations

import json

from pyjackett.cardigann import html_dom
from pyjackett.cardigann.definition import CaptchaBlock
from pyjackett.cardigann.host import CardigannHost
from pyjackett.cardigann.html_dom import Element
from pyjackett.config.items import (
    DisplayImageItem,
    DisplayInfoItem,
    StringItem,
)
from pyjackett.core.exceptions import ConfigurationError

SUPPORTED_TYPES = ("image", "text")
ANSWER_KEYS = {"image": "CaptchaText", "text": "CaptchaAnswer"}


async def add_captcha_items(
    host: CardigannHost,
    captcha: CaptchaBlock,
    page: Element,
    login_url: str,
    cookies: str | None,
    headers: dict[str, str],
) -> bool:
    """Show the captcha in the setup form; True if the page contained one."""
    if captcha.type not in SUPPORTED_TYPES:
        raise NotImplementedError(
            f'Captcha type "{captcha.type}" is not implemented'
        )
    element = html_dom.query_selector(page, captcha.selector)
    if element is None:
        return False
    if captcha.type == "image":
        await _add_image_item(host, element, login_url, cookies, headers)
    else:
        _add_text_item(host, element)
    return True


async def _add_image_item(
    host: CardigannHost,
    element: Element,
    login_url: str,
    cookies: str | None,
    headers: dict[str, str],
) -> None:
    image_url = host.resolve_path(
        html_dom.attribute_value(element, "src"), login_url
    )
    response = await host.requester.request(
        image_url, cookies, referer=login_url, headers=headers
    )
    host.config_data.add_dynamic(
        "CaptchaImage",
        DisplayImageItem("Captcha Image", response.content_bytes),
    )
    host.config_data.add_dynamic("CaptchaText", StringItem("Captcha Text"))


def _add_text_item(host: CardigannHost, element: Element) -> None:
    challenge = html_dom.text_content(element)
    host.config_data.add_dynamic(
        "CaptchaChallenge", DisplayInfoItem("Captcha Challenge", challenge)
    )
    host.config_data.add_dynamic("CaptchaAnswer", StringItem("Captcha Answer"))


def _answer_field_name(
    host: CardigannHost,
    captcha: CaptchaBlock,
    page: Element,
    use_selectors: bool,
) -> str:
    if not use_selectors:
        return captcha.input
    element = html_dom.query_selector(page, captcha.input)
    if element is None:
        raise ConfigurationError(
            f"Login failed: No captcha input found using {captcha.input}",
            host.config_data,
        )
    return html_dom.attribute_value(element, "name")


def captcha_answer_fields(
    host: CardigannHost,
    captcha: CaptchaBlock,
    page: Element,
    use_selectors: bool,
) -> dict[str, str]:
    """Form fields carrying the answer the user typed (if any)."""
    answer_key = ANSWER_KEYS.get(captcha.type)
    answer = host.config_data.get_dynamic(answer_key) if answer_key else None
    if answer is None:
        return {}
    name = _answer_field_name(host, captcha, page, use_selectors)
    return {name: answer.value}


async def simple_captcha_fields(
    host: CardigannHost, page: Element, login_url: str, headers: dict[str, str]
) -> dict[str, str]:
    """Solve "simpleCaptcha" pages automatically (no user input)."""
    script = html_dom.query_selector(page, 'script[src*="simpleCaptcha"]')
    if script is None:
        return {}
    captcha_url = host.resolve_path("simpleCaptcha.php?numImages=1")
    response = await host.requester.request(
        captcha_url, None, referer=login_url, headers=headers
    )
    selection = json.loads(response.content_string)["images"][0]["hash"]
    return {"captchaSelection": str(selection), "submitme": "X"}
