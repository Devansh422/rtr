"""Event listing, registration, QR check-in and participation certificates."""

from datetime import datetime, timezone
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, certificates, limits, notify, search
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
    require_state_scope,
)
from backend.core.models import Certificate, Citizen, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.events.models import (
    EVENT_KINDS,
    Event,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


class EventIn(BaseModel):
    title: str = Field(..., min_length=6, max_length=240)
    starts_at: datetime
    kind: str = "workshop"
    title_hi: str = ""
    description: str = ""
    ends_at: Optional[datetime] = None
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    is_online: bool = False
    venue: str = ""
    address: str = ""
    meeting_url: str = ""
    capacity: Optional[int] = Field(default=None, ge=1, le=100_000)
    organiser_name: str = ""
    organiser_contact: str = ""


def _event_dict(event: Event, *, for_attendee: bool = False) -> dict:
    return {
        "id": event.id,
        "slug": event.slug,
        "title": event.title,
        "titleHi": event.title_hi,
        "description": event.description,
        "kind": event.kind,
        "kindLabel": EVENT_KINDS.get(event.kind, event.kind),
        "state": event.state_code,
        "district": event.district_code,
        "isOnline": event.is_online,
        "venue": event.venue or None,
        "address": event.address or None,
        # Withheld until someone registers. See the note on the model.
        "meetingUrl": event.meeting_url if for_attendee else None,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
        "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "capacity": event.capacity,
        "registrationCount": event.registration_count,
        "attendedCount": event.attended_count,
        "seatsLeft": (event.capacity - event.registration_count) if event.capacity else None,
        "status": event.status,
        "organiser": {"name": event.organiser_name or None, "contact": event.organiser_contact or None},
        "cancellationReason": event.cancellation_reason or None,
        "url": f"/events/{event.slug}",
    }


async def _sync_counts(session: AsyncSession, event: Event) -> None:
    event.registration_count = (
        await session.execute(
            select(func.count())
            .select_from(EventRegistration)
            .where(
                EventRegistration.event_id == event.id,
                EventRegistration.status != RegistrationStatus.CANCELLED,
            )
        )
    ).scalar_one()
    event.attended_count = (
        await session.execute(
            select(func.count())
            .select_from(EventRegistration)
            .where(
                EventRegistration.event_id == event.id,
                EventRegistration.status == RegistrationStatus.ATTENDED,
            )
        )
    ).scalar_one()


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/events/kinds")
async def list_event_kinds():
    return [{"key": key, "label": label} for key, label in EVENT_KINDS.items()]


@router.get("/events")
async def list_events(
    state: Optional[str] = None,
    kind: Optional[str] = None,
    past: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    stmt = select(Event).where(
        Event.status.in_([EventStatus.PUBLISHED, EventStatus.COMPLETED, EventStatus.CANCELLED])
    )
    if state:
        stmt = stmt.where((Event.state_code == state.upper()) | (Event.state_code.is_(None)))
    if kind:
        stmt = stmt.where(Event.kind == kind)

    stmt = (
        stmt.where(Event.starts_at < now).order_by(Event.starts_at.desc())
        if past
        else stmt.where(Event.starts_at >= now).order_by(Event.starts_at)
    )
    rows = (await session.execute(stmt.limit(limit))).scalars()
    return [_event_dict(e) for e in rows]


@router.get("/events/{slug}")
async def get_event(slug: str, session: AsyncSession = Depends(get_session)):
    event = (await session.execute(select(Event).where(Event.slug == slug))).scalar_one_or_none()
    if event is None or event.status == EventStatus.DRAFT:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        **_event_dict(event),
        "share": notify.share_links(url=f"/events/{event.slug}", text=f"Join: {event.title}"),
    }


@router.post("/events/{slug}/register")
async def register_for_event(
    slug: str,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    event = (await session.execute(select(Event).where(Event.slug == slug))).scalar_one_or_none()
    if event is None or event.status != EventStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Event not open for registration")
    if event.starts_at < utcnow():
        raise HTTPException(status_code=400, detail="This event has already started")
    if event.capacity and event.registration_count >= event.capacity:
        raise HTTPException(status_code=400, detail="This event is full")

    existing = (
        await session.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event.id,
                EventRegistration.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status != RegistrationStatus.CANCELLED:
        return {
            "ok": True,
            "already": True,
            "ticketCode": existing.ticket_code,
            "event": _event_dict(event, for_attendee=True),
        }

    await limits.check("event.register", f"m:{citizen.email}")

    if existing is not None:
        # Re-registering after cancelling reuses the row and mints a fresh ticket,
        # so an old QR screenshot cannot be used to check in.
        existing.status = RegistrationStatus.REGISTERED
        existing.ticket_code = certificates.new_code("TKT")
        registration = existing
    else:
        registration = EventRegistration(
            event_id=event.id,
            citizen_id=citizen.id,
            ticket_code=certificates.new_code("TKT"),
            name_snapshot=citizen.display_name,
        )
        session.add(registration)

    await session.flush()
    await _sync_counts(session, event)

    await notify.send_email(
        to=citizen.email,
        subject=f"You're registered: {event.title}",
        html=notify.render(
            event.title,
            notify.paragraph(
                f"{event.starts_at.strftime('%d %B %Y, %H:%M')} - "
                f"{'Online' if event.is_online else (event.venue or 'venue to be confirmed')}"
            )
            + notify.paragraph(
                f"Your ticket code is <strong>{registration.ticket_code}</strong>. Bring the QR code "
                "from your dashboard -- a volunteer will scan it at the door."
            )
            + (notify.paragraph(f"Joining link: {event.meeting_url}") if event.meeting_url else "")
            + notify.button("See your ticket", "/dashboard"),
        ),
    )

    return {
        "ok": True,
        "already": False,
        "ticketCode": registration.ticket_code,
        "qrUrl": f"/api/events/tickets/{registration.ticket_code}/qr.svg",
        "event": _event_dict(event, for_attendee=True),
    }


@router.delete("/events/{slug}/register")
async def cancel_registration(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    event = (await session.execute(select(Event).where(Event.slug == slug))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    registration = (
        await session.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event.id,
                EventRegistration.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if registration is None:
        raise HTTPException(status_code=404, detail="You are not registered for this event")
    if registration.status == RegistrationStatus.ATTENDED:
        raise HTTPException(status_code=400, detail="You have already been marked present")

    registration.status = RegistrationStatus.CANCELLED
    await session.flush()
    await _sync_counts(session, event)
    return {"ok": True}


@router.get("/events/tickets/{ticket_code}/qr.svg")
async def ticket_qr(ticket_code: str, session: AsyncSession = Depends(get_session)):
    """The attendee's QR code, as SVG.

    Unauthenticated by design: the code itself is the secret, and requiring a
    session to fetch the image would break the common case of opening the ticket on
    a phone with a flaky connection at the venue door. Knowing a ticket code lets
    you render its QR; it does not let you check in, because check-in is an
    authenticated staff action.

    Vector rather than raster, so no Pillow is needed and it prints sharply from a
    cheap phone screenshot.
    """
    registration = (
        await session.execute(
            select(EventRegistration).where(EventRegistration.ticket_code == ticket_code.upper())
        )
    ).scalar_one_or_none()
    if registration is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:  # pragma: no cover - qrcode is in requirements.txt
        raise HTTPException(
            status_code=503,
            detail="QR generation is unavailable on this deployment. Show the ticket code instead.",
        )

    image = qrcode.make(
        registration.ticket_code,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        # Immutable: a ticket code's QR never changes, so let the phone keep it.
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/me/events")
async def my_events(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(EventRegistration, Event)
            .join(Event, Event.id == EventRegistration.event_id)
            .where(
                EventRegistration.citizen_id == citizen.id,
                EventRegistration.status != RegistrationStatus.CANCELLED,
            )
            .order_by(Event.starts_at.desc())
        )
    ).all()
    issued = {
        c.detail.get("eventSlug"): certificates.to_dict(c)
        for c in (
            await session.execute(
                select(Certificate).where(
                    Certificate.citizen_id == citizen.id,
                    Certificate.kind == "event_attendance",
                )
            )
        ).scalars()
    }
    return [
        {
            **_event_dict(event, for_attendee=True),
            "ticketCode": registration.ticket_code,
            "qrUrl": f"/api/events/tickets/{registration.ticket_code}/qr.svg",
            "registrationStatus": registration.status,
            "attended": registration.status == RegistrationStatus.ATTENDED,
            "certificate": issued.get(event.slug),
        }
        for registration, event in rows
    ]


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.post("/admin/events")
async def create_event(
    payload: EventIn,
    request: Request,
    admin: Principal = Depends(require_permission("events.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.kind not in EVENT_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(EVENT_KINDS)}")
    state_code = payload.state_code.upper() if payload.state_code else None
    if state_code:
        require_state_scope(admin, state_code)
    elif not admin.is_platform_wide():
        raise HTTPException(
            status_code=403, detail="Your account is scoped to a state, so name that state on the event."
        )
    if not payload.is_online and not payload.venue.strip():
        raise HTTPException(status_code=400, detail="An in-person event needs a venue")

    slug = slugify(payload.title)
    if (await session.execute(select(Event).where(Event.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{payload.starts_at.strftime('%Y%m%d')}"

    event = Event(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        description=payload.description.strip(),
        kind=payload.kind,
        state_code=state_code,
        district_code=payload.district_code.upper() if payload.district_code else None,
        is_online=payload.is_online,
        venue=payload.venue.strip(),
        address=payload.address.strip(),
        meeting_url=payload.meeting_url.strip(),
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
        organiser_name=payload.organiser_name.strip(),
        organiser_contact=payload.organiser_contact.strip(),
        status=EventStatus.DRAFT,
        created_by=admin.id,
    )
    session.add(event)
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="event",
        entity_id=slug,
        summary=f"Created event: {event.title}",
        is_public=False,
        request=request,
    )
    return _event_dict(event, for_attendee=True)


@router.post("/admin/events/{event_id}/status")
async def set_event_status(
    event_id: str,
    request: Request,
    status: str = Query(...),
    reason: str = "",
    admin: Principal = Depends(require_permission("events.manage")),
    session: AsyncSession = Depends(get_session),
):
    valid = {EventStatus.DRAFT, EventStatus.PUBLISHED, EventStatus.CANCELLED, EventStatus.COMPLETED}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(valid)}")

    event = (await session.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.state_code:
        require_state_scope(admin, event.state_code)
    if status == EventStatus.CANCELLED and len(reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Give a reason -- registered attendees are told.")

    before = event.status
    event.status = status
    event.cancellation_reason = reason.strip() or event.cancellation_reason

    await audit.record(
        session,
        actor=admin,
        action="event_status",
        entity_type="event",
        entity_id=event.slug,
        summary=f"{event.title}: {before} -> {status}",
        is_public=status == EventStatus.PUBLISHED,
        request=request,
    )
    await search.index(
        session,
        entity_type="event",
        entity_id=event.slug,
        title=event.title,
        subtitle=f"{EVENT_KINDS.get(event.kind, event.kind)} - {event.starts_at.date().isoformat()}",
        body=event.description,
        keywords=[event.kind, event.state_code or "", event.venue],
        state_code=event.state_code,
        is_published=status == EventStatus.PUBLISHED,
        url_path=f"/events/{event.slug}",
    )

    if status == EventStatus.CANCELLED:
        rows = (
            await session.execute(
                select(Citizen.email)
                .join(EventRegistration, EventRegistration.citizen_id == Citizen.id)
                .where(
                    EventRegistration.event_id == event.id,
                    EventRegistration.status == RegistrationStatus.REGISTERED,
                )
            )
        ).scalars()
        await notify.send_bulk(
            list(rows),
            subject=f"Cancelled: {event.title}",
            html=notify.render(
                f"{event.title} has been cancelled",
                notify.paragraph(event.cancellation_reason)
                + notify.paragraph("We are sorry for the change of plan."),
            ),
        )

    return _event_dict(event, for_attendee=True)


@router.post("/admin/events/{event_id}/checkin")
async def check_in(
    event_id: str,
    request: Request,
    ticket_code: str = Query(...),
    admin: Principal = Depends(require_permission("events.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Mark an attendee present by their scanned ticket code.

    Authenticated staff action, per the module docstring: the attendee holds the
    code, a volunteer with `events.manage` performs the check-in. Idempotent -- a
    second scan of the same ticket reports "already checked in" with the original
    time rather than double-counting or erroring, because at a door that is what a
    volunteer needs to hear.
    """
    event = (await session.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.state_code:
        require_state_scope(admin, event.state_code)

    registration = (
        await session.execute(
            select(EventRegistration).where(
                EventRegistration.ticket_code == ticket_code.strip().upper(),
                EventRegistration.event_id == event.id,
            )
        )
    ).scalar_one_or_none()
    if registration is None:
        raise HTTPException(
            status_code=404,
            detail="That ticket is not for this event. Check the attendee is at the right session.",
        )
    if registration.status == RegistrationStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="This registration was cancelled")

    if registration.status == RegistrationStatus.ATTENDED:
        return {
            "ok": True,
            "already": True,
            "name": registration.name_snapshot,
            "checkedInAt": registration.checked_in_at.isoformat() if registration.checked_in_at else None,
        }

    registration.status = RegistrationStatus.ATTENDED
    registration.checked_in_at = utcnow()
    registration.checked_in_by = admin.id
    await session.flush()
    await _sync_counts(session, event)

    return {
        "ok": True,
        "already": False,
        "name": registration.name_snapshot,
        "attendedCount": event.attended_count,
        "registrationCount": event.registration_count,
    }


@router.get("/admin/events/{event_id}/attendance")
async def attendance_sheet(
    event_id: str,
    admin: Principal = Depends(require_permission("events.manage")),
    session: AsyncSession = Depends(get_session),
):
    event = (await session.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.state_code:
        require_state_scope(admin, event.state_code)

    rows = (
        await session.execute(
            select(EventRegistration, Citizen)
            .join(Citizen, Citizen.id == EventRegistration.citizen_id)
            .where(EventRegistration.event_id == event.id)
            .order_by(EventRegistration.created_at)
        )
    ).all()
    return {
        "event": _event_dict(event, for_attendee=True),
        "items": [
            {
                "registrationId": registration.id,
                "ticketCode": registration.ticket_code,
                "name": citizen.display_name,
                "email": citizen.email,
                "state": citizen.state_code,
                "status": registration.status,
                "checkedInAt": (
                    registration.checked_in_at.isoformat() if registration.checked_in_at else None
                ),
            }
            for registration, citizen in rows
        ],
    }


@router.post("/admin/events/{event_id}/certificates")
async def issue_attendance_certificates(
    event_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("events.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Issue participation certificates to everyone marked present.

    Only to ATTENDED registrations, never to everyone who registered. A
    participation certificate for an event someone did not attend is a small lie
    that devalues every other certificate the platform issues.
    """
    event = (await session.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.state_code:
        require_state_scope(admin, event.state_code)

    rows = (
        await session.execute(
            select(EventRegistration, Citizen)
            .join(Citizen, Citizen.id == EventRegistration.citizen_id)
            .where(
                EventRegistration.event_id == event.id,
                EventRegistration.status == RegistrationStatus.ATTENDED,
            )
        )
    ).all()

    already = {
        c.detail.get("eventSlug")
        for c in (
            await session.execute(
                select(Certificate).where(Certificate.kind == "event_attendance")
            )
        ).scalars()
        if c.detail.get("eventSlug") == event.slug
    }

    issued = 0
    for registration, citizen in rows:
        existing = (
            await session.execute(
                select(Certificate).where(
                    Certificate.citizen_id == citizen.id,
                    Certificate.kind == "event_attendance",
                )
            )
        ).scalars()
        if any(c.detail.get("eventSlug") == event.slug for c in existing):
            continue
        await certificates.issue(
            session,
            kind="event_attendance",
            holder_name=citizen.display_name or citizen.email.split("@")[0],
            title=f"For attending {event.title}",
            detail={
                "Event": event.title,
                "Date": event.starts_at.date().isoformat(),
                "Venue": "Online" if event.is_online else (event.venue or "-"),
                "eventSlug": event.slug,
            },
            citizen_id=citizen.id,
            holder_email=citizen.email,
            issued_by=admin.id,
        )
        issued += 1

    await audit.record(
        session,
        actor=admin,
        action="issue_certificates",
        entity_type="event",
        entity_id=event.slug,
        summary=f"Issued {issued} participation certificate(s) for {event.title}",
        is_public=False,
        request=request,
    )
    return {"issued": issued, "attendees": len(rows), "skippedAlreadyIssued": len(rows) - issued}
