"""Manifesto accountability: the public evidence database, and the desk that fills it.

READ THE MODULE DOCSTRING IN models.py FIRST. It explains why fact and assessment
are separate tables; this file is where that separation is enforced.

Three rules run through every write handler here:

1. A factual status about a government's performance cannot be published without
   the records it rests on (`create_assessment`). This is the same gate §7 puts
   on claims about named people, applied to claims about administrations.
2. A published document must say where it came from (`source_note` or
   `source_url`). An anonymous PDF is not evidence.
3. Every meaningful change is written to the shared audit log against the
   PROMISE, not against the sub-record, so one query returns the whole chain's
   history and the public "Record history" panel can show it (§17 of the brief).

The public endpoints only ever return published rows. Research in progress is
real work, but a half-finished RTI trail published as a finished one is exactly
the sort of thing this module exists to hold other people to.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, citations, search
from backend.core.deps import get_session, require_permission
from backend.core.geography import STATES_BY_CODE, VALID_STATE_CODES
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.manifesto import service
from backend.modules.manifesto.models import (
    ANSWER_STATUSES,
    DEFAULT_PROMISE_STATUS,
    DOCUMENT_KINDS,
    PROMISE_STATUSES,
    RTI_ANSWERED_STATUSES,
    RTI_STATUSES,
    STATUSES_WITHOUT_EVIDENCE,
    SUGGESTED_CATEGORIES,
    GovernmentDocument,
    Manifesto,
    ManifestoElection,
    ManifestoPromise,
    PromiseAssessment,
    PromiseEvidence,
    RtiApplication,
    RtiQuestion,
    RtiResponse,
    status_label,
)

router = APIRouter(tags=["manifesto"])

# The statutory reply period under s.7(1) of the Right to Information Act 2005.
# Used only to pre-fill a due date an operator can then correct -- transfers
# under s.6(3) restart it and this module does not pretend to compute that.
RTI_REPLY_DAYS = 30

AUDIT_ENTITY = "manifesto_promise"


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------
async def _published_promise(session: AsyncSession, code: str) -> ManifestoPromise:
    promise = (
        await session.execute(
            select(ManifestoPromise).where(ManifestoPromise.code == code.upper())
        )
    ).scalar_one_or_none()
    if promise is None or not promise.is_published:
        raise HTTPException(status_code=404, detail="Promise not found")
    return promise


async def _promise_or_404(session: AsyncSession, promise_id: str) -> ManifestoPromise:
    promise = (
        await session.execute(
            select(ManifestoPromise).where(ManifestoPromise.id == promise_id)
        )
    ).scalar_one_or_none()
    if promise is None:
        raise HTTPException(status_code=404, detail="Promise not found")
    return promise


async def _election_or_404(session: AsyncSession, slug: str) -> ManifestoElection:
    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.slug == slug)
        )
    ).scalar_one_or_none()
    if election is None:
        raise HTTPException(status_code=404, detail="Election not found")
    return election


async def _elections_by_id(session: AsyncSession) -> dict[str, ManifestoElection]:
    """Every election, keyed by id. There are single digits of these; one query
    beats a join on each of the four list endpoints that need the URL."""
    return {e.id: e for e in (await session.execute(select(ManifestoElection))).scalars()}


async def _next_code(session: AsyncSession, election: ManifestoElection, letter: str) -> str:
    """UK-2022-P001. Human-quotable, because these get typed into RTI applications.

    Derived from the highest existing suffix rather than from a row count, so a
    deleted draft does not cause the next promise to reuse a code that has
    already been published, printed or cited.
    """
    prefix = f"{election.code_prefix or election.state_code}-{election.year}-{letter}"
    model = {"P": ManifestoPromise, "R": RtiApplication, "D": GovernmentDocument}[letter]
    existing = list(
        (await session.execute(select(model.code).where(model.code.like(f"{prefix}%")))).scalars()
    )
    highest = 0
    for code in existing:
        tail = code[len(prefix) :]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}{highest + 1:03d}"


# --------------------------------------------------------------------------
# Public: reference data
# --------------------------------------------------------------------------
@router.get("/manifesto/vocabulary")
async def vocabulary():
    """Statuses, their meanings and the document kinds, from one source.

    The frontend renders filters and legends from this rather than hard-coding a
    second copy of the status list -- a status whose label differs between the
    filter and the badge is a status nobody trusts.
    """
    return {
        "promiseStatuses": [service.status_dict(key) for key in PROMISE_STATUSES],
        "rtiStatuses": [{"key": k, "label": v} for k, v in RTI_STATUSES.items()],
        "answerStatuses": [{"key": k, "label": v} for k, v in ANSWER_STATUSES.items()],
        "documentKinds": [{"key": k, "label": v} for k, v in DOCUMENT_KINDS.items()],
        "categories": list(SUGGESTED_CATEGORIES),
        "editorialNote": (
            "Statuses describe what the available official records establish. They are "
            "not findings about anyone's conduct, and a status of 'not established' "
            "means the records do not show implementation -- not that nothing was done."
        ),
    }


@router.get("/manifesto/elections")
async def list_elections(session: AsyncSession = Depends(get_session)):
    """Published elections. One, for now, and the UI says so rather than implying more."""
    rows = (
        await session.execute(
            select(ManifestoElection)
            .where(ManifestoElection.is_published.is_(True))
            .order_by(ManifestoElection.year.desc())
        )
    ).scalars()
    return [service.election_dict(e) for e in rows]


@router.get("/manifesto/elections/{slug}")
async def get_election(slug: str, session: AsyncSession = Depends(get_session)):
    election = await _election_or_404(session, slug)
    if not election.is_published:
        raise HTTPException(status_code=404, detail="Election not found")

    manifestos = (
        await session.execute(
            select(Manifesto).where(
                Manifesto.election_id == election.id, Manifesto.is_published.is_(True)
            )
        )
    ).scalars()
    state = STATES_BY_CODE.get(election.state_code)
    return {
        **service.election_dict(election),
        "stateName": state.name if state else election.state_code,
        "stateSlug": state.slug if state else None,
        "manifestos": [service.manifesto_dict(m) for m in manifestos],
        "dashboard": await service.dashboard(session, election.id),
    }


@router.get("/manifesto/dashboard")
async def dashboard(
    election: Optional[str] = None, session: AsyncSession = Depends(get_session)
):
    election_id = None
    if election:
        election_id = (await _election_or_404(session, election)).id
    return await service.dashboard(session, election_id)


@router.get("/manifesto/filters")
async def filter_options(
    election: Optional[str] = None, session: AsyncSession = Depends(get_session)
):
    """Departments and categories that actually have promises behind them.

    Built from the data rather than from a fixed list, so a filter can never
    offer a department that returns nothing.
    """
    where = [ManifestoPromise.is_published.is_(True)]
    if election:
        where.append(ManifestoPromise.election_id == (await _election_or_404(session, election)).id)

    departments = (
        await session.execute(
            select(ManifestoPromise.department, func.count())
            .where(*where)
            .group_by(ManifestoPromise.department)
            .order_by(func.count().desc())
        )
    ).all()
    categories = (
        await session.execute(
            select(ManifestoPromise.category, func.count())
            .where(*where)
            .group_by(ManifestoPromise.category)
            .order_by(func.count().desc())
        )
    ).all()
    statuses = (
        await session.execute(
            select(ManifestoPromise.status, func.count()).where(*where).group_by(ManifestoPromise.status)
        )
    ).all()

    return {
        "departments": [
            {"value": value or "Not stated", "count": count} for value, count in departments
        ],
        "categories": [{"value": value, "count": count} for value, count in categories],
        "statuses": [
            {**service.status_dict(value), "count": count} for value, count in statuses
        ],
        "rtiStatuses": [{"key": k, "label": v} for k, v in RTI_STATUSES.items()],
    }


# --------------------------------------------------------------------------
# Public: promises
# --------------------------------------------------------------------------
@router.get("/manifesto/promises")
async def list_promises(
    election: Optional[str] = None,
    q: Optional[str] = None,
    department: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    rti_status: Optional[str] = None,
    sort: str = Query(default="code", pattern="^(code|updated|status|department)$"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ManifestoPromise).where(ManifestoPromise.is_published.is_(True))
    if election:
        stmt = stmt.where(
            ManifestoPromise.election_id == (await _election_or_404(session, election)).id
        )
    if department:
        stmt = stmt.where(ManifestoPromise.department == department)
    if category:
        stmt = stmt.where(ManifestoPromise.category == category)
    if status:
        if status not in PROMISE_STATUSES:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
        stmt = stmt.where(ManifestoPromise.status == status)
    if q:
        # Searches the promise TEXT as well as the title, because a reader
        # looking for "Gairsain" is looking for a word in the promise, not for
        # the summary somebody wrote of it.
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ManifestoPromise.code.ilike(pattern),
                ManifestoPromise.title.ilike(pattern),
                ManifestoPromise.promise_text.ilike(pattern),
                ManifestoPromise.department.ilike(pattern),
                ManifestoPromise.category.ilike(pattern),
            )
        )

    rows = list((await session.execute(stmt)).scalars())

    # The RTI for each promise, in one query rather than one per row.
    applications = {}
    if rows:
        ids = [p.id for p in rows]
        for rti in (
            await session.execute(
                select(RtiApplication)
                .where(
                    RtiApplication.promise_id.in_(ids),
                    RtiApplication.is_published.is_(True),
                )
                .order_by(RtiApplication.created_at)
            )
        ).scalars():
            applications.setdefault(rti.promise_id, rti)

        if rti_status:
            rows = [p for p in rows if (applications.get(p.id) and applications[p.id].status == rti_status)]

        evidence_counts = dict(
            (
                await session.execute(
                    select(PromiseEvidence.promise_id, func.count())
                    .where(
                        PromiseEvidence.promise_id.in_(ids),
                        PromiseEvidence.is_published.is_(True),
                    )
                    .group_by(PromiseEvidence.promise_id)
                )
            ).all()
        )
        document_counts = dict(
            (
                await session.execute(
                    select(GovernmentDocument.promise_id, func.count())
                    .where(
                        GovernmentDocument.promise_id.in_(ids),
                        GovernmentDocument.is_published.is_(True),
                    )
                    .group_by(GovernmentDocument.promise_id)
                )
            ).all()
        )
    else:
        evidence_counts, document_counts = {}, {}

    if sort == "updated":
        rows.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
    elif sort == "status":
        order = list(PROMISE_STATUSES)
        rows.sort(key=lambda p: (order.index(p.status) if p.status in order else 99, p.code))
    elif sort == "department":
        rows.sort(key=lambda p: (p.department or "zz", p.code))
    else:
        rows.sort(key=lambda p: (p.sort_order, p.code))

    return {
        "total": len(rows),
        "items": [
            service.promise_dict(
                p,
                rti=applications.get(p.id),
                evidence_count=evidence_counts.get(p.id, 0),
                document_count=document_counts.get(p.id, 0),
            )
            for p in rows[offset : offset + limit]
        ],
    }


@router.get("/manifesto/promises/{code}")
async def get_promise(code: str, session: AsyncSession = Depends(get_session)):
    """The complete documentary chain for one promise.

    Returned as one payload, in three labelled parts -- `manifestoSays`,
    `recordsSay`, `assessment` -- because the page is required to render them as
    three separate things (§14 of the brief). Handing the frontend one flat
    object would leave that separation to a template, where it is one refactor
    away from being lost.
    """
    promise = await _published_promise(session, code)

    manifesto = (
        await session.execute(select(Manifesto).where(Manifesto.id == promise.manifesto_id))
    ).scalar_one_or_none()
    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.id == promise.election_id)
        )
    ).scalar_one_or_none()

    applications = list(
        (
            await session.execute(
                select(RtiApplication)
                .where(
                    RtiApplication.promise_id == promise.id,
                    RtiApplication.is_published.is_(True),
                )
                .order_by(RtiApplication.created_at)
            )
        ).scalars()
    )
    rti_ids = [a.id for a in applications]

    responses = (
        list(
            (
                await session.execute(
                    select(RtiResponse)
                    .where(RtiResponse.rti_id.in_(rti_ids), RtiResponse.is_published.is_(True))
                    .order_by(RtiResponse.received_on)
                )
            ).scalars()
        )
        if rti_ids
        else []
    )
    questions = (
        list(
            (
                await session.execute(
                    select(RtiQuestion)
                    .where(RtiQuestion.rti_id.in_(rti_ids))
                    .order_by(RtiQuestion.number)
                )
            ).scalars()
        )
        if rti_ids
        else []
    )

    documents = list(
        (
            await session.execute(
                select(GovernmentDocument)
                .where(
                    GovernmentDocument.promise_id == promise.id,
                    GovernmentDocument.is_published.is_(True),
                )
                .order_by(GovernmentDocument.issued_on)
            )
        ).scalars()
    )
    documents_by_id = {d.id: d for d in documents}
    questions_by_id = {q.id: q for q in questions}

    evidence = list(
        (
            await session.execute(
                select(PromiseEvidence)
                .where(
                    PromiseEvidence.promise_id == promise.id,
                    PromiseEvidence.is_published.is_(True),
                )
                .order_by(PromiseEvidence.sort_order)
            )
        ).scalars()
    )

    assessment = (
        await session.execute(
            select(PromiseAssessment).where(
                PromiseAssessment.promise_id == promise.id,
                PromiseAssessment.is_current.is_(True),
                PromiseAssessment.is_published.is_(True),
            )
        )
    ).scalar_one_or_none()

    return {
        "code": promise.code,
        "title": promise.title,
        "titleHi": promise.title_hi,
        "department": promise.department or "Not stated",
        "category": promise.category,
        "tags": promise.tags or [],
        "status": service.status_dict(promise.status),
        "url": f"/manifesto/promise/{promise.code}",
        "election": service.election_dict(election) if election else None,
        # ---- 1. What the manifesto says ----
        "manifestoSays": {
            "promiseText": promise.promise_text,
            "promiseTextHi": promise.promise_text_hi,
            "page": promise.manifesto_page,
            "pageUrl": promise.manifesto_page_url or None,
            "manifesto": service.manifesto_dict(manifesto),
        },
        # ---- 2. What the government's own records say ----
        "recordsSay": {
            "rtiApplications": [
                {
                    **service.rti_dict(a),
                    "questions": [
                        service.question_dict(
                            question,
                            document=documents_by_id.get(question.supporting_document_id),
                        )
                        for question in questions
                        if question.rti_id == a.id
                    ],
                    "responses": [
                        service.response_dict(r, rti=a) for r in responses if r.rti_id == a.id
                    ],
                }
                for a in applications
            ],
            "documents": [service.document_dict(d) for d in documents],
            "evidence": [
                service.evidence_dict(
                    item,
                    document=documents_by_id.get(item.document_id),
                    question=questions_by_id.get(item.rti_question_id),
                )
                for item in evidence
            ],
        },
        # ---- 3. What this platform concludes, kept separate ----
        "assessment": service.assessment_dict(assessment),
        "timeline": service.timeline(
            promise=promise,
            manifesto=manifesto,
            applications=applications,
            responses=responses,
            documents=documents,
            evidence=evidence,
            assessment=assessment,
        ),
        "counts": {
            "rtiApplications": len(applications),
            "questions": len(questions),
            "answers": sum(1 for q in questions if q.answer_text),
            "responses": len(responses),
            "documents": len(documents),
            "evidence": len(evidence),
        },
        "disclaimer": (
            "The manifesto text and the government records on this page are reproduced as "
            "published or received. The assessment is this platform's reading of those "
            "records and is labelled as such; the records are provided so you can read "
            "them yourself."
        ),
    }


@router.get("/manifesto/promises/{code}/history")
async def promise_history(code: str, session: AsyncSession = Depends(get_session)):
    """Public record history: every step of this promise's chain, dated.

    Actor identity is omitted, as everywhere else on the platform: showing that
    an RTI was filed on 12 January and a reply logged on 15 February is the
    transparency promise; naming the volunteer who typed it is not part of it and
    invites harassment of the volunteer.
    """
    promise = await _published_promise(session, code)
    entries = await audit.history(session, entity_type=AUDIT_ENTITY, entity_id=promise.code)
    return [audit.to_dict(e, include_actor=False) for e in entries]


# --------------------------------------------------------------------------
# Public: the RTI, reply and document registers
# --------------------------------------------------------------------------
@router.get("/manifesto/rti")
async def list_rti(
    election: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    promise_ids = select(ManifestoPromise.id).where(ManifestoPromise.is_published.is_(True))
    if election:
        promise_ids = promise_ids.where(
            ManifestoPromise.election_id == (await _election_or_404(session, election)).id
        )

    stmt = (
        select(RtiApplication, ManifestoPromise)
        .join(ManifestoPromise, ManifestoPromise.id == RtiApplication.promise_id)
        .where(RtiApplication.is_published.is_(True), RtiApplication.promise_id.in_(promise_ids))
        .order_by(RtiApplication.filed_on.desc(), RtiApplication.code)
    )
    if status:
        stmt = stmt.where(RtiApplication.status == status)

    rows = (await session.execute(stmt)).all()
    return {
        "total": len(rows),
        "items": [service.rti_dict(rti, promise=promise) for rti, promise in rows[offset : offset + limit]],
    }


@router.get("/manifesto/replies")
async def list_replies(
    election: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Every government reply received, newest first, each with its original PDF."""
    promise_ids = select(ManifestoPromise.id).where(ManifestoPromise.is_published.is_(True))
    if election:
        promise_ids = promise_ids.where(
            ManifestoPromise.election_id == (await _election_or_404(session, election)).id
        )
    rti_ids = select(RtiApplication.id).where(
        RtiApplication.is_published.is_(True), RtiApplication.promise_id.in_(promise_ids)
    )

    rows = (
        await session.execute(
            select(RtiResponse, RtiApplication, ManifestoPromise)
            .join(RtiApplication, RtiApplication.id == RtiResponse.rti_id)
            .join(ManifestoPromise, ManifestoPromise.id == RtiApplication.promise_id)
            .where(RtiResponse.is_published.is_(True), RtiResponse.rti_id.in_(rti_ids))
            .order_by(RtiResponse.received_on.desc())
        )
    ).all()

    return {
        "total": len(rows),
        "items": [
            {
                **service.response_dict(response, rti=rti),
                "promise": {
                    "code": promise.code,
                    "title": promise.title,
                    "url": f"/manifesto/promise/{promise.code}",
                },
            }
            for response, rti, promise in rows[offset : offset + limit]
        ],
    }


