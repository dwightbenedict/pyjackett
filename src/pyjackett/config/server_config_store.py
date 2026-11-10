"""Loading and saving ``ServerConfig.json``."""

from __future__ import annotations

import json
import logging
import secrets
import string
from pathlib import Path

from pyjackett.config.paths import SERVER_CONFIG_FILE
from pyjackett.config.server_config import ServerConfig

logger = logging.getLogger(__name__)

_API_KEY_LENGTH = 32
_INSTANCE_ID_LENGTH = 64
_RANDOM_ALPHABET = string.ascii_lowercase + string.digits


def generate_random(length: int) -> str:
    return "".join(secrets.choice(_RANDOM_ALPHABET) for _ in range(length))


class ServerConfigStore:
    """Persists the server configuration inside the data directory."""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / SERVER_CONFIG_FILE

    def load(self) -> ServerConfig:
        """Read the file, creating missing identifiers on first start."""
        config = self._read() or ServerConfig()
        if self._ensure_identifiers(config):
            self.save(config)
        return config

    def save(self, config: ServerConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(config.to_json(), indent=2)
        self._path.write_text(text, encoding="utf-8")

    def _read(self) -> ServerConfig | None:
        if not self._path.exists():
            logger.debug("Config file does not exist: %s", self._path)
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return ServerConfig.from_json(data)
        except (OSError, ValueError) as error:
            logger.error("Error reading config file %s: %s", self._path, error)
            return None

    @staticmethod
    def _ensure_identifiers(config: ServerConfig) -> bool:
        changed = False
        if not (config.api_key or "").strip():
            config.api_key = generate_random(_API_KEY_LENGTH)
            changed = True
        if not (config.instance_id or "").strip():
            config.instance_id = generate_random(_INSTANCE_ID_LENGTH)
            changed = True
        return changed
