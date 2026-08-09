"""Relational schema for identity, RBAC, geography and the audit log.

Type choices are deliberately portable (String/JSON rather than Postgres-native
UUID/JSONB) for two reasons:

* the primary keys must interoperate with the ids already minted by the Mongo
  era (`str(uuid.uuid4())`), so the backfill in core/bootstrap.py is a straight
  copy rather than a type conversion; and
* the same metadata can be created against SQLite, which lets the test suite run
  without a live Postgres instance.

Where a Postgres-only feature genuinely earns its keep later (pgvector for the
AI assistant's retrieval index, per §9 of IMPLEMENTATION_PLAN.md) it will live
in its own module's models, not here.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PlatformMeta(Base):
    """Tiny key/value table for bookkeeping the app does about itself.

    Its first job is the seed fingerprint. On Vercel these startup hooks run on
    every cold start, so reconciling ~60 permission/role/state rows each time
    would add dozens of round-trips to a Neon instance that may itself be waking
    from autosuspend. Storing a hash of the static registry lets a cold start
    confirm "already reconciled" in one query instead.
    """

    __tablename__ = "platform_meta"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
class User(Base):
    """A staff account: anyone who can sign into the admin panel.

    Supporters and volunteers are NOT users -- they remain lightweight records
    in Mongo authenticated by an access code, because they have no permissions
    and no back-office presence. If the Forum (Phase 3) gives every citizen an
    account, that account type gets its own table rather than overloading this
    one; conflating "person who can moderate the forum" with "person who posted
    in it" is how permission systems rot.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Permissions granted to this account directly, outside any role.
    #
    # Roles are the intended mechanism, but the pre-Phase-0 admin UI edits a flat
    # permission list per user and existing accounts carry one. Keeping direct
    # grants as a first-class (if secondary) path means the migration does not
    # have to rewrite that screen on day one, and it stays useful afterwards for
    # the one-off case that does not justify inventing a role. Effective
    # permissions are the union of role grants and this list -- see
    # core/rbac.resolve_principal.
    extra_permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # True only for the account seeded from ADMIN_EMAIL/ADMIN_PASSWORD. It is
    # what makes "reset the password by changing the env var and redeploying"
    # (documented in DEPLOY.md) safe to keep doing without clobbering a
    # human-created account that happens to share the address.
    is_bootstrap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assignments: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


# --------------------------------------------------------------------------
# RBAC
# --------------------------------------------------------------------------
class Permission(Base):
    """One capability, e.g. `representatives.publish`.

    Rows are reconciled from the static registry in core/permissions.py on every
    boot; the table exists so that role->permission grants can be foreign-keyed
    and so the admin UI can list capabilities with human-readable descriptions.
    """

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="general")


