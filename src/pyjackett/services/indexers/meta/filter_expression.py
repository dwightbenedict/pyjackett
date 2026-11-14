"""The indexer filter language: ``tag:movies+lang:en,!type:private``.

Grammar (lowest precedence first): ``a,b`` is OR, ``a+b`` is AND, ``!a`` is
NOT and ``name:argument`` is a component test.
"""

from __future__ import annotations

from collections.abc import Callable

from pyjackett.services.indexers.base import BaseIndexer

Predicate = Callable[[BaseIndexer], bool]
Component = Callable[[str], Predicate]

OR_OPERATOR = ","
AND_OPERATOR = "+"
NOT_OPERATOR = "!"
SEPARATOR = ":"


def _configured(test: Predicate) -> Predicate:
    """Only configured indexers can pass a component test."""
    return lambda indexer: indexer.is_configured and test(indexer)


def _tag(argument: str) -> Predicate:
    tag = argument.lower()
    return _configured(lambda indexer: tag in indexer.tags)


def _language(argument: str) -> Predicate:
    prefix = argument.lower()
    return _configured(lambda i: i.language.lower().startswith(prefix))


def _type(argument: str) -> Predicate:
    kind = argument.lower()
    return _configured(lambda i: (i.type or "").lower() == kind)


def _test(argument: str) -> Predicate:
    outcomes = {
        "passed": lambda i: i.last_error is None,
        "failed": lambda i: i.last_error is not None,
    }
    if argument.lower() not in outcomes:
        raise ValueError("Invalid filter. Test should be 'passed' or 'failed'")
    return _configured(outcomes[argument.lower()])


def _status(argument: str) -> Predicate:
    outcomes = {
        "healthy": lambda i: i.is_healthy and not i.is_failing,
        "failing": lambda i: not i.is_healthy and i.is_failing,
        "unknown": lambda i: i.is_healthy == i.is_failing,
    }
    if argument.lower() not in outcomes:
        raise ValueError("Invalid filter. Status should be 'healthy', 'failing' or 'unknown'")
    return _configured(outcomes[argument.lower()])


COMPONENTS: dict[str, Component] = {
    "tag": _tag,
    "lang": _language,
    "type": _type,
    "test": _test,
    "status": _status,
}


def _all_of(predicates: list[Predicate]) -> Predicate:
    return lambda indexer: all(test(indexer) for test in predicates)


def _any_of(predicates: list[Predicate]) -> Predicate:
    return lambda indexer: any(test(indexer) for test in predicates)


def _parse_parts(parts: list[str]) -> list[Predicate] | None:
    predicates = [parse_filter(part) for part in parts]
    return None if None in predicates else predicates


def parse_filter(source: str | None) -> Predicate | None:
    """Compile a filter; None if the text is not a valid filter."""
    if source is None or not source.strip():
        return None
    for operator, combine in ((OR_OPERATOR, _any_of), (AND_OPERATOR, _all_of)):
        if operator in source:
            parts = _parse_parts(source.split(operator))
            return combine(parts) if parts else None
    if source[0] == NOT_OPERATOR:
        inner = parse_filter(source[1:])
        return (lambda indexer: not inner(indexer)) if inner else None
    name, separator, argument = source.partition(SEPARATOR)
    component = COMPONENTS.get(name.lower())
    if not separator or component is None:
        return None
    return component(argument)


def type_filter(indexer_type: str) -> tuple[str, Predicate]:
    """(filter text, predicate) for the predefined ``type:`` groups."""
    return f"type:{indexer_type}", _type(indexer_type)


def tag_filter(tag: str) -> tuple[str, Predicate]:
    return f"tag:{tag}", _tag(tag)
