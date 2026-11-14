"""Pinned hosts are checked before any request is sent to them."""

from __future__ import annotations

import hashlib

import pytest

import fakes
from pyjackett.config.server_config import ServerConfig
from pyjackett.http.certificates import TrustedCertificates
from pyjackett.http.session import HttpSession, PinnedCertificateError

CERTIFICATE = b"der-bytes"


def session_for(probe, sent):
    def handler(request):
        sent.append(request)
        return fakes.Response(200)

    certificates = TrustedCertificates()
    fingerprint = hashlib.sha1(CERTIFICATE).hexdigest()
    certificates.add("pinned.test", fingerprint)
    return HttpSession(
        ServerConfig(),
        certificates,
        client_factory=fakes.mock_network(handler),
        certificate_probe=probe,
    )


async def test_matching_certificate_is_sent_to():
    sent = []

    async def probe(host, port, timeout):
        assert (host, port) == ("pinned.test", 443)
        return CERTIFICATE

    session = session_for(probe, sent)
    await session.send({"method": "GET", "url": "https://pinned.test/"})
    assert len(sent) == 1


async def test_other_certificate_stops_before_sending():
    sent = []

    async def probe(host, port, timeout):
        return b"someone else"

    session = session_for(probe, sent)
    with pytest.raises(PinnedCertificateError):
        await session.send({"method": "GET", "url": "https://pinned.test/"})
    assert sent == []
