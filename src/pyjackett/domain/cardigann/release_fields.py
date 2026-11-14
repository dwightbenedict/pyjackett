"""Maps the fields scraped from a result row onto a :class:`ReleaseInfo`.

Each handler stores the parsed value on the release and returns the text
that becomes available to later templates as ``.Result.<field>``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from pyjackett.domain import dates
from pyjackett.domain.category_mappings import CategoryMappings
from pyjackett.domain.numbers import (
    coerce_float,
    coerce_int,
    extract_first_integer,
    parse_size,
)
from pyjackett.domain.release import ReleaseInfo
from pyjackett.domain.text import is_blank
from pyjackett.domain.urls import resolve_url

logger = logging.getLogger(__name__)

# peers/leechers above this are bogus (issue #6558 upstream)
MAX_PLAUSIBLE_PEERS = 5_000_000
_GENRE_DELIMITERS = ',/)(.;[]"|: '


@dataclass
class FieldContext:
    """Everything a field handler needs besides the value."""

    release: ReleaseInfo
    categories: CategoryMappings
    search_url: str
    indexer_id: str
    modifiers: list[str] = field(default_factory=list)

    def resolve(self, path: str) -> str:
        return resolve_url(path, self.search_url)


Handler = Callable[[str, FieldContext], str | None]


# ---- links ------------------------------------------------------------------


def _download(value: str, ctx: FieldContext) -> str | None:
    if not value:
        ctx.release.link = None
        return None
    if value.startswith("magnet:"):
        ctx.release.magnet_uri = value
        return value
    ctx.release.link = ctx.resolve(value)
    return ctx.release.link


def _magnet(value: str, ctx: FieldContext) -> str:
    ctx.release.magnet_uri = value
    return value


def _infohash(value: str, ctx: FieldContext) -> str:
    ctx.release.info_hash = value
    return value


def _details(value: str, ctx: FieldContext) -> str:
    ctx.release.details = ctx.resolve(value)
    return ctx.release.details


def _poster(value: str, ctx: FieldContext) -> str:
    if not is_blank(value):
        ctx.release.poster = ctx.resolve(value)
    return ctx.release.poster or ""


# ---- text fields ------------------------------------------------------------


def _assign_or_append(ctx: FieldContext, attribute: str, value: str) -> str:
    current = getattr(ctx.release, attribute)
    appended = "append" in ctx.modifiers and current is not None
    setattr(ctx.release, attribute, current + value if appended else value)
    return getattr(ctx.release, attribute)


def _title(value: str, ctx: FieldContext) -> str:
    return _assign_or_append(ctx, "title", value)


def _description(value: str, ctx: FieldContext) -> str:
    return _assign_or_append(ctx, "description", value)


def _plain_text(attribute: str) -> Handler:
    def handler(value: str, ctx: FieldContext) -> str:
        setattr(ctx.release, attribute, value)
        return value

    return handler


# ---- categories -------------------------------------------------------------


def _apply_categories(categories: list[int], value: str, ctx: FieldContext):
    release = ctx.release
    if "noappend" in ctx.modifiers:
        logger.warning(
            'CardigannIndexer (%s): The "noappend" modifier is deprecated. '
            'Please switch to "default".',
            ctx.indexer_id,
        )
    if categories:
        keep_existing = release.category and "noappend" not in ctx.modifiers
        merged = (
            [*release.category, *categories] if keep_existing else (categories)
        )
        release.category = list(dict.fromkeys(merged))
    if not is_blank(value) and not release.category:
        logger.warning(
            "[%s] Invalid category for value: '%s'", ctx.indexer_id, value
        )
        return value
    return ",".join(str(c) for c in release.category)


def _category(value: str, ctx: FieldContext) -> str:
    return _apply_categories(ctx.categories.to_torznab(value), value, ctx)


def _category_desc(value: str, ctx: FieldContext) -> str:
    found = ctx.categories.to_torznab_by_description(value)
    return _apply_categories(found, value, ctx)


# ---- numbers ----------------------------------------------------------------


def _size(value: str, ctx: FieldContext) -> str:
    ctx.release.size = parse_size(value)
    return str(ctx.release.size)


def _add_peers(release: ReleaseInfo, amount: int) -> None:
    release.peers = amount if release.peers is None else release.peers + amount


def _plausible(count: int) -> int:
    return count if count < MAX_PLAUSIBLE_PEERS else 0


def _leechers(value: str, ctx: FieldContext) -> str:
    leechers = _plausible(coerce_int(value))
    _add_peers(ctx.release, leechers)
    return str(leechers)


def _seeders(value: str, ctx: FieldContext) -> str:
    ctx.release.seeders = _plausible(coerce_int(value))
    _add_peers(ctx.release, ctx.release.seeders)
    return str(ctx.release.seeders)


def _integer(attribute: str) -> Handler:
    def handler(value: str, ctx: FieldContext) -> str:
        setattr(ctx.release, attribute, coerce_int(value))
        return str(getattr(ctx.release, attribute))

    return handler


def _decimal(attribute: str) -> Handler:
    def handler(value: str, ctx: FieldContext) -> str:
        setattr(ctx.release, attribute, coerce_float(value))
        return str(getattr(ctx.release, attribute))

    return handler


def _external_id(attribute: str) -> Handler:
    """Ids are the first number found in the text (0 when none)."""

    def handler(value: str, ctx: FieldContext) -> str:
        setattr(ctx.release, attribute, extract_first_integer(value) or 0)
        return str(getattr(ctx.release, attribute))

    return handler


def _date(value: str, ctx: FieldContext) -> str:
    ctx.release.publish_date = dates.from_unknown(value)
    return dates.format_rfc1123z(ctx.release.publish_date)


# ---- lists ------------------------------------------------------------------


def _split_genres(value: str) -> list[str]:
    words, current = [], []
    for char in value:
        if char in _GENRE_DELIMITERS:
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        words.append("".join(current))
    return words


def _genre(value: str, ctx: FieldContext) -> str:
    known = ctx.release.genres or []
    merged = list(dict.fromkeys([*known, *_split_genres(value)]))
    ctx.release.genres = [genre.replace("_", " ") for genre in merged]
    return ",".join(ctx.release.genres)


HANDLERS: dict[str, Handler] = {
    "download": _download,
    "magnet": _magnet,
    "infohash": _infohash,
    "details": _details,
    "title": _title,
    "description": _description,
    "category": _category,
    "categorydesc": _category_desc,
    "size": _size,
    "leechers": _leechers,
    "seeders": _seeders,
    "date": _date,
    "files": _integer("files"),
    "grabs": _integer("grabs"),
    "downloadvolumefactor": _decimal("download_volume_factor"),
    "uploadvolumefactor": _decimal("upload_volume_factor"),
    "minimumratio": _decimal("minimum_ratio"),
    "minimumseedtime": _integer("minimum_seed_time"),
    "imdb": _external_id("imdb"),
    "imdbid": _external_id("imdb"),
    "tmdbid": _external_id("tmdb"),
    "rageid": _external_id("rage_id"),
    "tvdbid": _external_id("tvdb_id"),
    "tvmazeid": _external_id("tvmaze_id"),
    "traktid": _external_id("trakt_id"),
    "doubanid": _external_id("douban_id"),
    "genre": _genre,
    "year": _integer("year"),
    "author": _plain_text("author"),
    "booktitle": _plain_text("book_title"),
    "publisher": _plain_text("publisher"),
    "artist": _plain_text("artist"),
    "album": _plain_text("album"),
    "label": _plain_text("label"),
    "track": _plain_text("track"),
    "poster": _poster,
}


def parse_field(
    value: str, field_name: str, context: FieldContext
) -> str | None:
    """Store ``value`` on the release; unknown names are template-only."""
    handler = HANDLERS.get(field_name)
    return handler(value, context) if handler else value
