"""Lets concurrent callers share one run of the same work."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class _Flight:
    task: asyncio.Future
    waiters: int = 0


class SingleFlight:
    """Runs the work for a key once while several callers wait for it.

    Many clients asking for the same thing at once cost one run. The work
    is cancelled only when every caller has given up, so one impatient
    client cannot take the answer away from the others.
    """

    def __init__(self) -> None:
        self._flights: dict[str, _Flight] = {}

    async def run(
        self,
        key: str,
        work: Callable[[], Awaitable[T]],
        share: Callable[[T], T] | None = None,
    ) -> T:
        """The result of ``work`` for ``key``, started by the first caller.

        Callers that joined a run already under way get ``share(result)``
        (say, a copy), so none of them can alter what the others hold.
        """
        flight = self._flights.get(key)
        leader = flight is None
        if flight is None:
            flight = self._start(key, work)
        flight.waiters += 1
        try:
            result = await asyncio.shield(flight.task)
        finally:
            flight.waiters -= 1
            if not flight.waiters and not flight.task.done():
                flight.task.cancel()  # nobody is waiting any more
        return result if leader or share is None else share(result)

    def _start(self, key: str, work: Callable[[], Awaitable[T]]) -> _Flight:
        flight = _Flight(asyncio.ensure_future(work()))
        self._flights[key] = flight
        flight.task.add_done_callback(
            lambda task: self._finish(key, flight, task)
        )
        return flight

    def _finish(self, key: str, flight: _Flight, task: asyncio.Future) -> None:
        if self._flights.get(key) is flight:
            del self._flights[key]
        if not task.cancelled():
            task.exception()  # a failure nobody awaits is not an error here
