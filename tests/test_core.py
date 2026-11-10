"""Queries, categories, capabilities and the log cleanser."""

from __future__ import annotations

from pyjackett.core.capabilities import TorznabCapabilities
from pyjackett.core.category_catalog import (
    MOVIES,
    MOVIES_HD,
    TV,
    TVHD,
)
from pyjackett.core.category_lookup import get_category_by_name
from pyjackett.core.query import TorznabQuery
from pyjackett.core.search_modes import SearchMode
from pyjackett.indexers.meta.filter_expression import parse_filter
from pyjackett.server.query_parsing import manual_search_query
from pyjackett.utils.log_cleansing import cleanse


def test_catalog_tree():
    assert MOVIES_HD in MOVIES.subcategories
    assert get_category_by_name("TV/HD") == TVHD
    assert TV.id == 5000


def test_category_mapping_and_custom_categories():
    caps = TorznabCapabilities()
    caps.categories.add("12", MOVIES_HD, "Films 720p")
    caps.categories.add("13", TVHD)
    assert caps.categories.to_torznab("12") == [2040, 100012]
    assert caps.categories.to_torznab_by_description("films 720p") == [
        2040,
        100012,
    ]
    query = TorznabQuery(categories=[2000])  # parent expands to children
    assert caps.categories.to_tracker_categories(query) == ["12"]
    tree = {
        c.id: [s.id for s in c.subcategories]
        for c in caps.categories.category_tree(True)
    }
    assert tree == {2000: [2040], 5000: [5040], 100012: []}


def test_supported_categories():
    caps = TorznabCapabilities()
    caps.categories.add("1", MOVIES_HD)
    assert caps.categories.supported_categories([2040, 9999]) == [2040]


def test_search_modes_are_validated():
    caps = TorznabCapabilities()
    caps.set_parameters(SearchMode.TV, ["q", "season", "ep"])
    assert caps.advertised_parameters(SearchMode.TV) == ["q", "season", "ep"]
    assert caps.tv_search_available and not caps.movie_search_available
    for bad in (["nope"], ["q", "q"]):
        try:
            caps.set_parameters(SearchMode.TV, bad)
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def test_episode_strings():
    assert (
        TorznabQuery(season=1, episode="2").episode_search_string() == "S01E02"
    )
    assert TorznabQuery(season=3).episode_search_string() == "S03"
    assert (
        TorznabQuery(season=2024, episode="03/15").episode_search_string()
        == "2024.03.15"
    )
    assert (
        TorznabQuery(season=1, episode="1A").episode_search_string()
        == "S01E01"
    )


def test_query_classification():
    assert TorznabQuery(query_type="search", search_term=" ").is_rss_search
    assert not TorznabQuery(query_type="search", imdb_id="tt1").is_rss_search
    assert TorznabQuery(query_type="movie").is_movie_search


def test_and_match_ignores_noise_words_and_accents():
    query = TorznabQuery(search_term="The Café and Bar")
    assert query.match_query_string_and("cafe.bar.2020")
    assert not query.match_query_string_and("only.cafe")


def test_cache_key_ignores_cache_flag():
    first, second = (
        TorznabQuery(search_term="x"),
        TorznabQuery(search_term="x", cache=False),
    )
    assert first.cache_key() == second.cache_key()
    assert first.cache_key() != TorznabQuery(search_term="y").cache_key()


def test_manual_search_parses_episode_and_imdb():
    query = manual_search_query({"query": "Show S02E05"})
    assert (query.search_term, query.season, query.episode) == ("Show", 2, "5")
    imdb = manual_search_query({"query": "tt133093"})
    assert imdb.imdb_id == "tt0133093"


def test_filter_expressions():
    class Fake:
        is_configured = True
        tags = ["movies"]
        language = "en-US"
        type = "public"

    assert parse_filter("tag:movies")(Fake())
    assert parse_filter("tag:tv,lang:en")(Fake())
    assert not parse_filter("tag:tv+lang:en")(Fake())
    assert parse_filter("!type:private")(Fake())
    assert parse_filter("garbage") is None


def test_log_cleansing_hides_secrets():
    line = "GET http://x/api?apikey=SECRET123&t=search passkey=abc"
    cleaned = cleanse(line)
    assert "SECRET123" not in cleaned and "abc" not in cleaned
    assert "t=search" in cleaned
