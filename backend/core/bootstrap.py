"""Startup reconciliation: registry -> database, and the Mongo -> Postgres backfill.

Serverless contract for everything in this module: on Vercel the app is a
serverless function, so these hooks run on EVERY cold start and several cold
starts can happen concurrently (a burst of traffic right after a deploy).
Everything here must therefore be idempotent and tolerant of a sibling instance
doing the same work at the same moment. Where a race is possible the loser
catches IntegrityError, rolls back and moves on -- the next boot finds the work
already done.

DDL is NOT run here. Alembic owns the schema (`python -m backend.scripts.migrate`
or `alembic upgrade head`), because a serverless function racing to create
tables at boot is how you get half-migrated databases. The one exception is
AUTO_CREATE_TABLES=1, a local-development and test convenience.
"""

from typing import Optional
import hashlib
import json
import logging
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config, db as database
from backend.core.geography import STATES
from backend.core.models import (
    Base,
    Permission,
    PlatformMeta,
    Role,
    RolePermission,
    State,
    User,
    UserRole,
)
from backend.core.mongo import content_coll, db as mongo_db
from backend.core.permissions import CONTENT_TYPES, PERMISSIONS, ROLES
from backend.core.security import hash_password, now_iso, verify_password

logger = logging.getLogger(__name__)

SEED_FINGERPRINT_KEY = "seed_fingerprint"


