"""Keeps the most recent log lines for the dashboard's "Logs" tab."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime

from pyjackett.utils.log_cleansing import cleanse

MAX_LOG_ENTRIES = 200
LOG_FORMAT = "%(name)s: %(message)s"


class LogCache(logging.Handler):
    """Logging handler holding the last log records, secrets removed."""

    def __init__(self, capacity: int = MAX_LOG_ENTRIES) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter(LOG_FORMAT))
        self._entries: deque[dict[str, str]] = deque(maxlen=capacity)
        self._entries_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "Level": record.levelname.title(),
            "Message": cleanse(self.format(record)),
            "When": datetime.fromtimestamp(record.created).isoformat(),
        }
        with self._entries_lock:
            self._entries.appendleft(entry)

    @property
    def logs(self) -> list[dict[str, str]]:
        """Newest entry first."""
        with self._entries_lock:
            return list(self._entries)
