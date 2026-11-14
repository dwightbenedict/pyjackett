"""Parses YAML text into :class:`IndexerDefinition` objects.

The parser is strict (unknown keys are errors) and keeps every scalar a
string until a typed field converts it, like the YamlDotNet based original.
"""

from __future__ import annotations

import dataclasses
import functools
import types
import typing
from typing import Any

import yaml

from pyjackett.domain.cardigann.definition import (
    IndexerDefinition,
    OrderedFields,
    SelectorBlock,
)

_KEPT_TAGS = {"tag:yaml.org,2002:null", "tag:yaml.org,2002:merge"}
_TRUE_WORDS = frozenset({"true", "yes", "on", "y"})
_FALSE_WORDS = frozenset({"false", "no", "off", "n"})


_BaseLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _StringScalarLoader(_BaseLoader):
    """SafeLoader that leaves numbers and booleans as plain strings."""


_StringScalarLoader.yaml_implicit_resolvers = {
    first_char: [(tag, rx) for tag, rx in resolvers if tag in _KEPT_TAGS]
    for first_char, resolvers in _BaseLoader.yaml_implicit_resolvers.items()
}


def _to_yaml_key(attribute: str) -> str:
    """``request_delay`` -> ``requestDelay``."""
    head, *tail = attribute.split("_")
    return head + "".join(word.capitalize() for word in tail)


def _is_optional(hint: Any) -> tuple[bool, Any]:
    """Split ``X | None`` into (True, X)."""
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        members = [m for m in typing.get_args(hint) if m is not type(None)]
        if len(members) == 1:
            return True, members[0]
    return False, hint


def _convert_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    raise ValueError(f"Cannot convert {value!r} to a boolean")


def _convert_scalar(hint: Any, value: Any) -> Any:
    if hint is bool:
        return _convert_bool(value)
    if isinstance(value, (dict, list)):
        raise ValueError(f"Expected a scalar, got {type(value).__name__}")
    if hint is int:
        return int(value)
    if hint is float:
        return float(value)
    return value if hint is Any else str(value)


def _convert_fields(value: Any) -> OrderedFields:
    if not isinstance(value, dict):
        raise ValueError("fields must be a mapping")
    return OrderedFields((name, _build(SelectorBlock, block)) for name, block in value.items())


def _convert_list(item_hint: Any, value: Any) -> list:
    if not isinstance(value, list):
        value = [value]  # a lone scalar stands for a one item list
    return [_convert(item_hint, item) for item in value]


def _convert_dict(value_hint: Any, value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Expected a mapping")
    return {str(k): _convert(value_hint, v) for k, v in value.items()}


def _convert(hint: Any, value: Any) -> Any:
    if value is None:
        return None
    _, hint = _is_optional(hint)
    if hint is Any:
        return value  # raw YAML (a string or a list of strings)
    if hint is OrderedFields:
        return _convert_fields(value)
    origin = typing.get_origin(hint)
    if origin is list:
        return _convert_list(typing.get_args(hint)[0], value)
    if origin is dict:
        return _convert_dict(typing.get_args(hint)[1], value)
    if dataclasses.is_dataclass(hint):
        return _build(hint, value)
    return _convert_scalar(hint, value)


@functools.cache
def _hints_of(cls: type) -> dict[str, Any]:
    """Resolved field types of ``cls`` (resolving them is slow)."""
    return typing.get_type_hints(cls)


@functools.cache
def _attributes_by_key(cls: type) -> dict[str, str]:
    """Maps each YAML key of ``cls`` to its attribute name."""
    return {_to_yaml_key(f.name): f.name for f in dataclasses.fields(cls)}


def _build(cls: type, data: Any) -> Any:
    """Instantiate dataclass ``cls`` from a parsed YAML mapping."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping for {cls.__name__}")
    hints = _hints_of(cls)
    by_key = _attributes_by_key(cls)
    values = {}
    for key, raw in data.items():
        if key not in by_key:
            raise ValueError(f"Unknown key '{key}' in {cls.__name__}")
        attribute = by_key[key]
        converted = _convert(hints[attribute], raw)
        if converted is not None:
            values[attribute] = converted
    return cls(**values)


def parse_definition(text: str) -> IndexerDefinition:
    """Parse the YAML ``text`` of one indexer definition."""
    data = yaml.load(text, Loader=_StringScalarLoader)  # noqa: S506
    return _build(IndexerDefinition, data)
