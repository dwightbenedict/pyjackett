"""A disk cache of parsed definitions, so a restart skips the YAML work."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import pickle
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from pyjackett.domain.cardigann import definition, definition_loader
from pyjackett.domain.cardigann.definition import IndexerDefinition
from pyjackett.domain.cardigann.definition_loader import parse_definition

logger = logging.getLogger(__name__)

CACHE_FORMAT = 1
_DIGEST_BYTES = 16


def _digest(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=_DIGEST_BYTES).hexdigest()


def code_fingerprint() -> str:
    """Changes whenever the parser or the model it builds changes."""
    seed = f"{CACHE_FORMAT}-{sys.version_info[:2]}".encode()
    sources = (definition.__file__, definition_loader.__file__)
    with contextlib.suppress(OSError):  # else the Python version must do
        seed += b"".join(Path(path).read_bytes() for path in sources)
    return _digest(seed)


class DefinitionCache:
    """Parsed definitions keyed by the digest of the text they came from.

    Parsing 585 definitions costs seconds of CPU, which a small host does
    on every start. Entries are never stale: an edited file has a new
    digest. Only definitions parsed or looked up since the last ``save``
    are kept, so removed ones drop out. Without a path nothing is stored.
    """

    def __init__(
        self,
        path: Path | None = None,
        parse: Callable[[str], IndexerDefinition] = parse_definition,
    ) -> None:
        self._path = path
        self._parse = parse
        self._stored: dict[str, IndexerDefinition] | None = None
        self._used: dict[str, IndexerDefinition] = {}
        self._lock = threading.Lock()

    def parse(self, text: str) -> IndexerDefinition:
        """The definition of ``text``, parsed only the first time."""
        key = _digest(text.encode("utf-8"))
        with self._lock:
            found = self._used.get(key) or self._read().get(key)
            if found is None:
                found = self._parse(text)  # an invalid text raises
            self._used[key] = found
            return found

    def save(self) -> None:
        """Write what was used; a no-op when nothing changed."""
        with self._lock:
            if self._path is None or self._used.keys() == self._read().keys():
                return
            self._write(self._used)
            self._stored = dict(self._used)

    # ---- file ---------------------------------------------------------------

    def _read(self) -> dict[str, IndexerDefinition]:
        if self._stored is None:
            self._stored = self._load()
        return self._stored

    def _load(self) -> dict[str, IndexerDefinition]:
        if self._path is None or not self._path.is_file():
            return {}
        try:
            with self._path.open("rb") as file:
                fingerprint, entries = pickle.load(file)  # noqa: S301
        except Exception as error:  # a damaged cache is only a slow start
            logger.warning(
                "Ignoring definition cache %s: %s", self._path, error
            )
            return {}
        return entries if fingerprint == code_fingerprint() else {}

    def _write(self, entries: dict[str, IndexerDefinition]) -> None:
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("wb") as file:
                pickle.dump((code_fingerprint(), entries), file)
            os.replace(temporary, self._path)
        except OSError as error:  # a read-only folder just means no cache
            logger.warning("Cannot write definition cache: %s", error)
