"""Template variables available to a definition (``.Config.*``, ``.Query.*``).

Absent values are ``None`` and render as empty text; booleans are the
string ``"True"`` or ``None``.
"""

from __future__ import annotations

from datetime import date

from pyjackett.domain.cardigann.definition import SettingsField
from pyjackett.domain.cardigann.filters import FilterContext, apply_filters
from pyjackett.domain.cardigann.template import (
    FALSE_VARIABLE,
    TRUE_VARIABLE,
    Variables,
)
from pyjackett.domain.config_items import (
    BoolItem,
    MultiSelectItem,
    PasswordItem,
    SingleSelectItem,
    StringItem,
)
from pyjackett.domain.indexer_config import ConfigurationData
from pyjackett.domain.query import TorznabQuery
from pyjackett.domain.text import is_blank

_KEYWORD_PARTS = ("Q", "Series", "Movie", "Year")


def _previous_year_until_february() -> str:
    today = date.today()
    return str(today.year if today.month > 1 else today.year - 1)


def _config_value(item, variables: Variables):
    """Template value of a configuration item (None if it has none)."""
    if isinstance(item, BoolItem):
        return variables[TRUE_VARIABLE if item.value else FALSE_VARIABLE]
    if isinstance(item, MultiSelectItem):
        return item.values
    if isinstance(item, (StringItem, PasswordItem, SingleSelectItem)):
        return item.value
    return getattr(item, "value", None)


def base_variables(
    site_link: str,
    settings: list[SettingsField],
    config_data: ConfigurationData,
) -> Variables:
    """Constants plus one ``.Config.<setting>`` variable per setting."""
    variables: Variables = {
        ".Config.sitelink": site_link,
        TRUE_VARIABLE: "True",
        FALSE_VARIABLE: None,
        ".Today.Year": _previous_year_until_february(),
    }
    for setting in settings:
        item = config_data.get_dynamic(setting.name)
        if item is not None:
            key = ".Config." + setting.name
            variables[key] = _config_value(item, variables)
    return variables


def _flag(value: bool) -> str | None:
    return "True" if value else None


def _text(value) -> str | None:
    return None if value is None else str(value)


def _value_variables(query: TorznabQuery) -> Variables:
    """Textual ``.Query.*`` values (None when not given)."""
    season = _text(query.season) if (query.season or 0) > 0 else None
    return {
        "Type": query.query_type,
        "Q": query.search_term,
        "Series": None,
        "Ep": query.episode,
        "Season": season,
        "Movie": None,
        "Year": _text(query.year),
        "Limit": str(query.limit),
        "Offset": str(query.offset),
        "Extended": str(query.extended),
        "Categories": [str(c) for c in query.categories],
        "APIKey": query.api_key,
        "TVDBID": _text(query.tvdb_id),
        "TVRageID": _text(query.rage_id),
        "IMDBID": query.imdb_id,
        "IMDBIDShort": query.imdb_id_short,
        "TMDBID": _text(query.tmdb_id),
        "TVMazeID": _text(query.tvmaze_id),
        "TraktID": _text(query.trakt_id),
        "DoubanID": _text(query.douban_id),
        "Album": query.album,
        "Artist": query.artist,
        "Label": query.label,
        "Track": query.track,
        "Genre": query.genre,
        "Episode": query.episode_search_string(),
        "Author": query.author,
        "Title": query.title,
        "Publisher": query.publisher,
    }


def _flag_variables(query: TorznabQuery) -> Variables:
    """``.Query.Is*`` flags: "True" or None."""
    flags = {
        "IsBookSearch": query.is_book_search,
        "IsDoubanQuery": query.is_douban_query,
        "IsGenreQuery": query.is_genre_query,
        "IsIdSearch": query.is_id_search,
        "IsImdbQuery": query.is_imdb_query,
        "IsMovieSearch": query.is_movie_search,
        "IsMusicSearch": query.is_music_search,
        "IsRssSearch": query.is_rss_search,
        "IsSearch": query.is_search,
        "IsTVRageQuery": query.is_tvrage_query,
        "IsTVSearch": query.is_tv_search,
        "IsTmdbQuery": query.is_tmdb_query,
        "IsTraktQuery": query.is_trakt_query,
        "IsTvdbQuery": query.is_tvdb_query,
        "IsTvmazeQuery": query.is_tvmaze_query,
    }
    return {name: _flag(value) for name, value in flags.items()}


def add_query_variables(variables: Variables, query: TorznabQuery) -> None:
    """Expose the Torznab query as ``.Query.*`` variables."""
    for name, value in {
        **_value_variables(query),
        **_flag_variables(query),
    }.items():
        variables[f".Query.{name}"] = value


def add_keyword_variables(
    variables: Variables,
    keyword_filters,
    filter_context: FilterContext,
) -> None:
    """``.Query.Keywords`` (raw) and ``.Keywords`` (after the filters)."""
    parts = [variables[f".Query.{key}"] for key in _KEYWORD_PARTS]
    parts.append(variables[".Query.Episode"])
    variables[".Query.Keywords"] = " ".join(
        p for p in parts if not is_blank(p)
    )
    filter_context.variables = variables
    variables[".Keywords"] = apply_filters(
        variables[".Query.Keywords"], keyword_filters, filter_context
    )
