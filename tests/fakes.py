"""A fake network for ``HttpSession``: handlers answer instead of servers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import SplitResult, urlsplit

from curl_cffi.requests.headers import Headers


@dataclass
class Request:
    """What the handler sees; ``url`` is split so ``url.path`` works."""

    method: str
    url: SplitResult
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes | None = None


class Response:
    """The parts of a curl_cffi response the web client reads."""

    def __init__(
        self,
        status_code: int,
        text: str | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = (
            content if content is not None else (text or "").encode()
        )
        self.headers = Headers(list((headers or {}).items()))


Handler = Callable[[Request], Response]


class MockSession:
    """Stands in for ``curl_cffi.requests.AsyncSession``."""

    def __init__(self, handler: Handler, **options) -> None:
        self._handler = handler
        self.options = options

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        **options,
    ) -> Response:
        request = Request(method, urlsplit(url), headers or {}, content)
        answer = self._handler(request)
        if inspect.isawaitable(answer):
            answer = await answer
        return answer

    async def close(self) -> None:
        return None


def mock_network(handler: Handler) -> Callable[..., MockSession]:
    """A ``client_factory`` whose sessions are answered by ``handler``."""
    return lambda **options: MockSession(handler, **options)
