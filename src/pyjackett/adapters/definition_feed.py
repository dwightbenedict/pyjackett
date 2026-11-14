"""Where definition updates come from: Jackett's GitHub repository."""

from __future__ import annotations

import json
import re
from typing import Protocol

from pyjackett import __version__
from pyjackett.adapters.http.session import HttpSession
from pyjackett.errors import DefinitionFeedError

UPSTREAM_REPOSITORY = "Jackett/Jackett"
UPSTREAM_BRANCH = "master"
UPSTREAM_PATH = "src/Jackett.Common/Definitions"
DEFINITION_NAME = re.compile(r"[A-Za-z0-9_.-]+\.yml")


class DefinitionFeed(Protocol):
    """A published set of definitions."""

    async def list_files(self) -> dict[str, str]:
        """The current revision of every definition, by file name."""

    async def fetch(self, name: str) -> str:
        """The text of one definition."""


class GitHubDefinitionFeed:
    """Lists a folder with one tree request and downloads raw files.

    A revision is the git blob hash, so unchanged files are never fetched.
    """

    def __init__(
        self,
        session: HttpSession,
        repository: str = UPSTREAM_REPOSITORY,
        branch: str = UPSTREAM_BRANCH,
        path: str = UPSTREAM_PATH,
    ) -> None:
        self._session = session
        self._repository = repository
        self._branch = branch
        self._path = path

    async def list_files(self) -> dict[str, str]:
        url = (
            f"https://api.github.com/repos/{self._repository}/git/trees/{self._branch}:{self._path}"
        )
        body = await self._get(url, "application/vnd.github+json")
        try:
            entries = json.loads(body)["tree"]
            return {
                entry["path"]: entry["sha"]
                for entry in entries
                if entry["type"] == "blob" and DEFINITION_NAME.fullmatch(entry["path"])
            }
        except (ValueError, KeyError, TypeError) as error:
            raise DefinitionFeedError("The definition listing is malformed") from error

    async def fetch(self, name: str) -> str:
        url = (
            f"https://raw.githubusercontent.com/{self._repository}"
            f"/{self._branch}/{self._path}/{name}"
        )
        body = await self._get(url, "text/plain")
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DefinitionFeedError(f"{name} is not UTF-8") from error

    async def _get(self, url: str, accept: str) -> bytes:
        headers = {"Accept": accept, "User-Agent": f"PyJackett/{__version__}"}
        try:
            response = await self._session.send({"method": "GET", "url": url, "headers": headers})
        except Exception as error:
            raise DefinitionFeedError(f"Cannot reach {url}: {error}") from error
        if response.status_code != 200:
            raise DefinitionFeedError(f"{url} answered HTTP {response.status_code}")
        return response.content
