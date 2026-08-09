"""Representative Database, Promise Tracker and the citation-gated claim store.

The one structural decision that matters here: **risk-bearing facts are not
columns on the representative row.** They live in `RepresentativeClaim`, one row
per (representative, field, period), each carrying its own citation and its own
verification status.

Why, concretely. §7 requires that "criminal cases", "assets" and "attendance %"
each ship with a source and a verification state. Modelled as columns that would
mean a `criminal_cases_count`, a `criminal_cases_source_url`, a
`criminal_cases_source_date`, a `criminal_cases_status` -- times fourteen fields,
on one very wide table, where nothing stops a migration adding the fifteenth
value column without its citation columns. A claim table makes the citation
structurally inseparable from the value: there is no way to store the number
without storing where it came from, the fact-check queue is one `WHERE
verification_status = 'unverified'`, and adding a new tracked metric is a
registry entry rather than a schema change.

`Representative` therefore holds only identity: who this person is, which seat
they hold, which party, which term. Those are also public record and also carry a
source, but they are the low-risk half -- getting a constituency wrong is an
error, getting an asset figure wrong is a defamation claim.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.citations import VerificationStatus
from backend.core.models import Base, new_id, utcnow


class House(str):
    """Which body a seat belongs to. Plain strings, validated at the router."""

    LOK_SABHA = "lok_sabha"
    RAJYA_SABHA = "rajya_sabha"
    ASSEMBLY = "assembly"
    COUNCIL = "council"


HOUSES: dict[str, str] = {
    House.LOK_SABHA: "Lok Sabha (MP)",
    House.RAJYA_SABHA: "Rajya Sabha (MP)",
    House.ASSEMBLY: "Legislative Assembly (MLA)",
    House.COUNCIL: "Legislative Council (MLC)",
}

# Houses filled by direct election from a territorial constituency. The
# distinction is not cosmetic: a recall right exercised by voters can only reach
# a seat that voters filled, so the profile page states plainly which category a
# representative is in.
DIRECTLY_ELECTED = frozenset({House.LOK_SABHA, House.ASSEMBLY})


class Party(Base):
    """A political party, recorded as a neutral fact.

    §1: "Party affiliation is shown as a neutral fact (like an infobox), never as
    framing." So this table holds identifiers and the Election Commission's own
    classification, and deliberately has no column for anything evaluative --
    no rating, no score, no editorial description. There is nowhere to put a
    thumb on the scale even by accident.
    """

    __tablename__ = "parties"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # ECI abbreviation, e.g. "BJP"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    # "national" | "state" | "registered_unrecognised" | "independent", as
    # classified by the ECI -- a fact about registration status, not a judgement.
    eci_status: Mapped[str] = mapped_column(String(30), nullable=False, default="registered_unrecognised")
    symbol: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Constituency(Base):
    """One seat: a Lok Sabha PC, an assembly AC, or a Rajya Sabha state slot.

    Kept separate from `Representative` because the seat outlives its occupant.
    Historical holders, the promise history attached to a constituency, and the
    "who represents me" lookup all need the seat to be the stable thing.
    """

    __tablename__ = "constituencies"
    __table_args__ = (
        UniqueConstraint("state_code", "house", "number", name="uq_constituency_number"),
        Index("ix_constituency_state_house", "state_code", "house"),
        Index("ix_constituency_slug", "slug", unique=True),
    )

    code: Mapped[str] = mapped_column(String(30), primary_key=True)  # e.g. "DL-LS-01"
    state_code: Mapped[str] = mapped_column(
        ForeignKey("states.code", ondelete="CASCADE"), nullable=False
    )
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    house: Mapped[str] = mapped_column(String(20), nullable=False)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ECI constituency number
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(180), nullable=False)

    # Reservation status under Articles 330/332. A fact from the delimitation
    # order, and one a recall proposal has to be careful about (see the note on
    # Article 330 in the constitution library).
    reserved_for: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "SC" | "ST"
    electors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Representative(Base):
    """A sitting or former MP/MLA/MLC.

    Identity only -- see the module docstring. Anything that could be defamatory
    if wrong lives in RepresentativeClaim with a mandatory citation.
    """

    __tablename__ = "representatives"
    __table_args__ = (
        Index("ix_rep_slug", "slug", unique=True),
        Index("ix_rep_constituency", "constituency_code"),
        Index("ix_rep_state_house", "state_code", "house"),
        Index("ix_rep_published", "is_published"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    photo_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    house: Mapped[str] = mapped_column(String(20), nullable=False)
    state_code: Mapped[str] = mapped_column(String(10), nullable=False)
    constituency_code: Mapped[Optional[str]] = mapped_column(
        ForeignKey("constituencies.code", ondelete="SET NULL"), nullable=True
    )
    party_code: Mapped[Optional[str]] = mapped_column(
        ForeignKey("parties.code", ondelete="SET NULL"), nullable=True
    )

    term_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    term_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_sitting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Ministerial or presiding office held, if any. Free text because the set of
    # portfolios is not enumerable and changes with every reshuffle.
    office: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Contact details published BY the office itself. Not personal data in the
    # DPDP sense -- an MP's official constituency office address and public email
    # are published by the House precisely so citizens can write to them, which
    # the Representation Generator depends on. Personal numbers are never stored.
    official_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    office_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    official_page_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Where the identity facts above came from -- the ECI result, the Lok Sabha
    # member page, the assembly roster. Required by the router on create.
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_title: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class RepresentativeClaim(Base):
    """One sourced, individually verifiable fact about one representative.

    This is where the §7 rule becomes structural rather than aspirational: the
    value and its citation are the same row, so a number cannot exist without a
    source, and `verification_status` starts at UNVERIFIED for every new row
    regardless of who entered it.
    """

    __tablename__ = "representative_claims"
    __table_args__ = (
        UniqueConstraint("representative_id", "field_key", "period", name="uq_claim_field_period"),
        Index("ix_claim_rep", "representative_id"),
        # The fact-check queue's query. Indexed because it is the screen a Fact
        # Checker keeps open all day.
        Index("ix_claim_status", "verification_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    representative_id: Mapped[str] = mapped_column(
        ForeignKey("representatives.id", ondelete="CASCADE"), nullable=False
    )

    # Key from CLAIM_FIELDS in this module's fields.py, e.g. "criminal.pending_cases".
    field_key: Mapped[str] = mapped_column(String(60), nullable=False)
    # Which term, session or financial year the value refers to. Empty string
    # rather than NULL so the uniqueness constraint behaves the same on both
    # SQLite and Postgres -- NULLs do not compare equal in a unique index.
    period: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    value_number: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ---- Citation (inseparable from the value, by construction) ----
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_date: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    source_publisher: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # Whether the source is a primary public record rather than a report of one.
    # Computed by core/citations.classify_source, stored so the public serialiser
    # does not re-parse a URL on every read.
    source_is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationStatus.UNVERIFIED.value
    )
    # Why a Fact Checker accepted, disputed or retracted it. Shown publicly for
    # disputed and retracted claims -- "disputed" with no explanation is an
    # insinuation.
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    submitted_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Promise(Base):
    """One public commitment, and what became of it.

    A promise needs two independent citations, and the model enforces the shape
    even though only the router can enforce the requirement: `source_url` for
    evidence the promise was made, and `status_source_url` for evidence of what
    happened to it. Marking a promise "broken" on the strength of the manifesto
    alone is an opinion; marking it broken with a link to the scheme's own
    progress report is a finding.

    Attachable to a representative, to a party, or to both -- a manifesto promise
    belongs to the party, a constituency commitment to the person, and a
    minister's assurance in the House to both.
    """

    __tablename__ = "promises"
    __table_args__ = (
        Index("ix_promise_rep", "representative_id"),
        Index("ix_promise_state_status", "state_code", "status"),
        Index("ix_promise_slug", "slug", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    representative_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("representatives.id", ondelete="CASCADE"), nullable=True
    )
    party_code: Mapped[Optional[str]] = mapped_column(
        ForeignKey("parties.code", ondelete="SET NULL"), nullable=True
    )
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    constituency_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(360), nullable=False, default="")
    # The commitment as closely as possible in its own words. Paraphrasing a
    # promise is how a promise tracker loses its authority.
    promise_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    promise_text_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="general")

    made_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    made_context: Mapped[str] = mapped_column(String(200), nullable=False, default="")  # manifesto, House assurance, rally
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="promised")
    status_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status_source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationStatus.UNVERIFIED.value
    )
    # [{"url": ..., "title": ..., "date": ..., "note": ...}] -- the evidence
    # trail as a status changes over time. Append-only in practice; the audit log
    # holds the authoritative history.
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


# Promise lifecycle. "stalled" and "partially_fulfilled" exist because the honest
# answer is usually one of them, and a tracker with only "kept" and "broken"
# forces every ambiguous case into a verdict it cannot support.
PROMISE_STATUSES: dict[str, str] = {
    "promised": "Promised",
    "in_progress": "In progress",
    "partially_fulfilled": "Partially fulfilled",
    "fulfilled": "Fulfilled",
    "stalled": "Stalled",
    "broken": "Not delivered",
    "not_assessable": "Cannot be assessed yet",
}

# Statuses that assert a failure by a named person, and therefore need a primary
# source for the STATUS as well as for the promise.
ADVERSE_STATUSES = frozenset({"broken", "stalled"})
