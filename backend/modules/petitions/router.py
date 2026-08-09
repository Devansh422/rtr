"""Creating, signing and administering petitions."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, erasure, limits, moderation, notify, search
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
    require_state_scope,
)
from backend.core.models import Citizen, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.petitions.models import (
    MILESTONES,
    PUBLIC_STATUSES,
    STATUS_LABELS,
    Petition,
    PetitionSignature,
    PetitionStatus,
    milestones_reached,
    next_milestone,
)

router = APIRouter(tags=["petitions"])

# Reputation for starting a petition that clears moderation. Small on purpose:
# the reward for a petition should be signatures, not points.
REPUTATION_FOR_PETITION = 5
DEFAULT_OPEN_DAYS = 90


class PetitionIn(BaseModel):
    title: str = Field(..., min_length=15, max_length=300)
    summary: str = Field(..., min_length=30, max_length=600)
    body: str = Field(..., min_length=100)
    addressed_to: str = Field(..., min_length=4, max_length=300)
    state_code: Optional[str] = None
    category: str = "right-to-recall"
    target_signatures: int = Field(default=1000, ge=50, le=1_000_000)
    title_hi: str = ""
    body_hi: str = ""


class SignatureIn(BaseModel):
    comment: str = Field(default="", max_length=1000)
    # Explicit opt-in. See the note on the model for why the default is private.
    show_my_name: bool = False


class PetitionStatusIn(BaseModel):
    status: str
    note: str = ""
    outcome_source_url: str = ""


def _serialise(petition: Petition, *, include_body: bool = False) -> dict:
    reached = milestones_reached(petition.signature_count)
    payload = {
        "id": petition.id,
        "slug": petition.slug,
        "title": petition.title,
        "titleHi": petition.title_hi,
        "summary": petition.summary,
        "addressedTo": petition.addressed_to,
        "state": petition.state_code,
        "category": petition.category,
        "status": petition.status,
        "statusLabel": STATUS_LABELS.get(petition.status, petition.status),
        "isOfficial": petition.is_official,
        "signatureCount": petition.signature_count,
        "targetSignatures": petition.target_signatures,
        "progressPercent": (
            min(100, round(petition.signature_count / petition.target_signatures * 100))
            if petition.target_signatures
            else 0
        ),
        "milestonesReached": reached,
        "nextMilestone": next_milestone(petition.signature_count),
        "closesAt": petition.closes_at.isoformat() if petition.closes_at else None,
        "createdAt": petition.created_at.isoformat() if petition.created_at else None,
        "url": f"/petitions/{petition.slug}",
    }
    if include_body:
        payload.update(
            {
                "body": petition.body,
                "bodyHi": petition.body_hi,
                "statusNote": petition.status_note,
                "outcomeSourceUrl": petition.outcome_source_url or None,
                "milestones": petition.milestones,
                "share": notify.share_links(
                    url=f"/petitions/{petition.slug}",
                    text=f"{petition.title} - sign this petition",
                ),
            }
        )
    return payload


async def _recount(session: AsyncSession, petition: Petition) -> None:
    """Recompute the denormalised count from the signature table.

    Recomputed rather than incremented: an increment that races or that runs after
    a rolled-back insert leaves a petition permanently overstating its support,
    which is the one number on the page that has to be right.
    """
    petition.signature_count = (
        await session.execute(
            select(func.count())
            .select_from(PetitionSignature)
            .where(PetitionSignature.petition_id == petition.id)
        )
    ).scalar_one()

    already = {m.get("count") for m in (petition.milestones or [])}
    new_marks = [
        {"count": m, "reachedAt": utcnow().isoformat()}
        for m in milestones_reached(petition.signature_count)
        if m not in already
    ]
    if new_marks:
        petition.milestones = [*(petition.milestones or []), *new_marks]


async def _index(session: AsyncSession, petition: Petition) -> None:
    await search.index(
        session,
        entity_type="petition",
        entity_id=petition.slug,
        title=petition.title,
        subtitle=f"Petition to {petition.addressed_to}",
        body=petition.summary,
        keywords=[petition.category, petition.state_code or ""],
        state_code=petition.state_code,
        is_published=petition.status in PUBLIC_STATUSES,
        url_path=f"/petitions/{petition.slug}",
    )


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/petitions")
async def list_petitions(
    state: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    sort: str = Query(default="trending", pattern="^(trending|newest|signatures)$"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Petition).where(Petition.status.in_(list(PUBLIC_STATUSES)))
    if state:
        stmt = stmt.where(Petition.state_code == state.upper())
    if status:
        stmt = stmt.where(Petition.status == status)
    if category:
        stmt = stmt.where(Petition.category == category)

    rows = list((await session.execute(stmt)).scalars())

    if sort == "signatures":
        rows.sort(key=lambda p: -p.signature_count)
    elif sort == "newest":
        rows.sort(key=lambda p: p.created_at, reverse=True)
    else:
        # "Trending" = signatures per day since opening, so a week-old petition
        # with 400 signatures ranks above a year-old one with 900. Ranking purely
        # by total makes the front page a permanent archive of the first petitions
        # ever created.
        now = datetime.now(timezone.utc)
        rows.sort(
            key=lambda p: -(
                p.signature_count / max(1, (now - p.created_at).days + 1)
            )
        )

    return {
        "total": len(rows),
        "items": [_serialise(p) for p in rows[offset : offset + limit]],
    }


@router.get("/petitions/{slug}")
async def get_petition(slug: str, session: AsyncSession = Depends(get_session)):
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None or petition.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Petition not found")
    return _serialise(petition, include_body=True)


@router.get("/petitions/{slug}/signatures")
async def list_signatures(
    slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Signatures whose signer opted in to being listed, newest first.

    The count on the petition page includes everyone; this list includes only
    those who chose to be named. The gap between the two numbers is expected and
    the response says so, so it does not read as a discrepancy.
    """
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None or petition.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Petition not found")

    rows = (
        await session.execute(
            select(PetitionSignature)
            .where(
                PetitionSignature.petition_id == petition.id,
                PetitionSignature.is_public.is_(True),
            )
            .order_by(PetitionSignature.created_at.desc())
            .limit(limit)
        )
    ).scalars()

    return {
        "totalSignatures": petition.signature_count,
        "note": (
            "Every signature is counted. Only signers who chose to be listed appear below."
        ),
        "items": [
            {
                "displayName": s.display_name or "A supporter",
                "state": s.state_code,
                "comment": None if s.comment_hidden else (s.comment or None),
                "signedOn": s.created_at.date().isoformat() if s.created_at else None,
            }
            for s in rows
        ],
    }


