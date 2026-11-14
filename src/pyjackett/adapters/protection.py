"""Reversible encryption of secrets stored in configuration files."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from pyjackett.adapters.paths import PROTECTION_KEY_FILE

KEY_ENV = "PYJACKETT_KEY"


class ProtectionService:
    """Encrypts and decrypts strings with a key kept next to the config."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @classmethod
    def for_data_dir(
        cls, data_dir: Path, passphrase: str | None = None
    ) -> ProtectionService:
        """Use ``passphrase`` if given, otherwise a generated key file."""
        if passphrase:
            return cls(_key_from_passphrase(passphrase))
        return cls(_load_or_create_key_file(data_dir / PROTECTION_KEY_FILE))

    def protect(self, plain_text: str | None) -> str:
        if not plain_text:
            return ""
        return self._fernet.encrypt(plain_text.encode("utf-8")).decode("ascii")

    def unprotect(self, token: str | None) -> str:
        """Decrypt ``token``; values that were never encrypted pass through."""
        if not token:
            return ""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError):
            return token


def _key_from_passphrase(passphrase: str) -> bytes:
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _load_or_create_key_file(path: Path) -> bytes:
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key)
    return key
