"""Reads and writes one JSON file per configured indexer."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pyjackett.adapters.paths import indexer_config_dir, indexer_config_path

logger = logging.getLogger(__name__)
BACKUP_SUFFIX = ".bak"


class IndexerConfigStore:
    """Atomic, backed-up persistence of indexer configuration lists."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def path_for(self, indexer_id: str) -> Path:
        return indexer_config_path(self._data_dir, indexer_id)

    def load(self, indexer_id: str) -> list[dict[str, Any]] | None:
        """Return the stored form values, falling back to the backup."""
        path = self.path_for(indexer_id)
        if not path.exists():
            return None
        try:
            return _read_json(path)
        except (OSError, ValueError) as error:
            logger.error("Failed loading %s, trying backup: %s", path, error)
        return self._load_backup(path)

    def _load_backup(self, path: Path) -> list[dict[str, Any]] | None:
        backup = _backup_of(path)
        if not backup.exists():
            logger.error("No backup available for %s; reconfigure it", path)
            return None
        try:
            data = _read_json(backup)
        except (OSError, ValueError) as error:
            logger.error("Failed loading backup %s: %s", backup, error)
            return None
        logger.info("Successfully loaded backup config %s", backup)
        return data

    def save(self, indexer_id: str, data: list[dict[str, Any]]) -> None:
        """Write via a temp file, keeping the previous version as ``.bak``."""
        content = json.dumps(data, indent=2)
        if "\x00" in content:
            raise ValueError(f"Config of {indexer_id} contains a NUL byte")
        path = self.path_for(indexer_id)
        indexer_config_dir(self._data_dir).mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(content, encoding="utf-8")
        _rotate_backup(path)
        temporary.replace(path)

    def delete(self, indexer_id: str) -> None:
        path = self.path_for(indexer_id)
        path.unlink(missing_ok=True)
        _backup_of(path).unlink(missing_ok=True)

    def rename(self, old_id: str, new_id: str) -> bool:
        """Move a config (and its backup) to a new id; True if it moved."""
        old_path = self.path_for(old_id)
        if not old_path.exists():
            return False
        new_path = self.path_for(new_id)
        new_path.unlink(missing_ok=True)
        old_path.replace(new_path)
        old_backup = _backup_of(old_path)
        if old_backup.exists():
            old_backup.replace(_backup_of(new_path))
        return True

    def stored_ids(self) -> list[str]:
        directory = indexer_config_dir(self._data_dir)
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.json"))


def _read_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _backup_of(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def _rotate_backup(path: Path) -> None:
    backup = _backup_of(path)
    backup.unlink(missing_ok=True)
    if path.exists():
        path.replace(backup)
