"""Settings taken from environment variables (hosting without a disk)."""

from __future__ import annotations

from collections.abc import Mapping

from pyjackett.config.server_config import ServerConfig
from pyjackett.services.security import SecurityService

API_KEY_ENV = "PYJACKETT_API_KEY"
ADMIN_USERNAME_ENV = "PYJACKETT_ADMIN_USERNAME"
ADMIN_PASSWORD_ENV = "PYJACKETT_ADMIN_PASSWORD"
MAX_CONCURRENCY_ENV = "PYJACKETT_MAX_CONCURRENCY"
CACHE_MAX_RELEASES_ENV = "PYJACKETT_CACHE_MAX_RELEASES"
SYNC_DEFINITIONS_ENV = "PYJACKETT_SYNC_DEFINITIONS"
DEFINITION_CACHE_ENV = "PYJACKETT_DEFINITION_CACHE"
INDEXERS_ENV = "PYJACKETT_INDEXERS"
MAX_ROWS_ENV = "PYJACKETT_MAX_ROWS"
RETRIES_ENV = "PYJACKETT_RETRIES"
SKIP_FAILING_ENV = "PYJACKETT_SKIP_FAILING"
DEFAULT_CACHE_MAX_RELEASES = 20000
_OFF_WORDS = frozenset({"0", "false", "no", "off"})
_ON_WORDS = frozenset({"1", "true", "yes", "on"})


def positive_int(environ: Mapping[str, str], name: str) -> int | None:
    """The variable as a positive integer; unset or invalid gives None."""
    try:
        value = int(environ.get(name, "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def non_negative_int(environ: Mapping[str, str], name: str) -> int | None:
    """The variable as an integer of 0 or more; unusable gives None."""
    try:
        value = int(environ.get(name, "").strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def skip_failing_from(environ: Mapping[str, str]) -> bool:
    """Whether a search leaves out indexers that are currently failing."""
    return environ.get(SKIP_FAILING_ENV, "").strip().lower() in _ON_WORDS


def public_indexers_from(
    environ: Mapping[str, str], default: frozenset[str] | None
) -> frozenset[str] | None:
    """The public indexers to configure at startup; None means all.

    Unset gives ``default``; "all" gives every public indexer; otherwise a
    comma or space separated list of ids.
    """
    ids = environ.get(INDEXERS_ENV, "").replace(",", " ").split()
    if not ids:
        return default
    return None if ids == ["all"] else frozenset(ids)


def sync_definitions_from(environ: Mapping[str, str]) -> bool:
    """Whether definitions update from upstream; on unless switched off."""
    value = environ.get(SYNC_DEFINITIONS_ENV, "")
    return value.strip().lower() not in _OFF_WORDS


def cache_limit_from(environ: Mapping[str, str]) -> int:
    """Most releases the results cache may hold in total."""
    return positive_int(environ, CACHE_MAX_RELEASES_ENV) or (
        DEFAULT_CACHE_MAX_RELEASES
    )


def apply_credentials(
    config: ServerConfig,
    security: SecurityService,
    environ: Mapping[str, str],
) -> bool:
    """Let the environment fix the API key and admin login; True if changed.

    A host with an ephemeral disk loses ``ServerConfig.json`` on every
    restart, which would otherwise rotate the key clients depend on.
    """
    api_key = environ.get(API_KEY_ENV, "").strip()
    username = environ.get(ADMIN_USERNAME_ENV, "").strip()
    password = environ.get(ADMIN_PASSWORD_ENV, "")
    before = (config.api_key, config.admin_username, config.admin_password)
    if api_key:
        config.api_key = api_key
    if username:
        security.set_username(username)
    if password:
        security.set_password(password)  # hashed with the key set above
    return before != (
        config.api_key,
        config.admin_username,
        config.admin_password,
    )
