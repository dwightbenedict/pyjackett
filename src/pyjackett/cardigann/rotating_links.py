"""Sites whose address changes on a schedule and can be computed from it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pyjackett.utils.urls import url_host

_MASK = 0xFFFFFFFF
_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_FNV_OFFSET = 2166136261
_FNV_PRIME = 16777619


class RotatingLinks(Protocol):
    """Knows which address a site answers on at a given moment."""

    def link_at(self, epoch_seconds: float) -> str:
        """Protocol method."""

    def owns(self, link: str) -> bool:
        """Protocol method."""


def _hash32(text: str) -> int:
    value = _FNV_OFFSET
    for char in text:
        value = ((value ^ ord(char)) * _FNV_PRIME) & _MASK
    return value


def _seeded_code(seed: str, length: int) -> str:
    """The page's xorshift generator, so the codes match its own."""
    state = _hash32(seed) or 1
    code = ""
    for _ in range(length):
        state ^= (state << 13) & _MASK
        state ^= state >> 17
        state ^= (state << 5) & _MASK
        code += _ALPHABET[state % len(_ALPHABET)]
    return code


@dataclass(frozen=True)
class AddressPageLinks:
    """A random sub domain of ``domain`` that a new slot replaces."""

    domain: str
    salt: str
    interval_minutes: int = 30
    code_length: int = 8
    domain_index: int = 0

    def link_at(self, epoch_seconds: float) -> str:
        slot = int(epoch_seconds // (self.interval_minutes * 60))
        seed = f"{self.salt}|{self.domain}|{slot}|{self.domain_index}"
        return f"https://{_seeded_code(seed, self.code_length)}.{self.domain}/"

    def owns(self, link: str) -> bool:
        host = url_host(link)
        return host == self.domain or host.endswith("." + self.domain)


# Indexer id -> where its address comes from. 52BT publishes it at
# https://www.52btbt.icu/, Magnet Cat on its own address page.
ROTATING_LINKS: dict[str, RotatingLinks] = {
    "52bt": AddressPageLinks("529075.xyz", salt="address-page-2026"),
    "magnetcat": AddressPageLinks("8800592.xyz", salt="address-page-2026"),
}


def rotating_links_for(indexer_id: str) -> RotatingLinks | None:
    return ROTATING_LINKS.get(indexer_id)
