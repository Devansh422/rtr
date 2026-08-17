"""Serialisation, the derived timeline, and the dashboard counters.

Kept out of the router because two of the three are rules rather than plumbing:

* `timeline()` DERIVES the promise's history from the records themselves instead
  of storing it. A stored timeline is a second copy of the truth that drifts from
  the first one silently -- somebody backdates an RTI, the timeline keeps the old
  date, and the page now shows a chronology that the documents underneath it
  contradict. Deriving it means the timeline cannot disagree with the evidence.

* `dashboard()` counts rows. Every number on the public dashboard is a `SELECT
  count(*)` over published records, so there is no path by which a figure on that
  page is a number somebody typed.
"""

from datetime import date
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.manifesto.models import (
    ANSWER_STATUSES,
    DOCUMENT_KINDS,
    PROMISE_STATUS_MEANINGS,
    PROMISE_STATUSES,
    RTI_ANSWERED_STATUSES,
    RTI_STATUSES,
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


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def promise_url(promise: ManifestoPromise, election: Optional[ManifestoElection] = None) -> str:
    """The canonical page for a promise.

    `/manifesto/uttarakhand/2022/UK-2022-P001` when the election is to hand: a
    path a reader can make sense of, and one that already has room for the second
    state without a redirect. `/manifesto/promise/UK-2022-P001` is the short form
    the frontend also routes, for the places (search results, share links typed
    from a printed code) where only the code is known.
    """
    if election is None:
        return f"/manifesto/promise/{promise.code}"
    state = election.slug.rsplit("-", 1)[0]
    return f"/manifesto/{state}/{election.year}/{promise.code}"


# --------------------------------------------------------------------------
# Serialisers
# --------------------------------------------------------------------------
def election_dict(election: ManifestoElection) -> dict:
    return {
        "id": election.id,
        "slug": election.slug,
        "state": election.state_code,
        "name": election.name,
        "nameHi": election.name_hi,
        "year": election.year,
        "house": election.house,
        "electionDate": _iso(election.election_date),
        "resultDate": _iso(election.result_date),
        "sourceUrl": election.source_url or None,
        "url": f"/manifesto/{election.slug}",
    }


def manifesto_dict(manifesto: Optional[Manifesto]) -> Optional[dict]:
    if manifesto is None:
        return None
    return {
        "id": manifesto.id,
        "slug": manifesto.slug,
        "party": manifesto.party_name,
        "partyCode": manifesto.party_code or None,
        "title": manifesto.title,
        "titleHi": manifesto.title_hi,
        "publishedOn": _iso(manifesto.published_on),
        "totalPages": manifesto.total_pages,
        "sourceUrl": manifesto.source_url or None,
        "sourceNote": manifesto.source_note,
    }


def status_dict(key: str) -> dict:
    """A status is never returned as a bare string.

    The label and the meaning travel with it, so no page can render the badge
    without the sentence that says what it is and is not claiming.
    """
    return {
        "key": key,
        "label": status_label(key),
        "meaning": PROMISE_STATUS_MEANINGS.get(key, ""),
    }


def promise_dict(
    promise: ManifestoPromise,
    *,
    election: Optional[ManifestoElection] = None,
    rti: Optional[RtiApplication] = None,
    evidence_count: int = 0,
    document_count: int = 0,
) -> dict:
    """Row shape for the listing. No assessment prose here -- see the detail view."""
    return {
        "id": promise.id,
        "code": promise.code,
        "title": promise.title,
        "titleHi": promise.title_hi,
        "promiseText": promise.promise_text,
        "department": promise.department or "Not stated",
        "category": promise.category,
        "tags": promise.tags or [],
        "manifestoPage": promise.manifesto_page,
        "status": status_dict(promise.status),
        "rti": {
            "code": rti.code if rti else None,
            "status": rti.status if rti else None,
            "statusLabel": RTI_STATUSES.get(rti.status, "Not filed yet") if rti else "Not filed yet",
            "filedOn": _iso(rti.filed_on) if rti else None,
        },
        "evidenceCount": evidence_count,
        "documentCount": document_count,
        "hasEvidence": evidence_count > 0 or document_count > 0,
        "updatedAt": _iso(promise.updated_at),
        "url": promise_url(promise, election),
    }


def promise_ref(
    promise: ManifestoPromise, election: Optional[ManifestoElection] = None
) -> dict:
    """The short reference to a promise, as embedded in RTI/reply/document rows."""
    return {
        "code": promise.code,
        "title": promise.title,
        "status": status_dict(promise.status),
        "url": promise_url(promise, election),
    }


def rti_dict(
    rti: RtiApplication,
    *,
    promise: Optional[ManifestoPromise] = None,
    election: Optional[ManifestoElection] = None,
) -> dict:
    return {
        "id": rti.id,
        "code": rti.code,
        "subject": rti.subject,
        "publicAuthority": rti.public_authority,
        "department": rti.department,
        "pioDesignation": rti.pio_designation,
        "applicationNumber": rti.application_number or None,
        "preparedOn": _iso(rti.prepared_on),
        "filedOn": _iso(rti.filed_on),
        "replyDueOn": _iso(rti.reply_due_on),
        "status": rti.status,
        "statusLabel": RTI_STATUSES.get(rti.status, rti.status),
        "applicationUrl": rti.application_url or None,
        "filingProofUrl": rti.filing_proof_url or None,
        "notes": rti.notes,
        "promise": promise_ref(promise, election) if promise else None,
    }


def response_dict(response: RtiResponse, *, rti: Optional[RtiApplication] = None) -> dict:
    return {
        "id": response.id,
        "rtiId": response.rti_id,
        "rtiCode": rti.code if rti else None,
        "receivedOn": _iso(response.received_on),
        "replyDated": _iso(response.reply_dated),
        "replyingAuthority": response.replying_authority,
        "department": response.department,
        "referenceNumber": response.reference_number or None,
        "documentUrl": response.document_url or None,
        "pageCount": response.page_count,
        "summary": response.summary,
        "isAppealReply": response.is_appeal_reply,
    }


def question_dict(
    question: RtiQuestion, *, document: Optional[GovernmentDocument] = None
) -> dict:
    return {
        "id": question.id,
        "number": question.number,
        "question": question.question_text,
        "questionHi": question.question_text_hi,
        "answer": question.answer_text or None,
        "answerStatus": question.answer_status,
        "answerStatusLabel": ANSWER_STATUSES.get(question.answer_status, question.answer_status),
        "responseId": question.response_id,
        "supportingDocument": document_dict(document) if document else None,
    }


def document_dict(document: GovernmentDocument) -> dict:
    return {
        "id": document.id,
        "code": document.code,
        "title": document.title,
        "kind": document.kind,
        "kindLabel": DOCUMENT_KINDS.get(document.kind, document.kind),
        "issuingAuthority": document.issuing_authority,
        "department": document.department,
        "referenceNumber": document.reference_number or None,
        "issuedOn": _iso(document.issued_on),
        "fileUrl": document.file_url or None,
        "sourceUrl": document.source_url or None,
        "sourceNote": document.source_note,
        "obtainedVia": document.obtained_via,
        "isPrimarySource": document.is_primary_source,
        "publisher": document.publisher or None,
        "pageCount": document.page_count,
        "uploadedAt": _iso(document.uploaded_at),
        "promiseId": document.promise_id,
    }


def evidence_dict(
    item: PromiseEvidence,
    *,
    document: Optional[GovernmentDocument] = None,
    question: Optional[RtiQuestion] = None,
) -> dict:
    return {
        "id": item.id,
        "statement": item.statement,
        "statementHi": item.statement_hi,
        "locator": item.locator,
        "recordedOn": _iso(item.recorded_on),
        "document": document_dict(document) if document else None,
        "rtiQuestion": (
            {"id": question.id, "number": question.number, "question": question.question_text}
            if question
            else None
        ),
    }


def assessment_dict(assessment: Optional[PromiseAssessment]) -> Optional[dict]:
    if assessment is None:
        return None
    return {
        "id": assessment.id,
        "status": status_dict(assessment.status),
        "rationale": assessment.rationale,
        "methodNote": assessment.method_note,
        "sources": assessment.sources or [],
        "assessedOn": _iso(assessment.assessed_on),
        "version": assessment.version,
        "isCurrent": assessment.is_current,
    }


# --------------------------------------------------------------------------
# Derived timeline
# --------------------------------------------------------------------------
def timeline(
    *,
    promise: ManifestoPromise,
    manifesto: Optional[Manifesto],
    applications: Iterable[RtiApplication],
    responses: Iterable[RtiResponse],
    documents: Iterable[GovernmentDocument],
    evidence: Iterable[PromiseEvidence],
    assessment: Optional[PromiseAssessment],
) -> list[dict]:
    """The eight stages of the chain, each with the date its record carries.

    A stage with no record is returned as `reached: false` rather than omitted.
    Showing the gaps is the point: "RTI filed 12 Jan, reply -- none" is the most
    important thing this module can tell a reader, and a timeline that only
    listed what happened would quietly drop it.
    """
    applications = list(applications)
    responses = list(responses)
    documents = list(documents)
    evidence = list(evidence)

    def earliest(values: Iterable[Optional[date]]) -> Optional[date]:
        real = [v for v in values if v]
        return min(real) if real else None

    filed_on = earliest(a.filed_on for a in applications)
    prepared_on = earliest(a.prepared_on for a in applications)
    replied_on = earliest(r.received_on or r.reply_dated for r in responses)
    documents_on = earliest(d.uploaded_at.date() if d.uploaded_at else None for d in documents)
    evidence_on = earliest(e.recorded_on or (e.created_at.date() if e.created_at else None) for e in evidence)

    stages = [
        {
            "key": "promise",
            "label": "Manifesto promise",
            "date": _iso(manifesto.published_on if manifesto else None),
            "reached": True,
            "detail": (
                f"Page {promise.manifesto_page} of {manifesto.title}"
                if manifesto and promise.manifesto_page
                else (manifesto.title if manifesto else "")
            ),
        },
        {
            "key": "rti_prepared",
            "label": "RTI prepared",
            "date": _iso(prepared_on),
            "reached": bool(applications),
            "detail": f"{len(applications)} application(s) drafted" if applications else "",
        },
        {
            "key": "rti_filed",
            "label": "RTI filed",
            "date": _iso(filed_on),
            "reached": bool(filed_on),
            "detail": ", ".join(a.public_authority for a in applications if a.filed_on)[:200],
        },
        {
            "key": "reply",
            "label": "Government reply",
            "date": _iso(replied_on),
            "reached": bool(responses),
            "detail": ", ".join(r.replying_authority for r in responses)[:200],
        },
        {
            "key": "documents",
            "label": "Documents received",
            "date": _iso(documents_on),
            "reached": bool(documents),
            "detail": f"{len(documents)} official record(s)" if documents else "",
        },
        {
            "key": "evidence",
            "label": "Evidence published",
            "date": _iso(evidence_on),
            "reached": bool(evidence),
            "detail": f"{len(evidence)} statement(s) drawn from the records" if evidence else "",
        },
        {
            "key": "assessment",
            "label": "Assessment",
            "date": _iso(assessment.assessed_on) if assessment else None,
            "reached": assessment is not None,
            "detail": assessment.method_note[:200] if assessment else "",
        },
        {
            "key": "status",
            "label": "Current status",
            "date": _iso(assessment.assessed_on) if assessment else None,
            "reached": True,
            "detail": status_label(promise.status),
        },
    ]
    return stages


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
async def dashboard(session: AsyncSession, election_id: Optional[str] = None) -> dict:
    """Every figure on the public dashboard, counted from published rows.

    Scoped to published records only, so the dashboard and the pages a visitor
    can actually open describe the same body of work. Draft research in progress
    is not a number the public is shown.
    """
    promise_filter = [ManifestoPromise.is_published.is_(True)]
    if election_id:
        promise_filter.append(ManifestoPromise.election_id == election_id)

    async def count(stmt) -> int:
        return (await session.execute(stmt)).scalar_one() or 0

    promise_ids = select(ManifestoPromise.id).where(*promise_filter)

    total_promises = await count(
        select(func.count()).select_from(ManifestoPromise).where(*promise_filter)
    )

    by_status_rows = (
        await session.execute(
            select(ManifestoPromise.status, func.count())
            .where(*promise_filter)
            .group_by(ManifestoPromise.status)
        )
    ).all()
    by_status = {key: 0 for key in PROMISE_STATUSES}
    for key, value in by_status_rows:
        by_status[key] = value

    rtis_filed = await count(
        select(func.count())
        .select_from(RtiApplication)
        .where(
            RtiApplication.is_published.is_(True),
            RtiApplication.filed_on.is_not(None),
            RtiApplication.promise_id.in_(promise_ids),
        )
    )
    replies_received = await count(
        select(func.count())
        .select_from(RtiApplication)
        .where(
            RtiApplication.is_published.is_(True),
            RtiApplication.status.in_(list(RTI_ANSWERED_STATUSES)),
            RtiApplication.promise_id.in_(promise_ids),
        )
    )
    documents = await count(
        select(func.count())
        .select_from(GovernmentDocument)
        .where(
            GovernmentDocument.is_published.is_(True),
            GovernmentDocument.promise_id.in_(promise_ids),
        )
    )
    evidence_items = await count(
        select(func.count())
        .select_from(PromiseEvidence)
        .where(
            PromiseEvidence.is_published.is_(True),
            PromiseEvidence.promise_id.in_(promise_ids),
        )
    )
    assessed = await count(
        select(func.count())
        .select_from(PromiseAssessment)
        .where(
            PromiseAssessment.is_published.is_(True),
            PromiseAssessment.is_current.is_(True),
            PromiseAssessment.promise_id.in_(promise_ids),
        )
    )

    return {
        "totalPromises": total_promises,
        "rtisFiled": rtis_filed,
        "repliesReceived": replies_received,
        # Filed minus replied, floored at zero: a reply can arrive against an
        # application whose filing date was never recorded, and a negative
        # "awaited" on a public dashboard destroys confidence in every other
        # number next to it.
        "repliesAwaited": max(0, rtis_filed - replies_received),
        "documentsPublished": documents,
        "evidenceItems": evidence_items,
        "promisesAssessed": assessed,
        "promisesNotYetAssessed": max(0, total_promises - assessed),
        "byStatus": [
            {**status_dict(key), "count": by_status.get(key, 0)} for key in PROMISE_STATUSES
        ],
        "note": (
            "Every figure here is counted from published records at the moment you "
            "loaded this page. Nothing on this dashboard is entered by hand."
        ),
    }
