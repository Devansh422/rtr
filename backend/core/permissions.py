"""The permission and role registry -- the single source of truth for §6 of
IMPLEMENTATION_PLAN.md.

This is static Python rather than editable data on purpose. Permissions are
referenced by name in route decorators, so a permission that can be renamed or
deleted from a UI is a permission that can silently unguard an endpoint. Roles
(the bundles) are reconciled into the database on boot so they can be joined
and displayed, but the definitions live here and code review is the change
process.

Backwards compatibility: the four keys that already existed before Phase 0
(`content.<ctype>`, `submissions.view`, `analytics.view`, `users.manage`) keep
their exact names, so permission lists stored on existing admin accounts stay
valid through the migration.
"""

from dataclasses import dataclass, field

# Content types served by the generic CMS CRUD. Kept here rather than in the CMS
# module because the permission keys are derived from it.
CONTENT_TYPES = [
    "campaigns",
    "blogs",
    "news",
    "faq",
    "testimonials",
    "resources",
    "leaders",
    "jurisdictions",
    "myths",
    "opportunities",
]

SORTED_BY_DATE = {"blogs", "news"}


@dataclass(frozen=True)
class PermissionDef:
    key: str
    label: str
    category: str


def _content_permissions() -> list[PermissionDef]:
    return [
        PermissionDef(f"content.{t}", f"Manage {t}", "CMS")
        for t in CONTENT_TYPES
    ]


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
# Editing a permission's key is a breaking change; editing its label is not.
PERMISSIONS: list[PermissionDef] = _content_permissions() + [
    # Pre-Phase-0 keys -- do not rename.
    PermissionDef("submissions.view", "View form submissions", "Operations"),
    PermissionDef("analytics.view", "View analytics", "Operations"),
    PermissionDef("users.manage", "Create and edit staff accounts", "Administration"),
    # Administration
    PermissionDef("roles.manage", "Assign roles to staff accounts", "Administration"),
    PermissionDef("audit.view", "View the internal audit log", "Administration"),
    # Constitution library
    PermissionDef("constitution.edit", "Draft constitution article content", "Constitution"),
    PermissionDef("constitution.publish", "Publish constitution article content", "Constitution"),
    # Representatives / accountability
    PermissionDef("representatives.edit", "Draft representative profile data", "Accountability"),
    PermissionDef("representatives.publish", "Publish representative profile data", "Accountability"),
    PermissionDef("promises.edit", "Draft promise tracker entries", "Accountability"),
    PermissionDef("promises.publish", "Publish promise tracker entries", "Accountability"),
    PermissionDef("factcheck.approve", "Approve sourced claims about named people", "Accountability"),
    PermissionDef("legal.review", "Sign off legal templates and disputed claims", "Accountability"),
    # States & campaigns
    PermissionDef("states.edit", "Edit state and district pages", "Campaigns"),
    PermissionDef("campaigns.status", "Move a state along the campaign pipeline", "Campaigns"),
    # Citizen-facing modules
    PermissionDef("petitions.manage", "Create and close petitions", "Community"),
    PermissionDef("reports.verify", "Verify or reject citizen report cards", "Community"),
    PermissionDef("forum.moderate", "Moderate forum threads and replies", "Community"),
    PermissionDef("volunteers.manage", "Assign tasks and verify volunteer work", "Community"),
    PermissionDef("events.manage", "Create events and issue certificates", "Community"),
    # Knowledge
    PermissionDef("academy.manage", "Manage courses and quizzes", "Knowledge"),
    PermissionDef("research.manage", "Manage the research document repository", "Knowledge"),
    PermissionDef("media.manage", "Manage the media library", "Knowledge"),
    # Trust layer -- the correction/dispute queue described in §7. Separate from
    # factcheck.approve because triaging an incoming correction (is this a real
    # objection, who should look at it) is a different job from ruling on
    # whether a sourced claim is true.
    PermissionDef("corrections.review", "Triage and resolve suggested corrections", "Accountability"),
    # Civic tools. Held by the Legal Team because an RTI or representation
    # template that misstates the law is published legal advice in all but name.
    PermissionDef("tools.manage", "Edit RTI, representation and PIL templates", "Tools"),
    # Outbound bulk email. Narrow on purpose: the free tier is 300 messages a
    # day, and a mistaken mass send cannot be recalled.
    PermissionDef("notifications.send", "Send bulk email to members", "Operations"),
    PermissionDef("ai.manage", "Manage the AI assistant index and answer cache", "Tools"),
]

PERMISSION_KEYS: list[str] = [p.key for p in PERMISSIONS]
PERMISSION_SET: frozenset[str] = frozenset(PERMISSION_KEYS)

# Exported under its historical name because the admin frontend and the
# pre-Phase-0 user-management endpoints validate against it.
ALL_PERMISSIONS = PERMISSION_KEYS


