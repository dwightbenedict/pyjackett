"""Data classes describing a Cardigann YAML indexer definition.

Field names are the snake_case form of the YAML keys (``request_delay``
is ``requestDelay`` in the file); see :mod:`definition_loader`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class OrderedFields(list):
    """Result fields as ``(name, SelectorBlock)`` pairs, in file order."""


@dataclass
class FilterBlock:
    name: str = ""
    args: Any = None  # str, list of str, or None


@dataclass
class SelectorBlock:
    selector: str | None = None
    optional: bool = False
    default: str | None = None
    text: str | None = None
    attribute: str | None = None
    remove: str | None = None
    filters: list[FilterBlock] | None = None
    case: dict[str, str] | None = None


@dataclass
class SelectorField:
    selector: str | None = None
    attribute: str | None = None
    usebeforeresponse: bool = False
    filters: list[FilterBlock] | None = None


@dataclass
class SettingsField:
    name: str = ""
    type: str | None = None
    label: str | None = None
    default: str | None = None
    defaults: list[str] | None = None
    options: dict[str, str] | None = None


@dataclass
class CategoryMappingBlock:
    id: str = ""
    cat: str | None = None
    desc: str | None = None
    default: bool = False


@dataclass
class CapabilitiesBlock:
    categories: dict[str, str] | None = None
    categorymappings: list[CategoryMappingBlock] | None = None
    modes: dict[str, list[str]] | None = None
    allowrawsearch: bool = False
    allowtvsearchimdb: bool = False


@dataclass
class CaptchaBlock:
    type: str | None = None
    selector: str | None = None
    input: str | None = None


@dataclass
class ErrorBlock:
    path: str | None = None
    selector: str | None = None
    message: SelectorBlock | None = None


@dataclass
class PageTestBlock:
    path: str | None = None
    selector: str | None = None


@dataclass
class LoginBlock:
    path: str | None = None
    submitpath: str | None = None
    cookies: list[str] | None = None
    method: str | None = None
    form: str | None = None
    selectors: bool = False
    inputs: dict[str, str] | None = None
    selectorinputs: dict[str, SelectorBlock] | None = None
    getselectorinputs: dict[str, SelectorBlock] | None = None
    error: list[ErrorBlock] | None = None
    test: PageTestBlock | None = None
    captcha: CaptchaBlock | None = None
    headers: dict[str, list[str]] | None = None


@dataclass
class RatioBlock(SelectorBlock):
    path: str | None = None


@dataclass
class ResponseBlock:
    type: str | None = None
    no_results_message: str | None = None


@dataclass
class RequestBlock:
    path: str | None = None
    method: str | None = None
    inputs: dict[str, str] | None = None
    queryseparator: str = "&"


@dataclass
class SearchPathBlock(RequestBlock):
    categories: list[str] = field(default_factory=list)
    inheritinputs: bool = True
    followredirect: bool = False
    response: ResponseBlock | None = None


@dataclass
class BeforeBlock(RequestBlock):
    pathselector: SelectorField | None = None


@dataclass
class InfohashBlock:
    hash: SelectorField | None = None
    title: SelectorField | None = None
    usebeforeresponse: bool = False


@dataclass
class DownloadBlock:
    selectors: list[SelectorField] | None = None
    method: str | None = None
    before: BeforeBlock | None = None
    infohash: InfohashBlock | None = None
    headers: dict[str, list[str]] | None = None


@dataclass
class RowsBlock(SelectorBlock):
    after: int = 0
    dateheaders: SelectorBlock | None = None
    count: SelectorBlock | None = None
    multiple: bool = False
    missing_attribute_equals_no_results: bool = False


@dataclass
class SearchBlock:
    path: str | None = None
    paths: list[SearchPathBlock] | None = None
    headers: dict[str, list[str]] | None = None
    keywordsfilters: list[FilterBlock] | None = None
    allow_empty_inputs: bool = False
    inputs: dict[str, str] | None = None
    error: list[ErrorBlock] | None = None
    preprocessingfilters: list[FilterBlock] | None = None
    rows: RowsBlock | None = None
    fields: OrderedFields | None = None


@dataclass
class IndexerDefinition:
    id: str = ""
    replaces: list[str] = field(default_factory=list)
    settings: list[SettingsField] | None = None
    name: str = ""
    description: str | None = None
    type: str | None = None
    language: str | None = None
    encoding: str | None = None
    request_delay: float | None = None
    links: list[str] = field(default_factory=list)
    legacylinks: list[str] | None = None
    followredirect: bool = False
    testlinktorrent: bool = True
    certificates: list[str] | None = None
    caps: CapabilitiesBlock | None = None
    login: LoginBlock | None = None
    ratio: RatioBlock | None = None
    search: SearchBlock | None = None
    download: DownloadBlock | None = None
