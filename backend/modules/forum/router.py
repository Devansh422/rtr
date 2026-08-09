"""Forum reads, writes, upvotes and the moderator queue."""

from datetime import datetime, timezone
from typing import Optional
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, limits, moderation
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
)
from backend.core.models import Citizen, as_aware, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.forum.models import (
    REPUTATION_GATES,
    ForumCategory,
    ForumReply,
    ForumThread,
    ForumVote,
    PostStatus,
)

router = APIRouter(tags=["forum"])

REPUTATION_PER_UPVOTE_RECEIVED = 1
_URL_RE = re.compile(r"https?://\S+")


class ThreadIn(BaseModel):
    category_key: str
    title: str = Field(..., min_length=12, max_length=300)
    body: str = Field(..., min_length=30)
    state_code: Optional[str] = None
    subject_ref: str = ""


class ReplyIn(BaseModel):
    body: str = Field(..., min_length=2)
    parent_id: Optional[str] = None


class ModerateIn(BaseModel):
    action: str  # publish | remove | lock | unlock | pin | unpin
    note: str = ""


class MuteIn(BaseModel):
    days: int = Field(..., ge=1, le=365)
    reason: str = Field(..., min_length=10)


def _gate(citizen: Citizen, action: str) -> None:
    required = REPUTATION_GATES.get(action, 0)
    if citizen.reputation < required:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This needs {required} contribution points. You have {citizen.reputation}. "
                "Points come from replies others found useful, corrections we accepted, and "
                "reports we published -- not from posting volume."
            ),
        )


def _thread_dict(thread: ForumThread, author: Optional[Citizen], *, include_body: bool = False) -> dict:
    payload = {
        "id": thread.id,
        "slug": thread.slug,
        "title": thread.title,
        "category": thread.category_key,
        "state": thread.state_code,
        "subjectRef": thread.subject_ref or None,
        "status": thread.status,
        "isPinned": thread.is_pinned,
        "isLocked": thread.is_locked,
        "replyCount": thread.reply_count,
        "upvotes": thread.upvotes,
        "author": author.public_dict() if author else None,
        "createdAt": thread.created_at.isoformat() if thread.created_at else None,
        "lastActivityAt": thread.last_activity_at.isoformat() if thread.last_activity_at else None,
        "url": f"/forum/{thread.slug}",
    }
    if include_body:
        payload["body"] = thread.body
        payload["moderationNote"] = thread.moderation_note or None
    return payload


def _reply_dict(reply: ForumReply, author: Optional[Citizen]) -> dict:
    return {
        "id": reply.id,
        "parentId": reply.parent_id,
        "body": (
            reply.body
            if reply.status == PostStatus.PUBLISHED
            else "[This reply was removed by a moderator.]"
        ),
        "status": reply.status,
        "upvotes": reply.upvotes,
        "author": author.public_dict() if author else None,
        "createdAt": reply.created_at.isoformat() if reply.created_at else None,
        "moderationNote": reply.moderation_note or None,
    }


async def _authors(session: AsyncSession, citizen_ids: list[str]) -> dict[str, Citizen]:
    ids = [c for c in set(citizen_ids) if c]
    if not ids:
        return {}
    rows = (await session.execute(select(Citizen).where(Citizen.id.in_(ids)))).scalars()
    return {c.id: c for c in rows}


async def _screen(text: str, *, citizen: Citizen, subject_ref: str) -> tuple[str, list[dict]]:
    """Run the content gate and the link/reputation gate together.

    Returns the status the post should land in, plus the flags. Held posts stay
    visible to their author -- see the note on PostStatus.HELD.
    """
    if _URL_RE.search(text):
        _gate(citizen, "post_links")
    if subject_ref.startswith("representative/"):
        _gate(citizen, "thread_on_representative")

    verdict = moderation.review(
        text,
        names_a_person=bool(subject_ref) or "representative" in subject_ref,
        has_citation=bool(_URL_RE.search(text)),
    )
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "This post cannot be accepted as written.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )
    status = PostStatus.HELD if verdict.decision is moderation.Decision.HOLD else PostStatus.PUBLISHED
    return status, [f.as_dict() for f in verdict.flags]


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/forum/categories")
async def list_categories(session: AsyncSession = Depends(get_session)):
    rows = list(
        (await session.execute(select(ForumCategory).order_by(ForumCategory.sort_order))).scalars()
    )
    counts = dict(
        (
            await session.execute(
                select(ForumThread.category_key, func.count())
                .where(ForumThread.status == PostStatus.PUBLISHED)
                .group_by(ForumThread.category_key)
            )
        ).all()
    )
    return [
        {
            "key": c.key,
            "name": c.name,
            "nameHi": c.name_hi,
            "description": c.description,
            "isLocked": c.is_locked,
            "minReputation": c.min_reputation,
            "threadCount": counts.get(c.key, 0),
        }
        for c in rows
    ]


