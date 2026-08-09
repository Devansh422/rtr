"""Filing, verifying and aggregating Citizen Report Cards."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, limits, moderation, search
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
    require_state_scope,
)
from backend.core.models import Citizen, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.reports.models import (
    PUBLIC_STATUSES,
    SERVICES,
    STATUS_LABELS,
    CitizenReport,
    ReportConfirmation,
    ReportStatus,
)

router = APIRouter(tags=["reports"])

REPUTATION_FOR_PUBLISHED_REPORT = 8

# Minimum reports in a place before an aggregate score is shown. Below this, a
# single annoyed neighbour becomes "this constituency scores 1/5 on water", which
# is not a finding -- it is noise with a decimal point.
MIN_REPORTS_FOR_SCORE = 5


class ReportIn(BaseModel):
    title: str = Field(..., min_length=10, max_length=300)
    body: str = Field(..., min_length=60)
    service: str
    state_code: str
    district_code: Optional[str] = None
    constituency_code: Optional[str] = None
    locality: str = Field(default="", max_length=200)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    evidence: list[str] = Field(default_factory=list)
    show_my_name: bool = False


class VerifyIn(BaseModel):
    status: str
    note: str = Field(..., min_length=10)


class ResponseIn(BaseModel):
    response_text: str = Field(..., min_length=10)
    response_from: str = Field(..., min_length=3, max_length=200)
    response_source_url: str = ""
    mark_resolved: bool = False


def _serialise(report: CitizenReport, *, for_author: bool = False, confirmations: int = 0) -> dict:
    payload = {
        "id": report.id,
        "slug": report.slug,
        "title": report.title,
        "body": report.body,
        "service": report.service,
        "serviceLabel": SERVICES.get(report.service, report.service),
        "state": report.state_code,
        "district": report.district_code,
        "constituency": report.constituency_code,
        "locality": report.locality or None,
        "rating": report.rating,
        "evidenceCount": len(report.evidence or []),
        "status": report.status,
        "statusLabel": STATUS_LABELS.get(report.status, report.status),
        "confirmations": confirmations,
        "filedOn": report.created_at.date().isoformat() if report.created_at else None,
        "verifiedOn": report.verified_at.date().isoformat() if report.verified_at else None,
        # Published because "how was this checked" is what separates a report card
        # from a comment.
        "verificationNote": report.verification_note or None,
        "response": (
            {
                "text": report.response_text,
                "from": report.response_from,
                "sourceUrl": report.response_source_url or None,
                "receivedOn": report.response_at.date().isoformat() if report.response_at else None,
            }
            if report.response_text
            else None
        ),
        "url": f"/reports/{report.slug}",
        "disclaimer": (
            "This is a citizen's own account of a public service in their area, checked by a "
            "moderator for the content policy and, where possible, against supporting evidence. "
            "It is not a finding against any individual official or representative."
        ),
    }
    if report.show_author or for_author:
        payload["author"] = {"displayName": None}  # filled by the caller when it has the Citizen
    return payload


async def _confirmation_counts(session: AsyncSession, report_ids: list[str]) -> dict[str, int]:
    if not report_ids:
        return {}
    rows = (
        await session.execute(
            select(ReportConfirmation.report_id, func.count())
            .where(ReportConfirmation.report_id.in_(report_ids))
            .group_by(ReportConfirmation.report_id)
        )
    ).all()
    return dict(rows)


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/reports/services")
async def list_services():
    return [{"key": key, "label": label} for key, label in SERVICES.items()]


@router.get("/reports")
async def list_reports(
    state: Optional[str] = None,
    district: Optional[str] = None,
    constituency: Optional[str] = None,
    service: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(CitizenReport).where(CitizenReport.status.in_(list(PUBLIC_STATUSES)))
    if state:
        stmt = stmt.where(CitizenReport.state_code == state.upper())
    if district:
        stmt = stmt.where(CitizenReport.district_code == district.upper())
    if constituency:
        stmt = stmt.where(CitizenReport.constituency_code == constituency.upper())
    if service:
        stmt = stmt.where(CitizenReport.service == service)
    if status in PUBLIC_STATUSES:
        stmt = stmt.where(CitizenReport.status == status)

    rows = list((await session.execute(stmt.order_by(CitizenReport.created_at.desc()))).scalars())
    window = rows[offset : offset + limit]
    counts = await _confirmation_counts(session, [r.id for r in window])
    return {
        "total": len(rows),
        "items": [_serialise(r, confirmations=counts.get(r.id, 0)) for r in window],
    }


@router.get("/reports/scorecard")
async def scorecard(
    state: str,
    constituency: Optional[str] = None,
    district: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Aggregate service ratings for a place.

    Reports a sample size next to every score, and withholds the score entirely
    below MIN_REPORTS_FOR_SCORE. A report card is a crowd-sourced signal, not a
    survey, and presenting three ratings as a constituency's water score would
    misrepresent what the platform knows.
    """
    stmt = select(CitizenReport).where(
        CitizenReport.state_code == state.upper(),
        CitizenReport.status.in_(list(PUBLIC_STATUSES)),
    )
    if constituency:
        stmt = stmt.where(CitizenReport.constituency_code == constituency.upper())
    if district:
        stmt = stmt.where(CitizenReport.district_code == district.upper())

    rows = list((await session.execute(stmt)).scalars())
    by_service: dict[str, list[int]] = {}
    for report in rows:
        if report.rating is not None:
            by_service.setdefault(report.service, []).append(report.rating)

    services = []
    for key, label in SERVICES.items():
        ratings = by_service.get(key, [])
        reports_here = [r for r in rows if r.service == key]
        services.append(
            {
                "service": key,
                "label": label,
                "reportCount": len(reports_here),
                "resolvedCount": len([r for r in reports_here if r.status == ReportStatus.RESOLVED]),
                "ratingCount": len(ratings),
                "averageRating": (
                    round(sum(ratings) / len(ratings), 1) if len(ratings) >= MIN_REPORTS_FOR_SCORE else None
                ),
                "scoreWithheld": 0 < len(ratings) < MIN_REPORTS_FOR_SCORE,
            }
        )

    return {
        "place": {"state": state.upper(), "district": district, "constituency": constituency},
        "totalReports": len(rows),
        "minimumForScore": MIN_REPORTS_FOR_SCORE,
        "services": [s for s in services if s["reportCount"] > 0],
        "note": (
            f"Scores are shown only where at least {MIN_REPORTS_FOR_SCORE} residents have rated a "
            "service. This is a crowd-sourced signal from people who chose to report, not a "
            "representative survey."
        ),
    }