@router.get("/manifesto/documents")
async def list_documents(
    election: Optional[str] = None,
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    promise_ids = select(ManifestoPromise.id).where(ManifestoPromise.is_published.is_(True))
    if election:
        promise_ids = promise_ids.where(
            ManifestoPromise.election_id == (await _election_or_404(session, election)).id
        )

    stmt = (
        select(GovernmentDocument, ManifestoPromise)
        .join(ManifestoPromise, ManifestoPromise.id == GovernmentDocument.promise_id)
        .where(
            GovernmentDocument.is_published.is_(True),
            GovernmentDocument.promise_id.in_(promise_ids),
        )
        .order_by(GovernmentDocument.issued_on.desc(), GovernmentDocument.code)
    )
    if kind:
        stmt = stmt.where(GovernmentDocument.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                GovernmentDocument.title.ilike(pattern),
                GovernmentDocument.issuing_authority.ilike(pattern),
                GovernmentDocument.reference_number.ilike(pattern),
            )
        )

    rows = (await session.execute(stmt)).all()
    return {
        "total": len(rows),
        "items": [
            {
                **service.document_dict(document),
                "promise": {
                    "code": promise.code,
                    "title": promise.title,
                    "url": f"/manifesto/promise/{promise.code}",
                },
            }
            for document, promise in rows[offset : offset + limit]
        ],
    }


