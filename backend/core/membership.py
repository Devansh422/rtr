"""Creating the supporter record that sits behind a member account.

This lives in core rather than in `modules/submissions` because two very
different surfaces now need the same thing: the join flow (`POST /supporters`)
and the national petition's one-step sign (`POST /petitions/{slug}/sign-public`),
where somebody who has never heard of "joining the movement" types their name
and email under a petition and is thereby a member.

There is exactly one way to mint an access code and exactly one place that
decides what a supporter document contains, because the alternative -- two
copies of a bcrypt-hashed credential path that drift -- is how a login stops
working for half the people who have one.

WHAT THIS DOES NOT DO. It does not verify that the person controls the address
they typed. Nothing in this platform does yet, and every count that rests on it
should be described accordingly: a signature is one verified *account*, unique
per petition and enforced by a database constraint, not a proven identity. When
email confirmation ships, it belongs here, and both callers gain it at once.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import logging

from backend.core.models import new_id
from backend.core.mongo import db
from backend.core.security import generate_access_code, hash_password, now_iso

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupporterRecord:
    email: str
    name: str
    movement_id: str
    created_at: str
    already: bool
    # Plaintext, and only ever on the response that created the record -- only the
    # bcrypt hash is stored, so this string cannot be produced again afterwards.
    # A returning supporter gets None here: reissuing a code would silently
    # invalidate the one they already have.
    access_code: Optional[str]


async def member_exists(email: str) -> bool:
    """Does this address already have a member account?

    Both collections are checked, for the same reason `auth/member-login` checks
    both: one person can be a supporter, a volunteer, or both.

    This is a SECURITY gate, not a convenience. Any path that hands out a session
    without checking a credential must first establish that it is not handing out
    somebody else's -- an address that can already log in has an owner, and that
    owner did not type this form.
    """
    email = (email or "").lower()
    if not email:
        return False
    return bool(
        await db.supporters.find_one({"email": email}, {"_id": 1})
        or await db.volunteers.find_one({"email": email}, {"_id": 1})
    )


async def ensure_supporter(
    *,
    email: str,
    name: str,
    state: Optional[str] = None,
    city: Optional[str] = None,
    mobile: Optional[str] = None,
    pledge: bool = True,
    campaign_id: Optional[str] = None,
    referred_by: Optional[str] = None,
    source: str = "join",
) -> SupporterRecord:
    """Find or create the supporter for `email`, and subscribe them to the list.

    Idempotent by email, which is the same key `auth/member-login` looks up, so
    one address is one member however many entry points it arrives through.
    """
    # Lowercased for storage so it matches how member_login looks emails up.
    email = email.lower()
    existing = await db.supporters.find_one({"email": email})
    if existing:
        return SupporterRecord(
            email=email,
            name=existing.get("name") or name,
            movement_id=existing.get("movement_id"),
            created_at=existing.get("created_at"),
            already=True,
            access_code=None,
        )

    movement_id = f"RTR-{datetime.now(timezone.utc).year}-{new_id().replace('-', '')[:6].upper()}"
    access_code = generate_access_code()
    created_at = now_iso()
    await db.supporters.insert_one(
        {
            "id": new_id(),
            "movement_id": movement_id,
            "name": name,
            "email": email,
            "state": state,
            "city": city,
            "mobile": mobile,
            "pledge": pledge,
            "campaign_id": campaign_id,
            "referred_by": referred_by,
            "source": source,
            "access_code_hash": hash_password(access_code),
            "created_at": created_at,
        }
    )
    if not await db.newsletter.find_one({"email": email}):
        await db.newsletter.insert_one(
            {"id": new_id(), "email": email, "source": "supporter", "created_at": created_at}
        )
    logger.info("New supporter: %s (%s) via %s", email, movement_id, source)

    return SupporterRecord(
        email=email,
        name=name,
        movement_id=movement_id,
        created_at=created_at,
        already=False,
        access_code=access_code,
    )
