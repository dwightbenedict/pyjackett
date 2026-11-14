"""State shared by the HTML/XML and JSON result parsers."""

from __future__ import annotations

from dataclasses import dataclass

from pyjackett.domain.capabilities import TorznabCapabilities
from pyjackett.domain.cardigann.definition import SearchBlock
from pyjackett.domain.cardigann.filters import FilterContext
from pyjackett.domain.cardigann.row_fields import RowParser


@dataclass
class ResultContext:
    """What a parser needs to turn a response into releases."""

    search: SearchBlock
    row_parser: RowParser
    caps: TorznabCapabilities
    indexer_id: str
    filter_context: FilterContext
    max_rows: int | None = None  # stop after this many releases

    def is_full(self, releases: list) -> bool:
        """True once a capped parser has all the releases it may keep."""
        return self.max_rows is not None and len(releases) >= self.max_rows
