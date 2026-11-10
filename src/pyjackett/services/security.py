"""Admin password hashing and checking."""

from __future__ import annotations

import hashlib
import hmac

from pyjackett.config.server_config import ServerConfig


class SecurityService:
    """Password protection of the dashboard (not of the Torznab API)."""

    def __init__(self, config: ServerConfig) -> None:
        self._config = config

    def hash_password(self, password: str | None) -> str | None:
        """SHA-512 of the password salted with the API key.

        Same scheme as upstream Jackett, so existing hashes stay valid.
        """
        if password is None:
            return None
        salted = (password + (self._config.api_key or "")).encode("utf-16-le")
        return hashlib.sha512(salted).hexdigest()

    def check_authorised(self, password: str | None) -> bool:
        stored = self._config.admin_password
        if not stored:
            return True  # no password set
        if not password:
            return False
        return hmac.compare_digest(self.hash_password(password), stored)
