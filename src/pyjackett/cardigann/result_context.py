"""State shared by the HTML/XML and JSON result parsers."""

from __future__ import annotations

from dataclasses import dataclass

from pyjackett.cardigann.definition import SearchBlock
from pyjackett.cardigann.filters import FilterContext
from pyjackett.cardigann.row_fields import RowParser
from pyjackett.core.capabilities import TorznabCapabilities


@dataclass
class ResultContext:
    """What a parser needs to turn a response into releases."""

    search: SearchBlock
    row_parser: RowParser
    caps: TorznabCapabilities
    indexer_id: str
    filter_context: FilterContext
