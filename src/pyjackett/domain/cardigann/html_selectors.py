"""Evaluates a :class:`SelectorBlock` against an HTML/XML element."""

from __future__ import annotations

from pyjackett.domain.cardigann import html_dom
from pyjackett.domain.cardigann.definition import SelectorBlock
from pyjackett.domain.cardigann.filters import FilterContext, apply_filters
from pyjackett.domain.cardigann.html_dom import Element
from pyjackett.domain.cardigann.template import Variables, apply_template
from pyjackett.domain.text import normalize_space


class SelectorError(Exception):
    """A required selector did not match."""


def _select_target(
    block: SelectorBlock, dom: Element, variables: Variables, required: bool
) -> Element | None:
    """The element a block refers to (``dom`` itself without a selector)."""
    if block.selector is None:
        return dom
    expanded = apply_template(block.selector, variables)
    if html_dom.matches(dom, expanded):
        return dom
    selection = html_dom.query_selector(dom, expanded)
    if selection is None and required:
        raise SelectorError(
            f'Selector "{expanded}" didn\'t match {html_dom.to_html(dom)}'
        )
    return selection


def _remove_descendants(block: SelectorBlock, selection: Element) -> None:
    if block.remove is None:
        return
    for element in html_dom.query_selector_all(selection, block.remove):
        element.decompose()


def _case_value(
    block: SelectorBlock,
    selection: Element,
    variables: Variables,
    required: bool,
) -> str | None:
    for condition, template in block.case.items():
        if html_dom.matches(selection, condition) or (
            html_dom.query_selector(selection, condition) is not None
        ):
            return apply_template(template, variables)
    if required:
        cases = ",".join(block.case)
        raise SelectorError(
            f'None of the case selectors "{cases}" matched '
            f"{html_dom.to_html(selection)}"
        )
    return None


def _attribute_value(
    block: SelectorBlock, selection: Element, required: bool
) -> str | None:
    value = html_dom.attribute_value(selection, block.attribute)
    if value is None and required:
        raise SelectorError(
            f'Attribute "{block.attribute}" is not set for element '
            f"{html_dom.to_html(selection)}"
        )
    return value


def _raw_value(
    block: SelectorBlock,
    selection: Element,
    variables: Variables,
    required: bool,
) -> str | None:
    if block.case is not None:
        return _case_value(block, selection, variables, required)
    if block.attribute is not None:
        return _attribute_value(block, selection, required)
    return html_dom.text_content(selection)


def handle_selector(
    block: SelectorBlock,
    dom: Element,
    variables: Variables,
    context: FilterContext,
    required: bool = True,
) -> str | None:
    """Extract and filter one value from ``dom``.

    Returns None when an optional selector does not match.
    """
    context.variables = variables
    if block.text is not None:
        text = apply_template(block.text, variables)
        return apply_filters(text, block.filters, context)
    selection = _select_target(block, dom, variables, required)
    if selection is None:
        return None
    _remove_descendants(block, selection)
    value = _raw_value(block, selection, variables, required)
    if value is None:
        return None
    return apply_filters(normalize_space(value), block.filters, context)
