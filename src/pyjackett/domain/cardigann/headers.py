"""Custom HTTP headers declared by a definition."""

from __future__ import annotations

from pyjackett.domain.cardigann.template import Variables, apply_template


def parse_custom_headers(
    headers: dict[str, list[str]] | None, variables: Variables
) -> dict[str, str]:
    """Expand templates in header values (only the first value is used)."""
    return {
        name: apply_template(values[0], variables)
        for name, values in (headers or {}).items()
        if values
    }
