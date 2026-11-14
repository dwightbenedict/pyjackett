"""Picks the curl_cffi browser profile closest to a User-Agent string."""

from __future__ import annotations

import re
from collections.abc import Iterable

from curl_cffi.requests import BrowserType

_FAMILIES = {"Chrome": "chrome", "Firefox": "firefox"}
_USER_AGENT_VERSION = re.compile(r"\b(Chrome|Firefox)/(\d+)")


def _available_profiles() -> list[str]:
    return [profile.value for profile in BrowserType]


def impersonation_for(
    user_agent: str, profiles: Iterable[str] | None = None
) -> str | None:
    """The newest profile not newer than the browser in ``user_agent``.

    Returns None when the User-Agent is not Chrome or Firefox, or when no
    profile is old enough, so callers fall back to their default profile.
    """
    found = _USER_AGENT_VERSION.search(user_agent)
    if found is None:
        return None
    prefix = _FAMILIES[found.group(1)]
    major = int(found.group(2))
    pattern = re.compile(rf"^{prefix}(\d+)$")
    versions = {}
    for profile in profiles if profiles is not None else _available_profiles():
        match = pattern.match(profile)
        if match and int(match.group(1)) <= major:
            versions[int(match.group(1))] = profile
    return versions[max(versions)] if versions else None
