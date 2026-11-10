"""Where pyjackett keeps its files."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR_ENV = "PYJACKETT_DATA"
APP_DIR_NAME = "PyJackett"
SERVER_CONFIG_FILE = "ServerConfig.json"
PROTECTION_KEY_FILE = "protection.key"
INDEXERS_DIR_NAME = "Indexers"
BUNDLED_DEFINITIONS_DIR = Path(__file__).resolve().parent.parent / (
    "definitions"
)
BUNDLED_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def default_data_dir() -> Path:
    """Per-user application data folder for the current platform."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData"))
        return base / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME.lower()


def resolve_data_dir(explicit: str | os.PathLike | None = None) -> Path:
    """Pick the data folder: argument, then environment, then default."""
    chosen = explicit or os.environ.get(DATA_DIR_ENV)
    return Path(chosen).expanduser() if chosen else default_data_dir()


def indexer_config_dir(data_dir: Path) -> Path:
    return data_dir / INDEXERS_DIR_NAME


def indexer_config_path(data_dir: Path, indexer_id: str) -> Path:
    return indexer_config_dir(data_dir) / f"{indexer_id}.json"
