"""Removes secrets (api keys, passkeys, passwords) from log messages."""

from __future__ import annotations

import regex

REMOVED = "(removed)"
_FLAGS = regex.IGNORECASE

_RULES = tuple(
    regex.compile(pattern, flags)
    for pattern, flags in (
        # url parameters
        (
            r"(?<=[?&: ;])(apikey|api_key|(?:(?:access|api)[-_]?)?token|"
            r"pass(?:key|wd)?|auth|authkey|rsskey|user|u?id|api|"
            r"[a-z_]*apikey|account|pwd)=(?<secret>[^&=\"]+?)(?=[ \"&=]|$)",
            _FLAGS,
        ),
        (
            r"(?<=[?& ;])[^=]*?(_?(?<!use|get_)token|username|passwo?rd)="
            r"(?<secret>[^&=]+?)(?= |&|$|;)",
            _FLAGS,
        ),
        (
            r"(?<=[?& ;])[^=]*?(pid)=(?<secret>[a-z0-9]{32}[^&=]+?)"
            r"(?= |&|$|;)",
            _FLAGS,
        ),
        (r"rss(24h)?\.torrentleech\.org/(?!rss)(?<secret>[0-9a-z]+)", _FLAGS),
        (
            r"torrentleech\.org/rss/download/[0-9]+/(?<secret>[0-9a-z]+)",
            _FLAGS,
        ),
        (
            r"iptorrents\.com/[/a-z0-9?&;]*?(?:[?&;](u|tp)="
            r"(?<secret>[^&=;]+?))+(?= |;|&|$)",
            _FLAGS,
        ),
        (r"/fetch/[a-z0-9]{32}/(?<secret>[a-z0-9]{32})", 0),
        (
            r"\b(\w*)?(_?(?<!use|get_)token|username|passwo?rd)="
            r"(?<secret>[^&=]+?)(?= |&|$|;)",
            _FLAGS,
        ),
        (r"(?<=authkey = \")(?<secret>[^&=]+?)(?=\")", _FLAGS),
        (
            r"(?<=beyond-hd\.[a-z]+/api/torrents/)(?<secret>[^&=][a-z0-9]+)",
            _FLAGS,
        ),
        (
            r"(?<=beyond-hd\.[a-z]+/torrent/download/[\w\d-]+[.]\d+[.])"
            r"(?<secret>[a-z0-9]+)",
            _FLAGS,
        ),
        (
            r"(?:sharewood)\.[a-z]{2,3}/api/(?<secret>[a-z0-9]{16,})/",
            _FLAGS,
        ),
        # UNIT3D
        (
            r"(?<=[a-z0-9-]+\.[a-z]+/torrent/download/\d+\.)"
            r"(?<secret>[^&=][a-z0-9]+)",
            _FLAGS,
        ),
        # paths
        (r"\"C:\\Users\\(?<secret>[^\"]+?)(\\|$)", _FLAGS),
        (r"\"/(home|Users)/(?<secret>[^/\"]+?)(/|$)", _FLAGS),
        # BroadcasTheNet
        (
            r"(?<=\?|&|;|=)(authkey|torrent_pass|torrents_notify)[_=]"
            r"(?<secret>[^&=]+?)(?=\"|&|$)",
            _FLAGS,
        ),
        # indexer responses
        (
            r"(?:avistaz|exoticaz|cinemaz|privatehd)\.[a-z]{2,3}/rss/"
            r"download/(?<secret>[^&=]+?)/(?<secret>[^&=]+?)\.torrent",
            _FLAGS,
        ),
        (
            r"(?:animebytes)\.[a-z]{2,3}/torrent/[0-9]+/download/"
            r"(?<secret>[^&=]+?)[\"]",
            _FLAGS,
        ),
        (
            r"\"(info_hash|token|((pass|rss)[- _]?key))\":\""
            r"(?<secret>[^&=]+?)\"",
            _FLAGS,
        ),
    )
)


def _mask_secrets(match: regex.Match) -> str:
    """The matched text with every ``secret`` capture replaced."""
    text, offset = match.group(0), match.start()
    spans = list(zip(match.starts("secret"), match.ends("secret"), strict=True))
    for start, end in reversed(spans):
        text = text[: start - offset] + REMOVED + text[end - offset :]
    return text


def cleanse(message: str | None) -> str | None:
    """Return ``message`` with credentials hidden."""
    if not message or not message.strip():
        return message
    for rule in _RULES:
        message = rule.sub(_mask_secrets, message)
    return message
