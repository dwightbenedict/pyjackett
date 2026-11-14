"""Read-only discovery API: indexers, capabilities and categories."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pyjackett.domain.category_catalog import PARENT_CATEGORIES
from pyjackett.interfaces.api_docs import (
    NOT_FOUND,
    UNAUTHORIZED,
    IndexerId,
    api_key_query,
    session_cookie,
)
from pyjackett.interfaces.auth import require_api_access
from pyjackett.interfaces.deps import Context
from pyjackett.interfaces.schemas import Capabilities, Category, IndexerSummary
from pyjackett.interfaces.serialization import (
    capabilities_json,
    category_json,
    indexer_json,
)
from pyjackett.services.indexers.base import BaseIndexer

router = APIRouter(
    tags=["discovery"],
    dependencies=[
        Depends(require_api_access),
        Depends(api_key_query),
        Depends(session_cookie),
    ],
    responses=UNAUTHORIZED,
)


def _matches(
    indexer: BaseIndexer,
    configured: bool | None,
    kind: str | None,
    language: str | None,
    tag: str | None,
    text: str | None,
) -> bool:
    if configured is not None and indexer.is_configured != configured:
        return False
    if kind and indexer.type != kind:
        return False
    if language and not indexer.language.lower().startswith(language.lower()):
        return False
    if tag and tag.lower() not in (t.lower() for t in indexer.tags):
        return False
    if text:
        needle = text.lower()
        return needle in indexer.name.lower() or needle in indexer.id.lower()
    return True


@router.get(
    "/indexers",
    operation_id="listIndexers",
    summary="List the available indexers",
    response_model=list[IndexerSummary],
)
async def list_indexers(
    context: Context,
    configured: bool | None = Query(
        None, description="Only configured (`true`) or unconfigured ones."
    ),
    kind: str | None = Query(
        None,
        alias="type",
        description="`public`, `semi-public` or `private`.",
    ),
    language: str | None = Query(
        None, description="Language prefix, e.g. `en` or `en-US`."
    ),
    tag: str | None = Query(None, description="Only indexers with this tag."),
    q: str | None = Query(
        None, description="Part of the name or id, ignoring case."
    ),
):
    """Every definition PyJackett knows, configured or not, filterable."""
    return [
        indexer_json(
            i,
            context.stats.last_elapsed_ms(i.id),
            context.test_runner.is_running(i.id),
        )
        for i in context.indexers.all_indexers()
        if _matches(i, configured, kind, language, tag, q)
    ]


@router.get(
    "/indexers/{indexer_id}/caps",
    operation_id="getIndexerCapabilities",
    summary="What an indexer can search for",
    response_model=Capabilities,
    responses=NOT_FOUND,
)
async def indexer_capabilities(context: Context, indexer_id: IndexerId):
    """The same information as Torznab `t=caps`, as JSON.

    Meta indexers such as `all` report the union of their members.
    """
    indexer = context.indexers.get_indexer(indexer_id)
    return capabilities_json(indexer.torznab_caps)


@router.get(
    "/categories",
    operation_id="listCategories",
    summary="The standard Torznab categories",
    response_model=list[Category],
)
async def categories():
    """The category ids accepted by the `cat` parameter, as a tree."""
    return [category_json(c) for c in PARENT_CATEGORIES]