@dataclass(frozen=True)
class RoleDef:
    key: str
    label: str
    description: str
    permissions: tuple[str, ...]
    # rank orders authority. A user can only grant roles strictly below their
    # own highest rank, which is what stops an Editor from promoting themselves
    # to Super Admin through the user-management screen.
    rank: int
    # True when an assignment of this role must name a state (and optionally a
    # district) to mean anything.
    scoped: bool = False


_CMS_CONTENT = tuple(f"content.{t}" for t in CONTENT_TYPES)

ROLES: list[RoleDef] = [
    RoleDef(
        key="super_admin",
        label="Super Admin",
        description="Full platform access, including role assignment and the audit log.",
        # Materialised rather than special-cased: an explicit grant list means
        # "what can this account do" has exactly one answer everywhere, and a
        # newly added permission is a visible diff here instead of silently
        # widening someone's access.
        permissions=tuple(PERMISSION_KEYS),
        rank=100,
    ),
    RoleDef(
        key="state_admin",
        label="State Admin",
        description="Manages one state's page, campaign status, volunteers and events.",
        permissions=(
            "states.edit",
            "campaigns.status",
            "volunteers.manage",
            "events.manage",
            "submissions.view",
            "petitions.manage",
            "content.campaigns",
            "content.news",
        ),
        rank=60,
        scoped=True,
    ),
    RoleDef(
        key="district_admin",
        label="District Admin",
        description="Same as State Admin, narrowed to a single district.",
        permissions=(
            "states.edit",
            "volunteers.manage",
            "events.manage",
            "submissions.view",
        ),
        rank=50,
        scoped=True,
    ),
    RoleDef(
        key="research_team",
        label="Research Team",
        description=(
            "Adds representative data, promises and research documents. Work is "
            "submitted for fact-check rather than published directly."
        ),
        permissions=(
            "representatives.edit",
            "promises.edit",
            "constitution.edit",
            "research.manage",
            # Corrections are research work: an incoming objection is a lead to
            # check against a source, which is exactly this team's job.
            "corrections.review",
        ),
        rank=40,
    ),
    RoleDef(
        key="fact_checker",
        label="Fact Checker",
        description="Approves sourced claims about named people before they go live.",
        permissions=(
            "factcheck.approve",
            "representatives.publish",
            "promises.publish",
            "representatives.edit",
            "promises.edit",
            "corrections.review",
            "reports.verify",
            "audit.view",
        ),
        rank=45,
    ),
    RoleDef(
        key="legal_team",
        label="Legal Team",
        description="Reviews PIL/RTI templates, disputed claims and defamation risk.",
        permissions=(
            "legal.review",
            "factcheck.approve",
            "corrections.review",
            "tools.manage",
            "content.resources",
            "audit.view",
        ),
        rank=45,
    ),
    RoleDef(
        key="editor",
        label="Editor",
        description="Publishes CMS content: blogs, news, FAQ, constitution plain-English text.",
        permissions=_CMS_CONTENT
        + (
            "constitution.edit",
            "constitution.publish",
            "media.manage",
            "academy.manage",
            "research.manage",
        ),
        rank=35,
    ),
    RoleDef(
        key="content_writer",
        label="Content Writer",
        description="Drafts CMS content. Cannot publish -- an Editor reviews first.",
        permissions=("content.blogs", "content.news", "content.faq", "media.manage"),
        rank=20,
    ),
    RoleDef(
        key="moderator",
        label="Moderator",
        description="Applies the non-partisan content policy to the forum and citizen reports.",
        permissions=("forum.moderate", "reports.verify", "petitions.manage", "corrections.review"),
        rank=30,
    ),
    RoleDef(
        key="volunteer_manager",
        label="Volunteer Manager",
        description="Assigns volunteer tasks, verifies hours and issues certificates.",
        permissions=(
            "volunteers.manage",
            "events.manage",
            "submissions.view",
            "notifications.send",
        ),
        rank=30,
    ),
    RoleDef(
        key="analyst",
        label="Analyst",
        description="Read-only access to the analytics dashboard.",
        permissions=("analytics.view",),
        rank=10,
    ),
]

ROLES_BY_KEY: dict[str, RoleDef] = {r.key: r for r in ROLES}


def validate_registry() -> None:
    """Fail fast on a typo in a role's permission list.

    Called at import time: a role granting a permission that does not exist is
    a silent hole (the grant does nothing, the person quietly cannot work), and
    the cost of catching it here is zero.
    """
    unknown = {
        f"{role.key}:{perm}"
        for role in ROLES
        for perm in role.permissions
        if perm not in PERMISSION_SET
    }
    if unknown:
        raise RuntimeError(f"Roles grant unknown permissions: {sorted(unknown)}")

    duplicates = [k for k in PERMISSION_KEYS if PERMISSION_KEYS.count(k) > 1]
    if duplicates:
        raise RuntimeError(f"Duplicate permission keys: {sorted(set(duplicates))}")


validate_registry()
