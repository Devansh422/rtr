"""Public content reads and the generic admin CMS CRUD.

Permission is checked inline rather than through the require_permission()
dependency factory because the required key -- `content.<ctype>` -- depends on a
path parameter that is not known at decoration time.

Every admin write appends to the audit log (§7). The log is best-effort here and
mandatory later: CMS content is editorial copy, so a failure to record history
must not block the edit. For representative and promise data, where history IS
the credibility claim, the write and the audit row will share one transaction
and fail together.
"""

from typing import Optional
import logging
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit
from backend.core.deps import get_current_admin, get_optional_session
from backend.core.mongo import content_coll, db
from backend.core.permissions import CONTENT_TYPES, SORTED_BY_DATE
from backend.core.rbac import Principal
from backend.core.security import now_iso, slugify
from backend.modules.cms.service import assert_known_type, list_content, with_live_supporter_counts

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cms"])


def _require_content_permission(admin: Principal, ctype: str) -> None:
    if not admin.can(f"content.{ctype}"):
        raise HTTPException(status_code=403, detail="Your account does not have this permission")


async def _audit(
    session: Optional[AsyncSession],
    *,
    admin: Principal,
    action: str,
    ctype: str,
    item_id: str,
    changes: Optional[dict],
    request: Request,
) -> None:
    if session is None:
        return
    try:
        await audit.record(
            session,
            actor=admin,
            action=action,
            entity_type=f"content.{ctype}",
            entity_id=item_id,
            summary=f"{action} {ctype}/{item_id}",
            changes=changes,
            # Editorial CMS history is internal. The public history tab is for
            # claims about named people and constitutional text, not for
            # "someone fixed a typo in a blog post".
            is_public=False,
            request=request,
        )
    except Exception as e:
        logger.warning("audit write failed for %s/%s: %s", ctype, item_id, e)


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/content/blogs/{blog_id}")
async def get_blog(blog_id: str):
    doc = await content_coll("blogs").find_one({"id": blog_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Blog not found")
    return doc


@router.get("/content/{ctype}")
async def get_content(ctype: str):
    items = await list_content(ctype)
    if ctype == "campaigns":
        items = await with_live_supporter_counts(items)
    return items


@router.get("/stats")
async def get_stats():
    return {
        "supporters": await db.supporters.count_documents({}),
        "volunteers": await db.volunteers.count_documents({}),
        "campaigns": await content_coll("campaigns").count_documents({}),
    }


# --------------------------------------------------------------------------
# Admin CRUD
# --------------------------------------------------------------------------
@router.get("/admin/content/{ctype}")
async def admin_list(ctype: str, admin: Principal = Depends(get_current_admin)):
    _require_content_permission(admin, ctype)
    return await list_content(ctype)


@router.post("/admin/content/{ctype}")
async def admin_create(
    ctype: str,
    request: Request,
    payload: dict = Body(...),
    admin: Principal = Depends(get_current_admin),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    assert_known_type(ctype)
    _require_content_permission(admin, ctype)

    payload.pop("_id", None)
    if not payload.get("id"):
        base = (
            payload.get("title")
            or payload.get("question")
            or payload.get("place")
            or payload.get("name")
            or payload.get("myth")
        )
        payload["id"] = slugify(base)
    if await content_coll(ctype).find_one({"id": payload["id"]}):
        payload["id"] = f'{payload["id"]}-{uuid.uuid4().hex[:4]}'
    if ctype in SORTED_BY_DATE and not payload.get("date"):
        from datetime import datetime, timezone

        payload["date"] = datetime.now(timezone.utc).date().isoformat()
    payload["created_at"] = now_iso()

    await content_coll(ctype).insert_one(payload)
    payload.pop("_id", None)

    await _audit(
        session,
        admin=admin,
        action="create",
        ctype=ctype,
        item_id=payload["id"],
        changes=audit.diff(None, payload),
        request=request,
    )
    return payload


@router.put("/admin/content/{ctype}/{item_id}")
async def admin_update(
    ctype: str,
    item_id: str,
    request: Request,
    payload: dict = Body(...),
    admin: Principal = Depends(get_current_admin),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    assert_known_type(ctype)
    _require_content_permission(admin, ctype)

    payload.pop("_id", None)
    payload.pop("id", None)

    before = await content_coll(ctype).find_one({"id": item_id}, {"_id": 0})
    res = await content_coll(ctype).update_one({"id": item_id}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    after = await content_coll(ctype).find_one({"id": item_id}, {"_id": 0})

    await _audit(
        session,
        admin=admin,
        action="update",
        ctype=ctype,
        item_id=item_id,
        changes=audit.diff(before, after),
        request=request,
    )
    return after


@router.delete("/admin/content/{ctype}/{item_id}")
async def admin_delete(
    ctype: str,
    item_id: str,
    request: Request,
    admin: Principal = Depends(get_current_admin),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    assert_known_type(ctype)
    _require_content_permission(admin, ctype)

    before = await content_coll(ctype).find_one({"id": item_id}, {"_id": 0})
    res = await content_coll(ctype).delete_one({"id": item_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    await _audit(
        session,
        admin=admin,
        action="delete",
        ctype=ctype,
        item_id=item_id,
        # The full prior document, not a diff: after a delete there is nothing
        # left to reconstruct it from, and "what was removed" is the whole
        # question anyone asks of a deletion record.
        changes=audit.diff(before, None),
        request=request,
    )
    return {"ok": True}


@router.get("/admin/content-types")
async def list_content_types(admin: Principal = Depends(get_current_admin)):
    """Content types this account may edit -- drives the admin sidebar."""
    return [t for t in CONTENT_TYPES if admin.can(f"content.{t}")]
