"""Keeps an indexer on the address its site currently answers on."""

from __future__ import annotations

from typing import Protocol

from pyjackett.cardigann.definition import IndexerDefinition
from pyjackett.cardigann.listed_links import (
    ListedLinkFollower,
    listed_links_for,
)
from pyjackett.cardigann.rotating_links import rotating_links_for
from pyjackett.http.client import WebClient
from pyjackett.utils.clock import Clock


def _with_slash(link: str) -> str:
    return link if link.endswith("/") else link + "/"


def default_link(definition: IndexerDefinition, clock: Clock) -> str:
    """The address a new indexer starts on."""
    rotating = rotating_links_for(definition.id)
    link = rotating.link_at(clock.time()) if rotating else definition.links[0]
    return _with_slash(link)


class AddressHost(Protocol):
    """The indexer whose address is followed."""

    site_link: str

    def move_to_site_link(self, link: str) -> None:
        """Protocol method."""


class SiteAddress:
    """Moves its host to the current address of a site that changes it."""

    def __init__(
        self,
        host: AddressHost,
        definition: IndexerDefinition,
        client: WebClient,
        clock: Clock,
    ) -> None:
        self._host = host
        self._clock = clock
        self._rotating = rotating_links_for(definition.id)
        listed = listed_links_for(definition.id)
        self._listed = listed and ListedLinkFollower(listed, client, clock)
        self._known = frozenset(
            _with_slash(link)
            for link in [*definition.links, *(definition.legacylinks or ())]
        )

    @property
    def follows_address(self) -> bool:
        return bool(self._rotating or self._listed)

    async def follow(self) -> None:
        link = self._host.site_link
        if not self.follows_address or not self._is_official(link):
            return
        target = await self._current_address(link)
        if target and target != link:
            self._host.move_to_site_link(target)

    def _is_official(self, link: str) -> bool:
        """False for an address the user typed in, which is left alone."""
        source = self._rotating or self._listed
        return source.owns(link) or _with_slash(link) in self._known

    async def _current_address(self, link: str) -> str | None:
        if self._rotating:
            return _with_slash(self._rotating.link_at(self._clock.time()))
        return await self._listed.replacement_for(link)