@router.post("/petitions")
async def create_petition(
    payload: PetitionIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Start a petition. Goes to moderation before it opens for signatures.

    Never auto-publishes. A petition carries this platform's name to the office
    it addresses, and §7 requires the non-partisan content policy to be applied by
    a person before that happens.
    """
    await limits.check("petition.create", f"m:{citizen.email}")

    verdict = moderation.review(
        f"{payload.title}\n{payload.summary}\n{payload.body}",
        names_a_person=True,
        has_citation=False,
    )
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "This petition cannot be accepted as written.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )

    slug = slugify(payload.title)
    if (await session.execute(select(Petition).where(Petition.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M')}"

    petition = Petition(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        body=moderation.scrub_identifiers(payload.body.strip()),
        body_hi=payload.body_hi.strip(),
        addressed_to=payload.addressed_to.strip(),
        state_code=payload.state_code.upper() if payload.state_code else citizen.state_code,
        category=payload.category,
        target_signatures=payload.target_signatures,
        citizen_id=citizen.id,
        is_official=False,
        status=PetitionStatus.UNDER_REVIEW,
        policy_flags=str([f.as_dict() for f in verdict.flags]) if verdict.flags else "",
        closes_at=utcnow() + timedelta(days=DEFAULT_OPEN_DAYS),
    )
    session.add(petition)
    await session.flush()

    citizen.reputation += REPUTATION_FOR_PETITION
    contributions = dict(citizen.contributions or {})
    contributions["petitionsStarted"] = contributions.get("petitionsStarted", 0) + 1
    citizen.contributions = contributions

    await audit.record(
        session,
        actor=None,
        action="create",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"Petition submitted for review: {petition.title}",
        is_public=False,
        request=request,
    )
    return {
        **_serialise(petition, include_body=True),
        "message": (
            "Your petition has been submitted. A moderator checks every petition against the "
            "content policy before it opens for signatures - usually within two working days."
        ),
        "flags": [f.as_dict() for f in verdict.flags],
    }


@router.post("/petitions/{slug}/sign")
async def sign_petition(
    slug: str,
    payload: SignatureIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None or petition.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Petition not found")
    if petition.status != PetitionStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail=f"This petition is {STATUS_LABELS[petition.status].lower()} and is no longer collecting signatures.",
        )
    if petition.closes_at and petition.closes_at < utcnow():
        raise HTTPException(status_code=400, detail="This petition has closed.")

    existing = (
        await session.execute(
            select(PetitionSignature).where(
                PetitionSignature.petition_id == petition.id,
                PetitionSignature.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already signed this petition.")

    await limits.check("petition.sign", f"m:{citizen.email}")

    comment_hidden = False
    if payload.comment.strip():
        verdict = moderation.review(payload.comment, names_a_person=True, has_citation=False)
        if verdict.decision is moderation.Decision.REJECT:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Your comment cannot be posted as written. Your signature was not recorded -- fix the comment and sign again.",
                    "flags": [f.as_dict() for f in verdict.flags],
                },
            )
        # A held comment must not block the signature. The signature is the civic
        # act; the comment is commentary, so it waits for a moderator while the
        # signature counts immediately.
        comment_hidden = verdict.decision is moderation.Decision.HOLD

    session.add(
        PetitionSignature(
            petition_id=petition.id,
            citizen_id=citizen.id,
            display_name=citizen.display_name,
            state_code=citizen.state_code,
            comment=moderation.scrub_identifiers(payload.comment.strip()),
            is_public=payload.show_my_name,
            comment_hidden=comment_hidden,
        )
    )
    await session.flush()
    await _recount(session, petition)

    contributions = dict(citizen.contributions or {})
    contributions["petitionsSigned"] = contributions.get("petitionsSigned", 0) + 1
    citizen.contributions = contributions

    return {
        "ok": True,
        "signatureCount": petition.signature_count,
        "nextMilestone": next_milestone(petition.signature_count),
        "commentPending": comment_hidden,
        "share": notify.share_links(
            url=f"/petitions/{petition.slug}",
            text=f"I just signed: {petition.title}",
        ),
    }


@router.delete("/petitions/{slug}/sign")
async def withdraw_signature(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Withdraw a signature. Hard delete -- see the module docstring."""
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")

    result = await session.execute(
        delete(PetitionSignature).where(
            PetitionSignature.petition_id == petition.id,
            PetitionSignature.citizen_id == citizen.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="You have not signed this petition.")

    await _recount(session, petition)
    # Withdrawing should not cost someone a slot in their hourly limit -- see
    # core/limits.reset.
    await limits.reset("petition.sign", f"m:{citizen.email}")
    return {"ok": True, "signatureCount": petition.signature_count}


@router.get("/me/petitions")
async def my_petitions(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Petitions this member started or signed -- their own record of participation."""
    started = list(
        (await session.execute(select(Petition).where(Petition.citizen_id == citizen.id))).scalars()
    )
    signed_rows = (
        await session.execute(
            select(Petition, PetitionSignature)
            .join(PetitionSignature, PetitionSignature.petition_id == Petition.id)
            .where(PetitionSignature.citizen_id == citizen.id)
            .order_by(PetitionSignature.created_at.desc())
        )
    ).all()
    return {
        "started": [{**_serialise(p), "isPublic": p.status in PUBLIC_STATUSES} for p in started],
        "signed": [
            {**_serialise(p), "signedOn": s.created_at.date().isoformat() if s.created_at else None}
            for p, s in signed_rows
        ],
    }


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/petitions")
async def admin_list_petitions(
    status: Optional[str] = None,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Petition).order_by(Petition.created_at.desc()).limit(300)
    if status:
        stmt = stmt.where(Petition.status == status)
    rows = (await session.execute(stmt)).scalars()
    return [
        {
            **_serialise(p, include_body=True),
            "citizenId": p.citizen_id,
            "policyFlags": p.policy_flags or None,
            "reviewedBy": p.reviewed_by,
        }
        for p in rows
        if admin.is_platform_wide() or (p.state_code and admin.can_in_state(p.state_code))
    ]


@router.post("/admin/petitions")
async def create_official_petition(
    payload: PetitionIn,
    request: Request,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """A petition run by the movement itself. Opens immediately.

    No moderation queue here: the permission gate IS the review, and the person
    creating it is accountable through the audit log.
    """
    state_code = payload.state_code.upper() if payload.state_code else None
    if state_code:
        require_state_scope(admin, state_code)

    slug = slugify(payload.title)
    if (await session.execute(select(Petition).where(Petition.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M')}"

    petition = Petition(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        body=payload.body.strip(),
        body_hi=payload.body_hi.strip(),
        addressed_to=payload.addressed_to.strip(),
        state_code=state_code,
        category=payload.category,
        target_signatures=payload.target_signatures,
        is_official=True,
        status=PetitionStatus.OPEN,
        closes_at=utcnow() + timedelta(days=DEFAULT_OPEN_DAYS),
        reviewed_by=admin.id,
    )
    session.add(petition)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"Opened official petition: {petition.title}",
        is_public=True,
        request=request,
    )
    await _index(session, petition)
    return _serialise(petition, include_body=True)


@router.post("/admin/petitions/{petition_id}/status")
async def set_petition_status(
    petition_id: str,
    payload: PetitionStatusIn,
    request: Request,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail=f"status must be one of {list(STATUS_LABELS)}")

    petition = (
        await session.execute(select(Petition).where(Petition.id == petition_id))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")
    if petition.state_code:
        require_state_scope(admin, petition.state_code)

    if payload.status == PetitionStatus.REJECTED and len(payload.note.strip()) < 10:
        # The person who wrote it is told why. A rejection with no reason is
        # indistinguishable from arbitrary moderation.
        raise HTTPException(
            status_code=400, detail="Explain why the petition was not accepted -- the author is told."
        )
    if payload.status in (PetitionStatus.DELIVERED, PetitionStatus.RESPONDED) and not (
        payload.outcome_source_url or petition.outcome_source_url
    ):
        raise HTTPException(
            status_code=400,
            detail="Claiming delivery or a response needs a link to the evidence (acknowledgement, reply, or news of it).",
        )

    before = petition.status
    petition.status = payload.status
    petition.status_note = payload.note.strip() or petition.status_note
    petition.outcome_source_url = payload.outcome_source_url or petition.outcome_source_url
    petition.reviewed_by = admin.id

    await audit.record(
        session,
        actor=admin,
        action="petition_status",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"{petition.title}: {STATUS_LABELS.get(before, before)} -> {STATUS_LABELS[payload.status]}",
        changes={"status": {"before": before, "after": payload.status}},
        source_url=petition.outcome_source_url or None,
        is_public=payload.status in PUBLIC_STATUSES,
        request=request,
    )
    await _index(session, petition)
    return _serialise(petition, include_body=True)


@router.post("/admin/petitions/{petition_id}/signatures/{signature_id}/moderate")
async def moderate_signature_comment(
    petition_id: str,
    signature_id: str,
    request: Request,
    hide: bool = True,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Hide or restore a signature's comment. Never removes the signature itself.

    The distinction matters: a comment that breaches the content policy is
    commentary, but the signature underneath it is a civic act that a moderator
    has no business cancelling.
    """
    signature = (
        await session.execute(
            select(PetitionSignature).where(
                PetitionSignature.id == signature_id, PetitionSignature.petition_id == petition_id
            )
        )
    ).scalar_one_or_none()
    if signature is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    signature.comment_hidden = hide
    await audit.record(
        session,
        actor=admin,
        action="moderate",
        entity_type="petition_signature",
        entity_id=signature_id,
        summary=f"{'Hid' if hide else 'Restored'} a signature comment",
        is_public=False,
        request=request,
    )
    return {"ok": True, "commentHidden": hide}


@router.get("/admin/petitions/{petition_id}/export")
async def export_signature_summary(
    petition_id: str,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Aggregates for the cover sheet handed to the addressee.

    Aggregates, not a name list. The office receiving a petition needs a
    verifiable count and its geographic spread; handing over a spreadsheet of
    signers' identities would betray the people who signed and, for those who
    did not opt in to being listed, would breach the basis on which their data
    was collected.
    """
    petition = (
        await session.execute(select(Petition).where(Petition.id == petition_id))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")

    by_state = (
        await session.execute(
            select(PetitionSignature.state_code, func.count())
            .where(PetitionSignature.petition_id == petition_id)
            .group_by(PetitionSignature.state_code)
        )
    ).all()
    first = (
        await session.execute(
            select(func.min(PetitionSignature.created_at)).where(
                PetitionSignature.petition_id == petition_id
            )
        )
    ).scalar_one()

    return {
        "petition": {"title": petition.title, "addressedTo": petition.addressed_to, "slug": petition.slug},
        "totalSignatures": petition.signature_count,
        "publiclyListed": (
            await session.execute(
                select(func.count())
                .select_from(PetitionSignature)
                .where(
                    PetitionSignature.petition_id == petition_id,
                    PetitionSignature.is_public.is_(True),
                )
            )
        ).scalar_one(),
        "byState": [{"state": state or "unspecified", "count": count} for state, count in by_state],
        "firstSignatureAt": first.isoformat() if first else None,
        "milestones": petition.milestones,
        "note": (
            "Signature identities are not exported. Every signature is tied to a verified member "
            "account and is unique per petition, enforced by a database constraint."
        ),
    }


# --------------------------------------------------------------------------
# DPDP erasure
# --------------------------------------------------------------------------
@erasure.register("petitions")
@erasure.covers("petitions")
async def _erase_petition_authorship(
    session: AsyncSession, email: str, citizen_id: Optional[str]
) -> dict:
    """Detach the author from petitions they started; do not delete the petitions.

    A petition with signatures belongs to everyone who signed it. Deleting it because
    its author left would erase other people's civic acts, and if it has already been
    handed to an office, the platform would be unable to account for a document that
    exists in the world.

    Their SIGNATURES are a different matter and are deleted -- those cascade from the
    citizens row, which core/erasure removes.
    """
    if not citizen_id:
        return {}
    rows = list(
        (
            await session.execute(select(Petition).where(Petition.citizen_id == citizen_id))
        ).scalars()
    )
    for row in rows:
        row.citizen_id = None
    return {"petitions_anonymised": len(rows)}
