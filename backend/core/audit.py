"""Writing and reading the append-only audit log.

Why this is Phase 0 and not "later": the public history tab described in §7 of
IMPLEMENTATION_PLAN.md is only credible if the log has been written since the
first edit. History cannot be reconstructed retroactively -- a platform that
starts logging in month six has a visible hole where its early, least-reviewed
edits were.

Nothing here updates or deletes. The only operations are append and read.
"""

from typing import Any, Iterable, Optional
import logging

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import AuditLog
from backend.core.rbac import Principal
from backend.core.security import hash_ip

logger = logging.getLogger(__name__)

# Fields that must never be archived in a diff, even if a caller passes the
# whole document in. Hashes are not plaintext, but there is no reason for them
# to exist in a second place -- especially one designed never to be deleted.
REDACTED_FIELDS = frozenset(
    {"password", "password_hash", "access_code", "access_code_hash", "token", "data"}
)


def diff(before: Optional[dict], after: Optional[dict], *, ignore: Iterable[str] = ()) -> dict:
    """Field-level changes between two versions of an entity.

    Only changed fields are recorded, so a one-word correction stores a one-word
    diff rather than a copy of the whole document -- which matters on a 0.5 GB
    free-tier database that is expected to accumulate history forever.
    """
    skip = REDACTED_FIELDS | set(ignore) | {"_id", "updated_at"}
    before = before or {}
    after = after or {}
    changes: dict[str, dict[str, Any]] = {}
    for key in set(before) | set(after):
        if key in skip:
            continue
        old, new = before.get(key), after.get(key)
        if old != new:
            changes[key] = {"before": old, "after": new}
    return changes


async def record(
    session: AsyncSession,
    *,
    actor: Optional[Principal],
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str = "",
    changes: Optional[dict] = None,
    source_url: Optional[str] = None,
    is_public: bool = True,
    request: Optional[Request] = None,
) -> AuditLog:
    """Append one entry. The caller's session commits it with the rest of the write.

    Deliberately part of the caller's transaction: an audit row that commits
    while the change it describes rolls back would be a lie, and one that is
    lost while the change succeeds is a hole. Same transaction, same fate.
    """
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary,
        changes=changes or None,
        source_url=source_url,
        is_public=is_public,
        ip_hash=hash_ip(request.client.host if request and request.client else None),
    )
    session.add(entry)
    return entry


async def history(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    public_only: bool = True,
    limit: int = 100,
) -> list[AuditLog]:
    """Change history for one entity, newest first -- backs the public history tab."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    if public_only:
        stmt = stmt.where(AuditLog.is_public.is_(True))
    return list((await session.execute(stmt)).scalars())


def to_dict(entry: AuditLog, *, include_actor: bool = True) -> dict:
    """Serialise for the API.

    `include_actor=False` is used by the PUBLIC history endpoint: showing that a
    profile was edited, when, and with what source is the transparency promise;
    naming the volunteer who typed it invites harassment of the volunteer and is
    not part of it.
    """
    payload = {
        "id": entry.id,
        "action": entry.action,
        "entityType": entry.entity_type,
        "entityId": entry.entity_id,
        "summary": entry.summary,
        "changes": entry.changes,
        "sourceUrl": entry.source_url,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
    }
    if include_actor:
        payload["actor"] = {"id": entry.actor_id, "email": entry.actor_email}
    return payload
