"""Helpers for the ``form`` login method: fields, inputs, multipart."""

from __future__ import annotations

import time

from pyjackett.cardigann import html_dom
from pyjackett.cardigann.definition import LoginBlock, SelectorBlock
from pyjackett.cardigann.filters import FilterContext
from pyjackett.cardigann.html_dom import Element
from pyjackett.cardigann.html_selectors import handle_selector
from pyjackett.cardigann.template import Variables, apply_template
from pyjackett.core.exceptions import ConfigurationError

_CHOICE_TYPES = ("checkbox", "radio")


def form_fields(form: Element) -> dict[str, str]:
    """Current values of the form's enabled, named inputs."""
    fields: dict[str, str] = {}
    for element in html_dom.query_selector_all(form, "input"):
        name = html_dom.attribute_value(element, "name")
        if name is None or html_dom.has_attribute(element, "disabled"):
            continue
        input_type = html_dom.attribute_value(element, "type") or ""
        is_choice = input_type.lower() in _CHOICE_TYPES
        if is_choice and not html_dom.has_attribute(element, "checked"):
            continue
        fields[name] = html_dom.attribute_value(element, "value") or ""
    return fields


def _input_name(
    key: str, document: Element, use_selectors: bool, config
) -> str:
    """A login input key is a field name, or a CSS selector to resolve."""
    if not use_selectors:
        return key
    element = html_dom.query_selector(document, key)
    if element is None:
        raise ConfigurationError(
            f"Login failed: No input found using selector {key}", config
        )
    return html_dom.attribute_value(element, "name")


def apply_configured_inputs(
    fields: dict[str, str],
    login: LoginBlock,
    document: Element,
    variables: Variables,
    config,
) -> None:
    """Overlay the definition's ``inputs`` on the scraped form values."""
    for key, template in (login.inputs or {}).items():
        name = _input_name(key, document, login.selectors, config)
        fields[name] = apply_template(template, variables)


def selector_values(
    blocks: dict[str, SelectorBlock] | None,
    root: Element,
    variables: Variables,
    context: FilterContext,
    label: str,
) -> dict[str, str]:
    """Evaluate ``selectorinputs``-style blocks against the login page."""
    values: dict[str, str] = {}
    for key, block in (blocks or {}).items():
        try:
            value = handle_selector(
                block, root, variables, context, required=not block.optional
            )
        except Exception as error:
            raise RuntimeError(
                f"Error while parsing {label}={key}, "
                f"selector={block.selector}: {error}"
            ) from error
        if not (block.optional and value is None):
            values[key] = value
    return values


def build_multipart(fields: dict[str, str]) -> tuple[str, str]:
    """Return (body, content type) of a multipart/form-data submission."""
    boundary = "---------------------------" + str(int(time.time()))
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        f"\r\n\r\n{value}"
        for name, value in fields.items()
    ]
    parts.append(f"--{boundary}--")
    return "\r\n".join(parts), f"multipart/form-data; boundary={boundary}"
