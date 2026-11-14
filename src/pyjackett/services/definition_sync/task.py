"""The background loop that runs an update round now and then."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from pyjackett.domain.server_config import ServerConfig
from pyjackett.errors import DefinitionFeedError
from pyjackett.services.definition_sync.updater import DefinitionUpdater
from pyjackett.services.ports import Clock

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 24 * 60 * 60
RETRY_SECONDS = 60 * 60
INTERVAL_JITTER = (0.9, 1.1)


class DefinitionSyncTask:
    """Updates the definitions in the background for the app's lifetime.

    "Disable Update Checks" in the server settings pauses it. ``on_changed``
    runs after a round that changed anything, so the indexers can reload.
    """

    def __init__(
        self,
        updater: DefinitionUpdater,
        config: ServerConfig,
        clock: Clock,
        on_changed: Callable[[], Awaitable[object]],
        interval: float = SYNC_INTERVAL_SECONDS,
    ) -> None:
        self._updater = updater
        self._config = config
        self._clock = clock
        self._on_changed = on_changed
        self._interval = interval
        self._reload_pending = False
        self._task: asyncio.Task | None = None

    # ---- lifecycle ----------------------------------------------------------

    def attach(self) -> None:
        """Start looping on the running event loop (once)."""
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._run(), name="definition-sync")

    async def detach(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # ---- rounds -------------------------------------------------------------

    async def _run(self) -> None:
        while True:
            await self._clock.sleep(await self.sync_now())

    async def sync_now(self) -> float:
        """Run one round; returns the seconds to wait before the next."""
        if self._config.update_disabled:
            return self._next_interval()
        try:
            changes = await self._updater.update()
            self._reload_pending = self._reload_pending or changes.changed
            if self._reload_pending:
                await self._on_changed()
                self._reload_pending = False
        except DefinitionFeedError as error:
            logger.warning("Definition update failed: %s", error)
            return RETRY_SECONDS
        except Exception:
            logger.exception("Definition update failed")
            return RETRY_SECONDS
        return self._next_interval()

    def _next_interval(self) -> float:
        return self._interval * self._clock.jitter(*INTERVAL_JITTER)
