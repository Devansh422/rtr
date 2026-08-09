"""Filing and resolving corrections.

The public read is the interesting part. Showing every submission verbatim the
moment it arrives would turn a correction box into an unmoderated allegation
channel attached to a named person's profile -- the opposite of what §7 is for.
Showing nothing until resolution would make the workflow invisible, which
forfeits its credibility value.

So: an unresolved correction is disclosed as a FACT (this field is contested, a
review is open, filed on this date) without its text. Once a reviewer has ruled,
the objection and the reasoning are both published. A reader learns that
objections exist, what happened to them, and never reads an unvetted claim about
a person.
"""

from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, erasure, limits, moderation
from backend.core.citations import CitationError, parse_citation
from backend.core.deps import get_current_citizen, get_session, require_permission
from backend.core.models import Citizen, utcnow
from backend.core.rbac import Principal
from backend.modules.corrections.models import (
    CORRECTABLE_ENTITIES,
    RESOLVED_STATUSES,
    STATUS_LABELS,
    Correction,
    CorrectionStatus,
)

router = APIRouter(tags=["corrections"])

# Reputation awarded to a signed-in citizen whose correction is accepted. The
# only place in the platform where being right about a fact earns standing.
REPUTATION_FOR_ACCEPTED = 10


class CorrectionIn(BaseModel):
    entity_type: str
    entity_id: str
    summary: str = Field(..., min_length=10, max_length=300)
    detail: str = ""
    field_key: str = ""
    proposed_value: str = ""
    source_url: str = ""
    source_title: str = ""
    contact_email: Optional[EmailStr] = None


class CorrectionResolve(BaseModel):
    status: str
    note: str = Field(..., min_length=10)
    resulted_in: str = ""


def _public_dict(correction: Correction) -> dict:
    """What a visitor sees. Unresolved submissions disclose the fact, not the text."""
    base = {
        "id": correction.id,
        "fieldKey": correction.field_key or None,
        "status": correction.status,
        "statusLabel": STATUS_LABELS.get(correction.status, correction.status),
        "filedOn": correction.created_at.date().isoformat() if correction.created_at else None,
        "resolvedOn": correction.reviewed_at.date().isoformat() if correction.reviewed_at else None,
    }
    if correction.status in RESOLVED_STATUSES:
        base.update(
            {
                "summary": correction.summary,
                "proposedValue": correction.proposed_value or None,
                "source": (
                    {"url": correction.source_url, "title": correction.source_title}
                    if correction.source_url
                    else None
                ),
                "resolutionNote": correction.resolution_note,
            }
        )
    else:
        base["summary"] = (
            "A correction has been filed about this record and is being reviewed. Its contents "
            "are published once a reviewer has checked it against the source."
        )
    return base


def _admin_dict(correction: Correction) -> dict:
    return {
        **_public_dict(correction),
        "entityType": correction.entity_type,
        "entityId": correction.entity_id,
        # Always present for a reviewer, whatever the status.
        "summary": correction.summary,
        "detail": correction.detail,
        "proposedValue": correction.proposed_value or None,
        "source": (
            {"url": correction.source_url, "title": correction.source_title}
            if correction.source_url
            else None
        ),
        "hasSource": bool(correction.source_url),
        "citizenId": correction.citizen_id,
        "isAnonymous": correction.citizen_id is None,
        "contactEmail": correction.contact_email or None,
        "policyFlags": json.loads(correction.policy_flags) if correction.policy_flags else [],
        "resultedIn": correction.resulted_in or None,
        "reviewedBy": correction.reviewed_by,
    }


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/corrections/entities")
async def correctable_entities():
    return [{"key": key, "label": label} for key, label in CORRECTABLE_ENTITIES.items()]


