"""Server-wide settings (the dashboard's "Configuration" panel)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any


class ProxyType(IntEnum):
    DISABLED = -1
    HTTP = 0
    SOCKS4 = 1
    SOCKS5 = 2


# attribute name -> key used in ServerConfig.json (same as upstream Jackett)
JSON_KEYS: dict[str, str] = {
    "port": "Port",
    "local_bind_address": "LocalBindAddress",
    "allow_external": "AllowExternal",
    "allow_cors": "AllowCORS",
    "api_key": "APIKey",
    "admin_password": "AdminPassword",
    "instance_id": "InstanceId",
    "blackhole_dir": "BlackholeDir",
    "update_disabled": "UpdateDisabled",
    "update_prerelease": "UpdatePrerelease",
    "base_path_override": "BasePathOverride",
    "base_url_override": "BaseUrlOverride",
    "cache_enabled": "CacheEnabled",
    "cache_ttl": "CacheTtl",
    "cache_max_results_per_indexer": "CacheMaxResultsPerIndexer",
    "flaresolverr_url": "FlareSolverrUrl",
    "flaresolverr_max_timeout": "FlareSolverrMaxTimeout",
    "omdb_api_key": "OmdbApiKey",
    "omdb_api_url": "OmdbApiUrl",
    "proxy_type": "ProxyType",
    "proxy_url": "ProxyUrl",
    "proxy_port": "ProxyPort",
    "proxy_username": "ProxyUsername",
    "proxy_password": "ProxyPassword",
}


@dataclass
class ServerConfig:
    """Every persisted server option, with Jackett's defaults."""

    port: int = 9117
    local_bind_address: str = "127.0.0.1"
    allow_external: bool = False
    allow_cors: bool = False
    api_key: str | None = None
    admin_password: str | None = None
    instance_id: str | None = None
    blackhole_dir: str | None = None
    update_disabled: bool = False
    update_prerelease: bool = False
    base_path_override: str | None = None
    base_url_override: str | None = None
    cache_enabled: bool = True
    # 35 minutes suits Sonarr/Radarr/Lidarr/Readarr polling intervals
    cache_ttl: int = 2100
    cache_max_results_per_indexer: int = 1000
    flaresolverr_url: str | None = None
    flaresolverr_max_timeout: int = 55000
    omdb_api_key: str | None = None
    omdb_api_url: str | None = None
    proxy_type: ProxyType = ProxyType.DISABLED
    proxy_url: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None
    tracing_enabled: bool = False  # runtime only, never persisted

    def __post_init__(self) -> None:
        self._observers: list[Callable[[ServerConfig], None]] = []

    # ---- change notification ----------------------------------------------

    def subscribe(self, observer: Callable[[ServerConfig], None]) -> None:
        self._observers.append(observer)

    def notify_changed(self) -> None:
        for observer in self._observers:
            observer(self)

    # ---- persistence --------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        return {
            json_key: _encode(getattr(self, attribute))
            for attribute, json_key in JSON_KEYS.items()
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ServerConfig:
        known = {f.name for f in fields(cls)}
        values = {
            attribute: data[json_key]
            for attribute, json_key in JSON_KEYS.items()
            if attribute in known and json_key in data
        }
        if "proxy_type" in values:
            values["proxy_type"] = ProxyType(values["proxy_type"])
        config = cls(**values)
        if not (config.proxy_url or "").strip():
            config.proxy_type = ProxyType.DISABLED
        return config

    # ---- proxy --------------------------------------------------------------

    @property
    def proxy_is_anonymous(self) -> bool:
        return (
            not (self.proxy_username or "").strip()
            or not (self.proxy_password or "").strip()
        )

    def proxy_address(self, with_credentials: bool = True) -> str | None:
        """Full proxy URL (``scheme://user:pass@host:port``) or None."""
        url = (self.proxy_url or "").strip()
        if self.proxy_type is ProxyType.DISABLED or not url:
            return None
        url = url.split("://", 1)[-1]
        if self.proxy_port:
            url = f"{url}:{self.proxy_port}"
        if with_credentials and not self.proxy_is_anonymous:
            url = f"{self.proxy_username}:{self.proxy_password}@{url}"
        return f"{self.proxy_type.name.lower()}://{url}"


def _encode(value: Any) -> Any:
    return int(value) if isinstance(value, ProxyType) else value
