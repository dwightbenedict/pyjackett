"""Torznab XML documents: capabilities, results feed and errors."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import regex

from pyjackett.core.capabilities import TorznabCapabilities
from pyjackett.core.release import ReleaseInfo
from pyjackett.core.search_modes import SearchMode
from pyjackett.utils.dates import local_now

ATOM_NS = "http://www.w3.org/2005/Atom"
TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z"

ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("torznab", TORZNAB_NS)

# control characters and lone surrogates are not allowed in XML
_INVALID_XML_CHARS = regex.compile(
    r"(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])"
    r"|[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F﻿￾￿]"
)
_SEARCH_ELEMENTS = (
    (SearchMode.SEARCH, "search"),
    (SearchMode.TV, "tv-search"),
    (SearchMode.MOVIE, "movie-search"),
    (SearchMode.MUSIC, "music-search"),
    (SearchMode.MUSIC, "audio-search"),  # used by various newznab indexers
    (SearchMode.BOOK, "book-search"),
)


def remove_invalid_chars(text: str | None) -> str | None:
    return None if text is None else _INVALID_XML_CHARS.sub("", text)


def serialize(root: ET.Element) -> str:
    return XML_DECLARATION + ET.tostring(root, encoding="unicode")


def _text(parent: ET.Element, tag: str, value) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = "" if value is None else str(value)
    return element


# ---- capabilities -----------------------------------------------------------


def _limits(root: ET.Element, caps: TorznabCapabilities) -> None:
    if caps.limits_max is None and caps.limits_default is None:
        return
    limits = ET.SubElement(root, "limits")
    if caps.limits_default is not None:
        limits.set("default", str(caps.limits_default))
    if caps.limits_max is not None:
        limits.set("max", str(caps.limits_max))


def _searching(root: ET.Element, caps: TorznabCapabilities) -> None:
    searching = ET.SubElement(root, "searching")
    for mode, tag in _SEARCH_ELEMENTS:
        element = ET.SubElement(searching, tag)
        element.set("available", "yes" if caps.mode_available(mode) else "no")
        element.set(
            "supportedParams", ",".join(caps.advertised_parameters(mode))
        )
        if caps.supports_raw_search:
            element.set("searchEngine", "raw")


def _categories(root: ET.Element, caps: TorznabCapabilities) -> None:
    categories = ET.SubElement(root, "categories")
    for parent in caps.categories.category_tree(sort=True):
        element = ET.SubElement(
            categories, "category", id=str(parent.id), name=parent.name
        )
        for child in parent.subcategories:
            ET.SubElement(element, "subcat", id=str(child.id), name=child.name)


def capabilities_element(caps: TorznabCapabilities) -> ET.Element:
    root = ET.Element("caps")
    ET.SubElement(root, "server", title="Jackett")
    _limits(root, caps)
    _searching(root, caps)
    _categories(root, caps)
    return root


def capabilities_xml(caps: TorznabCapabilities) -> str:
    return serialize(capabilities_element(caps))


# ---- errors -----------------------------------------------------------------


def error_xml(code: int, description: str) -> str:
    root = ET.Element("error", code=str(code), description=description)
    return serialize(root)


# ---- results feed -----------------------------------------------------------


def _format_date(moment: datetime | None) -> str:
    return (moment or local_now()).strftime(DATE_FORMAT)


def _attr(item: ET.Element, name: str, value) -> None:
    if value is not None:
        ET.SubElement(
            item, f"{{{TORZNAB_NS}}}attr", name=name, value=str(value)
        )


def _link_of(release: ReleaseInfo) -> str:
    return release.link or release.magnet_uri or ""


def _basic_elements(item: ET.Element, release: ReleaseInfo) -> None:
    origin = release.origin
    _text(item, "title", remove_invalid_chars(release.title))
    _text(item, "guid", release.guid)
    indexer = _text(item, "jackettindexer", origin.name)
    indexer.set("id", origin.id)
    _text(item, "type", origin.type)
    if release.details:
        _text(item, "comments", release.details)
    _text(item, "pubDate", _format_date(release.publish_date))
    for tag, value in (
        ("size", release.size),
        ("files", release.files),
        ("grabs", release.grabs),
    ):
        if value is not None:
            _text(item, tag, value)
    _text(item, "description", remove_invalid_chars(release.description))
    _text(item, "link", _link_of(release))
    for category in release.category:
        _text(item, "category", category)
    enclosure = ET.SubElement(item, "enclosure", url=_link_of(release))
    if release.size is not None:
        enclosure.set("length", str(release.size))
    enclosure.set("type", "application/x-bittorrent")


def _imdb_attrs(item: ET.Element, release: ReleaseInfo) -> None:
    if release.imdb is not None:
        _attr(item, "imdb", f"{release.imdb:07d}")
        _attr(item, "imdbid", f"tt{release.imdb:07d}")


def _torznab_attributes(item: ET.Element, release: ReleaseInfo) -> None:
    for category in release.category:
        _attr(item, "category", category)
    _attr(item, "rageid", release.rage_id)
    _attr(item, "tvdbid", release.tvdb_id)
    _imdb_attrs(item, release)
    _attr(item, "tmdbid", release.tmdb)
    _attr(item, "tvmazeid", release.tvmaze_id)
    _attr(item, "traktid", release.trakt_id)
    _attr(item, "doubanid", release.douban_id)
    if release.genres is not None:
        _attr(item, "genre", ", ".join(release.genres))
    for language in release.languages:
        _attr(item, "language", language)
    for subtitle in release.subs:
        _attr(item, "subs", subtitle)
    _attr(item, "year", release.year)
    for name in ("author", "book_title", "publisher", "artist", "album"):
        _attr(
            item,
            name.replace("_", ""),
            remove_invalid_chars(getattr(release, name)),
        )
    _attr(item, "label", remove_invalid_chars(release.label))
    _attr(item, "track", remove_invalid_chars(release.track))
    _attr(item, "seeders", release.seeders)
    _attr(item, "peers", release.peers)
    _attr(item, "coverurl", release.poster)
    _attr(item, "infohash", remove_invalid_chars(release.info_hash))
    _attr(item, "magneturl", release.magnet_uri)
    _attr(item, "minimumratio", release.minimum_ratio)
    _attr(item, "minimumseedtime", release.minimum_seed_time)
    _attr(item, "downloadvolumefactor", release.download_volume_factor)
    _attr(item, "uploadvolumefactor", release.upload_volume_factor)


def _channel(root, title, description, link, self_url) -> ET.Element:
    channel = ET.SubElement(root, "channel")
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        href=self_url,
        rel="self",
        type="application/rss+xml",
    )
    _text(channel, "title", title)
    _text(channel, "description", description)
    _text(channel, "link", link)
    _text(channel, "language", "en-US")
    _text(channel, "category", "search")
    return channel


def results_xml(
    releases: list[ReleaseInfo],
    title: str,
    description: str,
    link: str,
    self_url: str,
) -> str:
    """The RSS 2.0 feed with torznab attributes."""
    root = ET.Element("rss", version="2.0")
    channel = _channel(root, title, description, link, self_url)
    for release in releases:
        item = ET.SubElement(channel, "item")
        _basic_elements(item, release)
        _torznab_attributes(item, release)
    return serialize(root)


def indexers_xml(indexers) -> str:
    """The ``t=indexers`` listing of a meta indexer's members."""
    root = ET.Element("indexers")
    for indexer in indexers:
        element = ET.SubElement(
            root,
            "indexer",
            id=indexer.id,
            configured=str(indexer.is_configured).lower(),
        )
        _text(element, "title", indexer.name)
        _text(element, "description", indexer.description)
        _text(element, "link", indexer.site_link)
        _text(element, "language", indexer.language)
        _text(element, "type", indexer.type)
        element.append(capabilities_element(indexer.torznab_caps))
    return serialize(root)