@router.get("/reports/{slug}")
async def get_report(slug: str, session: AsyncSession = Depends(get_session)):
    report = (
        await session.execute(select(CitizenReport).where(CitizenReport.slug == slug))
    ).scalar_one_or_none()
    if report is None or report.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Report not found")

    counts = await _confirmation_counts(session, [report.id])
    payload = _serialise(report, confirmations=counts.get(report.id, 0))
    if report.show_author:
        citizen = (
            await session.execute(select(Citizen).where(Citizen.id == report.citizen_id))
        ).scalar_one_or_none()
        payload["author"] = citizen.public_dict() if citizen else None
    payload["evidence"] = report.evidence
    return payload


@router.post("/reports")
async def file_report(
    payload: ReportIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    if payload.service not in SERVICES:
        raise HTTPException(status_code=400, detail=f"service must be one of {list(SERVICES)}")

    await limits.check("report.create", f"m:{citizen.email}")

    verdict = moderation.review(
        f"{payload.title}\n{payload.body}", names_a_person=True, has_citation=bool(payload.evidence)
    )
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "This report cannot be accepted as written.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )

    slug = slugify(f"{payload.title}-{payload.state_code}")
    if (await session.execute(select(CitizenReport).where(CitizenReport.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M%S')}"

    report = CitizenReport(
        slug=slug,
        citizen_id=citizen.id,
        show_author=payload.show_my_name,
        title=payload.title.strip(),
        body=moderation.scrub_identifiers(payload.body.strip()),
        service=payload.service,
        state_code=payload.state_code.upper(),
        district_code=payload.district_code.upper() if payload.district_code else None,
        constituency_code=payload.constituency_code.upper() if payload.constituency_code else None,
        locality=payload.locality.strip(),
        rating=payload.rating,
        evidence=payload.evidence[:8],
        # Never published on submission. See the module docstring.
        status=ReportStatus.SUBMITTED,
        policy_flags=str([f.as_dict() for f in verdict.flags]) if verdict.flags else "",
    )
    session.add(report)
    await session.flush()

    await audit.record(
        session,
        actor=None,
        action="create",
        entity_type="report",
        entity_id=report.slug,
        summary=f"Citizen report filed: {SERVICES[report.service]} in {report.state_code}",
        is_public=False,
        request=request,
    )
    return {
        **_serialise(report, for_author=True),
        "message": (
            "Thank you. Every report is read by a moderator before it is published -- we check it "
            "against the content policy and, where you have given evidence, against that evidence. "
            "You will see its status in your dashboard."
        ),
        "flags": [f.as_dict() for f in verdict.flags],
    }


@router.post("/reports/{slug}/confirm")
async def confirm_report(
    slug: str,
    request: Request,
    note: str = "",
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """"This is happening to me too." Corroboration, not a vote."""
    report = (
        await session.execute(select(CitizenReport).where(CitizenReport.slug == slug))
    ).scalar_one_or_none()
    if report is None or report.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.citizen_id == citizen.id:
        raise HTTPException(status_code=400, detail="You filed this report.")

    existing = (
        await session.execute(
            select(ReportConfirmation).where(
                ReportConfirmation.report_id == report.id,
                ReportConfirmation.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already confirmed this report.")

    await limits.check("forum.vote", f"m:{citizen.email}")
    session.add(
        ReportConfirmation(
            report_id=report.id,
            citizen_id=citizen.id,
            note=moderation.scrub_identifiers(note.strip())[:1000],
        )
    )
    await session.flush()

    count = (
        await session.execute(
            select(func.count())
            .select_from(ReportConfirmation)
            .where(ReportConfirmation.report_id == report.id)
        )
    ).scalar_one()
    return {"ok": True, "confirmations": count}


@router.get("/me/reports")
async def my_reports(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """The author's own view, including reports still in the queue and rejected ones.

    Showing a rejected report back to its author with the reviewer's reason is
    what makes moderation feel like a process rather than a void.
    """
    rows = list(
        (
            await session.execute(
                select(CitizenReport)
                .where(CitizenReport.citizen_id == citizen.id)
                .order_by(CitizenReport.created_at.desc())
            )
        ).scalars()
    )
    counts = await _confirmation_counts(session, [r.id for r in rows])
    return [_serialise(r, for_author=True, confirmations=counts.get(r.id, 0)) for r in rows]


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/reports/queue")
async def report_queue(
    state: Optional[str] = None,
    limit: int = Query(default=60, ge=1, le=200),
    admin: Principal = Depends(require_permission("reports.verify")),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(CitizenReport)
        .where(CitizenReport.status.in_([ReportStatus.SUBMITTED, ReportStatus.UNDER_REVIEW]))
        .order_by(CitizenReport.created_at)
        .limit(limit)
    )
    if state:
        stmt = stmt.where(CitizenReport.state_code == state.upper())

    rows = [r for r in (await session.execute(stmt)).scalars() if admin.can_in_state(r.state_code)]
    counts = await _confirmation_counts(session, [r.id for r in rows])
    return {
        "total": len(rows),
        "items": [
            {
                **_serialise(r, for_author=True, confirmations=counts.get(r.id, 0)),
                "evidence": r.evidence,
                "policyFlags": r.policy_flags or None,
                "citizenId": r.citizen_id,
            }
            for r in rows
        ],
    }


@router.post("/admin/reports/{report_id}/verify")
async def verify_report(
    report_id: str,
    payload: VerifyIn,
    request: Request,
    admin: Principal = Depends(require_permission("reports.verify")),
    session: AsyncSession = Depends(get_session),
):
    allowed = {
        ReportStatus.UNDER_REVIEW,
        ReportStatus.PUBLISHED,
        ReportStatus.REJECTED,
        ReportStatus.WITHHELD,
    }
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")

    report = (
        await session.execute(select(CitizenReport).where(CitizenReport.id == report_id))
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    require_state_scope(admin, report.state_code)

    before = report.status
    report.status = payload.status
    report.verification_note = payload.note.strip()
    report.verified_by = admin.id
    report.verified_at = utcnow()

    if payload.status == ReportStatus.PUBLISHED:
        citizen = (
            await session.execute(select(Citizen).where(Citizen.id == report.citizen_id))
        ).scalar_one_or_none()
        if citizen is not None and before != ReportStatus.PUBLISHED:
            citizen.reputation += REPUTATION_FOR_PUBLISHED_REPORT
            contributions = dict(citizen.contributions or {})
            contributions["publishedReports"] = contributions.get("publishedReports", 0) + 1
            citizen.contributions = contributions

    await audit.record(
        session,
        actor=admin,
        action="report_verify",
        entity_type="report",
        entity_id=report.slug,
        summary=f"{report.title[:80]}: {STATUS_LABELS.get(before, before)} -> {STATUS_LABELS[payload.status]}",
        changes={"status": {"before": before, "after": payload.status}},
        is_public=payload.status in PUBLIC_STATUSES,
        request=request,
    )
    await search.index(
        session,
        entity_type="report",
        entity_id=report.slug,
        title=report.title,
        subtitle=f"Citizen report - {SERVICES.get(report.service, report.service)}",
        body=report.body,
        keywords=[report.service, report.state_code, report.locality],
        state_code=report.state_code,
        is_published=payload.status in PUBLIC_STATUSES,
        url_path=f"/reports/{report.slug}",
    )
    return _serialise(report, for_author=True)


@router.post("/admin/reports/{report_id}/response")
async def record_response(
    report_id: str,
    payload: ResponseIn,
    request: Request,
    admin: Principal = Depends(require_permission("reports.verify")),
    session: AsyncSession = Depends(get_session),
):
    """Record what the department or office said, and whether it was fixed.

    The most important endpoint in this module for the platform's credibility. A
    report card system that only records complaints looks like a campaign; one
    that publishes "the municipality repaired it in eleven days" alongside the
    complaint is doing accountability.
    """
    report = (
        await session.execute(select(CitizenReport).where(CitizenReport.id == report_id))
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    require_state_scope(admin, report.state_code)

    report.response_text = payload.response_text.strip()
    report.response_from = payload.response_from.strip()
    report.response_source_url = payload.response_source_url.strip()
    report.response_at = utcnow()
    if payload.mark_resolved:
        report.status = ReportStatus.RESOLVED

    await audit.record(
        session,
        actor=admin,
        action="report_response",
        entity_type="report",
        entity_id=report.slug,
        summary=f"Response recorded from {report.response_from}",
        source_url=report.response_source_url or None,
        is_public=True,
        request=request,
    )
    return _serialise(report, for_author=True)
