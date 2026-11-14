"""Builds the aggregate and filter indexers over the registry."""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Iterable

from pyjackett.domain.server_config import ServerConfig
from pyjackett.services.indexers.base import BaseIndexer
from pyjackett.services.indexers.dependencies import IndexerDependencies
from pyjackett.services.indexers.meta.filter_expression import (
    Predicate,
    parse_filter,
    tag_filter,
    type_filter,
)
from pyjackett.services.indexers.meta.imdb import ImdbSupport, OmdbResolver
from pyjackett.services.indexers.meta.meta_indexer import (
    AggregateIndexer,
    BaseMetaIndexer,
    FilterIndexer,
)

logger = logging.getLogger(__name__)

AGGREGATE_ID = "all"
PREDEFINED_TYPES = ("public", "private", "semi-public")
MAX_EXPRESSION_FILTERS = 64  # filters built from request URLs


class MetaIndexerFactory:
    """Creates meta indexers; remembers the ones asked for most recently."""

    def __init__(
        self,
        dependencies: IndexerDependencies,
        server_config: ServerConfig,
        indexers: Iterable[BaseIndexer],
    ) -> None:
        self._deps = dependencies
        self._config = server_config
        self._indexers = indexers  # a live view of every known indexer
        self._aggregate: AggregateIndexer | None = None
        self._predefined: dict[str, BaseMetaIndexer] = {}
        self._expressions: OrderedDict[str, BaseMetaIndexer] = OrderedDict()

    # ---- building -----------------------------------------------------------

    def rebuild(self) -> None:
        """(Re)build the "all" indexer and the predefined filter groups."""
        imdb = self._imdb_support()
        logger.info("Adding aggregate indexer ('all' indexer) ...")
        self._aggregate = AggregateIndexer(self._deps, imdb, self._indexers)
        tags = {tag for indexer in self._indexers for tag in indexer.tags}
        predefined = [type_filter(t) for t in PREDEFINED_TYPES]
        predefined += [tag_filter(tag) for tag in sorted(tags)]
        self._predefined = {
            text: self._create_filter(text, predicate, imdb) for text, predicate in predefined
        }
        self._expressions.clear()

    def _imdb_support(self) -> ImdbSupport:
        key = (self._config.omdb_api_key or "").strip()
        if not key:
            return ImdbSupport(None)
        client = self._deps.client_factory()
        return ImdbSupport(OmdbResolver(client, key, self._config.omdb_api_url))

    def _create_filter(self, text: str, predicate: Predicate, imdb: ImdbSupport) -> FilterIndexer:
        logger.info("Adding filter indexer ('%s' indexer) ...", text)
        return FilterIndexer(text, self._deps, imdb, predicate, self._indexers)

    # ---- lookup -------------------------------------------------------------

    def find(self, name: str) -> BaseMetaIndexer | None:
        """The meta indexer called ``name``, or None when there is none.

        Besides "all" and the predefined groups, ``name`` may be a filter
        expression such as ``tag:x,type:private``.
        """
        if name == AGGREGATE_ID:
            return self._aggregate
        if name in self._predefined:
            return self._predefined[name]
        return self._from_expression(name)

    def _from_expression(self, name: str) -> BaseMetaIndexer | None:
        if name in self._expressions:
            self._expressions.move_to_end(name)
            return self._expressions[name]
        try:
            predicate = parse_filter(name)
        except ValueError:
            predicate = None
        if predicate is None:
            return None
        indexer = self._create_filter(name, predicate, self._imdb_support())
        self._expressions[name] = indexer
        if len(self._expressions) > MAX_EXPRESSION_FILTERS:
            self._expressions.popitem(last=False)
        return indexer