# --------------------------------------------------------------------------
# Admin payloads
# --------------------------------------------------------------------------
class ElectionIn(BaseModel):
    state_code: str
    name: str = Field(..., min_length=4, max_length=200)
    name_hi: str = ""
    year: int = Field(..., ge=1950, le=2100)
    house: str = "assembly"
    election_date: Optional[date] = None
    result_date: Optional[date] = None
    source_url: str = ""
    is_published: bool = False


class ManifestoIn(BaseModel):
    election_slug: str
    party_name: str = Field(..., min_length=2, max_length=200)
    party_code: str = ""
    title: str = Field(..., min_length=4, max_length=300)
    title_hi: str = ""
    published_on: Optional[date] = None
    total_pages: Optional[int] = None
    source_url: str = Field(..., min_length=8)
    source_note: str = ""
    is_published: bool = False


class PromiseIn(BaseModel):
    manifesto_id: str
    title: str = Field(..., min_length=6, max_length=300)
    title_hi: str = ""
    promise_text: str = Field(..., min_length=10)
    promise_text_hi: str = ""
    manifesto_page: str = ""
    manifesto_page_url: str = ""
    department: str = ""
    category: str = "Other"
    tags: list[str] = Field(default_factory=list)
    sort_order: int = 0


class PromiseUpdate(BaseModel):
    title: Optional[str] = None
    title_hi: Optional[str] = None
    promise_text: Optional[str] = None
    promise_text_hi: Optional[str] = None
    manifesto_page: Optional[str] = None
    manifesto_page_url: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class RtiIn(BaseModel):
    subject: str = ""
    public_authority: str = Field(..., min_length=3, max_length=240)
    department: str = ""
    pio_designation: str = ""
    application_number: str = ""
    prepared_on: Optional[date] = None
    filed_on: Optional[date] = None
    application_url: str = ""
    filing_proof_url: str = ""
    notes: str = ""
    is_published: bool = False


