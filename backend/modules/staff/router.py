"""Staff account and role administration.

The pre-Phase-0 shape of these endpoints (a flat `permissions` list per user) is
preserved exactly so the existing admin screen keeps working, while the role
endpoints underneath it expose the richer model from §6. The intended workflow
is roles first, direct grants only for genuine one-offs.
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit
from backend.core.deps import get_optional_session, require_permission
from backend.core.models import User, UserRole
from backend.core.mongo import db as mongo_db
from backend.core.permissions import ALL_PERMISSIONS, PERMISSIONS, ROLES
from backend.core.rbac import Principal, RoleAssignmentError, validate_assignment
from backend.core.security import hash_password, now_iso
from backend.core.models import new_id

logger = logging.getLogger(__name__)
router = APIRouter(tags=["staff"])


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    permissions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[list[str]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)


class RoleAssignment(BaseModel):
    role: str
    state_code: Optional[str] = None
    district_code: Optional[str] = None


def _validate_permissions(permissions: list[str]) -> None:
    invalid = [p for p in permissions if p not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown permissions: {invalid}")


def _serialise(user: User, role_rows: list[UserRole]) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": "admin",
        "permissions": list(user.extra_permissions or []),
        "roles": [
            {"role": r.role_key, "state": r.state_code, "district": r.district_code} for r in role_rows
        ],
        "active": user.active,
        "isBootstrap": user.is_bootstrap,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "created_by": user.created_by,
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def _roles_for(session: AsyncSession, user_ids: list[str]) -> dict[str, list[UserRole]]:
    if not user_ids:
        return {}
    rows = (await session.execute(select(UserRole).where(UserRole.user_id.in_(user_ids)))).scalars()
    grouped: dict[str, list[UserRole]] = {uid: [] for uid in user_ids}
    for row in rows:
        grouped.setdefault(row.user_id, []).append(row)
    return grouped


# --------------------------------------------------------------------------
# Registry introspection -- lets the admin UI render checkboxes without
# hardcoding a copy of the registry that then drifts out of sync with it.
# --------------------------------------------------------------------------
@router.get("/admin/permissions")
async def list_permissions(admin: Principal = Depends(require_permission("users.manage"))):
    return [{"key": p.key, "label": p.label, "category": p.category} for p in PERMISSIONS]


@router.get("/admin/roles")
async def list_roles(admin: Principal = Depends(require_permission("users.manage"))):
    return [
        {
            "key": r.key,
            "label": r.label,
            "description": r.description,
            "scoped": r.scoped,
            "rank": r.rank,
            "permissions": list(r.permissions),
            # Pre-computed so the UI can grey out roles the caller may not grant
            # instead of offering them and failing on submit.
            "grantable": admin.legacy_full_access or r.rank < admin.rank,
        }
        for r in ROLES
    ]


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
@router.get("/admin/users")
async def list_admin_users(
    admin: Principal = Depends(require_permission("users.manage")),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    if session is None:
        # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
        return await mongo_db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(500)

    users = list((await session.execute(select(User).order_by(User.created_at))).scalars())
    roles = await _roles_for(session, [u.id for u in users])
    return [_serialise(u, roles.get(u.id, [])) for u in users]


@router.post("/admin/users")
async def create_admin_user(
    payload: AdminUserCreate,
    request: Request,
    admin: Principal = Depends(require_permission("users.manage")),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    email = payload.email.lower()
    _validate_permissions(payload.permissions)

    if session is None:
        # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
        if await mongo_db.users.find_one({"email": email}):
            raise HTTPException(status_code=409, detail="A user with this email already exists")
        doc = {
            "id": new_id(),
            "email": email,
            "password_hash": hash_password(payload.password),
            "name": payload.name,
            "role": "admin",
            "permissions": payload.permissions,
            "active": True,
            "created_at": now_iso(),
            "created_by": admin.id,
        }
        await mongo_db.users.insert_one(dict(doc))
        doc.pop("_id", None)
        doc.pop("password_hash", None)
        return doc

    if (await session.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    # Granting a permission you do not hold yourself is privilege escalation by
    # proxy -- the rank check on roles would be pointless without this.
    if not admin.legacy_full_access:
        overreach = [p for p in payload.permissions if not admin.can(p)]
        if overreach:
            raise HTTPException(
                status_code=403,
                detail=f"You cannot grant permissions you do not hold: {overreach}",
            )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        extra_permissions=payload.permissions,
        active=True,
        created_by=admin.id,
    )
    session.add(user)
    await session.flush()

    for role_key in payload.roles:
        try:
            validate_assignment(admin, role_key, None, None)
        except RoleAssignmentError as e:
            raise HTTPException(status_code=400, detail=str(e))
        session.add(UserRole(user_id=user.id, role_key=role_key, granted_by=admin.id))
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="staff_user",
        entity_id=user.id,
        summary=f"Created staff account {email}",
        changes={"email": {"before": None, "after": email}, "roles": {"before": [], "after": payload.roles}},
        is_public=False,
        request=request,
    )

    roles = await _roles_for(session, [user.id])
    return _serialise(user, roles.get(user.id, []))


@router.put("/admin/users/{user_id}")
async def update_admin_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("users.manage")),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    if payload.permissions is not None:
        _validate_permissions(payload.permissions)

    if session is None:
        # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
        updates: dict = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.permissions is not None:
            updates["permissions"] = payload.permissions
        if payload.active is not None:
            if user_id == admin.id and not payload.active:
                raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
            updates["active"] = payload.active
        if payload.password:
            updates["password_hash"] = hash_password(payload.password)
        if not updates:
            raise HTTPException(status_code=400, detail="No changes provided")
        res = await mongo_db.users.update_one({"id": user_id}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return await mongo_db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    changes: dict = {}
    if payload.name is not None and payload.name != user.name:
        changes["name"] = {"before": user.name, "after": payload.name}
        user.name = payload.name

    if payload.permissions is not None:
        if not admin.legacy_full_access:
            overreach = [p for p in payload.permissions if not admin.can(p)]
            if overreach:
                raise HTTPException(
                    status_code=403,
                    detail=f"You cannot grant permissions you do not hold: {overreach}",
                )
        if list(user.extra_permissions or []) != payload.permissions:
            changes["permissions"] = {"before": list(user.extra_permissions or []), "after": payload.permissions}
            user.extra_permissions = payload.permissions

    if payload.active is not None:
        if user_id == admin.id and not payload.active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if user.is_bootstrap and not payload.active:
            # The bootstrap account is recreated and reactivated from the
            # environment on every cold start, so "deactivate" would appear to
            # work and then silently undo itself. Rejecting it is more honest
            # than accepting a change that will not stick.
            raise HTTPException(
                status_code=400,
                detail="The bootstrap admin cannot be deactivated. Change ADMIN_EMAIL and redeploy instead.",
            )
        if user.active != payload.active:
            changes["active"] = {"before": user.active, "after": payload.active}
            user.active = payload.active

    if payload.password:
        user.password_hash = hash_password(payload.password)
        # The value is never logged, but the fact of the reset is: an
        # unexplained password change on someone else's account is exactly the
        # event an audit log exists to surface.
        changes["password"] = {"before": "***", "after": "reset"}

    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type="staff_user",
        entity_id=user.id,
        summary=f"Updated staff account {user.email}",
        changes=changes,
        is_public=False,
        request=request,
    )

    roles = await _roles_for(session, [user.id])
    return _serialise(user, roles.get(user.id, []))


@router.delete("/admin/users/{user_id}")
async def delete_admin_user(
    user_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("users.manage")),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if session is None:
        # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
        res = await mongo_db.users.delete_one({"id": user_id})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"ok": True}

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_bootstrap:
        raise HTTPException(
            status_code=400,
            detail="The bootstrap admin cannot be deleted. Change ADMIN_EMAIL and redeploy instead.",
        )

    email = user.email
    await session.delete(user)
    await audit.record(
        session,
        actor=admin,
        action="delete",
        entity_type="staff_user",
        entity_id=user_id,
        summary=f"Deleted staff account {email}",
        is_public=False,
        request=request,
    )
    return {"ok": True}


# --------------------------------------------------------------------------
# Role assignment
# --------------------------------------------------------------------------
@router.post("/admin/users/{user_id}/roles")
async def assign_role(
    user_id: str,
    payload: RoleAssignment,
    request: Request,
    admin: Principal = Depends(require_permission("roles.manage")),
    session: AsyncSession = Depends(get_optional_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Role assignment requires the relational database")

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        validate_assignment(admin, payload.role, payload.state_code, payload.district_code)
    except RoleAssignmentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_key == payload.role,
                UserRole.state_code.is_(payload.state_code)
                if payload.state_code is None
                else UserRole.state_code == payload.state_code,
                UserRole.district_code.is_(payload.district_code)
                if payload.district_code is None
                else UserRole.district_code == payload.district_code,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This role is already assigned with that scope")

    session.add(
        UserRole(
            user_id=user_id,
            role_key=payload.role,
            state_code=payload.state_code,
            district_code=payload.district_code,
            granted_by=admin.id,
        )
    )
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="grant_role",
        entity_type="staff_user",
        entity_id=user_id,
        summary=f"Granted {payload.role} to {user.email}",
        changes={
            "role": {"before": None, "after": payload.role},
            "scope": {"before": None, "after": [payload.state_code, payload.district_code]},
        },
        is_public=False,
        request=request,
    )

    roles = await _roles_for(session, [user_id])
    return _serialise(user, roles.get(user_id, []))


@router.delete("/admin/users/{user_id}/roles/{role_key}")
async def revoke_role(
    user_id: str,
    role_key: str,
    request: Request,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    admin: Principal = Depends(require_permission("roles.manage")),
    session: AsyncSession = Depends(get_optional_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Role assignment requires the relational database")

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Losing the last Super Admin locks everyone out of role management for
    # good -- there is no recovery path short of editing the database by hand.
    if role_key == "super_admin":
        remaining = (
            await session.execute(
                select(UserRole).where(UserRole.role_key == "super_admin", UserRole.user_id != user_id)
            )
        ).scalars().all()
        if not remaining:
            raise HTTPException(
                status_code=400, detail="Cannot revoke the last Super Admin on the platform"
            )

    result = await session.execute(
        delete(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_key == role_key,
            UserRole.state_code.is_(state_code) if state_code is None else UserRole.state_code == state_code,
            UserRole.district_code.is_(district_code)
            if district_code is None
            else UserRole.district_code == district_code,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="That role assignment does not exist")

    await audit.record(
        session,
        actor=admin,
        action="revoke_role",
        entity_type="staff_user",
        entity_id=user_id,
        summary=f"Revoked {role_key} from {user.email}",
        changes={"role": {"before": role_key, "after": None}},
        is_public=False,
        request=request,
    )

    roles = await _roles_for(session, [user_id])
    return _serialise(user, roles.get(user_id, []))
