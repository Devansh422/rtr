"""Published policies, consent records, and the DPDP data-access endpoint.

The policies are served from the API rather than hardcoded in the frontend so that
the version a user sees and the version recorded against their consent are
necessarily the same string.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import i18n, moderation
from backend.core.citations import STANDARD_DISCLAIMER
from backend.core.deps import get_current_member, get_optional_session, require_permission
from backend.core.mongo import db as mongo_db
from backend.core.rbac import Principal
from backend.core.security import hash_ip
from backend.modules.legal.models import ConsentRecord
from backend.modules.legal.policies import (
    CONSENT_PURPOSES,
    PRIVACY_EFFECTIVE_DATE,
    PRIVACY_POLICY,
    PRIVACY_POLICY_VERSION,
    SITE_DISCLAIMER,
)

router = APIRouter(tags=["legal"])


class ConsentIn(BaseModel):
    email: EmailStr
    purposes: list[str]
    source: str = ""
    policy_version: Optional[str] = None


class WithdrawIn(BaseModel):
    purpose: str


def _notice_for(purpose: str) -> str:
    """The one-paragraph notice that must appear next to a submit button.

    Generated from the same dict the policy page renders, so the short notice and
    the long policy cannot say different things.
    """
    spec = CONSENT_PURPOSES[purpose]
    return (
        f"We will collect: {', '.join(spec['data'])}. "
        f"Why: {spec['why']} "
        f"How long: {spec['retention']} "
        "You can delete all of it yourself from your dashboard at any time. We never sell your data or "
        "share it with any political party."
    )


# --------------------------------------------------------------------------
# Published policies
# --------------------------------------------------------------------------
@router.get("/legal/privacy")
async def privacy_policy():
    return {
        **PRIVACY_POLICY,
        "purposes": [
            {"key": key, **spec, "notice": _notice_for(key)} for key, spec in CONSENT_PURPOSES.items()
        ],
    }


@router.get("/legal/content-policy")
async def content_policy():
    """The non-partisan content policy, published verbatim.

    §7: publishing this is what lets the platform credibly claim non-partisanship.
    It is served from core/moderation, which is the module that enforces it, so the
    published rules and the applied rules are the same object.
    """
    return moderation.CONTENT_POLICY


@router.get("/legal/disclaimer")
async def disclaimer():
    return {**SITE_DISCLAIMER, "apiDisclaimer": STANDARD_DISCLAIMER}


@router.get("/legal/consent-notices")
async def consent_notices():
    """The short notices, for rendering next to each submit button.

    Exposed as an endpoint so the frontend cannot drift from the policy: a form that
    hardcodes its own wording is a form whose notice stops matching the policy after
    the first policy revision.
    """
    return {
        "policyVersion": PRIVACY_POLICY_VERSION,
        "effective": PRIVACY_EFFECTIVE_DATE,
        "policyUrl": "/privacy",
        "purposes": [
            {
                "key": key,
                "label": spec["label"],
                "required": spec["required"],
                "notice": _notice_for(key),
                "data": spec["data"],
                "retention": spec["retention"],
            }
            for key, spec in CONSENT_PURPOSES.items()
        ],
    }


@router.get("/locales")
async def locales():
    """Supported languages and which are actually live (§8)."""
    return {
        "default": i18n.DEFAULT_LOCALE,
        "locales": i18n.locale_catalogue(),
        "note": (
            "English and Hindi are authored directly. Other languages are added as volunteer "
            "translators review them -- constitutional text is never published as raw machine "
            "translation."
        ),
    }


# --------------------------------------------------------------------------
# Consent
# --------------------------------------------------------------------------
@router.post("/legal/consent")
async def record_consent(
    payload: ConsentIn,
    request: Request,
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    """Record consent for one or more purposes.

    Called by every form that collects personal data, at submit time, alongside the
    submission itself. Tolerates Postgres being unconfigured (the legacy mode in
    core/config) by falling back to Mongo rather than failing the signup -- a
    consent record that blocks the action it is recording consent for is worse than
    useless.
    """
    unknown = [p for p in payload.purposes if p not in CONSENT_PURPOSES]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown consent purposes: {unknown}")
    if not payload.purposes:
        raise HTTPException(status_code=400, detail="At least one purpose is required")

    email = payload.email.lower()
    version = payload.policy_version or PRIVACY_POLICY_VERSION
    ip = hash_ip(request.client.host if request.client else None)

    if session is None:
        # LEGACY FALLBACK (DATABASE_URL unset) -- see core/config.py.
        await mongo_db.consent_records.insert_many(
            [
                {
                    "subject_email": email,
                    "purpose": purpose,
                    "granted": True,
                    "policy_version": version,
                    "notice_shown": _notice_for(purpose),
                    "source": payload.source[:80],
                    "ip_hash": ip,
                }
                for purpose in payload.purposes
            ]
        )
        return {"ok": True, "recorded": payload.purposes, "policyVersion": version}

    for purpose in payload.purposes:
        session.add(
            ConsentRecord(
                subject_email=email,
                purpose=purpose,
                granted=True,
                policy_version=version,
                notice_shown=_notice_for(purpose),
                source=payload.source[:80],
                ip_hash=ip,
            )
        )
    return {"ok": True, "recorded": payload.purposes, "policyVersion": version}


@router.get("/me/consent")
async def my_consent(
    member: dict = Depends(get_current_member),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    """What this member has consented to, and when.

    The DPDP "right to know" in its most literal form: the person sees their own
    consent history rather than having to ask for it.
    """
    email = member["email"]
    if session is None:
        rows = await mongo_db.consent_records.find(
            {"subject_email": email}, {"_id": 0}
        ).to_list(200)
        history = [{**row, "createdAt": None} for row in rows]
    else:
        records = list(
            (
                await session.execute(
                    select(ConsentRecord)
                    .where(ConsentRecord.subject_email == email)
                    .order_by(ConsentRecord.created_at.desc())
                )
            ).scalars()
        )
        history = [
            {
                "purpose": r.purpose,
                "granted": r.granted,
                "policyVersion": r.policy_version,
                "source": r.source,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    # Current state is the LATEST record per purpose, since withdrawal appends
    # rather than updates.
    current: dict[str, bool] = {}
    for entry in reversed(history):
        current[entry["purpose"]] = entry.get("granted", True)

    return {
        "email": email,
        "current": [
            {
                "purpose": purpose,
                "label": CONSENT_PURPOSES.get(purpose, {}).get("label", purpose),
                "granted": granted,
                "required": CONSENT_PURPOSES.get(purpose, {}).get("required", False),
            }
            for purpose, granted in current.items()
        ],
        "history": history,
        "policyVersion": PRIVACY_POLICY_VERSION,
    }


@router.post("/me/consent/withdraw")
async def withdraw_consent(
    payload: WithdrawIn,
    request: Request,
    member: dict = Depends(get_current_member),
    session: Optional[AsyncSession] = Depends(get_optional_session),
):
    """Withdraw consent for one optional purpose.

    Appends a `granted=False` record rather than deleting the original -- the
    history is the evidence. Required purposes cannot be withdrawn individually,
    because withdrawing consent to hold your membership record IS deleting your
    account, and that has its own endpoint that actually erases the data.
    """
    purpose = payload.purpose
    if purpose not in CONSENT_PURPOSES:
        raise HTTPException(status_code=400, detail=f"Unknown purpose: {purpose}")
    if CONSENT_PURPOSES[purpose]["required"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "This purpose is what your membership record is for, so withdrawing it means deleting "
                "your data. Use 'Delete my data' -- it erases everything immediately."
            ),
        )

    email = member["email"]
    ip = hash_ip(request.client.host if request.client else None)

    if purpose == "newsletter":
        # Withdrawal has to actually DO something, not just log an intention.
        await mongo_db.newsletter.delete_many({"email": email})

    if session is None:
        await mongo_db.consent_records.insert_one(
            {
                "subject_email": email,
                "purpose": purpose,
                "granted": False,
                "policy_version": PRIVACY_POLICY_VERSION,
                "source": "dashboard-withdrawal",
                "ip_hash": ip,
            }
        )
    else:
        session.add(
            ConsentRecord(
                subject_email=email,
                purpose=purpose,
                granted=False,
                policy_version=PRIVACY_POLICY_VERSION,
                notice_shown="",
                source="dashboard-withdrawal",
                ip_hash=ip,
            )
        )
    return {"ok": True, "purpose": purpose, "granted": False}


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/legal/consent-summary")
async def consent_summary(
    admin: Principal = Depends(require_permission("submissions.view")),
    session: AsyncSession = Depends(get_optional_session),
):
    """Aggregate consent counts, for the compliance view.

    Counts by purpose and policy version. No email addresses: whoever needs the
    compliance picture does not need the list of people in it.
    """
    if session is None:
        raise HTTPException(status_code=503, detail="This view requires the relational database")

    by_purpose = (
        await session.execute(
            select(ConsentRecord.purpose, ConsentRecord.granted, func.count())
            .group_by(ConsentRecord.purpose, ConsentRecord.granted)
        )
    ).all()
    by_version = (
        await session.execute(
            select(ConsentRecord.policy_version, func.count()).group_by(ConsentRecord.policy_version)
        )
    ).all()
    return {
        "currentPolicyVersion": PRIVACY_POLICY_VERSION,
        "byPurpose": [
            {
                "purpose": purpose,
                "label": CONSENT_PURPOSES.get(purpose, {}).get("label", purpose),
                "granted": granted,
                "count": count,
            }
            for purpose, granted, count in by_purpose
        ],
        "byPolicyVersion": [{"version": version, "count": count} for version, count in by_version],
        # A count against an old version means those people consented to a notice
        # that no longer describes what the platform does.
        "staleConsentCount": sum(
            count for version, count in by_version if version != PRIVACY_POLICY_VERSION
        ),
    }
