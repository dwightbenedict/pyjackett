"""Go template subset used by definitions."""

from __future__ import annotations

import pytest

from pyjackett.domain.cardigann.template import apply_template
from pyjackett.domain.urls import url_encode


@pytest.fixture
def variables():
    return {
        ".True": "True",
        ".False": None,
        ".Keywords": "big movie",
        ".Config.user": "bob",
        ".Config.free": None,
        ".Config.empty": "",
        ".Categories": ["5000", "5040"],
    }


def test_plain_text_is_untouched(variables):
    assert apply_template("no braces", variables) == "no braces"


def test_variable(variables):
    assert apply_template("u={{ .Config.user }}", variables) == "u=bob"


def test_missing_value_renders_empty(variables):
    assert apply_template("[{{ .Config.free }}]", variables) == "[]"


def test_modifier_encodes_values(variables):
    result = apply_template("q={{ .Keywords }}", variables, url_encode)
    assert result == "q=big+movie"


def test_if_else(variables):
    template = "{{ if .Config.user }}yes{{ else }}no{{ end }}"
    assert apply_template(template, variables) == "yes"
    template = "{{ if .Config.empty }}yes{{ else }}no{{ end }}"
    assert apply_template(template, variables) == "no"


def test_range_joins_items(variables):
    template = "{{ range .Categories }}c={{.}}&{{end}}"
    assert apply_template(template, variables) == "c=5000&c=5040&"


def test_range_with_index(variables):
    template = "{{ range $i, $e := .Categories }}{{$i}}:{{.}} {{end}}"
    assert apply_template(template, variables) == "0:5000 1:5040 "


def test_join(variables):
    assert (
        apply_template('{{ join .Categories "," }}', variables) == "5000,5040"
    )


def test_re_replace(variables):
    template = '{{ re_replace .Keywords "[^a-z]+" "-" }}'
    assert apply_template(template, variables) == "big-movie"


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ('{{ if eq .Config.user "bob" }}Y{{ else }}N{{ end }}', "Y"),
        ('{{ if ne .Config.user "bob" }}Y{{ else }}N{{ end }}', "N"),
        ("{{ if and .Config.user .Keywords }}Y{{ else }}N{{ end }}", "Y"),
        ("{{ if and .Config.user .Config.free }}Y{{ else }}N{{ end }}", "N"),
        ("{{ if or .Config.free .Config.user }}Y{{ else }}N{{ end }}", "Y"),
        (
            '{{ if and eq (.Config.user) "bob" eq (.Keywords) "big movie" }}'
            "Y{{ else }}N{{ end }}",
            "Y",
        ),
    ],
)
def test_logic_functions(variables, template, expected):
    assert apply_template(template, variables) == expected