class Role(Base):
    """A named bundle of permissions (Super Admin, Fact Checker, ...).

    `scoped` records whether assignments of this role are meaningful per state
    or district. A State Admin assignment without a state is a configuration
    error; a Fact Checker assignment with one is meaningless. Enforced in
    core/rbac.py at assignment time.
    """

    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scoped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Higher = more authority. Used to stop a user granting a role at or above
    # their own level (privilege escalation via the user-management screen).
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    grants: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_key", "permission_key", name="uq_role_permission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    role_key: Mapped[str] = mapped_column(ForeignKey("roles.key", ondelete="CASCADE"), nullable=False)
    permission_key: Mapped[str] = mapped_column(
        ForeignKey("permissions.key", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[Role] = relationship(back_populates="grants")


class UserRole(Base):
    """Assignment of a role to a user, optionally narrowed to one state/district.

    A user may hold the same role in several places (State Admin for Delhi and
    for Goa) -- hence the uniqueness constraint spans the scope columns rather
    than just (user, role).
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_key", "state_code", "district_code", name="uq_user_role_scope"),
        Index("ix_user_roles_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_key: Mapped[str] = mapped_column(ForeignKey("roles.key", ondelete="CASCADE"), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    granted_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    user: Mapped[User] = relationship(back_populates="assignments")
    role: Mapped[Role] = relationship(lazy="selectin")


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------
class State(Base):
    """States and union territories.

    Seeded from a static list (core/geography.py) rather than a CMS table: the
    set of Indian states changes through an Act of Parliament, not through an
    editor's afternoon, and half the platform's routing (`/state/<code>`), RBAC
    scoping and campaign dashboard depend on these codes being stable.
    """

    __tablename__ = "states"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # ISO 3166-2 subdivision, e.g. DL, MH
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_union_territory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Whether this state has a legislature at all -- some UTs do not, which
    # changes what the state page can meaningfully show (no MLAs to list, and
    # a Right to Recall bill has no assembly to pass through).
    has_legislature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lok_sabha_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rajya_sabha_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assembly_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Pilot states (Delhi, Maharashtra) are built end-to-end first; the rest of
    # the country renders a "coming soon / help us build this" state page rather
    # than an empty one pretending to be complete.
    is_pilot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Where this state sits on the eight-stage Right to Recall pipeline
    # (core/geography.CAMPAIGN_STAGES). This is the number the state-wise
    # dashboard is built on, so it is a first-class column rather than CMS copy:
    # it has to be sortable, aggregatable and audited.
    campaign_stage: Mapped[str] = mapped_column(String(40), nullable=False, default="no_demand")
    # Public, sourced explanation of why the state is at that stage. Advancing a
    # state without saying what happened is the kind of unevidenced claim §7
    # exists to prevent.
    campaign_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    campaign_source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campaign_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = (Index("ix_districts_state", "state_code"),)

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    state_code: Mapped[str] = mapped_column(ForeignKey("states.code", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(140), nullable=False)


# --------------------------------------------------------------------------
# Community identity and the shared search index
# --------------------------------------------------------------------------
class Citizen(Base):
    """A member's community identity: who they are in the Forum, on petitions
    and on citizen reports.

    Separate from `User` on purpose, and the comment on that class explains why:
    conflating "person who can moderate the forum" with "person who posted in
    it" is how permission systems rot. A Citizen has no permissions at all.

    Also separate from the Mongo supporter/volunteer records, which stay where
    they are. This row is created lazily the first time a signed-in member does
    something that needs an author -- keyed by the email already in their member
    token, so there is no second signup and no second password. A supporter who
    never posts never gets a row.

    `display_name` is not their real name by default. Somebody filing a report
    about their own municipal ward should not have to publish their legal name to
    do it, and the pseudonym is what makes participation safe enough to be broad.
    """

    __tablename__ = "citizens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Earned, not self-declared: incremented when a report is verified, a
    # correction accepted, a petition created, an answer marked helpful. Reddit's
    # useful half without its scoreboard half -- it gates abuse-prone actions
    # (see REPUTATION_GATES in modules/forum) rather than ranking people.
    reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contributions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Moderation state. A mute is time-boxed and always carries a reason, so
    # "why can I not post" has an answer the member can be told.
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    muted_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_muted(self) -> bool:
        return self.muted_until is not None and self.muted_until > utcnow()

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "displayName": self.display_name or "Citizen",
            "state": self.state_code,
            "reputation": self.reputation,
            "since": self.created_at.isoformat() if self.created_at else None,
        }


class Certificate(Base):
    """An issued certificate: volunteer hours, event attendance, course completion.

    In core rather than in a module because three modules issue them (volunteers,
    events, academy) and §4's rule is that shared behaviour moves down rather than
    sideways.

    `code` is the reason this is a table at all. A certificate that cannot be
    checked is a decorated image, and people put these on CVs -- so every one
    carries a short public code, and `GET /api/certificates/{code}` says who holds
    it, what for, and whether it is still valid. That makes the certificate worth
    something and makes forging one pointless.
    """

    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificate_code", "code", unique=True),
        Index("ix_certificate_holder", "citizen_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Human-transcribable: uppercase, no confusable characters. See
    # core/certificates.new_code.
    code: Mapped[str] = mapped_column(String(24), nullable=False)

    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    citizen_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Denormalised, like audit_log.actor_email: a certificate must remain
    # verifiable after the holder deletes their account, and verification must not
    # resurrect deleted personal data by joining. On a DPDP erasure request the
    # certificate row goes too -- see modules/submissions.erase_my_data.
    holder_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    holder_name: Mapped[str] = mapped_column(String(160), nullable=False)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    # Hours, task count, quiz score, event name -- whatever the issuing module
    # wants printed. JSON because each kind prints different things.
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    issued_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SearchDoc(Base):
    """One denormalised, searchable row per public entity.

    The shared index that makes `/api/search` possible without the search module
    importing eleven others -- modules push into this table when they publish,
    the search module only reads it. §4's one-way dependency rule stays intact
    and adding a searchable module is one `search.index()` call.

    It is also the free-tier answer to Meilisearch. Self-hosting Meilisearch
    needs a container this project does not have yet (§5), so the default engine
    is Postgres: a LIKE/ILIKE scan over a few thousand short rows on a 0.5 GB
    database is unglamorous and completely adequate. `core/search.py` keeps the
    Meilisearch path behind the same interface for when the index outgrows that.
    """

    __tablename__ = "search_docs"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "locale", name="uq_search_entity_locale"),
        Index("ix_search_type", "entity_type"),
        Index("ix_search_state", "state_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    # Plain text, already stripped of markup by the caller. Truncated by
    # core/search.index() rather than here, so the cap lives with the reason.
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")

    url_path: Mapped[str] = mapped_column(String(300), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Unpublished rows are kept rather than deleted so that unpublishing and
    # republishing does not churn ids, and so a draft is findable by staff.
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# Audit log -- the "Wikipedia History" / "GitHub transparency" pillar
# --------------------------------------------------------------------------
class AuditLog(Base):
    """Append-only record of every change to platform data.

    Two jobs, and the second is the reason it is in Phase 0 rather than a
    "nice to have later":

    1. Internal accountability -- who changed this representative's asset figure.
    2. PUBLIC transparency. Per §7 of IMPLEMENTATION_PLAN.md, representative
       profiles, constitution articles and promise statuses expose a public
       history tab built from these rows. That is a credibility feature, and it
       only works if the log has been written since the first edit -- history
       cannot be backfilled after the fact.

    Nothing updates or deletes rows here. `is_public` decides whether an entry
    surfaces on the public history tab; moderation actions and user-management
    changes stay internal, content edits do not.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Denormalised on purpose: the log must stay readable after an account is
    # deleted, and it must not resurrect a deleted user's address by joining.
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, default="system")

    action: Mapped[str] = mapped_column(String(60), nullable=False)  # create | update | delete | publish | ...
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)  # representative | article | ...
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Field-level diff: {"field": {"before": ..., "after": ...}}. Only changed
    # fields are stored, so a one-word fix does not archive the whole document.
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Where the new value came from (ECI affidavit, PRS record, Gazette). The
    # citation requirement in §7 is enforced at the module level for
    # person-data edits; storing it here is what makes the public history
    # auditable rather than merely visible.
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