@router.get("/forum/threads")
async def list_threads(
    category: Optional[str] = None,
    state: Optional[str] = None,
    subject_ref: Optional[str] = None,
    sort: str = Query(default="active", pattern="^(active|new|top)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ForumThread).where(ForumThread.status == PostStatus.PUBLISHED)
    if category:
        stmt = stmt.where(ForumThread.category_key == category)
    if state:
        stmt = stmt.where(ForumThread.state_code == state.upper())
    if subject_ref:
        stmt = stmt.where(ForumThread.subject_ref == subject_ref)

    rows = list((await session.execute(stmt)).scalars())
    now = datetime.now(timezone.utc)
    if sort == "new":
        rows.sort(key=lambda t: as_aware(t.created_at), reverse=True)
    elif sort == "top":
        # Upvotes decayed by age, so "top" means "useful lately" rather than
        # "posted first". Without the decay the tab is a permanent hall of fame.
        rows.sort(
            key=lambda t: -(t.upvotes / max(1.0, ((now - as_aware(t.created_at)).days + 2) ** 0.8))
        )
    else:
        rows.sort(key=lambda t: as_aware(t.last_activity_at), reverse=True)
    rows.sort(key=lambda t: not t.is_pinned)

    window = rows[offset : offset + limit]
    authors = await _authors(session, [t.citizen_id for t in window])
    return {
        "total": len(rows),
        "items": [_thread_dict(t, authors.get(t.citizen_id)) for t in window],
    }


@router.get("/forum/threads/{slug}")
async def get_thread(slug: str, session: AsyncSession = Depends(get_session)):
    thread = (
        await session.execute(select(ForumThread).where(ForumThread.slug == slug))
    ).scalar_one_or_none()
    if thread is None or thread.status != PostStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Discussion not found")

    replies = list(
        (
            await session.execute(
                select(ForumReply)
                .where(ForumReply.thread_id == thread.id, ForumReply.status != PostStatus.HELD)
                .order_by(ForumReply.created_at)
            )
        ).scalars()
    )
    authors = await _authors(session, [thread.citizen_id, *[r.citizen_id for r in replies]])
    return {
        **_thread_dict(thread, authors.get(thread.citizen_id), include_body=True),
        "replies": [_reply_dict(r, authors.get(r.citizen_id)) for r in replies],
        "policyUrl": "/api/legal/content-policy",
    }


@router.post("/forum/threads")
async def create_thread(
    payload: ThreadIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    category = (
        await session.execute(select(ForumCategory).where(ForumCategory.key == payload.category_key))
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=404, detail="Unknown category")
    if category.is_locked:
        raise HTTPException(status_code=403, detail="This category is read-only")
    if citizen.reputation < category.min_reputation:
        raise HTTPException(
            status_code=403,
            detail=f"This category needs {category.min_reputation} contribution points to post in.",
        )

    _gate(citizen, "thread")
    await limits.check("forum.thread", f"m:{citizen.email}")
    status, flags = await _screen(
        f"{payload.title}\n{payload.body}", citizen=citizen, subject_ref=payload.subject_ref
    )

    slug = slugify(payload.title)
    if (await session.execute(select(ForumThread).where(ForumThread.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M%S')}"

    thread = ForumThread(
        slug=slug,
        category_key=payload.category_key,
        citizen_id=citizen.id,
        title=payload.title.strip(),
        body=moderation.scrub_identifiers(payload.body.strip()),
        state_code=payload.state_code.upper() if payload.state_code else citizen.state_code,
        subject_ref=payload.subject_ref[:140],
        status=status,
        policy_flags=json.dumps(flags) if flags else "",
    )
    session.add(thread)
    await session.flush()

    if status == PostStatus.HELD:
        await audit.record(
            session,
            actor=None,
            action="held",
            entity_type="forum_thread",
            entity_id=thread.slug,
            summary="Thread held by the content policy gate",
            is_public=False,
            request=request,
        )

    return {
        **_thread_dict(thread, citizen, include_body=True),
        "held": status == PostStatus.HELD,
        "message": (
            "Your post is waiting for a moderator because of the points below. It is not deleted "
            "-- you can see it in your dashboard, and a moderator will publish it or explain why not."
            if status == PostStatus.HELD
            else None
        ),
        "flags": flags,
    }


@router.post("/forum/threads/{slug}/replies")
async def create_reply(
    slug: str,
    payload: ReplyIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    thread = (
        await session.execute(select(ForumThread).where(ForumThread.slug == slug))
    ).scalar_one_or_none()
    if thread is None or thread.status != PostStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if thread.is_locked:
        raise HTTPException(status_code=403, detail="This discussion is closed to new replies")

    _gate(citizen, "reply")
    await limits.check("forum.reply", f"m:{citizen.email}")
    status, flags = await _screen(payload.body, citizen=citizen, subject_ref=thread.subject_ref)

    parent_id = None
    if payload.parent_id:
        parent = (
            await session.execute(
                select(ForumReply).where(
                    ForumReply.id == payload.parent_id, ForumReply.thread_id == thread.id
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="The reply you are responding to no longer exists")
        # Flatten deeper nesting onto the top-level parent rather than rejecting
        # it: the member's intent was to reply, and one level is a display
        # decision, not their problem.
        parent_id = parent.parent_id or parent.id

    reply = ForumReply(
        thread_id=thread.id,
        citizen_id=citizen.id,
        parent_id=parent_id,
        body=moderation.scrub_identifiers(payload.body.strip()),
        status=status,
        policy_flags=json.dumps(flags) if flags else "",
    )
    session.add(reply)
    await session.flush()

    if status == PostStatus.PUBLISHED:
        thread.reply_count = (
            await session.execute(
                select(func.count())
                .select_from(ForumReply)
                .where(ForumReply.thread_id == thread.id, ForumReply.status == PostStatus.PUBLISHED)
            )
        ).scalar_one()
        thread.last_activity_at = utcnow()

    return {
        **_reply_dict(reply, citizen),
        "held": status == PostStatus.HELD,
        "flags": flags,
    }


@router.post("/forum/{target_type}/{target_id}/upvote")
async def upvote(
    target_type: str,
    target_id: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Mark a post useful. Idempotent-by-constraint; calling again removes it."""
    if target_type not in ("thread", "reply"):
        raise HTTPException(status_code=400, detail="target_type must be 'thread' or 'reply'")

    model = ForumThread if target_type == "thread" else ForumReply
    target = (await session.execute(select(model).where(model.id == target_id))).scalar_one_or_none()
    if target is None or target.status != PostStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Post not found")
    if target.citizen_id == citizen.id:
        raise HTTPException(status_code=400, detail="You cannot upvote your own post")

    _gate(citizen, "upvote")
    await limits.check("forum.vote", f"m:{citizen.email}")

    existing = (
        await session.execute(
            select(ForumVote).where(
                ForumVote.target_type == target_type,
                ForumVote.target_id == target_id,
                ForumVote.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()

    author = (
        await session.execute(select(Citizen).where(Citizen.id == target.citizen_id))
    ).scalar_one_or_none()

    if existing is not None:
        await session.delete(existing)
        if author is not None:
            author.reputation = max(0, author.reputation - REPUTATION_PER_UPVOTE_RECEIVED)
        voted = False
    else:
        session.add(
            ForumVote(target_type=target_type, target_id=target_id, citizen_id=citizen.id)
        )
        if author is not None:
            author.reputation += REPUTATION_PER_UPVOTE_RECEIVED
        voted = True

    await session.flush()
    target.upvotes = (
        await session.execute(
            select(func.count())
            .select_from(ForumVote)
            .where(ForumVote.target_type == target_type, ForumVote.target_id == target_id)
        )
    ).scalar_one()
    return {"ok": True, "upvoted": voted, "upvotes": target.upvotes}


@router.get("/me/forum")
async def my_forum_activity(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Own threads and replies, including held ones.

    Held posts appear here with the reason, which is the whole point: a member
    whose post disappeared with no explanation concludes they were censored.
    """
    threads = list(
        (
            await session.execute(
                select(ForumThread)
                .where(ForumThread.citizen_id == citizen.id)
                .order_by(ForumThread.created_at.desc())
            )
        ).scalars()
    )
    replies = list(
        (
            await session.execute(
                select(ForumReply)
                .where(ForumReply.citizen_id == citizen.id)
                .order_by(ForumReply.created_at.desc())
                .limit(100)
            )
        ).scalars()
    )
    return {
        "profile": {
            **citizen.public_dict(),
            "contributions": citizen.contributions,
            "isMuted": citizen.is_muted(),
            "mutedUntil": citizen.muted_until.isoformat() if citizen.muted_until else None,
            "mutedReason": citizen.muted_reason or None,
        },
        "threads": [
            {
                **_thread_dict(t, citizen, include_body=True),
                "policyFlags": json.loads(t.policy_flags) if t.policy_flags else [],
            }
            for t in threads
        ],
        "replies": [
            {
                **_reply_dict(r, citizen),
                # The author always sees their own held text; the placeholder in
                # _reply_dict is for other readers.
                "body": r.body,
                "policyFlags": json.loads(r.policy_flags) if r.policy_flags else [],
            }
            for r in replies
        ],
    }


@router.put("/me/profile")
async def update_my_profile(
    display_name: str = Query(..., min_length=2, max_length=60),
    state_code: Optional[str] = None,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Set the pseudonym and state shown on posts."""
    verdict = moderation.review(display_name)
    if verdict.decision is not moderation.Decision.ALLOW:
        raise HTTPException(status_code=400, detail="Please choose a different display name.")
    citizen.display_name = display_name.strip()
    if state_code:
        citizen.state_code = state_code.upper()
    return citizen.public_dict()


# --------------------------------------------------------------------------
# Moderation
# --------------------------------------------------------------------------
@router.get("/admin/forum/queue")
async def moderation_queue(
    admin: Principal = Depends(require_permission("forum.moderate")),
    session: AsyncSession = Depends(get_session),
):
    threads = list(
        (
            await session.execute(
                select(ForumThread)
                .where(ForumThread.status == PostStatus.HELD)
                .order_by(ForumThread.created_at)
                .limit(100)
            )
        ).scalars()
    )
    replies = list(
        (
            await session.execute(
                select(ForumReply)
                .where(ForumReply.status == PostStatus.HELD)
                .order_by(ForumReply.created_at)
                .limit(200)
            )
        ).scalars()
    )
    authors = await _authors(session, [t.citizen_id for t in threads] + [r.citizen_id for r in replies])
    return {
        "policy": moderation.CONTENT_POLICY,
        "threads": [
            {
                **_thread_dict(t, authors.get(t.citizen_id), include_body=True),
                "policyFlags": json.loads(t.policy_flags) if t.policy_flags else [],
            }
            for t in threads
        ],
        "replies": [
            {
                **_reply_dict(r, authors.get(r.citizen_id)),
                "body": r.body,
                "threadId": r.thread_id,
                "policyFlags": json.loads(r.policy_flags) if r.policy_flags else [],
            }
            for r in replies
        ],
    }


async def _moderate(
    session: AsyncSession,
    request: Request,
    admin: Principal,
    target,
    entity_type: str,
    entity_id: str,
    payload: ModerateIn,
) -> dict:
    action = payload.action
    if action == "publish":
        target.status = PostStatus.PUBLISHED
    elif action == "remove":
        if len(payload.note.strip()) < 5:
            raise HTTPException(status_code=400, detail="Give a reason -- the author is shown it.")
        target.status = PostStatus.REMOVED
    elif action in ("lock", "unlock") and hasattr(target, "is_locked"):
        target.is_locked = action == "lock"
    elif action in ("pin", "unpin") and hasattr(target, "is_pinned"):
        target.is_pinned = action == "pin"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action '{action}' for this target")

    target.moderation_note = payload.note.strip() or target.moderation_note
    target.moderated_by = admin.id

    await audit.record(
        session,
        actor=admin,
        action=f"moderate_{action}",
        entity_type=entity_type,
        entity_id=entity_id,
        summary=f"{action} on {entity_type} ({payload.note.strip()[:80]})",
        # Moderation actions stay internal. Publishing "a moderator removed X's
        # post" is a second punishment and invites pile-ons on the moderator.
        is_public=False,
        request=request,
    )
    return {"ok": True, "status": target.status, "action": action}


@router.post("/admin/forum/threads/{thread_id}/moderate")
async def moderate_thread(
    thread_id: str,
    payload: ModerateIn,
    request: Request,
    admin: Principal = Depends(require_permission("forum.moderate")),
    session: AsyncSession = Depends(get_session),
):
    thread = (
        await session.execute(select(ForumThread).where(ForumThread.id == thread_id))
    ).scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await _moderate(session, request, admin, thread, "forum_thread", thread.slug, payload)


@router.post("/admin/forum/replies/{reply_id}/moderate")
async def moderate_reply(
    reply_id: str,
    payload: ModerateIn,
    request: Request,
    admin: Principal = Depends(require_permission("forum.moderate")),
    session: AsyncSession = Depends(get_session),
):
    reply = (
        await session.execute(select(ForumReply).where(ForumReply.id == reply_id))
    ).scalar_one_or_none()
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found")
    result = await _moderate(session, request, admin, reply, "forum_reply", reply.id, payload)

    thread = (
        await session.execute(select(ForumThread).where(ForumThread.id == reply.thread_id))
    ).scalar_one_or_none()
    if thread is not None:
        thread.reply_count = (
            await session.execute(
                select(func.count())
                .select_from(ForumReply)
                .where(ForumReply.thread_id == thread.id, ForumReply.status == PostStatus.PUBLISHED)
            )
        ).scalar_one()
    return result


@router.post("/admin/citizens/{citizen_id}/mute")
async def mute_citizen(
    citizen_id: str,
    payload: MuteIn,
    request: Request,
    admin: Principal = Depends(require_permission("forum.moderate")),
    session: AsyncSession = Depends(get_session),
):
    """Time-box a member out of posting. Never a permanent ban from reading.

    Always dated and always reasoned: the member is told both, and the mute
    expires on its own, so nobody has to remember to lift it.
    """
    from datetime import timedelta

    citizen = (
        await session.execute(select(Citizen).where(Citizen.id == citizen_id))
    ).scalar_one_or_none()
    if citizen is None:
        raise HTTPException(status_code=404, detail="Member not found")

    citizen.muted_until = utcnow() + timedelta(days=payload.days)
    citizen.muted_reason = payload.reason.strip()

    await audit.record(
        session,
        actor=admin,
        action="mute",
        entity_type="citizen",
        entity_id=citizen_id,
        summary=f"Muted for {payload.days} day(s): {payload.reason.strip()[:100]}",
        is_public=False,
        request=request,
    )
    return {
        "ok": True,
        "mutedUntil": citizen.muted_until.isoformat(),
        "reason": citizen.muted_reason,
    }


@router.delete("/admin/citizens/{citizen_id}/mute")
async def unmute_citizen(
    citizen_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("forum.moderate")),
    session: AsyncSession = Depends(get_session),
):
    citizen = (
        await session.execute(select(Citizen).where(Citizen.id == citizen_id))
    ).scalar_one_or_none()
    if citizen is None:
        raise HTTPException(status_code=404, detail="Member not found")
    citizen.muted_until = None
    citizen.muted_reason = ""
    await audit.record(
        session,
        actor=admin,
        action="unmute",
        entity_type="citizen",
        entity_id=citizen_id,
        summary="Mute lifted",
        is_public=False,
        request=request,
    )
    return {"ok": True}