def _registry_fingerprint() -> str:
    """Hash of everything sync_registry/sync_geography would write.

    Changing a role's permission list changes this hash, which is what makes the
    next cold start reconcile instead of skipping.
    """
    payload = json.dumps(
        {
            "permissions": [(p.key, p.label, p.category) for p in PERMISSIONS],
            "roles": [(r.key, r.label, r.description, sorted(r.permissions), r.rank, r.scoped) for r in ROLES],
            "states": [
                (
                    s.code,
                    s.name,
                    s.name_hi,
                    s.slug,
                    s.is_union_territory,
                    s.has_legislature,
                    s.lok_sabha_seats,
                    s.rajya_sabha_seats,
                    s.assembly_seats,
                    s.is_pilot,
                )
                for s in STATES
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _read_meta(session: AsyncSession, key: str) -> Optional[str]:
    row = (await session.execute(select(PlatformMeta).where(PlatformMeta.key == key))).scalar_one_or_none()
    return row.value if row else None


async def _write_meta(session: AsyncSession, key: str, value: str) -> None:
    row = (await session.execute(select(PlatformMeta).where(PlatformMeta.key == key))).scalar_one_or_none()
    if row is None:
        session.add(PlatformMeta(key=key, value=value))
    else:
        row.value = value


# --------------------------------------------------------------------------
# Registry reconciliation
# --------------------------------------------------------------------------
async def sync_registry(session: AsyncSession) -> None:
    """Make the permissions/roles tables match core/permissions.py exactly.

    Reconciliation is authoritative in both directions: a permission removed
    from the registry has its grants dropped, because leaving orphaned grants
    behind is how a revoked capability quietly keeps working.
    """
    existing_perms = {p.key: p for p in (await session.execute(select(Permission))).scalars()}
    registry_perms = {p.key: p for p in PERMISSIONS}

    for key, definition in registry_perms.items():
        row = existing_perms.get(key)
        if row is None:
            session.add(Permission(key=key, label=definition.label, category=definition.category))
        elif (row.label, row.category) != (definition.label, definition.category):
            row.label, row.category = definition.label, definition.category

    for key, row in existing_perms.items():
        if key not in registry_perms:
            await session.delete(row)

    await session.flush()

    existing_roles = {r.key: r for r in (await session.execute(select(Role))).scalars()}
    registry_roles = {r.key: r for r in ROLES}

    for key, definition in registry_roles.items():
        row = existing_roles.get(key)
        if row is None:
            row = Role(
                key=key,
                label=definition.label,
                description=definition.description,
                scoped=definition.scoped,
                rank=definition.rank,
            )
            session.add(row)
        else:
            row.label = definition.label
            row.description = definition.description
            row.scoped = definition.scoped
            row.rank = definition.rank

    for key, row in existing_roles.items():
        if key not in registry_roles:
            await session.delete(row)

    await session.flush()

    # Grants: diff rather than delete-all-and-reinsert, so the common case (no
    # change) writes nothing at all.
    current_grants: set[tuple[str, str]] = {
        (g.role_key, g.permission_key)
        for g in (await session.execute(select(RolePermission))).scalars()
    }
    wanted_grants: set[tuple[str, str]] = {
        (role.key, perm) for role in ROLES for perm in role.permissions
    }

    for role_key, perm_key in wanted_grants - current_grants:
        session.add(RolePermission(role_key=role_key, permission_key=perm_key))

    stale = current_grants - wanted_grants
    if stale:
        for grant in (await session.execute(select(RolePermission))).scalars():
            if (grant.role_key, grant.permission_key) in stale:
                await session.delete(grant)

    await session.flush()


async def sync_geography(session: AsyncSession) -> None:
    """Upsert the states/UTs table from the static list."""
    existing = {s.code: s for s in (await session.execute(select(State))).scalars()}
    for seed in STATES:
        row = existing.get(seed.code)
        if row is None:
            session.add(
                State(
                    code=seed.code,
                    name=seed.name,
                    name_hi=seed.name_hi,
                    slug=seed.slug,
                    is_union_territory=seed.is_union_territory,
                    has_legislature=seed.has_legislature,
                    lok_sabha_seats=seed.lok_sabha_seats,
                    rajya_sabha_seats=seed.rajya_sabha_seats,
                    assembly_seats=seed.assembly_seats,
                    is_pilot=seed.is_pilot,
                )
            )
            continue
        row.name = seed.name
        row.name_hi = seed.name_hi
        row.slug = seed.slug
        row.is_union_territory = seed.is_union_territory
        row.has_legislature = seed.has_legislature
        row.lok_sabha_seats = seed.lok_sabha_seats
        row.rajya_sabha_seats = seed.rajya_sabha_seats
        row.assembly_seats = seed.assembly_seats
        row.is_pilot = seed.is_pilot
    await session.flush()


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
async def backfill_users_from_mongo(session: AsyncSession) -> int:
    """Copy pre-Phase-0 admin accounts from Mongo into Postgres, once.

    Same primary key on both sides (the Mongo documents already store
    `str(uuid.uuid4())` in an `id` field), so this is a copy rather than a
    remapping and re-running it is a no-op. The Mongo `users` collection is left
    untouched: it is the rollback path until DATABASE_URL is set everywhere.
    """
    existing_emails = {e.lower() for e in (await session.execute(select(User.email))).scalars()}
    existing_ids = set((await session.execute(select(User.id))).scalars())

    copied = 0
    async for doc in mongo_db.users.find({"role": "admin"}):
        email = (doc.get("email") or "").lower()
        user_id = doc.get("id")
        if not email or not user_id or email in existing_emails or user_id in existing_ids:
            continue
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=doc.get("password_hash") or "",
                name=doc.get("name") or "",
                active=doc.get("active") is not False,
                # A legacy account with no `permissions` field had implicit full
                # access (see rbac.resolve_legacy_principal). Carrying that over
                # as a real super_admin assignment is done below, once the user
                # row exists -- not as a None here, because Postgres-side
                # "permissions is null means everything" would reintroduce
                # exactly the ambiguity RBAC is meant to remove.
                extra_permissions=list(doc.get("permissions") or []),
                # created_at is deliberately left to the column default rather
                # than parsed from the Mongo ISO string: the original value is a
                # free-text field of unknown timezone discipline, and a wrong
                # timestamp in an audit-adjacent table is worse than an honest
                # "this row was created at backfill time".
            )
        )
        existing_emails.add(email)
        existing_ids.add(user_id)
        copied += 1

    await session.flush()

    if copied:
        logger.info("Backfilled %d admin account(s) from Mongo into Postgres", copied)

    # Legacy full-access accounts (no explicit permission list) become real
    # Super Admins so their access survives the migration verbatim.
    async for doc in mongo_db.users.find({"role": "admin", "permissions": {"$exists": False}}):
        await ensure_role(session, doc.get("id"), "super_admin")

    return copied


async def ensure_role(
    session: AsyncSession,
    user_id: Optional[str],
    role_key: str,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
) -> None:
    """Idempotently assign a role."""
    if not user_id:
        return
    exists = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_key == role_key,
                UserRole.state_code.is_(state_code) if state_code is None else UserRole.state_code == state_code,
                UserRole.district_code.is_(district_code)
                if district_code is None
                else UserRole.district_code == district_code,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(
            UserRole(
                user_id=user_id,
                role_key=role_key,
                state_code=state_code,
                district_code=district_code,
                granted_by="system",
            )
        )
        await session.flush()


async def seed_bootstrap_admin(session: AsyncSession) -> None:
    """Create or repair the account described by ADMIN_EMAIL / ADMIN_PASSWORD.

    ADMIN_PASSWORD stays the source of truth for this one account: changing the
    environment variable and redeploying is the documented password reset (see
    DEPLOY.md). Safe under concurrent cold starts because every instance writes
    a valid hash of the same password, so whichever write lands last still
    leaves the account usable.
    """
    user = (
        await session.execute(select(User).where(User.email == config.ADMIN_EMAIL))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            email=config.ADMIN_EMAIL,
            password_hash=hash_password(config.ADMIN_PASSWORD),
            name="Admin",
            active=True,
            is_bootstrap=True,
            extra_permissions=[],
        )
        session.add(user)
        await session.flush()
        logger.info("Seeded bootstrap admin: %s", config.ADMIN_EMAIL)
    else:
        if not verify_password(config.ADMIN_PASSWORD, user.password_hash or ""):
            user.password_hash = hash_password(config.ADMIN_PASSWORD)
            logger.info("Reset bootstrap admin password from environment: %s", config.ADMIN_EMAIL)
        # Re-flagging matters when the address was first created by hand and
        # only later promoted to the env-managed bootstrap account.
        user.is_bootstrap = True
        if not user.active:
            user.active = True

    await ensure_role(session, user.id, "super_admin")


# --------------------------------------------------------------------------
# Mongo-side seeding (CMS content; unchanged behaviour from pre-Phase-0)
# --------------------------------------------------------------------------
def _load_seed_file(name: str) -> list:
    path = config.CONTENT_DIR / f"{name}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def seed_mongo_content() -> None:
    """Seed empty CMS collections from backend/content/*.json.

    Only collections that are still empty are touched, so an editor's changes in
    the admin panel are never overwritten by a redeploy.
    """
    from pymongo.errors import BulkWriteError, DuplicateKeyError

    for ctype in CONTENT_TYPES:
        coll = content_coll(ctype)
        if await coll.count_documents({}) != 0:
            continue
        items = _load_seed_file(ctype)
        if not items:
            continue
        # Deterministic _id per seeded item makes the insert idempotent: if two
        # cold starts race, the loser's writes are rejected as duplicate keys
        # instead of creating a second copy of the seed data. ordered=False lets
        # the non-conflicting documents through. _id is never exposed by the API
        # (every read projects it away).
        docs = []
        for idx, item in enumerate(items):
            doc = dict(item)
            doc["_id"] = f"seed:{ctype}:{doc.get('id') or idx}"
            docs.append(doc)
        try:
            await coll.insert_many(docs, ordered=False)
            logger.info("Seeded content_%s with %d items", ctype, len(docs))
        except BulkWriteError as e:
            non_duplicate = [err for err in e.details.get("writeErrors", []) if err.get("code") != 11000]
            if non_duplicate:
                logger.warning("seed content_%s: %s", ctype, non_duplicate)
            else:
                logger.info("content_%s already seeded by another instance", ctype)
        except DuplicateKeyError:
            logger.info("content_%s already seeded by another instance", ctype)


async def seed_mongo_admin() -> None:
    """LEGACY FALLBACK: seed the admin into Mongo when Postgres is unconfigured.

    Delete alongside the other DATABASE_URL fallbacks -- see core/config.py.
    """
    import uuid

    from pymongo.errors import DuplicateKeyError

    try:
        result = await mongo_db.users.update_one(
            {"email": config.ADMIN_EMAIL},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "password_hash": hash_password(config.ADMIN_PASSWORD),
                    "name": "Admin",
                    "role": "admin",
                    "created_at": now_iso(),
                }
            },
            upsert=True,
        )
        if result.upserted_id is not None:
            logger.info("Seeded admin user (Mongo): %s", config.ADMIN_EMAIL)
            return
    except DuplicateKeyError:
        pass

    existing = await mongo_db.users.find_one({"email": config.ADMIN_EMAIL})
    if existing and not verify_password(config.ADMIN_PASSWORD, existing.get("password_hash") or ""):
        await mongo_db.users.update_one(
            {"email": config.ADMIN_EMAIL},
            {"$set": {"password_hash": hash_password(config.ADMIN_PASSWORD)}},
        )
        logger.info("Updated admin password (Mongo): %s", config.ADMIN_EMAIL)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
