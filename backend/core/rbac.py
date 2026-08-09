"""Resolving "who is this and what may they do", independent of FastAPI.

The authenticated caller is represented by a `Principal`: a flat, already-
resolved snapshot of identity plus effective permissions plus geographic scope.
Route handlers never re-query roles; they ask the Principal. That keeps the
permission decision in one place and makes it cheap to check several times in a
request.

Two resolution paths exist during the Phase 0 migration -- see the DATABASE_URL
note in core/config.py for the removal trigger on the legacy one.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config
from backend.core.models import Role, RolePermission, User, UserRole
from backend.core.permissions import PERMISSION_SET, ROLES_BY_KEY

logger = logging.getLogger(__name__)


@dataclass
class Scope:
    """Where a role assignment applies. Both None means platform-wide."""

    state_code: Optional[str] = None
    district_code: Optional[str] = None


@dataclass
class Principal:
    id: str
    email: str
    name: str
    permissions: frozenset[str]
    roles: tuple[str, ...] = ()
    scopes: tuple[Scope, ...] = ()
    rank: int = 0
    # Set for accounts that predate RBAC and carry no explicit permission list.
    # See resolve_legacy_principal for why that means full access.
    legacy_full_access: bool = False

    def can(self, permission: str) -> bool:
        return self.legacy_full_access or permission in self.permissions

    def is_platform_wide(self) -> bool:
        """True when at least one role is unscoped, i.e. applies nationally."""
        if self.legacy_full_access:
            return True
        return any(s.state_code is None for s in self.scopes) or not self.scopes

    def can_in_state(self, state_code: str) -> bool:
        if self.is_platform_wide():
            return True
        return any(s.state_code == state_code for s in self.scopes)

    def can_in_district(self, state_code: str, district_code: str) -> bool:
        if self.is_platform_wide():
            return True
        for s in self.scopes:
            if s.state_code != state_code:
                continue
            # A state-level assignment covers every district inside it.
            if s.district_code is None or s.district_code == district_code:
                return True
        return False

    def as_public_dict(self) -> dict:
        """Shape returned by GET /api/auth/me.

        `permissions: None` is the wire signal for legacy full access, matching
        how the admin frontend has always interpreted it -- do not "fix" it to
        an empty list, that would read as "no permissions at all".
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": "admin",
            "permissions": None if self.legacy_full_access else sorted(self.permissions),
            "roles": list(self.roles),
            "scopes": [
                {"state": s.state_code, "district": s.district_code}
                for s in self.scopes
            ],
            "rank": self.rank,
        }


# --------------------------------------------------------------------------
# Postgres resolution (the intended path)
# --------------------------------------------------------------------------
async def resolve_principal(session: AsyncSession, user: User) -> Principal:
    """Effective permissions = union of role grants + direct grants."""
    rows = (
        await session.execute(
            select(UserRole, Role)
            .join(Role, Role.key == UserRole.role_key)
            .where(UserRole.user_id == user.id)
        )
    ).all()

    role_keys = [r.Role.key for r in rows]
    granted: set[str] = set()
    if role_keys:
        grant_rows = (
            await session.execute(
                select(RolePermission.permission_key).where(RolePermission.role_key.in_(role_keys))
            )
        ).scalars()
        granted.update(grant_rows)

    # Unknown keys are dropped rather than trusted: a permission removed from
    # the registry must stop granting access immediately, even if a stale row
    # still names it.
    direct = {p for p in (user.extra_permissions or []) if p in PERMISSION_SET}

    scopes = tuple(Scope(r.UserRole.state_code, r.UserRole.district_code) for r in rows)
    rank = max((r.Role.rank for r in rows), default=0)

    return Principal(
        id=user.id,
        email=user.email,
        name=user.name or "",
        permissions=frozenset(granted | direct),
        roles=tuple(role_keys),
        scopes=scopes,
        rank=rank,
    )


# --------------------------------------------------------------------------
# LEGACY FALLBACK -- delete with the DATABASE_URL removal trigger
# --------------------------------------------------------------------------
def resolve_legacy_principal(user_doc: dict) -> Principal:
    """Build a Principal from a pre-Phase-0 Mongo user document.

    A `permissions` field absent entirely (None) means the account predates
    RBAC -- the original bootstrap admin -- and is treated as full access, so
    that shipping RBAC could never lock out an already-deployed administrator.
    Accounts created after RBAC always carry an explicit list, even an empty one.
    """
    perms = user_doc.get("permissions")
    if perms is None:
        return Principal(
            id=user_doc["id"],
            email=user_doc["email"],
            name=user_doc.get("name") or "",
            permissions=frozenset(),
            rank=100,
            legacy_full_access=True,
        )
    return Principal(
        id=user_doc["id"],
        email=user_doc["email"],
        name=user_doc.get("name") or "",
        permissions=frozenset(p for p in perms if p in PERMISSION_SET),
        rank=50,
    )


# --------------------------------------------------------------------------
# Role assignment rules
# --------------------------------------------------------------------------
class RoleAssignmentError(ValueError):
    """Raised for an assignment the registry forbids; callers map it to a 400."""


def validate_assignment(
    granter: Principal, role_key: str, state_code: Optional[str], district_code: Optional[str]
) -> None:
    role = ROLES_BY_KEY.get(role_key)
    if role is None:
        raise RoleAssignmentError(f"Unknown role: {role_key}")

    # Privilege escalation guard: you may never grant authority equal to or
    # above your own. Without this, anyone holding users.manage could make
    # themselves a Super Admin, which makes every other rank meaningless.
    if not granter.legacy_full_access and role.rank >= granter.rank:
        raise RoleAssignmentError(
            f"You cannot grant the role '{role.label}' -- it ranks at or above your own access level"
        )

    if role.scoped and not state_code:
        raise RoleAssignmentError(f"The role '{role.label}' must be assigned to a specific state")
    if not role.scoped and (state_code or district_code):
        raise RoleAssignmentError(f"The role '{role.label}' applies platform-wide and cannot be scoped")
    if district_code and not state_code:
        raise RoleAssignmentError("A district-scoped role must also name its state")

    # A State Admin granting roles may only do so inside their own state.
    if state_code and not granter.can_in_state(state_code):
        raise RoleAssignmentError(f"You cannot grant roles in {state_code}")
