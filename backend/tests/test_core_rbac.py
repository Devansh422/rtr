"""Unit tests for the Phase 0 core: registry, RBAC, scoping, audit, seeding.

These run entirely in-process against SQLite, with no Mongo and no Postgres, so
they work on a laptop and in CI without infrastructure. The existing suites
(backend_test.py, test_admin.py) stay as they are: they drive a running server
over HTTP and cover the API contract from the outside.

Set the five required environment variables before importing anything from
backend.core -- config reads them at import time, on purpose.
"""

import os

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "rtr_test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-any-real-environment")
os.environ.setdefault("ADMIN_EMAIL", "bootstrap@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "bootstrap-password-123")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from backend.core import audit  # noqa: E402
from backend.core.bootstrap import (  # noqa: E402
    ensure_role,
    seed_bootstrap_admin,
    sync_geography,
    sync_registry,
)
from backend.core.geography import STATES, stage_index  # noqa: E402
from backend.core.models import (  # noqa: E402
    AuditLog,
    Base,
    Permission,
    Role,
    RolePermission,
    State,
    User,
    UserRole,
)
from backend.core.permissions import (  # noqa: E402
    PERMISSION_KEYS,
    PERMISSION_SET,
    ROLES,
    ROLES_BY_KEY,
    validate_registry,
)
from backend.core.rbac import (  # noqa: E402
    Principal,
    RoleAssignmentError,
    Scope,
    resolve_legacy_principal,
    resolve_principal,
    validate_assignment,
)
from backend.core.security import (  # noqa: E402
    generate_access_code,
    hash_password,
    slugify,
    verify_password,
)


@pytest.fixture
async def session() -> AsyncSession:
    """A fresh in-memory schema per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def seeded(session: AsyncSession) -> AsyncSession:
    await sync_registry(session)
    await sync_geography(session)
    return session


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
class TestRegistry:
    def test_registry_is_self_consistent(self):
        # Also runs at import time; asserted here so a failure is a named test
        # rather than a collection error.
        validate_registry()

    def test_no_role_grants_an_unknown_permission(self):
        for role in ROLES:
            for perm in role.permissions:
                assert perm in PERMISSION_SET, f"{role.key} grants unknown {perm}"

    def test_super_admin_holds_every_permission(self):
        assert set(ROLES_BY_KEY["super_admin"].permissions) == set(PERMISSION_KEYS)

    def test_scoped_roles_are_the_geographic_ones(self):
        assert {r.key for r in ROLES if r.scoped} == {"state_admin", "district_admin"}

    def test_content_writer_cannot_publish_constitution_text(self):
        # A drafting role that can publish is not a drafting role.
        writer = ROLES_BY_KEY["content_writer"]
        assert "constitution.publish" not in writer.permissions
        assert "representatives.publish" not in writer.permissions

    def test_only_super_admin_can_manage_roles(self):
        holders = [r.key for r in ROLES if "roles.manage" in r.permissions]
        assert holders == ["super_admin"]


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------
class TestSeeding:
    async def test_sync_registry_populates_permissions_and_grants(self, session):
        await sync_registry(session)
        assert len((await session.execute(select(Permission))).scalars().all()) == len(PERMISSION_KEYS)
        assert len((await session.execute(select(Role))).scalars().all()) == len(ROLES)

        grants = (await session.execute(select(RolePermission))).scalars().all()
        expected = sum(len(r.permissions) for r in ROLES)
        assert len(grants) == expected

    async def test_sync_registry_is_idempotent(self, session):
        await sync_registry(session)
        first = len((await session.execute(select(RolePermission))).scalars().all())
        await sync_registry(session)
        second = len((await session.execute(select(RolePermission))).scalars().all())
        assert first == second

    async def test_sync_geography_seeds_every_state_and_ut(self, session):
        await sync_geography(session)
        rows = (await session.execute(select(State))).scalars().all()
        assert len(rows) == len(STATES) == 36  # 28 states + 8 union territories

        pilots = {r.code for r in rows if r.is_pilot}
        assert pilots == {"DL", "MH"}

        # Every state starts at the bottom of the pipeline; claiming otherwise
        # would be an unsourced assertion about a legislature.
        assert all(r.campaign_stage == "no_demand" for r in rows)

    async def test_sync_geography_does_not_clobber_campaign_edits(self, session):
        await sync_geography(session)
        delhi = (await session.execute(select(State).where(State.code == "DL"))).scalar_one()
        delhi.campaign_stage = "awareness"
        delhi.campaign_note = "Awareness drive under way across constituencies."
        await session.flush()

        # A redeploy re-runs geography sync; editorial state must survive it.
        await sync_geography(session)
        delhi = (await session.execute(select(State).where(State.code == "DL"))).scalar_one()
        assert delhi.campaign_stage == "awareness"
        assert delhi.campaign_note.startswith("Awareness drive")

    async def test_bootstrap_admin_is_created_as_super_admin(self, seeded):
        await seed_bootstrap_admin(seeded)
        user = (
            await seeded.execute(select(User).where(User.email == os.environ["ADMIN_EMAIL"]))
        ).scalar_one()
        assert user.is_bootstrap is True
        assert verify_password(os.environ["ADMIN_PASSWORD"], user.password_hash)

        principal = await resolve_principal(seeded, user)
        assert "super_admin" in principal.roles
        assert principal.can("users.manage")
        assert principal.can("audit.view")

    async def test_bootstrap_admin_rerun_does_not_duplicate_role(self, seeded):
        await seed_bootstrap_admin(seeded)
        await seed_bootstrap_admin(seeded)
        rows = (await seeded.execute(select(UserRole))).scalars().all()
        assert len([r for r in rows if r.role_key == "super_admin"]) == 1

    async def test_bootstrap_admin_password_resets_from_environment(self, seeded):
        await seed_bootstrap_admin(seeded)
        user = (
            await seeded.execute(select(User).where(User.email == os.environ["ADMIN_EMAIL"]))
        ).scalar_one()
        user.password_hash = hash_password("something-else-entirely")
        await seeded.flush()

        # This is the documented password-reset path in DEPLOY.md.
        await seed_bootstrap_admin(seeded)
        await seeded.refresh(user)
        assert verify_password(os.environ["ADMIN_PASSWORD"], user.password_hash)


# --------------------------------------------------------------------------
# Permission resolution
# --------------------------------------------------------------------------
class TestResolution:
    async def test_effective_permissions_union_roles_and_direct_grants(self, seeded):
        user = User(email="editor@example.com", password_hash="x", name="Ed", extra_permissions=["audit.view"])
        seeded.add(user)
        await seeded.flush()
        await ensure_role(seeded, user.id, "content_writer")

        principal = await resolve_principal(seeded, user)
        assert principal.can("content.blogs")  # from the role
        assert principal.can("audit.view")  # direct grant
        assert not principal.can("users.manage")

    async def test_unknown_direct_grants_are_ignored(self, seeded):
        user = User(
            email="stale@example.com",
            password_hash="x",
            name="S",
            extra_permissions=["content.blogs", "permission.that.was.deleted"],
        )
        seeded.add(user)
        await seeded.flush()

        principal = await resolve_principal(seeded, user)
        assert principal.can("content.blogs")
        assert not principal.can("permission.that.was.deleted")

    async def test_rank_is_the_highest_held_role(self, seeded):
        user = User(email="multi@example.com", password_hash="x", name="M", extra_permissions=[])
        seeded.add(user)
        await seeded.flush()
        await ensure_role(seeded, user.id, "content_writer")  # rank 20
        await ensure_role(seeded, user.id, "state_admin", state_code="MH")  # rank 60

        principal = await resolve_principal(seeded, user)
        assert principal.rank == 60

    def test_legacy_account_without_permission_field_gets_full_access(self):
        # The pre-RBAC bootstrap admin. Treating this as "no permissions" would
        # have locked a live deployment out of its own admin panel.
        principal = resolve_legacy_principal({"id": "1", "email": "old@example.com", "name": "Old"})
        assert principal.legacy_full_access
        assert principal.can("anything.at.all")

    def test_legacy_account_with_explicit_empty_list_has_nothing(self):
        principal = resolve_legacy_principal(
            {"id": "2", "email": "new@example.com", "name": "New", "permissions": []}
        )
        assert not principal.legacy_full_access
        assert not principal.can("content.blogs")


# --------------------------------------------------------------------------
# Geographic scoping
# --------------------------------------------------------------------------
class TestScoping:
    def test_unscoped_principal_is_platform_wide(self):
        p = Principal(id="1", email="a@b.c", name="A", permissions=frozenset({"states.edit"}))
        assert p.is_platform_wide()
        assert p.can_in_state("MH")

    def test_state_admin_is_confined_to_their_state(self):
        p = Principal(
            id="1",
            email="mh@b.c",
            name="A",
            permissions=frozenset({"states.edit"}),
            roles=("state_admin",),
            scopes=(Scope("MH", None),),
            rank=60,
        )
        assert p.can_in_state("MH")
        assert not p.can_in_state("DL")

    def test_state_scope_covers_every_district_within_it(self):
        p = Principal(
            id="1", email="a@b.c", name="A", permissions=frozenset(), scopes=(Scope("MH", None),), rank=60
        )
        assert p.can_in_district("MH", "MH-PUNE")
        assert not p.can_in_district("DL", "DL-NORTH")

    def test_district_scope_does_not_widen_to_the_state(self):
        p = Principal(
            id="1",
            email="a@b.c",
            name="A",
            permissions=frozenset(),
            scopes=(Scope("MH", "MH-PUNE"),),
            rank=50,
        )
        assert p.can_in_district("MH", "MH-PUNE")
        assert not p.can_in_district("MH", "MH-NAGPUR")


# --------------------------------------------------------------------------
# Role assignment guards
# --------------------------------------------------------------------------
class TestAssignmentGuards:
    def _principal(self, rank: int, scopes=()) -> Principal:
        return Principal(
            id="1", email="a@b.c", name="A", permissions=frozenset(), scopes=scopes, rank=rank
        )

    def test_cannot_grant_a_role_at_or_above_own_rank(self):
        editor = self._principal(rank=35)
        with pytest.raises(RoleAssignmentError, match="at or above"):
            validate_assignment(editor, "super_admin", None, None)
        with pytest.raises(RoleAssignmentError, match="at or above"):
            validate_assignment(editor, "editor", None, None)

    def test_can_grant_a_strictly_lower_role(self):
        editor = self._principal(rank=35)
        validate_assignment(editor, "content_writer", None, None)  # rank 20, no raise

    def test_scoped_role_requires_a_state(self):
        admin = self._principal(rank=100)
        with pytest.raises(RoleAssignmentError, match="specific state"):
            validate_assignment(admin, "state_admin", None, None)

    def test_unscoped_role_rejects_a_state(self):
        admin = self._principal(rank=100)
        with pytest.raises(RoleAssignmentError, match="platform-wide"):
            validate_assignment(admin, "editor", "MH", None)

    def test_state_admin_cannot_grant_roles_in_another_state(self):
        mh_admin = self._principal(rank=60, scopes=(Scope("MH", None),))
        with pytest.raises(RoleAssignmentError, match="cannot grant roles in DL"):
            validate_assignment(mh_admin, "district_admin", "DL", "DL-NORTH")

    def test_unknown_role_is_rejected(self):
        admin = self._principal(rank=100)
        with pytest.raises(RoleAssignmentError, match="Unknown role"):
            validate_assignment(admin, "supreme_leader", None, None)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------
class TestAudit:
    def test_diff_records_only_changed_fields(self):
        changes = audit.diff({"a": 1, "b": 2}, {"a": 1, "b": 3})
        assert changes == {"b": {"before": 2, "after": 3}}

    def test_diff_never_archives_secrets(self):
        changes = audit.diff(
            {"password_hash": "old", "access_code_hash": "old", "name": "A"},
            {"password_hash": "new", "access_code_hash": "new", "name": "B"},
        )
        assert set(changes) == {"name"}

    def test_diff_captures_creation_and_deletion(self):
        assert audit.diff(None, {"a": 1}) == {"a": {"before": None, "after": 1}}
        assert audit.diff({"a": 1}, None) == {"a": {"before": 1, "after": None}}

    async def test_record_and_read_back_history(self, seeded):
        actor = Principal(id="u1", email="editor@example.com", name="E", permissions=frozenset())
        await audit.record(
            seeded,
            actor=actor,
            action="campaign_stage",
            entity_type="state",
            entity_id="MH",
            summary="No Demand Yet -> Awareness Stage",
            changes={"stage": {"before": "no_demand", "after": "awareness"}},
            source_url="https://example.gov.in/record",
        )
        await seeded.flush()

        entries = await audit.history(seeded, entity_type="state", entity_id="MH")
        assert len(entries) == 1
        assert entries[0].source_url == "https://example.gov.in/record"

    async def test_public_history_omits_the_actor(self, seeded):
        actor = Principal(id="u1", email="volunteer@example.com", name="V", permissions=frozenset())
        await audit.record(
            seeded, actor=actor, action="update", entity_type="state", entity_id="DL", summary="x"
        )
        await seeded.flush()

        entry = (await seeded.execute(select(AuditLog))).scalars().first()
        public = audit.to_dict(entry, include_actor=False)
        internal = audit.to_dict(entry, include_actor=True)

        assert "actor" not in public
        assert internal["actor"]["email"] == "volunteer@example.com"

    async def test_private_entries_are_excluded_from_public_history(self, seeded):
        actor = Principal(id="u1", email="a@b.c", name="A", permissions=frozenset())
        await audit.record(
            seeded, actor=actor, action="update", entity_type="state", entity_id="GA",
            summary="internal", is_public=False,
        )
        await seeded.flush()

        assert await audit.history(seeded, entity_type="state", entity_id="GA", public_only=True) == []
        assert len(await audit.history(seeded, entity_type="state", entity_id="GA", public_only=False)) == 1


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------
class TestHelpers:
    def test_campaign_stage_ordering(self):
        assert stage_index("no_demand") == 0
        assert stage_index("act_enforced") == 7
        assert stage_index("bill_introduced") > stage_index("awareness")
        # An unrecognised stage must not sort as "furthest along".
        assert stage_index("nonsense") == 0

    def test_access_code_avoids_confusable_characters(self):
        for _ in range(200):
            code = generate_access_code()
            assert len(code) == 9 and code[4] == "-"
            assert not set(code[:4] + code[5:]) & set("O0I1")

    def test_slugify(self):
        assert slugify("Article 324: Election Commission") == "article-324-election-commission"
        assert slugify("") != ""  # falls back to a random id rather than an empty key

    def test_password_hash_roundtrip(self):
        h = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", h)
        assert not verify_password("wrong", h)
