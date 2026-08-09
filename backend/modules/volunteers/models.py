"""Volunteer Portal: skills, a task board, claimed work and verified hours.

Identity note: a volunteer is a `Citizen` with a `VolunteerProfile` attached, not a
third kind of account. The platform already has two identity types for good
reasons (staff who can act on the platform, members who participate on it); adding
a third for "member who also does tasks" would mean three places to check whether
someone is muted and three things to erase on a DPDP request. A profile row is the
right weight for "this member has told us what they can help with".

The hours model is the part that matters. Volunteer hours become certificates, and
certificates go on CVs, so self-reported hours cannot be the record. A volunteer
CLAIMS hours; a Volunteer Manager VERIFIES them; only verified hours count toward
anything. `hours_claimed` and `hours_verified` are therefore separate columns
rather than one column with a boolean, so the gap between what was claimed and what
was confirmed stays visible instead of being overwritten.
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

from backend.core.models import Base, new_id, utcnow

# The skill categories from the brief. Enumerated rather than free text because
# the task board's whole job is matching a task to the people who can do it, and
# free-text skills make that matching impossible.
SKILLS: dict[str, str] = {
    "translation": "Translation and language review",
    "legal": "Legal research and drafting",
    "research": "Research and fact-checking",
    "design": "Design and illustration",
    "social_media": "Social media and content",
    "field": "Field organising and outreach",
    "data_entry": "Data entry and verification",
    "media": "Photography and video",
    "teaching": "Teaching and workshops",
    "tech": "Software development",
    "fundraising": "Fundraising",
    "events": "Event management",
    "writing": "Writing and editing",
}

# Verified hours needed before a service certificate can be issued. Low enough to
# be reachable in a few evenings, high enough that the certificate means something.
CERTIFICATE_HOURS_THRESHOLD = 20


class TaskStatus(str):
    OPEN = "open"
    FULL = "full"
    CLOSED = "closed"


class AssignmentStatus(str):
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    # Returned with a reason, not deleted -- the volunteer can fix and resubmit.
    RETURNED = "returned"
    ABANDONED = "abandoned"


ASSIGNMENT_LABELS: dict[str, str] = {
    AssignmentStatus.CLAIMED: "In progress",
    AssignmentStatus.SUBMITTED: "Awaiting verification",
    AssignmentStatus.VERIFIED: "Verified",
    AssignmentStatus.RETURNED: "Returned for changes",
    AssignmentStatus.ABANDONED: "Given up",
}


class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"
    __table_args__ = (
        UniqueConstraint("citizen_id", name="uq_volunteer_citizen"),
        Index("ix_volunteer_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )

    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    languages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    hours_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Denormalised from verified assignments, recomputed on each verification.
    # Never written directly from a volunteer's input.
    verified_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completed_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class VolunteerTask(Base):
    __tablename__ = "volunteer_tasks"
    __table_args__ = (
        Index("ix_task_slug", "slug", unique=True),
        Index("ix_task_skill_status", "skill", "status"),
        Index("ix_task_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skill: Mapped[str] = mapped_column(String(30), nullable=False)
    # What "done" looks like. A task board without this generates submissions
    # nobody can verify, which is how a volunteer programme stalls.
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False, default="")

    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # None = anywhere
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # How many volunteers may work on it at once. Translation of forty articles
    # wants ten people; verifying one affidavit wants one.
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    claimed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.OPEN)
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint("task_id", "profile_id", name="uq_task_assignment"),
        Index("ix_assignment_profile", "profile_id"),
        Index("ix_assignment_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("volunteer_tasks.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("volunteer_profiles.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AssignmentStatus.CLAIMED)
    submission_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    submission_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Claimed by the volunteer; verified by a manager. Kept apart on purpose --
    # see the module docstring.
    hours_claimed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hours_verified: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verified_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
