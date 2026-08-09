"""Events, registration, QR attendance and participation certificates.

The attendance design is worth explaining because a simpler version is tempting
and wrong. The obvious approach is one QR code per event, displayed at the door
and scanned by attendees. That is trivially defeated: a photograph of the code
marks anyone present anywhere.

So the QR is per TICKET, not per event: each registration gets a unique code, the
volunteer at the door scans the attendee's code, and check-in is an authenticated
call by a staff account. The attendee cannot mark themselves present, one code
cannot check in two people (`checked_in_at` is set once), and a leaked code is one
person's ticket rather than the whole event's.

Cost: zero. `qrcode` generates the SVG server-side, `html5-qrcode` scans it in the
volunteer's browser camera, and neither needs a service (§5).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow

EVENT_KINDS: dict[str, str] = {
    "workshop": "Workshop",
    "training": "Volunteer training",
    "public_meeting": "Public meeting",
    "webinar": "Online session",
    "signature_drive": "Signature drive",
    "awareness": "Awareness campaign",
    "legal_clinic": "Legal help clinic",
}


class EventStatus(str):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RegistrationStatus(str):
    REGISTERED = "registered"
    ATTENDED = "attended"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_event_slug", "slug", unique=True),
        Index("ix_event_when", "starts_at"),
        Index("ix_event_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="workshop")

    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    venue: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Released to registered attendees only. A public joining link is an open door
    # for anyone who wants to disrupt a civic meeting.
    meeting_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    registration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attended_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Published so attendees can reach a human. Allowed to be a phone number
    # here -- this is an organiser's published contact for the event, which is the
    # one case where a contact detail is the point (see moderation.review's
    # allow_contact_details).
    organiser_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    organiser_contact: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EventStatus.DRAFT)
    cancellation_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "citizen_id", name="uq_event_registration"),
        Index("ix_registration_ticket", "ticket_code", unique=True),
        Index("ix_registration_event", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )

    # The QR payload. Unique per registration -- see the module docstring for why
    # this is not one code per event.
    ticket_code: Mapped[str] = mapped_column(String(24), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RegistrationStatus.REGISTERED)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Which staff account scanned it. Attendance is a record someone is
    # accountable for, not an anonymous count.
    checked_in_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
