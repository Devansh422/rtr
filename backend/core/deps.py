"""FastAPI dependencies: authentication, permission gates and DB sessions."""

from typing import AsyncIterator, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config, db as database
from backend.core.models import Citizen, User, utcnow
from backend.core.mongo import db as mongo_db
from backend.core.rbac import Principal, resolve_legacy_principal, resolve_principal
from backend.core.security import decode_token


async def get_session() -> AsyncIterator[AsyncSession]:
    """Request-scoped Postgres session. 503 when Postgres is not configured."""
    if not config.postgres_enabled():
        raise HTTPException(
            status_code=503,
            detail="This feature requires the relational database (DATABASE_URL is not configured)",
        )
    async for session in database.session_scope():
        yield session


async def get_optional_session() -> AsyncIterator[Optional[AsyncSession]]:
    """Like get_session but yields None instead of failing.

    For endpoints that work either way -- typically because they have a legacy
    Mongo path to fall back on during the migration.
    """
    if not config.postgres_enabled():
        yield None
        return
    async for session in database.session_scope():
        yield session


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth[7:]


def _decode(token: str, expected_type: str) -> dict:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != expected_type:
        # Token types are not interchangeable: a member token must never be
        # replayable against an admin endpoint, or vice versa.
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


async def get_current_admin(
    request: Request, session: Optional[AsyncSession] = Depends(get_optional_session)
) -> Principal:
    payload = _decode(_bearer_token(request), "access")
    user_id = payload.get("sub")

    if session is not None:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="Not authorized")
        if not user.active:
            raise HTTPException(status_code=401, detail="This account has been deactivated")
        return await resolve_principal(session, user)

    # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
    doc = await mongo_db.users.find_one({"id": user_id})
    if not doc or doc.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    if doc.get("active") is False:
        raise HTTPException(status_code=401, detail="This account has been deactivated")
    return resolve_legacy_principal(doc)


async def get_current_member(request: Request) -> dict:
    """Auth for the supporter/volunteer dashboards.

    Members are not staff: they have no permissions and no Principal, only an
    identity. Keeping them on a separate token type and a separate dependency
    is what guarantees a supporter's token can never reach an admin route.
    """
    payload = _decode(_bearer_token(request), "member")
    return {"email": payload["email"]}


async def get_current_citizen(
    request: Request, session: AsyncSession = Depends(get_session)
) -> Citizen:
    """The signed-in member's community identity, created on first use.

    Lazy creation is the whole design. A supporter who only ever downloads a
    certificate never needs a Citizen row; the first time they post in the forum
    or sign a petition, one appears, keyed by the email already inside their
    existing member token. No second signup, no second password, no second
    session -- and no empty rows for the majority who only read.

    `display_name` defaults to a pseudonym rather than their real name. Someone
    reporting on their own municipal ward should not have to publish their legal
    name to do it (see the note on the Citizen model).
    """
    member = await get_current_member(request)
    email = member["email"].lower()

    citizen = (
        await session.execute(select(Citizen).where(Citizen.email == email))
    ).scalar_one_or_none()

    if citizen is None:
        # Derive a neutral handle from the local part of the address. Not
        # guaranteed unique and not required to be: `id` is the identifier,
        # display_name is a label the member can change.
        handle = email.split("@")[0][:24].replace(".", " ").strip().title() or "Citizen"
        supporter = await mongo_db.supporters.find_one({"email": email}, {"state": 1})
        citizen = Citizen(
            email=email,
            display_name=handle,
            state_code=None,
            # The supporter record's `state` is a free-text form field, not a
            # state code, so it is not copied into a column that RBAC scoping
            # reads. Recorded loosely instead, for the "reports from your state"
            # filter, until the signup form is migrated to codes.
            contributions={"signupState": (supporter or {}).get("state")} if supporter else {},
        )
        session.add(citizen)
        await session.flush()

    citizen.last_seen_at = utcnow()
    return citizen


async def require_speaking_citizen(
    citizen: Citizen = Depends(get_current_citizen),
) -> Citizen:
    """Like get_current_citizen, but refuses a muted account.

    Reads stay open to a muted member on purpose: a mute is a restriction on
    speaking, not a ban from the platform, and telling someone they may not read
    a public forum they are muted in would be both pointless and punitive.
    """
    if citizen.is_muted():
        raise HTTPException(
            status_code=403,
            detail=(
                "Posting is paused on your account until "
                f"{citizen.muted_until.date().isoformat()}. Reason: "
                f"{citizen.muted_reason or 'content policy breach'}. "
                "You can contest this through the contact form."
            ),
        )
    return citizen


def require_permission(key: str):
    """Dependency factory for routes whose required permission is fixed.

    Routes whose permission depends on a path parameter (the CMS content CRUD,
    where the key is `content.<ctype>`) check inline via `principal.can(...)`
    instead -- the key is not known at decoration time.
    """

    async def checker(admin: Principal = Depends(get_current_admin)) -> Principal:
        if not admin.can(key):
            raise HTTPException(status_code=403, detail="Your account does not have this permission")
        return admin

    return checker


def require_any_permission(*keys: str):
    """Passes if the caller holds at least one of `keys`."""

    async def checker(admin: Principal = Depends(get_current_admin)) -> Principal:
        if not any(admin.can(k) for k in keys):
            raise HTTPException(status_code=403, detail="Your account does not have this permission")
        return admin

    return checker


def require_state_scope(admin: Principal, state_code: str) -> None:
    """Guard for state-scoped writes. Call inside the handler once the state is known."""
    if not admin.can_in_state(state_code):
        raise HTTPException(status_code=403, detail=f"Your account is not scoped to {state_code}")
