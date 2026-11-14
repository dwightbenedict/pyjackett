"""Server level helpers: base paths and proxied download links."""

from __future__ import annotations

from urllib.parse import quote_plus

from pyjackett.adapters.protection import ProtectionService
from pyjackett.domain.server_config import ServerConfig
from pyjackett.domain.urls import base64url_encode

MAGNET_PREFIX = "magnet:"
BLACKHOLE_ACTION = "bh"


class ServerService:
    """Builds the URLs Torznab clients use to download through us."""

    def __init__(
        self, config: ServerConfig, protector: ProtectionService
    ) -> None:
        self._config = config
        self._protector = protector

    def base_path(self) -> str:
        """The configured path prefix ("" or "/prefix")."""
        path = (self._config.base_path_override or "").strip("/")
        return f"/{path}" if path else ""

    def convert_to_proxy_link(
        self,
        link: str | None,
        server_url: str,
        indexer_id: str,
        action: str = "dl",
        file: str = "t",
    ) -> str | None:
        """Wrap ``link`` so it is fetched through this server.

        The original link travels encrypted in the ``path`` parameter so
        credentials embedded in it are never exposed to the client.
        """
        if link is None:
            return None
        if link.startswith(MAGNET_PREFIX) and action != BLACKHOLE_ACTION:
            return link  # magnets need no proxy
        token = self._protector.protect(link)
        path = base64url_encode(token.encode("utf-8"))
        return (
            f"{server_url}{action}/{indexer_id}/"
            f"?jackett_apikey={self._config.api_key}&path={path}"
            f"&file={quote_plus(file)}"
        )
