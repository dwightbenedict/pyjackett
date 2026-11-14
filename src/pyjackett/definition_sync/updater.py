"""One update round: fetch what changed, keep only what still parses."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from pyjackett.cardigann.definition_loader import parse_definition
from pyjackett.core.exceptions import DefinitionFeedError
from pyjackett.definition_sync.feed import DefinitionFeed
from pyjackett.definition_sync.store import DefinitionStore, Download

logger = logging.getLogger(__name__)

MAX_PARALLEL_DOWNLOADS = 8


@dataclass(frozen=True)
class DefinitionChanges:
    """What an update round did, by file name."""

    added: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.removed)


class DefinitionUpdater:
    """Brings the store in line with the feed.

    Upstream files overwrite same-named ones on disk. A definition the
    engine cannot parse (upstream may use newer features) never replaces a
    working one; it is retried on the next round.
    """

    def __init__(
        self,
        feed: DefinitionFeed,
        store: DefinitionStore,
        parallel_downloads: int = MAX_PARALLEL_DOWNLOADS,
    ) -> None:
        self._feed = feed
        self._store = store
        self._parallel = parallel_downloads

    async def update(self) -> DefinitionChanges:
        remote = await self._feed.list_files()
        if not remote:
            raise DefinitionFeedError("The definition listing is empty")
        known = self._store.revisions()
        wanted = [
            name
            for name, revision in sorted(remote.items())
            if known.get(name) != revision
        ]
        removed = sorted(set(known) - set(remote))
        texts = await self._fetch_all(wanted)
        changes = await asyncio.to_thread(
            self._apply, remote, known, texts, removed
        )
        logger.info(
            "Definitions: %d added, %d updated, %d removed, %d rejected",
            len(changes.added),
            len(changes.updated),
            len(changes.removed),
            len(changes.rejected),
        )
        return changes

    async def _fetch_all(self, names: list[str]) -> dict[str, str]:
        gate = asyncio.Semaphore(self._parallel)

        async def fetch(name: str) -> tuple[str, str | None]:
            async with gate:
                try:
                    return name, await self._feed.fetch(name)
                except DefinitionFeedError as error:
                    logger.warning("Cannot download %s: %s", name, error)
                    return name, None

        fetched = await asyncio.gather(*(fetch(name) for name in names))
        return {name: text for name, text in fetched if text is not None}

    def _apply(
        self,
        remote: dict[str, str],
        known: dict[str, str],
        texts: dict[str, str],
        removed: list[str],
    ) -> DefinitionChanges:
        accepted: dict[str, Download] = {}
        rejected: list[str] = []
        for name, text in texts.items():
            try:
                parse_definition(text)
            except Exception as error:
                logger.warning(
                    "Ignoring updated definition %s: %s", name, error
                )
                rejected.append(name)
            else:
                accepted[name] = Download(text, remote[name])
        self._store.save(accepted, removed)
        return DefinitionChanges(
            added=tuple(n for n in accepted if n not in known),
            updated=tuple(n for n in accepted if n in known),
            removed=tuple(removed),
            rejected=tuple(rejected),
        )
