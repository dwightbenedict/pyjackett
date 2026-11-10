"""Certificate pinning for trackers that use self-signed certificates."""

from __future__ import annotations

import hashlib
import threading


class TrustedCertificates:
    """Maps certificate SHA-1 fingerprints to the hosts allowed to use them."""

    def __init__(self) -> None:
        self._hosts_by_hash: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def add(self, host: str, fingerprint: str) -> None:
        with self._lock:
            hosts = self._hosts_by_hash.setdefault(fingerprint.upper(), set())
            hosts.add(host.lower())

    def has_pins_for(self, host: str) -> bool:
        host = host.lower()
        return any(host in hosts for hosts in self._hosts_by_hash.values())

    def is_trusted(self, host: str, certificate_der: bytes) -> bool:
        fingerprint = hashlib.sha1(certificate_der).hexdigest().upper()
        return host.lower() in self._hosts_by_hash.get(fingerprint, set())
