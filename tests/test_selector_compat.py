"""Selectors and patterns from Jackett definitions that need leniency."""

from __future__ import annotations

import pytest

from pyjackett.domain.cardigann import html_dom
from pyjackett.domain.regex_compat import replace_all

PAGE = """
<table>
 <tr id="a"><td><a href="magnet:?xt=1">one</a></td></tr>
 <tr id="b"><td><a href="/torrent/2">two</a></td></tr>
</table>
<div class="box"><div id="hit"><p><a href="/torrent/9">x</a></p></div>
 <div id="skip"><p><a href="/torrent/8">y</a></p>
  <span class="__cf_email__"></span></div></div>
<div class="poststuff" id="post"></div>
<div class="entry"><a class="download">dl</a></div>
"""


@pytest.fixture
def document():
    return html_dom.parse_html(PAGE)


def ids(document, selector):
    return [
        e.attributes.get("id")
        for e in html_dom.query_selector_all(document, selector)
    ]


def test_has_may_be_nested(document):
    selector = 'tr:has(td:has(a[href^="magnet:"]))'
    assert ids(document, selector) == ["a"]


def test_has_may_contain_complex_selectors(document):
    selector = "div.poststuff:has(~ div.entry a.download)"
    assert ids(document, selector) == ["post"]


def test_nested_has_with_not_has(document):
    selector = (
        "div.box > div:has(p:has(a[href^='/torrent/']))"
        ":not(:has(span.__cf_email__))"
    )
    assert ids(document, selector) == ["hit"]


def test_dotnet_unicode_block_names_are_understood():
    result = replace_all(
        r"([\p{IsCJKUnifiedIdeographs}\W]+)", ".", "abc 你好 def"
    )
    assert result == "abc.def"


def test_dotnet_script_names_still_work():
    assert replace_all(r"\p{IsCyrillic}+", "-", "abc привет") == "abc -"


def test_matches_means_the_element_itself(document):
    row = html_dom.query_selector(document, "#a")
    assert html_dom.matches(row, "tr")
    assert not html_dom.matches(row, "td")
    assert not html_dom.matches(row, "tr td a")


def test_contains_is_case_insensitive(document):
    found = html_dom.query_selector_all(document, 'a:contains("ONE")')
    assert [html_dom.text_content(e) for e in found] == ["one"]


def test_xml_keeps_empty_elements_and_void_names():
    document = html_dom.parse_xml(
        "<rss><channel><item><title>A</title><link>http://a</link>"
        '<torznab:attr name="seeders" value="5"/><size>3</size></item>'
        "</channel></rss>"
    )
    item = html_dom.query_selector(document, "item")
    link = html_dom.query_selector(item, "link")
    assert html_dom.text_content(link) == "http://a"
    attr = html_dom.query_selector(item, '[name="seeders"]')
    assert html_dom.attribute_value(attr, "value") == "5"
    assert html_dom.text_content(html_dom.query_selector(item, "size")) == "3"


def test_xml_namespace_prefixes_are_dropped_from_element_names():
    document = html_dom.parse_xml(
        '<rss xmlns:tv="urn:tv"><item><tv:raw_title>Show 720p</tv:raw_title>'
        "<tv:link>magnet:?xt=1</tv:link></item></rss>"
    )
    item = html_dom.query_selector(document, "item")
    title = html_dom.query_selector(item, "raw_title")
    assert html_dom.text_content(title) == "Show 720p"
    link = html_dom.query_selector(item, "link")
    assert html_dom.text_content(link) == "magnet:?xt=1"
