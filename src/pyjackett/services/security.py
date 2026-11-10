"""Admin password hashing, dashboard sessions and API key checks."""

from __future__ import annotations

import hashlib
import hmac

from pyjackett.config.server_config import ServerConfig
from pyjackett.utils.clock import SYSTEM_CLOCK, Clock

SESSION_DAYS = 14
SECONDS_PER_DAY = 86400


class SecurityService:
    """Password protection of the dashboard (not of the Torznab API)."""

    def __init__(
        self, config: ServerConfig, clock: Clock = SYSTEM_CLOCK
    ) -> None:
        self._config = config
        self._clock = clock

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

    # ---- dashboard sessions (signed cookie) ---------------------------------

    def _signature(self, expires: str) -> str:
        secret = f"{self._config.api_key}{self._config.instance_id}"
        return hmac.new(
            secret.encode(), expires.encode(), hashlib.sha256
        ).hexdigest()

    def create_session_cookie(self) -> str:
        lifetime = SESSION_DAYS * SECONDS_PER_DAY
        expires = str(int(self._clock.time()) + lifetime)
        return f"{expires}.{self._signature(expires)}"

    def is_valid_session(self, cookie: str | None) -> bool:
        if not cookie or "." not in cookie:
            return False
        expires, signature = cookie.split(".", 1)
        if not expires.isdigit() or int(expires) < self._clock.time():
            return False
        return hmac.compare_digest(signature, self._signature(expires))

    def is_authenticated(self, cookie: str | None) -> bool:
        """True when no password is set or the session cookie is valid."""
        if not self._config.admin_password:
            return True
        return self.is_valid_session(cookie)

    # ---- API key ------------------------------------------------------------

    def is_valid_api_key(self, key: str | None) -> bool:
        return bool(key) and hmac.compare_digest(key, self._config.api_key)
