"""Manifesto accountability: what was promised, what the official record says, and
the gap between them -- with the documents attached.

WHAT THIS MODULE IS. Not a scorecard. A public evidence database whose unit is a
documentary chain:

    manifesto promise -> RTI application -> question -> government answer
        -> official document -> evidence -> assessment -> status

Every link in that chain is a row here, and every row that makes a factual claim
carries the record it rests on. A reader who disagrees with the assessment at the
end must be able to walk back to the original PDF and check it themselves. If
they cannot, this module has failed at the only thing it exists to do.

THE THREE LAYERS ARE SEPARATE TABLES ON PURPOSE. §1 and §7 of
IMPLEMENTATION_PLAN.md forbid presenting an inference as a fact, and the surest
way to enforce that is to make them different objects that the API returns
separately and the page renders in different blocks:

  1. `ManifestoPromise.promise_text` -- what the manifesto says. Quoted, never
     paraphrased, with the page number and a link to the PDF.
  2. `RtiQuestion.answer_text`, `RtiResponse`, `GovernmentDocument` -- what the
     government's own records say. Reproduced, with the reply's reference number
     and the original file.
  3. `PromiseAssessment` -- what this platform concludes from (1) and (2), signed,
     dated, and refusing to save without the records it is drawn from.

Nothing merges those three into one "verdict" field, because a merged field is
one careless edit away from publishing an opinion as a government record.

NAMING. Tables that would otherwise take a generic name in a schema of forty-odd
tables are prefixed (`manifesto_promises`, `manifesto_evidence`); the ones whose
names are already unambiguous are not (`rti_applications`, `rti_questions`,
`rti_responses`, `government_documents`, `promise_assessments`).

FUTURE STATES. The hierarchy is state -> election -> party -> manifesto ->
promise from the first migration, so a second state is data entry rather than a
schema change. The UI deliberately exposes only Uttarakhand 2022 for now: an
election selector listing states with nothing behind them advertises emptiness.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow

# --------------------------------------------------------------------------
# Fixed vocabularies
# --------------------------------------------------------------------------
# Static Python, not editable rows, for the reason given in core/permissions.py:
# these keys appear in URLs, in filters and in the assessment gate below, and a
# status that can be renamed from an admin screen is a status that can silently
# change what a published page asserts.
#
# The wording is the point. Every label describes the STATE OF THE RECORD, not
# the character of anyone's conduct: "could not be established from available
# records" is a statement this platform can defend, "the government lied" is
# not, and the difference is the whole editorial policy of the module (§23 of
# the brief, §1 of the plan).
PROMISE_STATUSES: dict[str, str] = {
    "fulfilled": "Fulfilled",
    "partially_fulfilled": "Partially fulfilled",
    "under_implementation": "Under implementation",
    "information_insufficient": "Information insufficient",
    "rti_reply_awaited": "RTI reply awaited",
    "not_established": "Status not established from available records",
}

# Longer forms, shown next to the badge so a reader is never left to guess what a
# two-word status is claiming.
PROMISE_STATUS_MEANINGS: dict[str, str] = {
    "fulfilled": (
        "Official records establish that what was promised has been delivered."
    ),
    "partially_fulfilled": (
        "Official records establish that part of what was promised has been "
        "delivered. The records for the remainder are shown alongside."
    ),
    "under_implementation": (
        "Official records show work formally under way -- an order issued, funds "
        "sanctioned, a scheme notified -- but not completed."
    ),
    "information_insufficient": (
        "A reply was received, but the information in it does not establish "
        "whether the promise was implemented. The reply is published in full so "
        "readers can judge it for themselves."
    ),
    "rti_reply_awaited": (
        "An RTI application has been filed and the reply has not yet arrived. No "
        "assessment is made until it does."
    ),
    "not_established": (
        "Implementation could not be established from the records currently "
        "available. This is a statement about the records, not a finding that "
        "nothing was done."
    ),
}

# The default for a new promise, and the honest one: a promise nobody has
# researched yet is not "broken", it is unexamined.
DEFAULT_PROMISE_STATUS = "not_established"

# The two statuses that assert nothing about implementation. Every OTHER status
# is a factual claim about a government's performance, so the router refuses to
# publish one without at least one record behind it -- the same gate the
# representative claim store applies to claims about named people (§7).
STATUSES_WITHOUT_EVIDENCE = frozenset({"rti_reply_awaited", "not_established"})

RTI_STATUSES: dict[str, str] = {
    "drafted": "Drafted, not yet filed",
    "filed": "Filed, awaiting reply",
    "reply_received": "Reply received",
    "partial_reply": "Partial reply received",
    "transferred": "Transferred to another public authority",
    "no_reply": "No reply within the statutory period",
    "information_denied": "Information denied",
    "first_appeal": "First appeal filed",
    "second_appeal": "Second appeal filed",
}

# RTI statuses that mean a reply exists to publish.
RTI_ANSWERED_STATUSES = frozenset({"reply_received", "partial_reply"})

# How a public authority dealt with one specific question. Recorded per question
# rather than per application because a single reply routinely answers three
# questions, deflects two and transfers one, and an application-level status
# would hide exactly the part a reader needs.
ANSWER_STATUSES: dict[str, str] = {
    "answered": "Answered",
    "partially_answered": "Partially answered",
    "not_answered": "Not answered",
    "transferred": "Transferred to another authority",
    "denied": "Information denied under an exemption",
    "awaited": "Awaiting reply",
}

DOCUMENT_KINDS: dict[str, str] = {
    "government_order": "Government Order",
    "notification": "Notification",
    "circular": "Circular",
    "sanction_order": "Sanction order",
    "department_report": "Department report",
    "budget_document": "Budget document",
    "completion_report": "Completion or progress report",
    "correspondence": "Official correspondence",
    "rti_reply": "RTI reply",
    "tender": "Tender or work order",
    "legislation": "Act, rules or ordinance",
    "other": "Other official record",
}

# Departments and categories are free text with a suggested list rather than
# enums: Uttarakhand renames and merges departments, and a promise filed under a
# department that no longer exists must not become unreachable.
SUGGESTED_CATEGORIES: tuple[str, ...] = (
    "Education",
    "Health",
    "Employment",
    "Agriculture",
    "Infrastructure",
    "Water",
    "Energy",
    "Women and child development",
    "Youth and sports",
    "Tourism",
    "Environment and forests",
    "Governance and transparency",
    "Law and order",
    "Social welfare",
    "Disaster management",
    "Other",
)


def status_label(key: str) -> str:
    return PROMISE_STATUSES.get(key, PROMISE_STATUSES[DEFAULT_PROMISE_STATUS])


# --------------------------------------------------------------------------
# Election -> manifesto -> promise
# --------------------------------------------------------------------------
class ManifestoElection(Base):
    """One election, in one state, in one year.

    `state_code` is the ISO code from core/geography, so this joins to everything
    else the platform organises by state without a second vocabulary.
    """

    __tablename__ = "manifesto_elections"
    __table_args__ = (
        Index("ix_manifesto_election_slug", "slug", unique=True),
        Index("ix_manifesto_election_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    state_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    # The letters public identifiers are built from: UK-2022-P001.
    #
    # Separate from `state_code` because they answer different questions. The
    # state code is ISO 3166-2:IN (UT for Uttarakhand), which is what RBAC
    # scoping and every other module key off; the prefix is what a citizen
    # writes on an RTI application and reads out on the phone, and there the
    # common Indian abbreviation (UK) is the one that will not confuse anybody.
    # See the note at the top of core/geography.py on the same tension.
    code_prefix: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    house: Mapped[str] = mapped_column(String(40), nullable=False, default="assembly")
    election_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    result_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Where the schedule/result came from. An election is a matter of public
    # record; the link is here so the page can say which record.
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Manifesto(Base):
    """A party's published manifesto for one election.

    `party_name` is a snapshot alongside `party_code` for the same reason a
    signature snapshots a display name: the document was published by a party
    under the name it used then, and a later rename must not rewrite history.

    `source_url` is effectively required by the router. A manifesto page that
    cannot show the manifesto is asking to be taken on trust, which is the exact
    posture this module exists to avoid.
    """

    __tablename__ = "manifestos"
    __table_args__ = (
        Index("ix_manifesto_slug", "slug", unique=True),
        Index("ix_manifesto_election", "election_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    election_id: Mapped[str] = mapped_column(
        ForeignKey("manifesto_elections.id", ondelete="CASCADE"), nullable=False
    )
    party_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    party_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(360), nullable=False, default="")
    published_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # The PDF as published. Preserved as issued -- never re-typeset, never
    # "cleaned up" (§18).
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ManifestoPromise(Base):
    """One promise, quoted from the manifesto, with its page number.

    `code` (UK-2022-P001) is the public identifier: it appears in the URL, on
    printed material and in RTI applications, so it is unique and never reused
    even if a promise is withdrawn.

    `status` is a cache of the current assessment's status, kept here so listing
    a hundred promises is one query. `PromiseAssessment` remains the source of
    truth and the router recomputes this column from it rather than letting the
    two be set independently.
    """

    __tablename__ = "manifesto_promises"
    __table_args__ = (
        UniqueConstraint("code", name="uq_manifesto_promise_code"),
        Index("ix_promise_election", "election_id"),
        Index("ix_promise_status", "status"),
        Index("ix_promise_department", "department"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    election_id: Mapped[str] = mapped_column(
        ForeignKey("manifesto_elections.id", ondelete="CASCADE"), nullable=False
    )
    manifesto_id: Mapped[str] = mapped_column(
        ForeignKey("manifestos.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(360), nullable=False, default="")
    # The promise AS PRINTED. The router does not permit this to be edited into a
    # summary: paraphrasing a promise is how an accountability project ends up
    # being accused of inventing the thing it is holding someone to.
    promise_text: Mapped[str] = mapped_column(Text, nullable=False)
    promise_text_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    manifesto_page: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    manifesto_page_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    department: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(120), nullable=False, default="Other")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_PROMISE_STATUS
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# RTI: application -> questions -> replies
# --------------------------------------------------------------------------
class RtiApplication(Base):
    """One RTI application, filed against one promise.

    Filed under the Right to Information Act 2005, so the fields mirror what an
    application and its acknowledgement actually contain -- public authority,
    PIO, application number, filing date -- rather than a generic "request"
    shape. Those are the details a reader needs to file the same RTI themselves,
    which is the point of publishing them.
    """

    __tablename__ = "rti_applications"
    __table_args__ = (
        UniqueConstraint("code", name="uq_rti_code"),
        Index("ix_rti_promise", "promise_id"),
        Index("ix_rti_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    promise_id: Mapped[str] = mapped_column(
        ForeignKey("manifesto_promises.id", ondelete="CASCADE"), nullable=False
    )

    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    public_authority: Mapped[str] = mapped_column(String(240), nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    pio_designation: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    application_number: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    prepared_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    filed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 30 days under s.7(1). Stored rather than computed so a holiday adjustment
    # or a transfer under s.6(3) can move it truthfully.
    reply_due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(40), nullable=False, default="drafted")
    # The application itself and the receipt/acknowledgement, as filed.
    application_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    filing_proof_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RtiResponse(Base):
    """A reply received against an application -- the covering document.

    Plural per application on purpose: an RTI routinely produces a first reply, a
    transfer, then an appellate reply, and publishing only the latest would hide
    what the authority said first.
    """

    __tablename__ = "rti_responses"
    __table_args__ = (Index("ix_rti_response_application", "rti_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rti_id: Mapped[str] = mapped_column(
        ForeignKey("rti_applications.id", ondelete="CASCADE"), nullable=False
    )

    received_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reply_dated: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    replying_authority: Mapped[str] = mapped_column(String(240), nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    reference_number: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # The reply exactly as received. Required by the router: a reply nobody can
    # read is a claim about a reply.
    document_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # A neutral note about the reply as a whole ("transferred to three
    # directorates under s.6(3)"), never an evaluation of it.
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_appeal_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RtiQuestion(Base):
    """One numbered question and the answer given to it.

    Question and answer live on the same row because they are meaningless apart:
    the transparency claim of this module is that a reader sees exactly what was
    asked next to exactly what came back, in the authority's own words, and a
    schema that lets one be displayed without the other invites that.
    """

    __tablename__ = "rti_questions"
    __table_args__ = (
        UniqueConstraint("rti_id", "number", name="uq_rti_question_number"),
        Index("ix_rti_question_application", "rti_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rti_id: Mapped[str] = mapped_column(
        ForeignKey("rti_applications.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The answer as given. Quoted, never summarised -- see the module docstring.
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_status: Mapped[str] = mapped_column(String(40), nullable=False, default="awaited")
    # Which reply this answer came from, when an application has several.
    response_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("rti_responses.id", ondelete="SET NULL"), nullable=True
    )
    # The specific record the authority attached to this answer, if any.
    supporting_document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("government_documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# Documents and evidence
# --------------------------------------------------------------------------
class GovernmentDocument(Base):
    """An official record: an order, a notification, a sanction, a report.

    Stored BY REFERENCE, like the research repository: `file_url` may point at
    this platform's own upload route or at the department's site. Where the
    document is still on an official domain, that link is the better citation and
    rehosting adds nothing.

    Nothing here edits the file. §18 of the brief and plain sense agree: the
    value of this archive is that the PDF is the one the department issued, so
    the platform stores metadata beside it and never over it.
    """

    __tablename__ = "government_documents"
    __table_args__ = (
        UniqueConstraint("code", name="uq_government_document_code"),
        Index("ix_gov_doc_promise", "promise_id"),
        Index("ix_gov_doc_kind", "kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    promise_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("manifesto_promises.id", ondelete="CASCADE"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), nullable=False, default="other")
    issuing_authority: Mapped[str] = mapped_column(String(240), nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    reference_number: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    issued_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    file_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Where this copy came from: "received with the RTI reply dated ...", "downloaded
    # from the department portal on ...". A document with no provenance is an
    # anonymous PDF, and this module cannot publish one.
    source_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    obtained_via: Mapped[str] = mapped_column(String(40), nullable=False, default="rti")
    # Cached from core.citations.classify_source: is the link the record itself
    # (a gov.in domain) or somebody's report of it?
    is_primary_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PromiseEvidence(Base):
    """One factual statement about what a specific record shows.

    The bridge between a document and an assessment, and the reason the
    assessment can be short. Each row says "this document, at this page, states
    X" -- a description of the record that anyone holding the record can check --
    and points at the record it describes.

    `statement` is deliberately not called "finding" or "verdict". It is what the
    paper says, not what it means; what it means is the assessment's job.
    """

    __tablename__ = "manifesto_evidence"
    __table_args__ = (
        Index("ix_evidence_promise", "promise_id"),
        Index("ix_evidence_document", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    promise_id: Mapped[str] = mapped_column(
        ForeignKey("manifesto_promises.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: some evidence is an RTI answer rather than an attached document.
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("government_documents.id", ondelete="SET NULL"), nullable=True
    )
    rti_question_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("rti_questions.id", ondelete="SET NULL"), nullable=True
    )

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    statement_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Page or paragraph inside the record, so a reader is not sent to hunt
    # through forty scanned pages.
    locator: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    recorded_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PromiseAssessment(Base):
    """This platform's conclusion, kept apart from the records it rests on.

    Versioned rather than overwritten: `is_current` marks the live one and the
    superseded rows stay. An accountability project that silently changes its own
    published conclusion is doing the thing it criticises, so a status change
    leaves both the old assessment and the audit entry explaining the change.

    `sources` lists the evidence and document ids the conclusion is drawn from.
    The router refuses to publish any status other than the two that assert
    nothing (see STATUSES_WITHOUT_EVIDENCE) with an empty list -- that check is
    what stops this table becoming an opinion column.
    """

    __tablename__ = "promise_assessments"
    __table_args__ = (
        Index("ix_assessment_promise", "promise_id"),
        Index("ix_assessment_current", "promise_id", "is_current"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    promise_id: Mapped[str] = mapped_column(
        ForeignKey("manifesto_promises.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=DEFAULT_PROMISE_STATUS)
    # Why this status, in the module's neutral register. Shown behind the "Why
    # this status?" control next to every badge.
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # How the conclusion was reached: which records were read, what was looked
    # for, and what could not be checked. Method belongs next to a conclusion.
    method_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # [{"kind": "evidence"|"document"|"rti_question", "id": "...", "label": "..."}]
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    assessed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assessed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
