"""Value filters of the Cardigann engine."""

from __future__ import annotations

import pytest

from pyjackett.domain.cardigann.definition import FilterBlock
from pyjackett.domain.cardigann.filters import FilterContext, apply_filters


def run(value, name, args=None):
    context = FilterContext(variables={".True": "True"})
    return apply_filters(value, [FilterBlock(name, args)], context)


@pytest.mark.parametrize(
    ("value", "name", "args", "expected"),
    [
        ("Hello", "tolower", None, "hello"),
        ("Hello", "toupper", None, "HELLO"),
        ("  x ", "trim", None, "x"),
        ("--x--", "trim", "-", "x"),
        ("a", "append", "b", "ab"),
        ("b", "prepend", "a", "ab"),
        ("a-b-c", "replace", ["-", "+"], "a+b+c"),
        ("abc123", "regexp", r"(\d+)", "123"),
        ("abc", "regexp", r"(\d+)", ""),
        ("x1y22z", "re_replace", [r"\d+", "#"], "x#y#z"),
        (
            "2024-05-06",
            "re_replace",
            [r"(\d+)-(\d+)-(\d+)", "$3/$2/$1"],
            "06/05/2024",
        ),
        ("a,b,c", "split", [",", "1"], "b"),
        ("a,b,c", "split", [",", "-1"], "c"),
        ("http://x/?id=7&a=1", "querystring", "id", "7"),
        ("a%20b", "urldecode", None, "a b"),
        ("a b&c", "urlencode", None, "a+b%26c"),
        ("&lt;b&gt;", "htmldecode", None, "<b>"),
        ("Café", "diacritics", "replace", "Cafe"),
        ("a/b?c", "validfilename", None, "a_b_c"),
        ("aGk", "base64decode", None, "hi"),
        ("hi", "base64encode", None, "aGk"),
        ("The Movie (2020) [HD]", "validate", "movie hd 4k", "movie,hd"),
    ],
)
def test_filter(value, name, args, expected):
    assert run(value, name, args) == expected


def test_dateparse_dotnet_layout():
    result = run("2024-03-01 12:00:00 +00:00", "dateparse", "yyyy-MM-dd HH:mm:ss zzz")
    assert result.startswith("Fri, 01 Mar 2024") or result.startswith("Thu, 29 Feb")


def test_dateparse_failure_keeps_value():
    assert run("not a date", "dateparse", "yyyy-MM-dd") == "not a date"


def test_unknown_filter_is_ignored():
    assert run("x", "does-not-exist") == "x"


def test_chain_runs_in_order():
    context = FilterContext(variables={})
    chain = [FilterBlock("append", "!"), FilterBlock("toupper")]
    assert apply_filters("hi", chain, context) == "HI!"
