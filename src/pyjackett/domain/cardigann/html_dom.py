"""HTML/XML parsing and CSS selection helpers (selectolax + lexbor).

Lexbor implements the HTML5 parsing rules (implicit ``<tbody>``, ...) the
selectors in the definitions rely on. It has no XML mode, so XML documents
are rewritten into markup it keeps intact: empty-element tags are expanded,
namespace prefixes are dropped (``<tv:raw_title>`` becomes ``<raw_title>``, as
definitions select by local name) and the names of HTML void elements
(``<link>``) are given a prefix, both in the markup and in the selectors used
on such documents.
"""

from __future__ import annotations

import functools
import re

from selectolax.lexbor import LexborHTMLParser, LexborNode

Document = LexborHTMLParser
Element = LexborNode

_ROOT_PREFIX = ":root"
_CONTAINS = ":contains("
_XML_WRAPPER = "pjxml"
_XML_PREFIX = "xml-"
_VOID_ELEMENTS = (
    "area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr"
)
_EMPTY_TAG = re.compile(r"<([\w:.-]+)((?:\s[^<>]*?)?)\s*/>")
_NAMESPACE_PREFIX = re.compile(r"<(/?)[\w.-]+:(?=[\w.-])")
_VOID_TAG = re.compile(rf"<(/?)({_VOID_ELEMENTS})(?=[\s/>])", re.IGNORECASE)
_VOID_SELECTOR = re.compile(
    rf"(?<![\w#.\[=\"'-])({_VOID_ELEMENTS})(?![\w-])", re.IGNORECASE
)


def parse_html(markup: str) -> Document:
    return LexborHTMLParser(markup)


def parse_xml(markup: str) -> Document:
    expanded = _EMPTY_TAG.sub(r"<\1\2></\1>", markup)
    local_names = _NAMESPACE_PREFIX.sub(r"<\1", expanded)
    prefixed = _VOID_TAG.sub(rf"<\1{_XML_PREFIX}\2", local_names)
    return LexborHTMLParser(f"<{_XML_WRAPPER}>{prefixed}</{_XML_WRAPPER}>")


def root_element(document: Document) -> Element | None:
    """The first element of the document (``<html>``, ``<rss>``, ...)."""
    return document.root


# ---- selector dialect -------------------------------------------------------


def _read_argument(selector: str, start: int) -> tuple[str, int]:
    """Read a parenthesised argument; returns (text, index after ``)``)."""
    depth, quote, position = 1, None, start
    while position < len(selector) and depth:
        char = selector[position]
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        position += 1
    return selector[start : position - 1], position


def _quote_argument(argument: str) -> str:
    argument = argument.strip()
    if argument[:1] in "\"'" and argument[-1:] == argument[:1]:
        argument = argument[1:-1]
    escaped = argument.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@functools.lru_cache(maxsize=2048)
def translate_selector(selector: str, xml: bool = False) -> str:
    """Rewrite ``:contains(text)`` into lexbor's case-insensitive form."""
    if xml:
        selector = _VOID_SELECTOR.sub(rf"{_XML_PREFIX}\1", selector)
    parts, position = [], 0
    while True:
        found = selector.find(_CONTAINS, position)
        if found < 0:
            parts.append(selector[position:])
            return "".join(parts)
        parts.append(selector[position:found])
        argument, position = _read_argument(selector, found + len(_CONTAINS))
        parts.append(f":lexbor-contains({_quote_argument(argument)} i)")


# ---- querying ---------------------------------------------------------------


def _top(element: Element) -> Element:
    while element.parent is not None:
        element = element.parent
    return element


def _is_xml(scope: Document | Element) -> bool:
    if isinstance(scope, LexborHTMLParser):
        return scope.css_first(_XML_WRAPPER) is not None
    node = scope
    while node is not None:
        if node.tag == _XML_WRAPPER:
            return True
        node = node.parent
    return False


def _prepare(scope: Document | Element, selector: str):
    """``:root`` is relative to the whole document, not to ``scope``."""
    translated = translate_selector(selector, _is_xml(scope))
    if translated.startswith(_ROOT_PREFIX) and isinstance(scope, Element):
        scope = _top(scope)
    return scope, translated


def query_selector(element: Element, selector: str) -> Element | None:
    scope, translated = _prepare(element, selector)
    return scope.css_first(translated)


def query_selector_all(
    element: Document | Element, selector: str
) -> list[Element]:
    scope, translated = _prepare(element, selector)
    return scope.css(translated)


def matches(element: Element, selector: str) -> bool:
    """True if ``element`` itself matches (not just one of its children)."""
    translated = translate_selector(selector, _is_xml(element))
    scope = element.parent
    if scope is None:
        return element.css_matches(translated)
    return any(
        found.mem_id == element.mem_id for found in scope.css(translated)
    )


# ---- reading ----------------------------------------------------------------


def text_content(element: Element) -> str:
    return element.text()


def attribute_value(element: Element, name: str) -> str | None:
    """Value of ``name``; None if absent, empty for valueless attributes."""
    attributes = element.attributes
    if name not in attributes:
        return None
    return attributes[name] or ""


def has_attribute(element: Element, name: str) -> bool:
    return name in element.attributes


def to_html(element: Element | None) -> str:
    """Markup of ``element`` for log and error messages."""
    return "<NULL>" if element is None else element.html


# ---- navigating and editing -------------------------------------------------


def previous_element(element: Element) -> Element | None:
    """The closest previous sibling that is an element."""
    sibling = element.prev
    while sibling is not None and not sibling.is_element_node:
        sibling = sibling.prev
    return sibling


def parent_element(element: Element) -> Element | None:
    parent = element.parent
    if parent is None or parent.is_document_node:
        return None
    return parent


def copy_children(source: Element, target: Element) -> None:
    """Append a copy of every child of ``source`` to ``target``."""
    for child in list(source.iter(include_text=True)):
        target.insert_child(child)
