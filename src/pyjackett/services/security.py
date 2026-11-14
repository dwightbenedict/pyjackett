"""Admin password hashing, dashboard sessions and API key checks."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable

from pyjackett.config.server_config import ServerConfig
from pyjackett.config.server_config_store import generate_api_key
from pyjackett.core.exceptions import (
    InvalidCredentialsError,
    InvalidPasswordError,
)
from pyjackett.utils.clock import SYSTEM_CLOCK, Clock

DEFAULT_CREDENTIAL = "admin"
SESSION_DAYS = 14
SECONDS_PER_DAY = 86400


class SecurityService:
    """Password protection of the dashboard (not of the Torznab API)."""

    def __init__(
        self,
        config: ServerConfig,
        clock: Clock = SYSTEM_CLOCK,
        new_api_key: Callable[[], str] = generate_api_key,
    ) -> None:
        self._config = config
        self._clock = clock
        self._new_api_key = new_api_key

    @property
    def has_admin_password(self) -> bool:
        return bool(self._config.admin_password)

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

    def ensure_default_credentials(self) -> bool:
        """Fill in admin/admin on a fresh install; True when it changed."""
        changed = False
        if not self._config.admin_username:
            self._config.admin_username = DEFAULT_CREDENTIAL
            changed = True
        if not self._config.admin_password:
            self._config.admin_password = self.hash_password(
                DEFAULT_CREDENTIAL
            )
            changed = True
        return changed

    @property
    def uses_default_credentials(self) -> bool:
        return self._config.admin_username == DEFAULT_CREDENTIAL and (
            self._config.admin_password
            == self.hash_password(DEFAULT_CREDENTIAL)
        )

    def check_credentials(
        self, username: str | None, password: str | None
    ) -> bool:
        expected = (self._config.admin_username or "").encode()
        given = (username or "").encode()
        return hmac.compare_digest(given, expected) and (
            self.check_authorised(password)
        )

    def set_username(self, username: str | None) -> None:
        username = (username or "").strip()
        if not username:
            raise InvalidCredentialsError("The username cannot be empty")
        self._config.admin_username = username

    def set_password(self, password: str | None) -> None:
        if not password:
            raise InvalidCredentialsError("The password cannot be empty")
        self._config.admin_password = self.hash_password(password)

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

    def rotate_api_key(self, password: str | None = None) -> str:
        """Replace the API key and return the new one.

        The password hash and the session signatures are derived from the
        key, so the hash is recomputed: that needs the current password.
        Sessions signed with the old key stop being valid.
        """
        protected = bool(self._config.admin_password)
        if protected and not self.check_authorised(password):
            raise InvalidPasswordError("The admin password is wrong")
        self._config.api_key = self._new_api_key()
        if protected:
            self._config.admin_password = self.hash_password(password)
        return self._config.api_key
