"""First-party pageview tracking and the admin analytics read model.

No third-party script, no cookie, no cross-site identifier: `session_id` is
generated client-side per browsing session and never joined to a person. That
is a deliberate DPDP-Act-friendly default for a civic platform whose visitors
may be researching their own representatives, and it is why this stays
first-party rather than becoming a Google Analytics embed.

Self-hosted Umami (§5) covers the general traffic dashboard; these endpoints
survive alongside it because they answer product questions Umami cannot -- which
campaign a signup came through, which constitution articles get searched.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.deps import require_permission
from backend.core.models import new_id
from backend.core.mongo import db
from backend.core.rbac import Principal
from backend.core.security import now_iso

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])


class PageviewCreate(BaseModel):
    path: str = Field(..., max_length=200)
    referrer_path: Optional[str] = Field(default=None, max_length=200)
    session_id: str = Field(..., max_length=64)


@router.post("/track/pageview")
async def track_pageview(payload: PageviewCreate):
    # Public and fire-and-forget from the frontend: a transient DB hiccup here
    # must never surface as an error to the visitor or break navigation.
    try:
        await db.pageviews.insert_one(
            {
                "id": new_id(),
                "path": payload.path,
                "referrer_path": payload.referrer_path,
                "session_id": payload.session_id,
                "created_at": now_iso(),
            }
        )
    except Exception as e:
        logger.warning("track_pageview failed: %s", e)
    return {"ok": True}


@router.get("/admin/analytics/pageviews")
async def analytics_pageviews(
    days: int = 30, admin: Principal = Depends(require_permission("analytics.view"))
):
    days = max(1, min(days, 365))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    total = await db.pageviews.count_documents({"created_at": {"$gte": since}})
    unique_sessions = len(await db.pageviews.distinct("session_id", {"created_at": {"$gte": since}}))

    top_pages = [
        {"path": row["_id"], "views": row["views"]}
        async for row in db.pageviews.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {"$group": {"_id": "$path", "views": {"$sum": 1}}},
                {"$sort": {"views": -1}},
                {"$limit": 10},
            ]
        )
    ]

    top_flows = [
        {"from": row["_id"]["from"], "to": row["_id"]["to"], "count": row["count"]}
        async for row in db.pageviews.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}, "referrer_path": {"$ne": None}}},
                {"$group": {"_id": {"from": "$referrer_path", "to": "$path"}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 15},
            ]
        )
    ]

    return {
        "days": days,
        "total": total,
        "uniqueSessions": unique_sessions,
        "topPages": top_pages,
        "topFlows": top_flows,
    }