async def create_all_tables_for_dev() -> None:
    """Create tables directly from the models, bypassing Alembic.

    Local development and tests only, behind AUTO_CREATE_TABLES=1. Never enable
    this in a deployed environment: it silently diverges the live schema from
    the migration history, and the first migration that assumes otherwise fails
    in a way that is genuinely painful to unpick.
    """
    engine = database.get_engine()
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("AUTO_CREATE_TABLES: schema created from models (development only)")


async def run_postgres_bootstrap() -> None:
    if os.environ.get("AUTO_CREATE_TABLES") == "1":
        await create_all_tables_for_dev()

    fingerprint = _registry_fingerprint()

    # `transaction()` rather than `async for session_scope()`: the early return
    # below writes (seed_bootstrap_admin may reset the password from the
    # environment), and a return out of an `async for` over an async generator
    # does not commit. See the warning in core/db.transaction.
    async with database.transaction() as session:
        try:
            if await _read_meta(session, SEED_FINGERPRINT_KEY) == fingerprint:
                # Registry unchanged since the last reconciliation; the admin
                # account is still checked because ADMIN_PASSWORD may have been
                # rotated without touching the registry.
                await seed_bootstrap_admin(session)
                return

            await sync_registry(session)
            await sync_geography(session)

            # The backfill is transitional and reads the OTHER database, so it
            # is the one step here that can fail for reasons unrelated to
            # Postgres. Mongo being unreachable must not stop the platform from
            # coming up with a working admin account -- but the fingerprint is
            # then withheld so the next boot tries the backfill again rather
            # than declaring the migration done.
            backfilled = True
            try:
                await backfill_users_from_mongo(session)
            except Exception as e:
                backfilled = False
                logger.warning("Mongo -> Postgres user backfill deferred to next boot: %s", e)

            await seed_bootstrap_admin(session)

            if backfilled:
                await _write_meta(session, SEED_FINGERPRINT_KEY, fingerprint)
                logger.info("Postgres bootstrap complete (fingerprint %s)", fingerprint[:12])
        except IntegrityError as e:
            # Another cold start reconciled concurrently. Its writes are
            # equivalent to ours, so rolling back loses nothing.
            await session.rollback()
            logger.info("Postgres bootstrap skipped, another instance is seeding: %s", e.orig)


