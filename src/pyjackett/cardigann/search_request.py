"""Builds the HTTP request of one ``search.paths`` entry."""

from __future__ import annotations

from dataclasses import dataclass

from pyjackett.cardigann.definition import SearchBlock, SearchPathBlock
from pyjackett.cardigann.host import CardigannHost
from pyjackett.cardigann.methods import request_type
from pyjackett.cardigann.template import Variables, apply_template
from pyjackett.http.models import RequestType
from pyjackett.utils.text import is_blank
from pyjackett.utils.urls import build_query_string, url_encode

RAW_INPUT_KEY = "$raw"


@dataclass
class SearchRequest:
    url: str
    method: RequestType
    inputs: list[tuple[str, str]]

    @property
    def is_get(self) -> bool:
        return self.method is RequestType.GET


def restrict_categories(
    mapped: list[str], path: SearchPathBlock
) -> list[str] | None:
    """Categories to search in ``path``; None if the path must be skipped.

    A path listing categories only runs when one of them was requested; a
    leading ``!`` inverts that rule.
    """
    if not path.categories:
        return mapped
    shared = [c for c in mapped if c in path.categories]
    matches = bool(shared)
    if path.categories[0] == "!":
        matches = not matches
    if not matches:
        return None
    return shared


def _raw_pairs(template: str, variables: Variables) -> list[tuple[str, str]]:
    """Expand a ``$raw`` input: an already URL-encoded query fragment."""
    pairs = []
    for part in apply_template(template, variables, url_encode).split("&"):
        key, _, value = part.partition("=")
        if key:
            pairs.append((key, value))
    return pairs


def _input_pairs(
    inputs: dict[str, str] | None,
    variables: Variables,
    allow_empty: bool,
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, template in (inputs or {}).items():
        if key == RAW_INPUT_KEY:
            pairs.extend(_raw_pairs(template, variables))
            continue
        value = apply_template(template, variables)
        if not is_blank(value) or allow_empty:
            pairs.append((key, value))
    return pairs


def build_search_request(
    host: CardigannHost,
    search: SearchBlock,
    path: SearchPathBlock,
    variables: Variables,
) -> SearchRequest:
    """Resolve the URL and collect the (inherited) inputs."""
    # .NET's UrlPathEncode only encodes spaces: use + as %20 instead
    encoded_path = apply_template(path.path, variables, url_encode)
    url = host.resolve_path(encoded_path.replace("+", "%20"))
    method = request_type(path.method)
    pairs: list[tuple[str, str]] = []
    if path.inheritinputs:
        pairs += _input_pairs(
            search.inputs, variables, search.allow_empty_inputs
        )
    pairs += _input_pairs(path.inputs, variables, search.allow_empty_inputs)
    if method is RequestType.GET and pairs:
        url += "?" + build_query_string(pairs, host.encoding)
    return SearchRequest(url, method, pairs)
