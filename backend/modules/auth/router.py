"""Staff login, session introspection, and member (supporter/volunteer) login.

The response shapes here are frozen: the admin SPA and the member dashboard both
read them, and the integration suite asserts on them. The Phase 0 refactor moved
where the user record is read FROM without changing anything that goes over
the wire.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_admin, get_current_member, get_optional_session
from backend.core.models import User, utcnow
from backend.core.mongo import db as mongo_db
from backend.core.rbac import Principal
from backend.core.security import create_access_token, create_member_token, verify_password
from backend.modules.auth import throttle

router = APIRouter(tags=["auth"])


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class MemberLoginPayload(BaseModel):
    email: EmailStr
    code: str


@router.post("/auth/login")
async def login(payload: LoginPayload, session: Optional[AsyncSession] = Depends(get_optional_session)):
    email = payload.email.lower()
    identifier = f"login:{email}"
    await throttle.assert_not_locked(identifier)

    if session is not None:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None or not verify_password(payload.password, user.password_hash or ""):
            await throttle.record_failure(identifier)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.active:
            raise HTTPException(status_code=401, detail="This account has been deactivated")

        await throttle.clear(identifier)
        user.last_login_at = utcnow()
        return {
            "access_token": create_access_token(user.id, user.email),
            "token_type": "bearer",
            # `role` is a constant here rather than a lookup: it distinguishes a
            # staff session from a member session for the frontend, and has
            # never meant "which RBAC role". Real roles arrive via /auth/me.
            "user": {"email": user.email, "name": user.name, "role": "admin"},
        }

    # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
    doc = await mongo_db.users.find_one({"email": email})
    if not doc or not verify_password(payload.password, doc.get("password_hash") or ""):
        await throttle.record_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if doc.get("active") is False:
        raise HTTPException(status_code=401, detail="This account has been deactivated")

    await throttle.clear(identifier)
    return {
        "access_token": create_access_token(doc["id"], doc["email"]),
        "token_type": "bearer",
        "user": {"email": doc["email"], "name": doc.get("name"), "role": doc.get("role")},
    }


@router.get("/auth/me")
async def auth_me(admin: Principal = Depends(get_current_admin)):
    return admin.as_public_dict()


@router.post("/auth/member-login")
async def member_login(payload: MemberLoginPayload):
    """Supporters and volunteers sign in with the access code issued at signup.

    Both collections are checked because one person can be both, and the token
    that comes back is scoped to the email rather than to whichever record's
    code they happened to type.
    """
    email = payload.email.lower()
    code = payload.code.strip().upper()
    identifier = f"member-login:{email}"
    await throttle.assert_not_locked(identifier)

    supporter = await mongo_db.supporters.find_one({"email": email})
    volunteer = await mongo_db.volunteers.find_one({"email": email})

    ok = (supporter is not None and verify_password(code, supporter.get("access_code_hash") or "")) or (
        volunteer is not None and verify_password(code, volunteer.get("access_code_hash") or "")
    )
    if not ok:
        await throttle.record_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or access code")

    await throttle.clear(identifier)
    roles = [role for role, present in (("supporter", supporter), ("volunteer", volunteer)) if present]
    return {"access_token": create_member_token(email), "token_type": "bearer", "roles": roles}


@router.get("/auth/session")
async def member_session(member: dict = Depends(get_current_member)):
    """Cheap "is my member token still valid" check for the dashboard shell."""
    return {"email": member["email"], "authenticated": True}
