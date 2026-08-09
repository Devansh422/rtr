"""Petitions and signatures.

The design question that decides whether a petition system is worth having:
**can a signature be trusted?** A petition with 50,000 signatures that anyone can
inflate with a script is worth less than one with 500 that cannot, because the
first can be dismissed in one sentence by the office it is addressed to.

So signing requires an authenticated member -- the supporter/volunteer access
code that already exists -- and uniqueness is enforced by a database constraint
on (petition, citizen) rather than by a check the application might skip. There is
no anonymous signing path. That is a real cost in conversion, accepted
deliberately: this platform's petitions are meant to be handed to a Chief
Minister, and the number on the cover has to survive scrutiny.

Withdrawal is supported and hard-deletes the row. A signature is an expression of
support; when someone withdraws it, keeping a `withdrawn: true` record with their
name attached is neither honest nor DPDP-compliant.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
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


class PetitionStatus(str):
    DRAFT = "draft"
    # Citizen-created petitions land here: the non-partisan content policy has to
    # be applied by a person before a petition goes out under this platform's name.
    UNDER_REVIEW = "under_review"
    OPEN = "open"
    CLOSED = "closed"
    DELIVERED = "delivered"
    RESPONDED = "responded"
    REJECTED = "rejected"


STATUS_LABELS: dict[str, str] = {
    PetitionStatus.DRAFT: "Draft",
    PetitionStatus.UNDER_REVIEW: "Awaiting moderation",
    PetitionStatus.OPEN: "Open for signatures",
    PetitionStatus.CLOSED: "Closed",
    PetitionStatus.DELIVERED: "Delivered to the addressee",
    PetitionStatus.RESPONDED: "Response received",
    PetitionStatus.REJECTED: "Not accepted",
}

PUBLIC_STATUSES = frozenset(
    {
        PetitionStatus.OPEN,
        PetitionStatus.CLOSED,
        PetitionStatus.DELIVERED,
        PetitionStatus.RESPONDED,
    }
)

# Signature thresholds worth marking. Chosen to give a new petition an early
# reachable milestone -- a progress bar whose first marker is 10,000 tells a
# petition with 40 signatures that it has failed.
MILESTONES: tuple[int, ...] = (50, 100, 500, 1_000, 5_000, 10_000, 25_000, 50_000, 100_000)


class Petition(Base):
    __tablename__ = "petitions"
    __table_args__ = (
        Index("ix_petition_slug", "slug", unique=True),
        Index("ix_petition_status", "status"),
        Index("ix_petition_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(360), nullable=False, default="")
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Who the petition asks. A petition addressed to nobody is a press release,
    # so the router requires this.
    addressed_to: Mapped[str] = mapped_column(String(300), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="right-to-recall")

    target_signatures: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    # Denormalised count. The signature table is the source of truth; this column
    # exists so a list of 50 petitions is one query instead of 51, and it is
    # recomputed on every sign and withdrawal rather than trusted blindly.
    signature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Null for a staff-created ("official") petition.
    citizen_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PetitionStatus.UNDER_REVIEW)
    status_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Evidence of delivery or of a response. A petition tracker that says
    # "delivered" with nothing behind it has the same credibility problem as an
    # unsourced claim about a person.
    outcome_source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # [{"count": 1000, "reachedAt": "..."}]
    milestones: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_flags: Mapped[str] = mapped_column(Text, nullable=False, default="")

    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class PetitionSignature(Base):
    __tablename__ = "petition_signatures"
    __table_args__ = (
        # The integrity guarantee, in the schema rather than in application code.
        UniqueConstraint("petition_id", "citizen_id", name="uq_petition_signature"),
        Index("ix_signature_petition", "petition_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    petition_id: Mapped[str] = mapped_column(
        ForeignKey("petitions.id", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )

    # Snapshot of the name at signing time. A signature is a record of what
    # someone said on a date; if they later change their display name, the
    # petition already submitted should not silently change with it.
    display_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Signatures are counted always and listed only with consent. Defaults to
    # private: a civic platform should not publish a name because someone forgot
    # to untick a box.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comment_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def milestones_reached(count: int) -> list[int]:
    return [m for m in MILESTONES if count >= m]


def next_milestone(count: int) -> Optional[int]:
    return next((m for m in MILESTONES if m > count), None)
