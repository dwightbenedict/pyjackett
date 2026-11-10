"""A small implementation of the Go ``text/template`` subset Cardigann uses.

Supported: simple variables, ``re_replace``, ``join``, ``and``/``or``/``eq``/
``ne``, ``if ... else ... end`` and ``range``. Every construct is expanded
in a separate pass, in the same order as the original implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import regex

from pyjackett.utils.regex_compat import replace_all
from pyjackett.utils.text import is_blank

Variables = dict[str, Any]
Modifier = Callable[[str], str] | None

_LOGIC_FUNCTIONS = ("and", "or", "eq", "ne")
_FUNCTIONS_WITH_LITERALS = ("eq", "ne")

_RE_REPLACE = regex.compile(
    r'\{\{\s*re_replace\s+(\..+?)\s+"(.*?)"\s+"(.*?)"\s*\}\}'
)
_JOIN = regex.compile(r'\{\{\s*join\s+(\..+?)\s+"(.*?)"\s*\}\}')
# a logic function followed by 2+ of: (.var) or .var or "string literal"
_LOGIC = regex.compile(
    r"\b("
    + "|".join(_LOGIC_FUNCTIONS)
    + r')(?:\s+(\(?\.[^\)\s]+\)?|"[^"]+")){2,}'
)
_IF_ELSE = regex.compile(
    r"\{\{\s*if\s*(.+?)\s*\}\}(.*?)\{\{\s*else\s*\}\}(.*?)\{\{\s*end\s*\}\}"
)
_RANGE = regex.compile(
    r"\{\{\s*range\s*(((?<index>\$.+?),)((\s*(?<element>.+?)\s*(:=)\s*)))?"
    r"(?<variable>.+?)\s*\}\}(?<prefix>.*?)\{\{\.\}\}"
    r"(?<postfix>.*?)\{\{end\}\}"
)
_VARIABLE = regex.compile(r"\{\{\s*(\..+?)\s*\}\}")

TRUE_VARIABLE = ".True"
FALSE_VARIABLE = ".False"


def _modify(value: str | None, modifier: Modifier) -> str:
    text = "" if value is None else value
    return modifier(text) if modifier else text


def _replace_each(template: str, original: str, pattern, expand) -> str:
    """Replace every match of ``original`` (as found there) in ``template``.

    Matches are located in the untouched input while the replacements are
    applied to the working copy, which is what the original implementation
    does.
    """
    for match in pattern.finditer(original):
        template = template.replace(match.group(0), expand(match))
    return template


# ---- re_replace -------------------------------------------------------------


def _expand_re_replace(template: str, variables: Variables, modifier) -> str:
    def expand(match: regex.Match) -> str:
        variable, pattern, replacement = match.groups()
        text = variables[variable] or ""
        return _modify(replace_all(pattern, replacement, text), modifier)

    return _replace_each(template, template, _RE_REPLACE, expand)


# ---- join -------------------------------------------------------------------


def _expand_join(template: str, variables: Variables, modifier) -> str:
    def expand(match: regex.Match) -> str:
        variable, delimiter = match.groups()
        joined = delimiter.join(str(v) for v in variables[variable])
        return _modify(joined, modifier)

    return _replace_each(template, template, _JOIN, expand)


# ---- and / or / eq / ne -----------------------------------------------------


def _is_string_literal(parameter: str) -> bool:
    return parameter.startswith('"')


def _first_by_emptiness(
    parameters: list[str], variables: Variables, stop_when_blank: bool
) -> str:
    """``and`` stops at the first blank value, ``or`` at the first filled."""
    result = ""
    for parameter in parameters:
        result = parameter
        value = variables[parameter]
        blank = is_blank(value if isinstance(value, str) else None)
        if blank == stop_when_blank:
            break
    return result


def _equality(parameters: list[str], variables: Variables, want_equal: bool):
    values = []
    for parameter in parameters[:2]:
        if _is_string_literal(parameter):
            values.append(parameter.strip('"'))
        else:
            value = variables[parameter]
            values.append(value if isinstance(value, str) else None)
    is_equal = len(set(values)) == 1
    return TRUE_VARIABLE if is_equal == want_equal else FALSE_VARIABLE


def _logic_result(name: str, parameters: list[str], variables: Variables):
    if name == "and":
        return _first_by_emptiness(parameters, variables, True)
    if name == "or":
        return _first_by_emptiness(parameters, variables, False)
    return _equality(parameters, variables, name == "eq")


def _expand_logic_functions(template: str, variables: Variables) -> str:
    """Rewrite logic calls by their result; nested calls work because the
    search restarts after every substitution."""
    match = _LOGIC.search(template)
    while match:
        name = match.group(1)
        captures = match.captures(2)
        parameters = [c.strip("()") for c in captures]
        length = match.end() - match.start()
        if name not in _FUNCTIONS_WITH_LITERALS:
            parameters = [p for p in parameters if not _is_string_literal(p)]
        elif len(parameters) > 2:
            # eq/ne take exactly two parameters
            length = match.starts(2)[2] - match.start()
        result = _logic_result(name, parameters, variables)
        template = (
            template[: match.start()]
            + result
            + template[match.start() + length :]
        )
        match = _LOGIC.search(template)
    return template


# ---- if / else / end --------------------------------------------------------


def _is_truthy(variable: str, value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return not is_blank(value)
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    raise TypeError(f"Unexpected type for variable {variable}: {type(value)}")


def _expand_if_else(template: str, variables: Variables) -> str:
    def expand(match: regex.Match) -> str:
        condition, on_true, on_false = match.groups()
        if not condition.startswith("."):
            raise NotImplementedError(
                f"CardigannIndexer: Condition operation '{condition}' "
                "not implemented"
            )
        value = variables[condition]
        return on_true if _is_truthy(condition, value) else on_false

    return _replace_each(template, template, _IF_ELSE, expand)


# ---- range ------------------------------------------------------------------


def _expand_range(template: str, variables: Variables, modifier) -> str:
    def expand(match: regex.Match) -> str:
        index = match.group("index")
        prefix, postfix = match.group("prefix"), match.group("postfix")
        placeholder = "{{" + index + "}}" if index else None
        parts = []
        for position, value in enumerate(variables[match.group("variable")]):
            text = _modify(value, modifier)
            if placeholder:
                before = prefix.replace(placeholder, str(position))
                after = postfix.replace(placeholder, str(position))
                parts.append(before + text + after)
            else:
                parts.append(prefix + text + postfix)
        return "".join(parts)

    return _replace_each(template, template, _RANGE, expand)


# ---- simple variables -------------------------------------------------------


def _expand_variables(template: str, variables: Variables, modifier) -> str:
    def expand(match: regex.Match) -> str:
        value = variables[match.group(1)]
        if value is not None and not isinstance(value, str):
            raise TypeError(f"Variable {match.group(1)} is not a string")
        return _modify(value, modifier)

    return _replace_each(template, template, _VARIABLE, expand)


# ---- public -----------------------------------------------------------------


def apply_template(
    template: str | None,
    variables: Variables,
    modifier: Modifier = None,
) -> str | None:
    """Expand ``{{ ... }}`` expressions of ``template``.

    ``modifier`` post-processes every inserted value (e.g. URL encoding).
    """
    if is_blank(template) or "{{" not in template:
        return template
    template = _expand_re_replace(template, variables, modifier)
    template = _expand_join(template, variables, modifier)
    template = _expand_logic_functions(template, variables)
    template = _expand_if_else(template, variables)
    template = _expand_range(template, variables, modifier)
    return _expand_variables(template, variables, modifier)
