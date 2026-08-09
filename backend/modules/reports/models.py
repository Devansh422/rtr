"""Citizen Report Cards: what service delivery actually looks like on the ground.

A report card is a first-person account, which makes it the most useful and the
most dangerous content on the platform at once. Useful, because no official
dataset records that a health centre has had no doctor for four months.
Dangerous, because an unverified first-person account naming an official is a
defamation exposure and, in volume, a vector for coordinated attacks on one
party's representatives -- which would destroy the non-partisan claim in §1.

Three structural answers, all in this model:

1. **Nothing publishes on submission.** Every report enters `submitted` and needs
   a Moderator or Fact Checker to move it. There is no auto-publish path, not
   even for a high-reputation member.
2. **The subject is a place and a service, not a person.** `constituency_code`
   and `service` are required; `representative_id` is optional and, when set,
   records whose constituency it is -- not an accusation against them. The
   serialiser never presents a report as a claim about the representative's
   conduct.
3. **A government response is a first-class field.** A report card that cannot
   record "the department fixed it" is a complaint box, not an accountability
   record, and the platform loses the right to say it is fair.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class ReportStatus(str):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    PUBLISHED = "published"
    # Published, and the issue has since been addressed. The status the platform
    # most wants to be able to record.
    RESOLVED = "resolved"
    REJECTED = "rejected"
    # Withheld because it named an individual or breached the content policy, and
    # the author was told why.
    WITHHELD = "withheld"


STATUS_LABELS: dict[str, str] = {
    ReportStatus.SUBMITTED: "Submitted",
    ReportStatus.UNDER_REVIEW: "Being verified",
    ReportStatus.PUBLISHED: "Published",
    ReportStatus.RESOLVED: "Resolved",
    ReportStatus.REJECTED: "Not published",
    ReportStatus.WITHHELD: "Withheld pending changes",
}

PUBLIC_STATUSES = frozenset({ReportStatus.PUBLISHED, ReportStatus.RESOLVED})

# The services a report can be about. An enumerated list rather than free text,
# because the whole point of collecting these is to aggregate them -- "37 reports
# about water supply in this district" is the finding, and free-text categories
# make that impossible.
SERVICES: dict[str, str] = {
    "roads": "Roads and footpaths",
    "water": "Drinking water supply",
    "sanitation": "Sanitation and drainage",
    "electricity": "Electricity supply",
    "health": "Health centre or hospital",
    "education": "School or anganwadi",
    "ration": "Ration shop / public distribution",
    "pension": "Pension or welfare payment",
    "transport": "Public transport",
    "waste": "Waste collection",
    "scheme_delivery": "A scheme not reaching people",
    "office_access": "Getting a public office to respond",
    "grievance_ignored": "A filed grievance going unanswered",
    "other": "Something else",
}


class CitizenReport(Base):
    __tablename__ = "citizen_reports"
    __table_args__ = (
        Index("ix_report_slug", "slug", unique=True),
        Index("ix_report_status", "status"),
        Index("ix_report_place", "state_code", "district_code"),
        Index("ix_report_service", "service"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    # Publishing under a pseudonym is the default. Someone reporting that their
    # ward's water has been off for a month should not have to make themselves
    # findable by the contractor to say so.
    show_author: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    service: Mapped[str] = mapped_column(String(40), nullable=False)

    state_code: Mapped[str] = mapped_column(String(10), nullable=False)
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    constituency_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    locality: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Whose constituency this is, recorded as context. NOT an allegation about
    # them -- see the module docstring.
    representative_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # 1-5, "how well is this service working here". Aggregated into the
    # constituency score; meaningless individually and presented as such.
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Photos, RTI replies, complaint receipts. Upload ids or URLs.
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReportStatus.SUBMITTED)
    # Why it was published, withheld or rejected. Shown to the author always, and
    # publicly for a published report -- "verified how" is the difference between
    # a report card and a comment.
    verification_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verified_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- The other side of the story ----
    response_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_from: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    response_source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    policy_flags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ReportConfirmation(Base):
    """"This is happening to me too."

    Corroboration rather than a vote. One person saying a health centre has no
    doctor is an anecdote; forty people in the same constituency saying it is
    data, and the difference is worth modelling as its own row so it can be
    counted per place rather than as an undifferentiated score.
    """

    __tablename__ = "report_confirmations"
    __table_args__ = (
        Index("ix_confirmation_report", "report_id"),
        Index("ix_confirmation_unique", "report_id", "citizen_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("citizen_reports.id", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
