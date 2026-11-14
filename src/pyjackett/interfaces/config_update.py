"""Validation and application of the server settings form."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

from pyjackett import __version__
from pyjackett.domain.server_config import DEFAULT_TEST_TIMEOUT, ProxyType
from pyjackett.wiring import AppContext

logger = logging.getLogger(__name__)

MIN_FLARESOLVERR_TIMEOUT = 5000
MIN_TEST_TIMEOUT = 1
MAX_TEST_TIMEOUT = 300
INVALID_PORT_MESSAGE = "Port must be between 1 and 65535."
RESTRICTED_PORTS = frozenset(
    {
        1,
        7,
        9,
        11,
        13,
        15,
        17,
        19,
        20,
        21,
        22,
        23,
        25,
        37,
        42,
        43,
        53,
        69,
        77,
        79,
        87,
        95,
        101,
        102,
        103,
        104,
        109,
        110,
        111,
        113,
        115,
        117,
        119,
        123,
        135,
        137,
        139,
        143,
        161,
        179,
        389,
        427,
        465,
        512,
        513,
        514,
        515,
        526,
        530,
        531,
        532,
        540,
        548,
        554,
        556,
        563,
        587,
        601,
        636,
        989,
        990,
        993,
        995,
        1719,
        1720,
        1723,
        2049,
        3659,
        4045,
        5060,
        5061,
        6000,
        6566,
        6665,
        6666,
        6667,
        6668,
        6669,
        6697,
        10080,
    }
)


class ServerConfigPayload(BaseModel):
    """The settings form of the dashboard."""

    port: int
    external: bool
    local_bind_address: str
    cors: bool = False
    blackholedir: str | None = None
    updatedisabled: bool = False
    prerelease: bool = False
    logging: bool = False
    basepathoverride: str | None = None
    baseurloverride: str | None = None
    cache_enabled: bool = True
    cache_ttl: int = 2100
    cache_max_results_per_indexer: int = 1000
    test_timeout: int = DEFAULT_TEST_TIMEOUT
    flaresolverrurl: str | None = None
    flaresolverr_maxtimeout: int = 55000
    omdbkey: str | None = None
    omdburl: str | None = None
    proxy_type: int = -1
    proxy_url: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None


def config_json(context: AppContext) -> dict:
    """Server settings as shown in the form (password hash is hidden)."""
    c = context.config
    return {
        "notices": [],
        "port": c.port,
        "external": c.allow_external,
        "local_bind_address": c.local_bind_address,
        "cors": c.allow_cors,
        "api_key": c.api_key,
        "blackholedir": c.blackhole_dir,
        "updatedisabled": c.update_disabled,
        "prerelease": c.update_prerelease,
        "password": (c.admin_password or "")[:10],
        "username": c.admin_username,
        "default_credentials": context.security.uses_default_credentials,
        "logging": c.tracing_enabled,
        "basepathoverride": c.base_path_override,
        "baseurloverride": c.base_url_override,
        "cache_enabled": c.cache_enabled,
        "cache_ttl": c.cache_ttl,
        "cache_max_results_per_indexer": c.cache_max_results_per_indexer,
        "test_timeout": c.test_timeout,
        "flaresolverrurl": c.flaresolverr_url,
        "flaresolverr_maxtimeout": c.flaresolverr_max_timeout,
        "omdbkey": c.omdb_api_key,
        "omdburl": c.omdb_api_url,
        "app_version": __version__,
        "proxy_type": int(c.proxy_type),
        "proxy_url": c.proxy_url,
        "proxy_port": c.proxy_port,
        "proxy_username": c.proxy_username,
        "proxy_password": c.proxy_password,
    }


# ---- validation -------------------------------------------------------------


def _clean_url(value: str | None, label: str, example: str) -> str:
    """Trim a URL and ensure it is absolute http(s); "" means unset."""
    value = (value or "").strip().rstrip("/")
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"{label} is invalid. Example: {example}")
    return value


def _clean_base_path(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.rstrip("/")
    if value and not value.startswith("/"):
        raise ValueError("The Base Path Override must start with a /")
    return value


def _validate_network(payload: ServerConfigPayload) -> None:
    if payload.port in RESTRICTED_PORTS:
        raise ValueError("That port is restricted. Choose another.")
    if not 1 <= payload.port <= 65535:
        raise ValueError(INVALID_PORT_MESSAGE)
    if not payload.local_bind_address.strip():
        raise ValueError("You need to provide a local bind address.")


def _validate_test_timeout(payload: ServerConfigPayload) -> None:
    if not MIN_TEST_TIMEOUT <= payload.test_timeout <= MAX_TEST_TIMEOUT:
        raise ValueError(
            f"The test timeout must be between {MIN_TEST_TIMEOUT} and {MAX_TEST_TIMEOUT} seconds."
        )


def _restart_needed(config, payload, base_path: str | None) -> bool:
    """Network and base-path changes only apply after a restart."""
    return (
        (base_path or "") != (config.base_path_override or "")
        or payload.cors != config.allow_cors
        or (payload.port, payload.external, payload.local_bind_address)
        != (config.port, config.allow_external, config.local_bind_address)
    )


def _validated_flaresolverr(payload: ServerConfigPayload) -> str:
    url = _clean_url(
        payload.flaresolverrurl,
        "FlareSolverr API URL",
        "http://127.0.0.1:8191",
    )
    if url and payload.flaresolverr_maxtimeout < MIN_FLARESOLVERR_TIMEOUT:
        raise ValueError("FlareSolverr Max Timeout must be greater than 5000 ms.")
    return url


def _validated_blackhole(payload: ServerConfigPayload) -> str | None:
    directory = payload.blackholedir or None
    if directory and not Path(directory).is_dir():
        raise ValueError("Blackhole directory does not exist")
    return directory


def _copy_network(config, payload: ServerConfigPayload) -> None:
    config.port, config.allow_external = payload.port, payload.external
    config.local_bind_address = payload.local_bind_address
    config.allow_cors = payload.cors


def _copy_cache(config, payload: ServerConfigPayload) -> None:
    config.cache_enabled = payload.cache_enabled
    config.cache_ttl = payload.cache_ttl
    config.cache_max_results_per_indexer = payload.cache_max_results_per_indexer


def _copy_integrations(config, payload: ServerConfigPayload) -> None:
    config.omdb_api_key = payload.omdbkey
    config.omdb_api_url = (payload.omdburl or "").rstrip("/") or None
    config.flaresolverr_max_timeout = payload.flaresolverr_maxtimeout
    config.update_disabled = payload.updatedisabled
    config.update_prerelease = payload.prerelease
    config.tracing_enabled = payload.logging


def apply_server_config(context: AppContext, payload: ServerConfigPayload) -> bool:
    """Validate and copy the payload; True if a restart is needed."""
    config = context.config
    _validate_network(payload)
    _validate_test_timeout(payload)
    flare_url = _validated_flaresolverr(payload)
    blackhole = _validated_blackhole(payload)
    base_path = _clean_base_path(payload.basepathoverride)
    base_url = _clean_url(payload.baseurloverride, "Base URL Override", "http://pyjackett:9117")
    restart = _restart_needed(config, payload, base_path)
    if _apply_proxy(config, payload):
        context.cache.clean_cache()  # let the user test the new proxy
    _copy_network(config, payload)
    _copy_cache(config, payload)
    config.test_timeout = payload.test_timeout
    _copy_integrations(config, payload)
    config.blackhole_dir = blackhole
    config.base_path_override, config.base_url_override = base_path, base_url
    config.flaresolverr_url = flare_url or None
    return restart


def _apply_proxy(config, payload: ServerConfigPayload) -> bool:
    """Copy proxy settings; True if they changed."""
    if payload.proxy_port is not None and not 1 <= payload.proxy_port <= 65535:
        raise ValueError(INVALID_PORT_MESSAGE)
    new = (
        ProxyType(payload.proxy_type) if (payload.proxy_url or "").strip() else ProxyType.DISABLED,
        payload.proxy_url,
        payload.proxy_port,
        payload.proxy_username,
        payload.proxy_password,
    )
    old = (
        config.proxy_type,
        config.proxy_url,
        config.proxy_port,
        config.proxy_username,
        config.proxy_password,
    )
    (
        config.proxy_type,
        config.proxy_url,
        config.proxy_port,
        config.proxy_username,
        config.proxy_password,
    ) = new
    return new != old