async def run() -> None:
    """Called once from the FastAPI startup hook.

    Every branch is wrapped: a transient database error during seeding must not
    turn every subsequent request into a 500. A backend that comes up degraded
    and logs loudly is strictly better than one that refuses to come up at all.
    """
    from pymongo.errors import DuplicateKeyError, OperationFailure

    try:
        await mongo_db.users.create_index("email", unique=True)
    except (DuplicateKeyError, OperationFailure) as e:
        logger.warning("users index: %s", e)
    except Exception as e:
        logger.warning("users index skipped: %s", e)

    if config.postgres_enabled():
        try:
            await run_postgres_bootstrap()
        except SQLAlchemyError as e:
            logger.error(
                "Postgres bootstrap failed -- has `alembic upgrade head` been run? %s", e
            )
        except Exception as e:
            logger.error("Postgres bootstrap failed: %s", e)
    else:
        logger.warning(
            "DATABASE_URL is not set: running in legacy Mongo-only mode. "
            "RBAC roles, scoping and the audit log are unavailable."
        )
        try:
            await seed_mongo_admin()
        except Exception as e:
            logger.warning("seed_mongo_admin: %s", e)

    try:
        await seed_mongo_content()
    except Exception as e:
        logger.warning("seed_mongo_content: %s", e)
