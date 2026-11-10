"""HTML/XML parsing and CSS selection helpers (BeautifulSoup + soupsieve).

html5lib is used for HTML because it implements the HTML5 parsing rules
(implicit ``<tbody>``, ...) the selectors in the definitions rely on.
"""

from __future__ import annotations

import functools
import warnings

import soupsieve
from bs4 import BeautifulSoup, Tag
from bs4.builder import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_ROOT_PREFIX = ":root"
_CONTAINS = ":contains("


def parse_html(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, "html5lib", multi_valued_attributes=None)


def parse_xml(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, "xml", multi_valued_attributes=None)


def root_element(document: BeautifulSoup) -> Tag | None:
    """The first element of the document (``<html>``, ``<rss>``, ...)."""
    return document.find(True)


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
def translate_selector(selector: str) -> str:
    """Rewrite ``:contains(text)`` into soupsieve's quoted form."""
    parts, position = [], 0
    while True:
        found = selector.find(_CONTAINS, position)
        if found < 0:
            parts.append(selector[position:])
            return "".join(parts)
        parts.append(selector[position:found])
        argument, position = _read_argument(selector, found + len(_CONTAINS))
        parts.append(f":-soup-contains({_quote_argument(argument)})")


def _compile(selector: str) -> soupsieve.SoupSieve:
    return soupsieve.compile(translate_selector(selector))


# ---- querying ---------------------------------------------------------------


def _resolve_root(element: Tag, selector: str) -> tuple[Tag, str]:
    """``:root`` is not supported by every engine; climb to the root."""
    if not selector.startswith(_ROOT_PREFIX):
        return element, selector
    while element.parent is not None and isinstance(element.parent, Tag):
        element = element.parent
    return element, selector[len(_ROOT_PREFIX) :]


def query_selector(element: Tag, selector: str) -> Tag | None:
    element, selector = _resolve_root(element, selector)
    return _compile(selector).select_one(element)


def query_selector_all(element: Tag | BeautifulSoup, selector: str):
    return _compile(selector).select(element)


def matches(element: Tag, selector: str) -> bool:
    return _compile(selector).match(element)


# ---- reading ----------------------------------------------------------------


def text_content(element: Tag) -> str:
    return element.get_text()


def attribute_value(element: Tag, name: str) -> str | None:
    value = element.get(name)
    if isinstance(value, list):  # multi-valued attributes, if ever enabled
        return " ".join(value)
    return value


def to_html(element: Tag | None) -> str:
    """Markup of ``element`` for log and error messages."""
    return "<NULL>" if element is None else element.prettify()
