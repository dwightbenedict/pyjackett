"""Short failure reasons shown on indexer cards."""

from __future__ import annotations

from types import SimpleNamespace

from pyjackett.core.exceptions import (
    IndexerError,
    IndexerTestFailedError,
    describe_failure,
)


def test_plain_error_keeps_its_message():
    error = IndexerTestFailedError("No results.")
    assert describe_failure(error) == "No results."


def test_wrapped_error_shows_only_the_cause_once():
    cause = ValueError("Connection refused")
    error = IndexerError(SimpleNamespace(id="demo"), cause)
    assert describe_failure(error) == "Connection refused"


def test_http_boilerplate_is_dropped():
    cause = RuntimeError(
        "Client error '403 Forbidden' for url 'https://x.test' "
        "For more information check: https://developer.mozilla.org"
    )
    error = IndexerError(SimpleNamespace(id="demo"), cause)
    assert describe_failure(error) == (
        "Client error '403 Forbidden' for url 'https://x.test'"
    )


def test_empty_message_falls_back_to_the_type_name():
    assert describe_failure(TimeoutError()) == "TimeoutError"
