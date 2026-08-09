"""Site-wide search.

This module reads `search_docs` and nothing else. It imports no other module, which
is the whole point of the shared index (see core/search): search spans nine content
types without search knowing that nine modules exist.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import search as search_core
from backend.core.deps import get_session
from backend.core.models import SearchDoc

router = APIRouter(tags=["search"])

# Display names and grouping order for the results page. Ordered by what a visitor
# most likely wanted: a provision of the Constitution, then a person, then the rest.
TYPE_LABELS: dict[str, str] = {
    "constitution_article": "Constitution",
    "representative": "Representatives",
    "promise": "Promises",
    "state": "States",
    "petition": "Petitions",
    "research_document": "Research & media",
    "course": "Academy",
    "report": "Citizen reports",
    "event": "Events",
}


@router.get("/search")
async def site_search(
    q: str = Query(..., min_length=2, max_length=200),
    type: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    results = await search_core.query(
        session,
        q,
        types=[type] if type else None,
        state_code=state.upper() if state else None,
        limit=limit,
    )

    grouped: dict[str, list[dict]] = {}
    for hit in results:
        grouped.setdefault(hit["entityType"], []).append(hit)

    return {
        "query": q,
        "total": len(results),
        "engine": "meilisearch" if search_core.meilisearch_enabled() else "postgres",
        # Flat list for a simple results page...
        "items": results,
        # ...and grouped, for the tabbed layout, in a deliberate order.
        "groups": [
            {"type": key, "label": TYPE_LABELS.get(key, key), "items": grouped[key]}
            for key in TYPE_LABELS
            if key in grouped
        ],
    }


@router.get("/search/suggest")
async def suggest(
    q: str = Query(..., min_length=2, max_length=80),
    session: AsyncSession = Depends(get_session),
):
    """Type-ahead. Prefix match on titles only, so it stays fast and predictable."""
    return await search_core.suggest(session, q)


@router.get("/search/coverage")
async def coverage(session: AsyncSession = Depends(get_session)):
    """How much of the platform is actually searchable, by type.

    Public because it is the honest version of "how complete is this site". A
    visitor searching for their MLA and finding nothing deserves to be able to see
    that 12 representative profiles exist rather than 4,000, instead of concluding
    the search is broken.
    """
    rows = (
        await session.execute(
            select(SearchDoc.entity_type, func.count())
            .where(SearchDoc.is_published.is_(True))
            .group_by(SearchDoc.entity_type)
        )
    ).all()
    return {
        "types": [
            {"type": entity_type, "label": TYPE_LABELS.get(entity_type, entity_type), "count": count}
            for entity_type, count in rows
        ],
        "total": sum(count for _, count in rows),
    }
