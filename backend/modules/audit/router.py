"""Reading the audit log: an internal view and a public one.

The split matters. Internally, `audit.view` shows everything including who did
it -- that is accountability. Publicly, anyone can see that a record changed,
when, and on what source, but not which volunteer typed it -- that is
transparency without exposing contributors to pressure.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit
from backend.core.deps import get_session, require_permission
from backend.core.models import AuditLog
from backend.core.rbac import Principal

router = APIRouter(tags=["audit"])

# Entity types whose history is published. An allow-list rather than a
# deny-list: a module added later is private until someone deliberately decides
# its history should be public, which is the safe direction for that default.
PUBLIC_ENTITY_TYPES = {"state", "representative", "promise", "constitution_article"}


@router.get("/history/{entity_type}/{entity_id}")
async def public_history(
    entity_type: str,
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    if entity_type not in PUBLIC_ENTITY_TYPES:
        # 404 rather than 403: whether an internal entity type exists is itself
        # not public information.
        return []
    entries = await audit.history(session, entity_type=entity_type, entity_id=entity_id)
    return [audit.to_dict(e, include_actor=False) for e in entries]


@router.get("/admin/audit")
async def list_audit(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    admin: Principal = Depends(require_permission("audit.view")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_email:
        stmt = stmt.where(AuditLog.actor_email == actor_email.lower())
    if action:
        stmt = stmt.where(AuditLog.action == action)

    entries = (await session.execute(stmt)).scalars()
    return [audit.to_dict(e) for e in entries]