class RtiUpdate(BaseModel):
    subject: Optional[str] = None
    public_authority: Optional[str] = None
    department: Optional[str] = None
    pio_designation: Optional[str] = None
    application_number: Optional[str] = None
    prepared_on: Optional[date] = None
    filed_on: Optional[date] = None
    reply_due_on: Optional[date] = None
    status: Optional[str] = None
    application_url: Optional[str] = None
    filing_proof_url: Optional[str] = None
    notes: Optional[str] = None
    is_published: Optional[bool] = None


class QuestionIn(BaseModel):
    number: Optional[int] = None
    question_text: str = Field(..., min_length=5)
    question_text_hi: str = ""


class AnswerIn(BaseModel):
    answer_text: str = ""
    answer_status: str = "answered"
    response_id: Optional[str] = None
    supporting_document_id: Optional[str] = None


class ResponseIn(BaseModel):
    received_on: Optional[date] = None
    reply_dated: Optional[date] = None
    replying_authority: str = Field(..., min_length=3, max_length=240)
    department: str = ""
    reference_number: str = ""
    # Required: a reply nobody can read is a claim about a reply, not a record.
    document_url: str = Field(..., min_length=4)
    page_count: Optional[int] = None
    summary: str = ""
    is_appeal_reply: bool = False
    # Whether the reply answered everything asked, which decides the
    # application's status. A factual distinction, recorded by the operator who
    # read it rather than guessed at here.
    is_partial: bool = False
    is_published: bool = True


