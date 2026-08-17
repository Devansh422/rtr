"""Public form submissions: join, volunteer, contact, newsletter.

Every endpoint here collects personal data (name, email, sometimes mobile), so
every one of them is in scope for the DPDP Act obligations listed as a Phase 0
requirement in IMPLEMENTATION_PLAN.md §1. The consent flag and the erasure
endpoint below are the backend half of that; the frontend must render the
consent notice next to the submit button rather than burying it in a footer link.
"""

from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.core import erasure, membership
from backend.core.deps import get_current_member, get_optional_session, require_permission
from backend.core.models import new_id
from backend.core.mongo import db
from backend.core.rbac import Principal
from backend.core.security import generate_access_code, hash_password, now_iso

logger = logging.getLogger(__name__)
router = APIRouter(tags=["submissions"])


class VolunteerCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: str = Field(..., min_length=6)
    state: str
    profession: str
    reason: str = Field(..., min_length=5)


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    subject: str = Field(..., min_length=2)
    message: str = Field(..., min_length=5)


class NewsletterCreate(BaseModel):
    email: EmailStr


class SupporterCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    state: str = Field(..., min_length=2)
    city: Optional[str] = None
    mobile: Optional[str] = None
    pledge: bool = True
    # Which campaign's "join" CTA the supporter came through, if any (the generic
    # navbar/footer "Join Movement" action leaves this unset). Recorded once at
    # signup; a returning supporter clicking a DIFFERENT campaign's CTA is not
    # re-attributed -- see the "already exists" branch in join_movement.
    campaign_id: Optional[str] = None
    # movement_id of the supporter who referred this signup, if they arrived via
    # a personal referral link (/join?ref=<movement_id>).
    referred_by: Optional[str] = None


@router.post("/volunteers")
async def create_volunteer(payload: VolunteerCreate):
    email = payload.email.lower()
    existing = await db.volunteers.find_one({"email": email})
    if existing:
        # Dedupe by email, same shape as join_movement: a volunteer dashboard
        # login is keyed by email, so there can only be one record per address.
        # No new access code here -- the original signup's code still works.
        return {
            "message": "You're already registered as a volunteer!",
            "already": True,
            "volunteer_id": existing.get("volunteer_id"),
            "name": existing.get("name"),
            "created_at": existing.get("created_at"),
        }

    volunteer_id = f"RTR-VOL-{datetime.now(timezone.utc).year}-{new_id().replace('-', '')[:6].upper()}"
    access_code = generate_access_code()
    created_at = now_iso()
    await db.volunteers.insert_one(
        {
            "id": new_id(),
            "volunteer_id": volunteer_id,
            **payload.model_dump(exclude={"email"}),
            "email": email,
            "access_code_hash": hash_password(access_code),
            "created_at": created_at,
        }
    )
    logger.info("New volunteer: %s (%s)", email, volunteer_id)
    return {
        "message": "You're in! Welcome to the movement.",
        "already": False,
        "volunteer_id": volunteer_id,
        "name": payload.name,
        "created_at": created_at,
        # Plaintext exists only in this one response -- only the bcrypt hash is
        # ever stored. The frontend must show this once and never re-fetch it.
        "access_code": access_code,
    }


@router.post("/contact")
async def create_contact(payload: ContactCreate):
    doc = {"id": new_id(), **payload.model_dump(), "created_at": now_iso()}
    await db.contacts.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info("New contact message from: %s", payload.email)
    return doc


@router.post("/newsletter")
async def subscribe_newsletter(payload: NewsletterCreate):
    existing = await db.newsletter.find_one({"email": payload.email})
    if existing:
        return {"message": "You are already subscribed!", "already": True}
    await db.newsletter.insert_one({"id": new_id(), "email": payload.email, "created_at": now_iso()})
    return {"message": "Subscribed! Welcome to the movement.", "already": False}