@router.get("/corrections")
async def list_corrections(
    entityType: str = Query(..., alias="entityType"),
    entityId: str = Query(..., alias="entityId"),
    session: AsyncSession = Depends(get_session),
):
    """Corrections filed against one record, for its "Corrections" tab."""
    if entityType not in CORRECTABLE_ENTITIES:
        raise HTTPException(status_code=400, detail=f"entityType must be one of {list(CORRECTABLE_ENTITIES)}")

    rows = list(
        (
            await session.execute(
                select(Correction)
                .where(Correction.entity_type == entityType, Correction.entity_id == entityId)
                .order_by(Correction.created_at.desc())
                .limit(100)
            )
        ).scalars()
    )
    return {
        "total": len(rows),
        "openCount": len([r for r in rows if r.status not in RESOLVED_STATUSES]),
        "acceptedCount": len([r for r in rows if r.status == CorrectionStatus.ACCEPTED]),
        "items": [_public_dict(r) for r in rows],
    }


@router.post("/corrections")
async def submit_correction(
    payload: CorrectionIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """File a correction. Open to anyone, signed in or not.

    Anonymous submission is deliberate: requiring an account to report an error
    about a powerful person filters out precisely the people most likely to know
    about one. The trade-off is that an anonymous correction earns no reputation
    and cannot be followed up unless an email is supplied.
    """
    if payload.entity_type not in CORRECTABLE_ENTITIES:
        raise HTTPException(
            status_code=400, detail=f"entity_type must be one of {list(CORRECTABLE_ENTITIES)}"
        )

    # A correction is attached to a named person's record, so the moderation gate
    # runs with `names_a_person` set: an unsourced accusation is held for review
    # rather than published, per the content policy.
    text = f"{payload.summary}\n{payload.detail}\n{payload.proposed_value}"
    verdict = moderation.review(
        text,
        names_a_person=payload.entity_type in ("representative", "promise"),
        has_citation=bool(payload.source_url),
    )
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "This submission cannot be accepted as written.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )

    citizen: Optional[Citizen] = None
    try:
        citizen = await get_current_citizen(request, session)
    except HTTPException:
        # Not signed in. Expected, and allowed -- see the docstring.
        citizen = None

    identity = limits.identity_for(request, email=citizen.email if citizen else None)
    await limits.check("correction.suggest", identity)

    source_url, source_title = "", ""
    if payload.source_url:
        try:
            citation = parse_citation(
                {"url": payload.source_url, "title": payload.source_title or payload.summary},
                require_primary=False,
                field_name="your source",
            )
            source_url, source_title = citation.url, citation.title
        except CitationError as e:
            raise HTTPException(status_code=400, detail=str(e))

    correction = Correction(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        field_key=payload.field_key[:60],
        summary=payload.summary.strip(),
        detail=moderation.scrub_identifiers(payload.detail.strip()),
        proposed_value=payload.proposed_value.strip(),
        source_url=source_url,
        source_title=source_title,
        citizen_id=citizen.id if citizen else None,
        contact_email=(payload.contact_email or (citizen.email if citizen else "") or "").lower(),
        status=CorrectionStatus.OPEN,
        policy_flags=json.dumps([f.as_dict() for f in verdict.flags]) if verdict.flags else "",
    )
    session.add(correction)
    await session.flush()

    await audit.record(
        session,
        actor=None,
        action="correction_filed",
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        summary=f"Correction filed on {payload.field_key or 'the record'}",
        # Internal until resolved, for the reason in the module docstring: the
        # public history must not become a feed of unreviewed allegations.
        is_public=False,
        source_url=source_url or None,
        request=request,
    )

    return {
        "id": correction.id,
        "status": correction.status,
        "message": (
            "Thank you. A reviewer will check this against the source you gave and the record "
            "will be updated or the objection published with the reason it was not accepted."
            if source_url
            else "Thank you. Corrections that cite a public record are resolved much faster -- "
            "if you can add a link to a court filing, affidavit, RTI reply or official order, "
            "please file it again with that link."
        ),
        "flags": [f.as_dict() for f in verdict.flags],
    }


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/corrections")
async def admin_list_corrections(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=300),
    admin: Principal = Depends(require_permission("corrections.review")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Correction).order_by(Correction.created_at).limit(limit)
    if status:
        stmt = stmt.where(Correction.status == status)
    else:
        # Default view is the work queue, not the archive.
        stmt = stmt.where(Correction.status.notin_(list(RESOLVED_STATUSES)))
    if entity_type:
        stmt = stmt.where(Correction.entity_type == entity_type)

    rows = (await session.execute(stmt)).scalars()
    return [_admin_dict(r) for r in rows]


@router.get("/admin/corrections/summary")
async def corrections_summary(
    admin: Principal = Depends(require_permission("corrections.review")),
    session: AsyncSession = Depends(get_session),
):
    """Queue depth by status and by entity type -- the dashboard tile."""
    by_status = dict(
        (
            await session.execute(select(Correction.status, func.count()).group_by(Correction.status))
        ).all()
    )
    by_entity = dict(
        (
            await session.execute(
                select(Correction.entity_type, func.count())
                .where(Correction.status.notin_(list(RESOLVED_STATUSES)))
                .group_by(Correction.entity_type)
            )
        ).all()
    )
    return {
        "byStatus": [
            {"status": key, "label": STATUS_LABELS.get(key, key), "count": count}
            for key, count in by_status.items()
        ],
        "openByEntity": [{"entityType": key, "count": count} for key, count in by_entity.items()],
        "openTotal": sum(count for key, count in by_status.items() if key not in RESOLVED_STATUSES),
    }


@router.post("/admin/corrections/{correction_id}")
async def resolve_correction(
    correction_id: str,
    payload: CorrectionResolve,
    request: Request,
    admin: Principal = Depends(require_permission("corrections.review")),
    session: AsyncSession = Depends(get_session),
):
    """Rule on a correction.

    Accepting one does not edit the record it concerns -- see the module
    docstring. It records the finding, credits the citizen who filed it, and
    publishes the reasoning; the edit itself is made through the owning module so
    the citation and audit rules apply exactly once.
    """
    if payload.status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail=f"status must be one of {list(STATUS_LABELS)}")

    correction = (
        await session.execute(select(Correction).where(Correction.id == correction_id))
    ).scalar_one_or_none()
    if correction is None:
        raise HTTPException(status_code=404, detail="Correction not found")

    before = correction.status
    correction.status = payload.status
    correction.resolution_note = payload.note.strip()
    correction.resulted_in = payload.resulted_in[:120]
    correction.reviewed_by = admin.id
    correction.reviewed_at = utcnow()

    if payload.status == CorrectionStatus.ACCEPTED and correction.citizen_id:
        citizen = (
            await session.execute(select(Citizen).where(Citizen.id == correction.citizen_id))
        ).scalar_one_or_none()
        if citizen is not None:
            citizen.reputation += REPUTATION_FOR_ACCEPTED
            contributions = dict(citizen.contributions or {})
            contributions["acceptedCorrections"] = contributions.get("acceptedCorrections", 0) + 1
            citizen.contributions = contributions

    await audit.record(
        session,
        actor=admin,
        action="correction_resolved",
        entity_type=correction.entity_type,
        entity_id=correction.entity_id,
        summary=f"Correction {STATUS_LABELS[payload.status].lower()}: {correction.summary[:120]}",
        changes={"status": {"before": before, "after": payload.status}},
        source_url=correction.source_url or None,
        # Now public: a reviewer has read it and written a reason, which is the
        # transparency payoff described in §7.
        is_public=payload.status in RESOLVED_STATUSES,
        request=request,
    )
    return _admin_dict(correction)


# --------------------------------------------------------------------------
# DPDP erasure
# --------------------------------------------------------------------------
@erasure.register("corrections")
@erasure.covers("corrections")
async def _erase_corrections(session: AsyncSession, email: str, citizen_id: Optional[str]) -> dict:
    """Detach the submitter from their corrections rather than deleting them.

    A resolved correction is part of a public record's history: the objection, the
    reviewer's reasoning, and the change it led to. Deleting it would rewrite the
    audit trail of a claim about a third party, which the person requesting erasure
    has no right to do. So the correction survives with nothing identifying left on
    it -- which is also the state an anonymous submission was always in.
    """
    conditions = [Correction.contact_email == email]
    if citizen_id:
        conditions.append(Correction.citizen_id == citizen_id)

    rows = list(
        (await session.execute(select(Correction).where(or_(*conditions)))).scalars()
    )
    for row in rows:
        row.citizen_id = None
        row.contact_email = ""
    return {"corrections_anonymised": len(rows)}