class DocumentIn(BaseModel):
    title: str = Field(..., min_length=4, max_length=300)
    kind: str = "other"
    issuing_authority: str = Field(..., min_length=2, max_length=240)
    department: str = ""
    reference_number: str = ""
    issued_on: Optional[date] = None
    file_url: str = ""
    source_url: str = ""
    source_note: str = ""
    obtained_via: str = "rti"
    page_count: Optional[int] = None
    is_published: bool = False


class EvidenceIn(BaseModel):
    statement: str = Field(..., min_length=10)
    statement_hi: str = ""
    locator: str = ""
    document_id: Optional[str] = None
    rti_question_id: Optional[str] = None
    recorded_on: Optional[date] = None
    sort_order: int = 0
    is_published: bool = True


class AssessmentIn(BaseModel):
    status: str
    # Long enough to be a reason. A one-word rationale next to a public finding
    # about a government is not a rationale.
    rationale: str = Field(..., min_length=30)
    method_note: str = ""
    sources: list[dict] = Field(default_factory=list)
    assessed_on: Optional[date] = None
    is_published: bool = True


# --------------------------------------------------------------------------
# Admin: elections, manifestos
# --------------------------------------------------------------------------
@router.post("/admin/manifesto/elections")
async def create_election(
    payload: ElectionIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.publish")),
    session: AsyncSession = Depends(get_session),
):
    state_code = payload.state_code.upper()
    if state_code not in VALID_STATE_CODES:
        raise HTTPException(status_code=400, detail=f"Unknown state code: {payload.state_code}")

    slug = slugify(f"{STATES_BY_CODE[state_code].slug}-{payload.year}")
    if (
        await session.execute(select(ManifestoElection).where(ManifestoElection.slug == slug))
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"{slug} already exists")

    election = ManifestoElection(
        slug=slug,
        state_code=state_code,
        name=payload.name.strip(),
        name_hi=payload.name_hi.strip(),
        year=payload.year,
        house=payload.house,
        election_date=payload.election_date,
        result_date=payload.result_date,
        source_url=payload.source_url.strip(),
        is_published=payload.is_published,
    )
    session.add(election)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="manifesto_election",
        entity_id=election.slug,
        summary=f"Added election: {election.name}",
        source_url=election.source_url or None,
        is_public=True,
        request=request,
    )
    return service.election_dict(election)


@router.post("/admin/manifesto/manifestos")
async def create_manifesto(
    payload: ManifestoIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.publish")),
    session: AsyncSession = Depends(get_session),
):
    election = await _election_or_404(session, payload.election_slug)
    slug = slugify(f"{election.slug}-{payload.party_code or payload.party_name}")
    if (await session.execute(select(Manifesto).where(Manifesto.slug == slug))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"{slug} already exists")

    manifesto = Manifesto(
        slug=slug,
        election_id=election.id,
        party_code=payload.party_code.upper(),
        party_name=payload.party_name.strip(),
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        published_on=payload.published_on,
        total_pages=payload.total_pages,
        source_url=payload.source_url.strip(),
        source_note=payload.source_note.strip(),
        is_published=payload.is_published,
    )
    session.add(manifesto)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="manifesto",
        entity_id=manifesto.slug,
        summary=f"Added manifesto: {manifesto.title} ({manifesto.party_name})",
        source_url=manifesto.source_url,
        is_public=True,
        request=request,
    )
    return service.manifesto_dict(manifesto)


