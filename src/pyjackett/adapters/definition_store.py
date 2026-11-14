"""The downloaded definitions on disk, with a manifest of their revisions."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from pyjackett.services.ports import Download

MANIFEST_FILE = "manifest.json"


class DefinitionStore:
    """Writes definitions atomically, overwriting, and remembers them.

    Only files in the manifest are ever deleted.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def revisions(self) -> dict[str, str]:
        """Revision of every downloaded definition that is still on disk."""
        return {
            name: revision
            for name, revision in self._read_manifest().items()
            if self.has_file(name)
        }

    def has_file(self, name: str) -> bool:
        return (self._directory / name).is_file()

    def save(self, downloads: Mapping[str, Download], removed: Iterable[str]) -> None:
        """Write the downloads, delete the removed, update the manifest."""
        self._directory.mkdir(parents=True, exist_ok=True)
        manifest = self._read_manifest()
        for name, download in downloads.items():
            self._write(self._directory / name, download.text)
            manifest[name] = download.revision
        for name in removed:
            (self._directory / name).unlink(missing_ok=True)
            manifest.pop(name, None)
        self._write(self._directory / MANIFEST_FILE, json.dumps(manifest))

    def _read_manifest(self) -> dict[str, str]:
        try:
            text = (self._directory / MANIFEST_FILE).read_text("utf-8")
            manifest = json.loads(text)
        except (OSError, ValueError):
            return {}
        return manifest if isinstance(manifest, dict) else {}

    @staticmethod
    def _write(path: Path, text: str) -> None:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