@router.post("/supporters")
async def join_movement(payload: SupporterCreate):
    """Join the movement. Creates the member account, or recognises an existing one.

    The record itself is written by `core.membership`, which the national
    petition's one-step sign also calls -- one place mints access codes, so a
    supporter created through a petition can log in exactly like one created here.
    """
    record = await membership.ensure_supporter(
        email=payload.email,
        name=payload.name,
        state=payload.state,
        city=payload.city,
        mobile=payload.mobile,
        pledge=payload.pledge,
        campaign_id=payload.campaign_id,
        referred_by=payload.referred_by,
        source="join",
    )
    if record.already:
        # No new access code on a repeat join -- their original one still
        # works, and reissuing here would silently invalidate it.
        return {
            "message": "You're already part of the movement!",
            "already": True,
            "movement_id": record.movement_id,
            "name": record.name,
            "created_at": record.created_at,
        }
    return {
        "message": "You're in! Welcome to the movement.",
        "already": False,
        "movement_id": record.movement_id,
        "name": record.name,
        "created_at": record.created_at,
        # Plaintext exists only in this one response -- only the bcrypt hash is
        # ever stored. The frontend must show this once and never re-fetch it.
        "access_code": record.access_code,
    }


# --------------------------------------------------------------------------
# Admin read
# --------------------------------------------------------------------------
_SUBMISSION_KINDS = {
    "volunteers": "volunteers",
    "contacts": "contacts",
    "supporters": "supporters",
    "newsletter": "newsletter",
}


@router.get("/admin/submissions/{kind}")
async def admin_submissions(kind: str, admin: Principal = Depends(require_permission("submissions.view"))):
    if kind not in _SUBMISSION_KINDS:
        raise HTTPException(status_code=404, detail="Unknown kind")
    # access_code_hash is a bcrypt hash, not a plaintext secret, but there is no
    # reason for it to ever leave the database -- excluding it here means a
    # future frontend change can't accidentally render or log it.
    return (
        await db[_SUBMISSION_KINDS[kind]]
        .find({}, {"_id": 0, "access_code_hash": 0})
        .sort("created_at", -1)
        .to_list(2000)
    )


# --------------------------------------------------------------------------
# Data subject rights (DPDP Act 2023)
# --------------------------------------------------------------------------
@router.delete("/me/data")
async def erase_my_data(
    member: dict = Depends(get_current_member),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    """Erase everything the platform holds about the signed-in member.

    Required by the DPDP Act's right to erasure, and listed as a Phase 0
    obligation precisely because it is far cheaper to build now, against four
    collections, than after twenty modules each hold a copy of someone's email.

    Two halves, because the platform has two databases:

    * MONGO, below: the supporter/volunteer/contact/newsletter records this module
      owns, deleted directly.
    * POSTGRES, via `core.erasure.run_all`: the community side. That used to be a
      list in this function, which stopped being viable at thirteen modules --
      this module cannot import the forum or the academy without breaking §4's
      dependency rule. Each module now registers its own erasure step, core owns
      the order, and a test asserts there are no gaps. See core/erasure.py.

    Deletion is real, not a soft flag: a `deleted: true` marker on a row that
    still contains the person's mobile number does not satisfy an erasure
    request.
    """
    email = member["email"]
    supporter = await db.supporters.find_one({"email": email})

    removed = {
        "supporters": (await db.supporters.delete_many({"email": email})).deleted_count,
        "volunteers": (await db.volunteers.delete_many({"email": email})).deleted_count,
        "contacts": (await db.contacts.delete_many({"email": email})).deleted_count,
        "newsletter": (await db.newsletter.delete_many({"email": email})).deleted_count,
    }

    if supporter:
        volunteer_ids = await db.volunteers.distinct("id", {"email": email})
        if volunteer_ids:
            removed["contributions"] = (
                await db.volunteer_contributions.delete_many({"volunteer_id": {"$in": volunteer_ids}})
            ).deleted_count
        # Referral links are severed rather than cascaded: the people this
        # person referred are separate data subjects whose own records must
        # survive, but they must not keep pointing at a deleted movement_id.
        await db.supporters.update_many(
            {"referred_by": supporter.get("movement_id")}, {"$set": {"referred_by": None}}
        )

    if session is not None:
        removed.update(await erasure.run_all(session, email))

    logger.info("Erasure request completed for %s: %s", email, removed)
    return {
        "ok": True,
        "removed": removed,
        # Named explicitly rather than left to the privacy policy, because this is
        # the moment the person is deciding, and an honest answer here is worth
        # more than a reassuring one.
        "retained": [
            "The audit log of staff edits to platform records, which is append-only "
            "and does not contain your submissions.",
            "Replies other members wrote to your posts -- their words, with your name detached.",
            "Petitions you started that other people have signed, with your authorship removed.",
            "Resolved corrections you filed, anonymised, because they are part of the "
            "public history of the record they concern.",
        ],
    }