# --------------------------------------------------------------------------
# Admin: promises
# --------------------------------------------------------------------------
@router.get("/admin/manifesto/promises")
async def admin_list_promises(
    election: Optional[str] = None,
    include_drafts: bool = True,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ManifestoPromise).order_by(ManifestoPromise.code).limit(500)
    if election:
        stmt = stmt.where(
            ManifestoPromise.election_id == (await _election_or_404(session, election)).id
        )
    if not include_drafts:
        stmt = stmt.where(ManifestoPromise.is_published.is_(True))
    rows = (await session.execute(stmt)).scalars()
    return [
        {**service.promise_dict(p), "isPublished": p.is_published, "id": p.id} for p in rows
    ]


@router.post("/admin/manifesto/promises")
async def create_promise(
    payload: PromiseIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    manifesto = (
        await session.execute(select(Manifesto).where(Manifesto.id == payload.manifesto_id))
    ).scalar_one_or_none()
    if manifesto is None:
        raise HTTPException(status_code=404, detail="Manifesto not found")
    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.id == manifesto.election_id)
        )
    ).scalar_one()

    promise = ManifestoPromise(
        code=await _next_code(session, election, "P"),
        election_id=election.id,
        manifesto_id=manifesto.id,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        promise_text=payload.promise_text.strip(),
        promise_text_hi=payload.promise_text_hi.strip(),
        manifesto_page=payload.manifesto_page.strip(),
        manifesto_page_url=payload.manifesto_page_url.strip(),
        department=payload.department.strip(),
        category=payload.category.strip() or "Other",
        tags=payload.tags,
        sort_order=payload.sort_order,
        status=DEFAULT_PROMISE_STATUS,
        is_published=False,
    )
    session.add(promise)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Promise recorded from {manifesto.title}, page {promise.manifesto_page or '-'}",
        source_url=manifesto.source_url or None,
        is_public=True,
        request=request,
    )
    return {**service.promise_dict(promise), "id": promise.id, "isPublished": promise.is_published}


@router.put("/admin/manifesto/promises/{promise_id}")
async def update_promise(
    promise_id: str,
    payload: PromiseUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    promise = await _promise_or_404(session, promise_id)
    fields = payload.model_dump(exclude_unset=True)

    # Publishing is a separate permission from editing, for the same reason the
    # representative store splits them: putting a claim about a government in
    # front of the public is a different act from typing it up.
    if "is_published" in fields and not admin.can("manifesto.publish"):
        raise HTTPException(
            status_code=403, detail="Publishing a promise needs the manifesto.publish permission"
        )

    before = {key: getattr(promise, key) for key in fields}
    for key, value in fields.items():
        setattr(promise, key, value)
    changes = audit.diff(before, fields)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Promise record updated ({', '.join(sorted(changes))})",
        changes=changes,
        is_public=True,
        request=request,
    )
    if promise.is_published:
        await _index(session, promise)
    return {**service.promise_dict(promise), "id": promise.id, "isPublished": promise.is_published}


async def _index(session: AsyncSession, promise: ManifestoPromise) -> None:
    await search.index(
        session,
        entity_type="manifesto_promise",
        entity_id=promise.code,
        title=f"{promise.code}: {promise.title}",
        subtitle=f"Manifesto promise - {promise.department or 'department not stated'}",
        body=promise.promise_text,
        keywords=[promise.category, promise.department, *(promise.tags or [])],
        is_published=promise.is_published,
        url_path=f"/manifesto/promise/{promise.code}",
    )


# --------------------------------------------------------------------------
# Admin: RTI applications, questions, replies
# --------------------------------------------------------------------------
@router.post("/admin/manifesto/promises/{promise_id}/rti")
async def create_rti(
    promise_id: str,
    payload: RtiIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    promise = await _promise_or_404(session, promise_id)
    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.id == promise.election_id)
        )
    ).scalar_one()

    rti = RtiApplication(
        code=await _next_code(session, election, "R"),
        promise_id=promise.id,
        subject=payload.subject.strip(),
        public_authority=payload.public_authority.strip(),
        department=payload.department.strip(),
        pio_designation=payload.pio_designation.strip(),
        application_number=payload.application_number.strip(),
        prepared_on=payload.prepared_on,
        filed_on=payload.filed_on,
        reply_due_on=(payload.filed_on + timedelta(days=RTI_REPLY_DAYS)) if payload.filed_on else None,
        status="filed" if payload.filed_on else "drafted",
        application_url=payload.application_url.strip(),
        filing_proof_url=payload.filing_proof_url.strip(),
        notes=payload.notes.strip(),
        is_published=payload.is_published,
    )
    session.add(rti)
    await session.flush()

    # The promise reflects the wait as soon as an RTI is filed: "awaiting reply"
    # is the truthful status of a promise nobody has an answer about yet, and
    # leaving it at "not established" would understate the work in progress.
    if rti.filed_on and promise.status == DEFAULT_PROMISE_STATUS:
        promise.status = "rti_reply_awaited"

    await audit.record(
        session,
        actor=admin,
        action="rti_filed" if rti.filed_on else "rti_prepared",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=(
            f"RTI {rti.code} filed with {rti.public_authority}"
            if rti.filed_on
            else f"RTI {rti.code} drafted for {rti.public_authority}"
        ),
        is_public=True,
        request=request,
    )
    return service.rti_dict(rti, promise=promise)


@router.put("/admin/manifesto/rti/{rti_id}")
async def update_rti(
    rti_id: str,
    payload: RtiUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    rti = (
        await session.execute(select(RtiApplication).where(RtiApplication.id == rti_id))
    ).scalar_one_or_none()
    if rti is None:
        raise HTTPException(status_code=404, detail="RTI application not found")
    promise = await _promise_or_404(session, rti.promise_id)

    fields = payload.model_dump(exclude_unset=True)
    if fields.get("status") and fields["status"] not in RTI_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown RTI status: {fields['status']}")

    before = {key: getattr(rti, key) for key in fields}
    for key, value in fields.items():
        setattr(rti, key, value)
    if fields.get("filed_on") and not rti.reply_due_on:
        rti.reply_due_on = rti.filed_on + timedelta(days=RTI_REPLY_DAYS)
        if rti.status == "drafted":
            rti.status = "filed"

    changes = audit.diff(before, fields)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    await audit.record(
        session,
        actor=admin,
        action="rti_filed" if "filed_on" in changes else "update",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"RTI {rti.code} updated ({', '.join(sorted(changes))})",
        changes=changes,
        is_public=True,
        request=request,
    )
    return service.rti_dict(rti, promise=promise)


@router.post("/admin/manifesto/rti/{rti_id}/questions")
async def add_question(
    rti_id: str,
    payload: QuestionIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    rti = (
        await session.execute(select(RtiApplication).where(RtiApplication.id == rti_id))
    ).scalar_one_or_none()
    if rti is None:
        raise HTTPException(status_code=404, detail="RTI application not found")
    promise = await _promise_or_404(session, rti.promise_id)

    number = payload.number
    if number is None:
        highest = (
            await session.execute(
                select(func.max(RtiQuestion.number)).where(RtiQuestion.rti_id == rti.id)
            )
        ).scalar_one()
        number = (highest or 0) + 1

    question = RtiQuestion(
        rti_id=rti.id,
        number=number,
        question_text=payload.question_text.strip(),
        question_text_hi=payload.question_text_hi.strip(),
        answer_status="awaited",
    )
    session.add(question)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Question {number} added to RTI {rti.code}",
        is_public=True,
        request=request,
    )
    return service.question_dict(question)


@router.put("/admin/manifesto/questions/{question_id}/answer")
async def record_answer(
    question_id: str,
    payload: AnswerIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Record the government's answer to one question, in its own words."""
    question = (
        await session.execute(select(RtiQuestion).where(RtiQuestion.id == question_id))
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if payload.answer_status not in ANSWER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown answer status: {payload.answer_status}")

    rti = (
        await session.execute(select(RtiApplication).where(RtiApplication.id == question.rti_id))
    ).scalar_one()
    promise = await _promise_or_404(session, rti.promise_id)

    before = {
        "answer_text": question.answer_text,
        "answer_status": question.answer_status,
    }
    question.answer_text = payload.answer_text.strip()
    question.answer_status = payload.answer_status
    question.response_id = payload.response_id or question.response_id
    question.supporting_document_id = (
        payload.supporting_document_id or question.supporting_document_id
    )

    await audit.record(
        session,
        actor=admin,
        action="reply_received",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Answer recorded for question {question.number} of RTI {rti.code}",
        changes=audit.diff(before, {"answer_text": question.answer_text, "answer_status": question.answer_status}),
        is_public=True,
        request=request,
    )
    document = (
        (
            await session.execute(
                select(GovernmentDocument).where(
                    GovernmentDocument.id == question.supporting_document_id
                )
            )
        ).scalar_one_or_none()
        if question.supporting_document_id
        else None
    )
    return service.question_dict(question, document=document)


@router.post("/admin/manifesto/rti/{rti_id}/responses")
async def record_response(
    rti_id: str,
    payload: ResponseIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Log a reply received against an application, with the original document."""
    rti = (
        await session.execute(select(RtiApplication).where(RtiApplication.id == rti_id))
    ).scalar_one_or_none()
    if rti is None:
        raise HTTPException(status_code=404, detail="RTI application not found")
    promise = await _promise_or_404(session, rti.promise_id)

    response = RtiResponse(
        rti_id=rti.id,
        received_on=payload.received_on,
        reply_dated=payload.reply_dated,
        replying_authority=payload.replying_authority.strip(),
        department=payload.department.strip(),
        reference_number=payload.reference_number.strip(),
        document_url=payload.document_url.strip(),
        page_count=payload.page_count,
        summary=payload.summary.strip(),
        is_appeal_reply=payload.is_appeal_reply,
        is_published=payload.is_published,
    )
    session.add(response)
    rti.status = "partial_reply" if payload.is_partial else "reply_received"

    # A reply exists, so the promise is no longer "awaiting" one. It is not
    # assessed either: that needs a person to read the reply, which is the next
    # step and a separate permission.
    if promise.status == "rti_reply_awaited":
        promise.status = "information_insufficient" if payload.is_partial else DEFAULT_PROMISE_STATUS

    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="reply_received",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=(
            f"Reply received from {response.replying_authority} against RTI {rti.code}"
            + (f", ref {response.reference_number}" if response.reference_number else "")
        ),
        source_url=response.document_url,
        is_public=True,
        request=request,
    )
    return service.response_dict(response, rti=rti)


# --------------------------------------------------------------------------
# Admin: documents and evidence
# --------------------------------------------------------------------------
@router.post("/admin/manifesto/promises/{promise_id}/documents")
async def add_document(
    promise_id: str,
    payload: DocumentIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    promise = await _promise_or_404(session, promise_id)
    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.id == promise.election_id)
        )
    ).scalar_one()

    if payload.kind not in DOCUMENT_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown document kind: {payload.kind}")
    if not (payload.file_url.strip() or payload.source_url.strip()):
        raise HTTPException(
            status_code=400,
            detail="A document needs a link to the file itself -- either uploaded here or on the issuing authority's site.",
        )
    if not (payload.source_note.strip() or payload.source_url.strip()):
        raise HTTPException(
            status_code=400,
            detail="Say where this copy came from. A record with no provenance cannot be published as evidence.",
        )

    is_primary, publisher = citations.classify_source(payload.source_url or payload.file_url)
    document = GovernmentDocument(
        code=await _next_code(session, election, "D"),
        promise_id=promise.id,
        title=payload.title.strip(),
        kind=payload.kind,
        issuing_authority=payload.issuing_authority.strip(),
        department=payload.department.strip(),
        reference_number=payload.reference_number.strip(),
        issued_on=payload.issued_on,
        file_url=payload.file_url.strip(),
        source_url=payload.source_url.strip(),
        source_note=payload.source_note.strip(),
        obtained_via=payload.obtained_via,
        is_primary_source=is_primary,
        publisher=publisher or "",
        page_count=payload.page_count,
        is_published=payload.is_published,
    )
    session.add(document)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="document_added",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"{DOCUMENT_KINDS[document.kind]} added: {document.title}",
        source_url=document.source_url or document.file_url or None,
        is_public=True,
        request=request,
    )
    return service.document_dict(document)


@router.post("/admin/manifesto/promises/{promise_id}/evidence")
async def add_evidence(
    promise_id: str,
    payload: EvidenceIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Record what a specific document or answer states.

    Requires a link to the record it describes. An evidence row with nothing
    behind it is an assertion, and this table exists precisely so assertions
    cannot enter the chain unattached.
    """
    promise = await _promise_or_404(session, promise_id)
    if not (payload.document_id or payload.rti_question_id):
        raise HTTPException(
            status_code=400,
            detail="Attach the record this statement comes from -- a document or an RTI answer.",
        )

    item = PromiseEvidence(
        promise_id=promise.id,
        document_id=payload.document_id,
        rti_question_id=payload.rti_question_id,
        statement=payload.statement.strip(),
        statement_hi=payload.statement_hi.strip(),
        locator=payload.locator.strip(),
        recorded_on=payload.recorded_on,
        sort_order=payload.sort_order,
        is_published=payload.is_published,
    )
    session.add(item)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="evidence_added",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Evidence added: {item.statement[:120]}",
        is_public=True,
        request=request,
    )
    return service.evidence_dict(item)


# --------------------------------------------------------------------------
# Admin: assessment -- the gated one
# --------------------------------------------------------------------------
@router.post("/admin/manifesto/promises/{promise_id}/assessment")
async def create_assessment(
    promise_id: str,
    payload: AssessmentIn,
    request: Request,
    admin: Principal = Depends(require_permission("manifesto.publish")),
    session: AsyncSession = Depends(get_session),
):
    """Publish a conclusion about one promise. The most consequential write here.

    Two gates, and neither is negotiable:

    * Any status other than the two that assert nothing needs `sources` -- the
      evidence and document ids it is drawn from. This is the difference between
      an evidence database and a blog.
    * The previous assessment is superseded, not overwritten, and the change is
      audited publicly. A platform that quietly rewrites its own published
      finding has no standing to ask a government not to.
    """
    promise = await _promise_or_404(session, promise_id)
    if payload.status not in PROMISE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Status must be one of: {list(PROMISE_STATUSES)}"
        )
    if payload.status not in STATUSES_WITHOUT_EVIDENCE and not payload.sources:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{status_label(payload.status)}' is a factual claim about implementation, so it "
                "cannot be published without the records it rests on. Attach the evidence or "
                "document ids in `sources`, or use 'Status not established from available records'."
            ),
        )

    previous = (
        await session.execute(
            select(PromiseAssessment).where(
                PromiseAssessment.promise_id == promise.id,
                PromiseAssessment.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if previous is not None:
        previous.is_current = False

    assessment = PromiseAssessment(
        promise_id=promise.id,
        status=payload.status,
        rationale=payload.rationale.strip(),
        method_note=payload.method_note.strip(),
        sources=payload.sources,
        assessed_on=payload.assessed_on or date.today(),
        assessed_by=admin.id,
        version=(previous.version + 1) if previous else 1,
        is_current=True,
        is_published=payload.is_published,
    )
    session.add(assessment)

    before_status = promise.status
    promise.status = payload.status
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="status_changed",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=(
            f"Assessment v{assessment.version} published: "
            f"{status_label(before_status)} -> {status_label(payload.status)}"
        ),
        changes={"status": {"before": before_status, "after": payload.status}},
        is_public=True,
        request=request,
    )
    if promise.is_published:
        await _index(session, promise)
    return {
        **(service.assessment_dict(assessment) or {}),
        "promise": {"code": promise.code, "status": service.status_dict(promise.status)},
    }
