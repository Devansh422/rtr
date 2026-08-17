"""Creating, signing and administering petitions."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, erasure, limits, membership, moderation, notify, search
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
    require_state_scope,
)
from backend.core.geography import (
    CAMPAIGN_STAGE_LABELS,
    STATES,
    STATES_BY_CODE,
    VALID_STATE_CODES,
    ZONE_SOURCE_URL,
    ZONES,
    zone_of,
)
from backend.core.models import Citizen, State, as_aware, utcnow
from backend.core.rbac import Principal
from backend.core.security import create_member_token, slugify
from backend.modules.petitions.models import (
    MILESTONES,
    NATIONAL_PETITION_SLUG,
    PUBLIC_STATUSES,
    STATUS_LABELS,
    Petition,
    PetitionSignature,
    PetitionStatus,
    milestones_reached,
    next_milestone,
)

router = APIRouter(tags=["petitions"])

# Reputation for starting a petition that clears moderation. Small on purpose:
# the reward for a petition should be signatures, not points.
REPUTATION_FOR_PETITION = 5
DEFAULT_OPEN_DAYS = 90


class PetitionIn(BaseModel):
    title: str = Field(..., min_length=15, max_length=300)
    summary: str = Field(..., min_length=30, max_length=600)
    body: str = Field(..., min_length=100)
    addressed_to: str = Field(..., min_length=4, max_length=300)
    state_code: Optional[str] = None
    category: str = "right-to-recall"
    target_signatures: int = Field(default=1000, ge=50, le=1_000_000)
    title_hi: str = ""
    body_hi: str = ""


class SignatureIn(BaseModel):
    comment: str = Field(default="", max_length=1000)
    # Explicit opt-in. See the note on the model for why the default is private.
    show_my_name: bool = False
    # Optional, and only ever FILLS IN a missing value (see sign_petition): a
    # member whose Citizen row predates the state field can supply it while
    # signing, so their signature lands in the state-wise breakdown instead of
    # in "not stated". It never overwrites a state already recorded, because a
    # petition form is not the place to silently change someone's profile.
    state_code: Optional[str] = None


class PublicSignatureIn(BaseModel):
    """Sign and become a member in one step. See sign_petition_publicly."""

    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    state_code: str = Field(..., min_length=2, max_length=10)
    city: Optional[str] = Field(default=None, max_length=80)
    comment: str = Field(default="", max_length=1000)
    show_my_name: bool = False
    # DPDP Act 2023: consent must be informed, specific and affirmative, so this
    # is a required true rather than a default. The consent RECORD is written by
    # `POST /legal/consent`, which the same form calls -- see the note there on
    # why a consent write never blocks the submission it accompanies.
    consent: bool = False


class PetitionStatusIn(BaseModel):
    status: str
    note: str = ""
    outcome_source_url: str = ""


def _public_path(petition: Petition) -> str:
    """Where this petition lives on the site.

    The national petition has its own page (`/petition`) rather than a row in the
    directory, so links, share text and search results all have to agree on that
    -- including the ones already sitting in somebody's WhatsApp.
    """
    return "/petition" if petition.slug == NATIONAL_PETITION_SLUG else f"/petitions/{petition.slug}"


def _serialise(petition: Petition, *, include_body: bool = False) -> dict:
    reached = milestones_reached(petition.signature_count)
    payload = {
        "id": petition.id,
        "slug": petition.slug,
        "title": petition.title,
        "titleHi": petition.title_hi,
        "summary": petition.summary,
        "addressedTo": petition.addressed_to,
        "state": petition.state_code,
        "category": petition.category,
        "status": petition.status,
        "statusLabel": STATUS_LABELS.get(petition.status, petition.status),
        "isOfficial": petition.is_official,
        "signatureCount": petition.signature_count,
        "targetSignatures": petition.target_signatures,
        "progressPercent": (
            min(100, round(petition.signature_count / petition.target_signatures * 100))
            if petition.target_signatures
            else 0
        ),
        "milestonesReached": reached,
        "nextMilestone": next_milestone(petition.signature_count),
        "closesAt": petition.closes_at.isoformat() if petition.closes_at else None,
        "createdAt": petition.created_at.isoformat() if petition.created_at else None,
        "isNational": petition.slug == NATIONAL_PETITION_SLUG,
        "url": _public_path(petition),
    }
    if include_body:
        payload.update(
            {
                "body": petition.body,
                "bodyHi": petition.body_hi,
                "statusNote": petition.status_note,
                "outcomeSourceUrl": petition.outcome_source_url or None,
                "milestones": petition.milestones,
                "share": notify.share_links(
                    url=_public_path(petition),
                    text=f"{petition.title} - sign this petition",
                ),
            }
        )
    return payload


async def _recount(session: AsyncSession, petition: Petition) -> None:
    """Recompute the denormalised count from the signature table.

    Recomputed rather than incremented: an increment that races or that runs after
    a rolled-back insert leaves a petition permanently overstating its support,
    which is the one number on the page that has to be right.
    """
    petition.signature_count = (
        await session.execute(
            select(func.count())
            .select_from(PetitionSignature)
            .where(PetitionSignature.petition_id == petition.id)
        )
    ).scalar_one()

    already = {m.get("count") for m in (petition.milestones or [])}
    new_marks = [
        {"count": m, "reachedAt": utcnow().isoformat()}
        for m in milestones_reached(petition.signature_count)
        if m not in already
    ]
    if new_marks:
        petition.milestones = [*(petition.milestones or []), *new_marks]


async def _public_petition(session: AsyncSession, slug: str) -> Petition:
    # "national" is a reserved alias for the common cause, so every path under
    # /petitions/{slug} works for it too -- signing, signatures, the state
    # breakdown -- without a caller having to know its real slug.
    if slug == "national":
        slug = NATIONAL_PETITION_SLUG
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None or petition.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Petition not found")
    return petition


async def _state_breakdown(session: AsyncSession, petition: Petition) -> dict:
    """Signatures per state and union territory, grouped by zonal council.

    Aggregates only -- counts, never identities. The same rule as the admin
    export: where a signature came from is a fact about the campaign, who signed
    is a fact about a person, and only the first is anyone else's business.

    Every one of the 36 rows is returned, including the ones on zero. A page that
    lists only the states with signatures tells a reader their state is missing
    rather than empty, and "nobody here has signed yet" is the more useful thing
    for the reader to know.
    """
    counted = dict(
        (
            await session.execute(
                select(PetitionSignature.state_code, func.count())
                .where(PetitionSignature.petition_id == petition.id)
                .group_by(PetitionSignature.state_code)
            )
        ).all()
    )
    # Campaign stage comes from the states table so a zero-signature state still
    # says something true about itself ("bill introduced") rather than nothing.
    stages = {
        row.code: (row.campaign_stage, row.slug)
        for row in (await session.execute(select(State))).scalars()
    }

    recorded = sum(count for code, count in counted.items() if code)
    unspecified = counted.get(None, 0) + counted.get("", 0)

    def share(count: int) -> float:
        return round(count / recorded * 100, 1) if recorded else 0.0

    rows = []
    for seed in STATES:
        count = counted.get(seed.code, 0)
        stage, slug = stages.get(seed.code, ("no_demand", seed.slug))
        rows.append(
            {
                "code": seed.code,
                "name": seed.name,
                "nameHi": seed.name_hi,
                "slug": slug,
                "url": f"/states/{slug}",
                "zone": zone_of(seed.code),
                "isUnionTerritory": seed.is_union_territory,
                "hasLegislature": seed.has_legislature,
                "isPilot": seed.is_pilot,
                "assemblySeats": seed.assembly_seats,
                "campaignStage": stage,
                "campaignStageLabel": CAMPAIGN_STAGE_LABELS.get(stage, stage),
                "count": count,
                "share": share(count),
            }
        )

    # Rank by signatures, and only for states that have some: a shared rank of
    # "27th" across nine states on zero would be a scoreboard nobody asked for.
    for position, row in enumerate(
        sorted([r for r in rows if r["count"]], key=lambda r: -r["count"]), start=1
    ):
        row["rank"] = position
    for row in rows:
        row.setdefault("rank", None)

    by_code = {row["code"]: row for row in rows}
    zones = [
        {
            "key": zone.key,
            "label": zone.label,
            "labelHi": zone.label_hi,
            "count": sum(by_code[code]["count"] for code in zone.codes),
            "states": sorted(
                (by_code[code] for code in zone.codes),
                key=lambda r: (-r["count"], r["name"]),
            ),
        }
        for zone in ZONES
    ]
    for zone in zones:
        zone["share"] = share(zone["count"])

    return {
        "totalSignatures": petition.signature_count,
        # The denominator for every percentage here. Kept separate from the total
        # so the two numbers can differ visibly rather than quietly.
        "recorded": recorded,
        "unspecified": unspecified,
        "statesWithSignatures": sum(1 for row in rows if row["count"]),
        "totalStates": len(rows),
        "states": sorted(rows, key=lambda r: (-r["count"], r["name"])),
        "zones": sorted(zones, key=lambda z: -z["count"]),
        "zoneSourceUrl": ZONE_SOURCE_URL,
        "note": (
            "Percentages are of the signatures that carry a state, not of all signatures. "
            "Members who signed before the state field existed appear under 'not stated'. "
            "Counts only -- no signer is identified by this breakdown."
        ),
    }


async def _index(session: AsyncSession, petition: Petition) -> None:
    await search.index(
        session,
        entity_type="petition",
        entity_id=petition.slug,
        title=petition.title,
        subtitle=f"Petition to {petition.addressed_to}",
        body=petition.summary,
        keywords=[petition.category, petition.state_code or ""],
        state_code=petition.state_code,
        is_published=petition.status in PUBLIC_STATUSES,
        url_path=_public_path(petition),
    )


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/petitions")
async def list_petitions(
    state: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    sort: str = Query(default="trending", pattern="^(trending|newest|signatures)$"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Petition).where(Petition.status.in_(list(PUBLIC_STATUSES)))
    if state:
        stmt = stmt.where(Petition.state_code == state.upper())
    if status:
        stmt = stmt.where(Petition.status == status)
    if category:
        stmt = stmt.where(Petition.category == category)

    rows = list((await session.execute(stmt)).scalars())

    if sort == "signatures":
        rows.sort(key=lambda p: -p.signature_count)
    elif sort == "newest":
        rows.sort(key=lambda p: as_aware(p.created_at), reverse=True)
    else:
        # "Trending" = signatures per day since opening, so a week-old petition
        # with 400 signatures ranks above a year-old one with 900. Ranking purely
        # by total makes the front page a permanent archive of the first petitions
        # ever created.
        now = datetime.now(timezone.utc)
        rows.sort(
            key=lambda p: -(
                p.signature_count / max(1, (now - as_aware(p.created_at)).days + 1)
            )
        )

    return {
        "total": len(rows),
        "items": [_serialise(p) for p in rows[offset : offset + limit]],
    }


# Declared BEFORE /petitions/{slug}: FastAPI matches in declaration order, and
# "national" would otherwise be read as a slug and 404.
@router.get("/petitions/national")
async def get_national_petition(session: AsyncSession = Depends(get_session)):
    """The common cause -- the one petition the whole platform points at.

    Served under its own path rather than by making the frontend hard-code a slug,
    so which petition is the national one is decided in exactly one place
    (modules/petitions/models.NATIONAL_PETITION_SLUG) and the page keeps working
    if it ever changes.
    """
    petition = (
        await session.execute(select(Petition).where(Petition.slug == NATIONAL_PETITION_SLUG))
    ).scalar_one_or_none()
    if petition is None or petition.status not in PUBLIC_STATUSES:
        # A 404 here means seeding has not run, not that a visitor asked for
        # something that does not exist, so the message says which.
        raise HTTPException(
            status_code=404,
            detail=(
                "The national petition has not been opened on this deployment yet. "
                "It is seeded at startup; check that the database migration has run."
            ),
        )
    return {
        **_serialise(petition, include_body=True),
        "isNational": True,
        "url": "/petition",
        "stateBreakdown": await _state_breakdown(session, petition),
    }


@router.get("/petitions/{slug}")
async def get_petition(slug: str, session: AsyncSession = Depends(get_session)):
    petition = await _public_petition(session, slug)
    return _serialise(petition, include_body=True)


@router.get("/petitions/{slug}/by-state")
async def petition_by_state(slug: str, session: AsyncSession = Depends(get_session)):
    """Public state-wise breakdown of a petition's signatures."""
    return await _state_breakdown(session, await _public_petition(session, slug))


@router.get("/petitions/{slug}/signatures")
async def list_signatures(
    slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Signatures whose signer opted in to being listed, newest first.

    The count on the petition page includes everyone; this list includes only
    those who chose to be named. The gap between the two numbers is expected and
    the response says so, so it does not read as a discrepancy.
    """
    petition = await _public_petition(session, slug)

    rows = (
        await session.execute(
            select(PetitionSignature)
            .where(
                PetitionSignature.petition_id == petition.id,
                PetitionSignature.is_public.is_(True),
            )
            .order_by(PetitionSignature.created_at.desc())
            .limit(limit)
        )
    ).scalars()

    return {
        "totalSignatures": petition.signature_count,
        "note": (
            "Every signature is counted. Only signers who chose to be listed appear below."
        ),
        "items": [
            {
                "displayName": s.display_name or "A supporter",
                "state": s.state_code,
                "comment": None if s.comment_hidden else (s.comment or None),
                "signedOn": s.created_at.date().isoformat() if s.created_at else None,
            }
            for s in rows
        ],
    }


@router.post("/petitions")
async def create_petition(
    payload: PetitionIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Start a petition. Goes to moderation before it opens for signatures.

    Never auto-publishes. A petition carries this platform's name to the office
    it addresses, and §7 requires the non-partisan content policy to be applied by
    a person before that happens.
    """
    await limits.check("petition.create", f"m:{citizen.email}")

    verdict = moderation.review(
        f"{payload.title}\n{payload.summary}\n{payload.body}",
        names_a_person=True,
        has_citation=False,
    )
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "This petition cannot be accepted as written.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )

    slug = slugify(payload.title)
    if (await session.execute(select(Petition).where(Petition.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M')}"

    petition = Petition(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        body=moderation.scrub_identifiers(payload.body.strip()),
        body_hi=payload.body_hi.strip(),
        addressed_to=payload.addressed_to.strip(),
        state_code=payload.state_code.upper() if payload.state_code else citizen.state_code,
        category=payload.category,
        target_signatures=payload.target_signatures,
        citizen_id=citizen.id,
        is_official=False,
        status=PetitionStatus.UNDER_REVIEW,
        policy_flags=str([f.as_dict() for f in verdict.flags]) if verdict.flags else "",
        closes_at=utcnow() + timedelta(days=DEFAULT_OPEN_DAYS),
    )
    session.add(petition)
    await session.flush()

    citizen.reputation += REPUTATION_FOR_PETITION
    contributions = dict(citizen.contributions or {})
    contributions["petitionsStarted"] = contributions.get("petitionsStarted", 0) + 1
    citizen.contributions = contributions

    await audit.record(
        session,
        actor=None,
        action="create",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"Petition submitted for review: {petition.title}",
        is_public=False,
        request=request,
    )
    return {
        **_serialise(petition, include_body=True),
        "message": (
            "Your petition has been submitted. A moderator checks every petition against the "
            "content policy before it opens for signatures - usually within two working days."
        ),
        "flags": [f.as_dict() for f in verdict.flags],
    }


def _assert_open(petition: Petition) -> None:
    if petition.status != PetitionStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail=f"This petition is {STATUS_LABELS[petition.status].lower()} and is no longer collecting signatures.",
        )
    if petition.closes_at and as_aware(petition.closes_at) < utcnow():
        raise HTTPException(status_code=400, detail="This petition has closed.")


def _screen_comment(comment: str) -> bool:
    """Run a signature comment past the content policy. Returns comment_hidden.

    A held comment must not block the signature. The signature is the civic act;
    the comment is commentary, so it waits for a moderator while the signature
    counts immediately.
    """
    if not comment.strip():
        return False
    verdict = moderation.review(comment, names_a_person=True, has_citation=False)
    if verdict.decision is moderation.Decision.REJECT:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Your comment cannot be posted as written. Your signature was not recorded -- fix the comment and sign again.",
                "flags": [f.as_dict() for f in verdict.flags],
            },
        )
    return verdict.decision is moderation.Decision.HOLD


def _normalise_state(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    upper = code.strip().upper()
    if upper not in VALID_STATE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"{code} is not a state or union territory code. Expected one of the 36 ISO codes.",
        )
    return upper


@router.post("/petitions/{slug}/sign")
async def sign_petition(
    slug: str,
    payload: SignatureIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    petition = await _public_petition(session, slug)
    _assert_open(petition)

    existing = (
        await session.execute(
            select(PetitionSignature).where(
                PetitionSignature.petition_id == petition.id,
                PetitionSignature.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already signed this petition.")

    await limits.check("petition.sign", f"m:{citizen.email}")

    # Fills a gap, never overwrites: see the note on SignatureIn.state_code.
    state_code = _normalise_state(payload.state_code)
    if state_code and not citizen.state_code:
        citizen.state_code = state_code

    comment_hidden = _screen_comment(payload.comment)

    session.add(
        PetitionSignature(
            petition_id=petition.id,
            citizen_id=citizen.id,
            display_name=citizen.display_name,
            state_code=citizen.state_code,
            comment=moderation.scrub_identifiers(payload.comment.strip()),
            is_public=payload.show_my_name,
            comment_hidden=comment_hidden,
        )
    )
    await session.flush()
    await _recount(session, petition)

    contributions = dict(citizen.contributions or {})
    contributions["petitionsSigned"] = contributions.get("petitionsSigned", 0) + 1
    citizen.contributions = contributions

    return {
        "ok": True,
        "signatureCount": petition.signature_count,
        "nextMilestone": next_milestone(petition.signature_count),
        "commentPending": comment_hidden,
        "share": notify.share_links(
            url=_public_path(petition),
            text=f"I just signed: {petition.title}",
        ),
    }


@router.post("/petitions/{slug}/sign-public")
async def sign_petition_publicly(
    slug: str,
    payload: PublicSignatureIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Sign without already having an account: joining and signing in one step.

    WHAT THIS DOES NOT DO IS RELAX THE RULE. The module docstring's guarantee is
    that a signature belongs to a member account and is unique per petition,
    enforced by a database constraint rather than by application code. That is
    exactly as true here: this endpoint creates the member account (the same
    record `POST /supporters` creates, through the same `core.membership` helper)
    and then signs as that member. The unique constraint on
    (petition_id, citizen_id) does the work it always did.

    What changes is the number of forms a citizen fills in to do it. Asking
    somebody who arrived at a petition to sign up, find an access code in their
    email, log in and come back is a fair description of how to collect very few
    signatures, and the two-step version was never a security control -- the
    account it insists on could be created by anyone in the same ten seconds.

    What it costs, stated plainly rather than hidden: nothing here proves the
    person controls the address they typed, so a count of these signatures is a
    count of verified *accounts*, not of verified people. That is a smaller claim
    than it sounds, it is the same claim the join flow already makes, and the
    honest place to fix it is email confirmation in `core.membership`, where both
    entry points would gain it at once. Until then the rate limits below are what
    stands between this and a script.

    What that unproven address must NEVER buy is access to somebody else's
    account, so an address that already has one is refused here and sent to the
    login page (see the check below). The member token returned is therefore only
    ever for an account this request has just created, and it exists so the
    browser that signed can withdraw that signature without first hunting for an
    access code in an inbox.
    """
    petition = await _public_petition(session, slug)
    _assert_open(petition)

    if not payload.consent:
        raise HTTPException(
            status_code=400,
            detail="Please agree to the data notice before signing. Consent cannot be assumed.",
        )
    state_code = _normalise_state(payload.state_code)
    email = payload.email.lower().strip()
    name = payload.name.strip()

    # Two limits, deliberately. The email one is the same counter a signed-in
    # member spends, so this endpoint is not a way around it; the IP one is what
    # a script actually hits, since it can invent a fresh address every time.
    await limits.check("petition.sign", f"m:{email}")
    await limits.check("petition.sign.public", limits.identity_for(request))

    comment_hidden = _screen_comment(payload.comment)

    # An address that already has an account is turned away to the login page,
    # and this is the most important line in the endpoint. Nothing here proves
    # the person typing owns the address, so continuing would mean signing in
    # somebody else's name -- and, since this endpoint returns a session, handing
    # over their dashboard, their data and their right to erase it. Friction for
    # the few who already have an account is the correct trade.
    if await membership.member_exists(email):
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This email already has an account here. Sign in and you can sign this "
                    "petition in one click."
                ),
                "code": "member_exists",
            },
        )

    supporter = await membership.ensure_supporter(
        email=email,
        name=name,
        # The supporter record's `state` has always been the free-text state NAME
        # (see core/deps.get_current_citizen), so it stays a name here; the CODE
        # goes on the Citizen row, which is what state-wise aggregates read.
        state=STATES_BY_CODE[state_code].name if state_code else None,
        city=payload.city,
        pledge=True,
        source=f"petition:{petition.slug}",
    )

    citizen = (
        await session.execute(select(Citizen).where(Citizen.email == email))
    ).scalar_one_or_none()
    if citizen is None:
        citizen = Citizen(
            email=email,
            # Their real name becomes their community display name only if they
            # asked to be listed publicly. Otherwise the neutral handle applies,
            # for the reason on the Citizen model: nobody should end up posting
            # in the forum under their legal name because they signed a petition.
            display_name=name[:60] if payload.show_my_name else email.split("@")[0][:24].title(),
            state_code=state_code,
        )
        session.add(citizen)
        await session.flush()
    else:
        if not citizen.state_code:
            citizen.state_code = state_code
        if citizen.is_muted():
            raise HTTPException(
                status_code=403,
                detail=(
                    "Posting is paused on this account until "
                    f"{citizen.muted_until.date().isoformat()}. You can contest this "
                    "through the contact form."
                ),
            )

    existing = (
        await session.execute(
            select(PetitionSignature).where(
                PetitionSignature.petition_id == petition.id,
                PetitionSignature.citizen_id == citizen.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This email address has already signed this petition. One signature per "
                "person is what makes the number worth handing to an office."
            ),
        )

    session.add(
        PetitionSignature(
            petition_id=petition.id,
            citizen_id=citizen.id,
            display_name=name[:60] if payload.show_my_name else citizen.display_name,
            state_code=citizen.state_code,
            comment=moderation.scrub_identifiers(payload.comment.strip()),
            is_public=payload.show_my_name,
            comment_hidden=comment_hidden,
        )
    )
    await session.flush()
    await _recount(session, petition)

    contributions = dict(citizen.contributions or {})
    contributions["petitionsSigned"] = contributions.get("petitionsSigned", 0) + 1
    citizen.contributions = contributions

    return {
        "ok": True,
        "signatureCount": petition.signature_count,
        "nextMilestone": next_milestone(petition.signature_count),
        "commentPending": comment_hidden,
        "state": state_code,
        "isNewMember": not supporter.already,
        "movementId": supporter.movement_id,
        # Plaintext, once, and only for an account created by this request. See
        # core/membership: it cannot be produced again afterwards.
        "accessCode": supporter.access_code,
        "memberToken": create_member_token(email),
        "share": notify.share_links(
            url=_public_path(petition),
            text=f"I just signed: {petition.title}",
        ),
    }


@router.delete("/petitions/{slug}/sign")
async def withdraw_signature(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Withdraw a signature. Hard delete -- see the module docstring."""
    petition = (
        await session.execute(select(Petition).where(Petition.slug == slug))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")

    result = await session.execute(
        delete(PetitionSignature).where(
            PetitionSignature.petition_id == petition.id,
            PetitionSignature.citizen_id == citizen.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="You have not signed this petition.")

    await _recount(session, petition)
    # Withdrawing should not cost someone a slot in their hourly limit -- see
    # core/limits.reset.
    await limits.reset("petition.sign", f"m:{citizen.email}")
    return {"ok": True, "signatureCount": petition.signature_count}


@router.get("/me/petitions")
async def my_petitions(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Petitions this member started or signed -- their own record of participation."""
    started = list(
        (await session.execute(select(Petition).where(Petition.citizen_id == citizen.id))).scalars()
    )
    signed_rows = (
        await session.execute(
            select(Petition, PetitionSignature)
            .join(PetitionSignature, PetitionSignature.petition_id == Petition.id)
            .where(PetitionSignature.citizen_id == citizen.id)
            .order_by(PetitionSignature.created_at.desc())
        )
    ).all()
    return {
        "started": [{**_serialise(p), "isPublic": p.status in PUBLIC_STATUSES} for p in started],
        "signed": [
            {**_serialise(p), "signedOn": s.created_at.date().isoformat() if s.created_at else None}
            for p, s in signed_rows
        ],
    }


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/petitions")
async def admin_list_petitions(
    status: Optional[str] = None,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Petition).order_by(Petition.created_at.desc()).limit(300)
    if status:
        stmt = stmt.where(Petition.status == status)
    rows = (await session.execute(stmt)).scalars()
    return [
        {
            **_serialise(p, include_body=True),
            "citizenId": p.citizen_id,
            "policyFlags": p.policy_flags or None,
            "reviewedBy": p.reviewed_by,
        }
        for p in rows
        if admin.is_platform_wide() or (p.state_code and admin.can_in_state(p.state_code))
    ]


@router.post("/admin/petitions")
async def create_official_petition(
    payload: PetitionIn,
    request: Request,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """A petition run by the movement itself. Opens immediately.

    No moderation queue here: the permission gate IS the review, and the person
    creating it is accountable through the audit log.
    """
    state_code = payload.state_code.upper() if payload.state_code else None
    if state_code:
        require_state_scope(admin, state_code)

    slug = slugify(payload.title)
    if (await session.execute(select(Petition).where(Petition.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M')}"

    petition = Petition(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        body=payload.body.strip(),
        body_hi=payload.body_hi.strip(),
        addressed_to=payload.addressed_to.strip(),
        state_code=state_code,
        category=payload.category,
        target_signatures=payload.target_signatures,
        is_official=True,
        status=PetitionStatus.OPEN,
        closes_at=utcnow() + timedelta(days=DEFAULT_OPEN_DAYS),
        reviewed_by=admin.id,
    )
    session.add(petition)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"Opened official petition: {petition.title}",
        is_public=True,
        request=request,
    )
    await _index(session, petition)
    return _serialise(petition, include_body=True)


@router.post("/admin/petitions/{petition_id}/status")
async def set_petition_status(
    petition_id: str,
    payload: PetitionStatusIn,
    request: Request,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail=f"status must be one of {list(STATUS_LABELS)}")

    petition = (
        await session.execute(select(Petition).where(Petition.id == petition_id))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")
    if petition.state_code:
        require_state_scope(admin, petition.state_code)

    if payload.status == PetitionStatus.REJECTED and len(payload.note.strip()) < 10:
        # The person who wrote it is told why. A rejection with no reason is
        # indistinguishable from arbitrary moderation.
        raise HTTPException(
            status_code=400, detail="Explain why the petition was not accepted -- the author is told."
        )
    if payload.status in (PetitionStatus.DELIVERED, PetitionStatus.RESPONDED) and not (
        payload.outcome_source_url or petition.outcome_source_url
    ):
        raise HTTPException(
            status_code=400,
            detail="Claiming delivery or a response needs a link to the evidence (acknowledgement, reply, or news of it).",
        )

    before = petition.status
    petition.status = payload.status
    petition.status_note = payload.note.strip() or petition.status_note
    petition.outcome_source_url = payload.outcome_source_url or petition.outcome_source_url
    petition.reviewed_by = admin.id

    await audit.record(
        session,
        actor=admin,
        action="petition_status",
        entity_type="petition",
        entity_id=petition.slug,
        summary=f"{petition.title}: {STATUS_LABELS.get(before, before)} -> {STATUS_LABELS[payload.status]}",
        changes={"status": {"before": before, "after": payload.status}},
        source_url=petition.outcome_source_url or None,
        is_public=payload.status in PUBLIC_STATUSES,
        request=request,
    )
    await _index(session, petition)
    return _serialise(petition, include_body=True)


@router.post("/admin/petitions/{petition_id}/signatures/{signature_id}/moderate")
async def moderate_signature_comment(
    petition_id: str,
    signature_id: str,
    request: Request,
    hide: bool = True,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Hide or restore a signature's comment. Never removes the signature itself.

    The distinction matters: a comment that breaches the content policy is
    commentary, but the signature underneath it is a civic act that a moderator
    has no business cancelling.
    """
    signature = (
        await session.execute(
            select(PetitionSignature).where(
                PetitionSignature.id == signature_id, PetitionSignature.petition_id == petition_id
            )
        )
    ).scalar_one_or_none()
    if signature is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    signature.comment_hidden = hide
    await audit.record(
        session,
        actor=admin,
        action="moderate",
        entity_type="petition_signature",
        entity_id=signature_id,
        summary=f"{'Hid' if hide else 'Restored'} a signature comment",
        is_public=False,
        request=request,
    )
    return {"ok": True, "commentHidden": hide}


@router.get("/admin/petitions/{petition_id}/export")
async def export_signature_summary(
    petition_id: str,
    admin: Principal = Depends(require_permission("petitions.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Aggregates for the cover sheet handed to the addressee.

    Aggregates, not a name list. The office receiving a petition needs a
    verifiable count and its geographic spread; handing over a spreadsheet of
    signers' identities would betray the people who signed and, for those who
    did not opt in to being listed, would breach the basis on which their data
    was collected.
    """
    petition = (
        await session.execute(select(Petition).where(Petition.id == petition_id))
    ).scalar_one_or_none()
    if petition is None:
        raise HTTPException(status_code=404, detail="Petition not found")

    by_state = (
        await session.execute(
            select(PetitionSignature.state_code, func.count())
            .where(PetitionSignature.petition_id == petition_id)
            .group_by(PetitionSignature.state_code)
        )
    ).all()
    first = (
        await session.execute(
            select(func.min(PetitionSignature.created_at)).where(
                PetitionSignature.petition_id == petition_id
            )
        )
    ).scalar_one()

    return {
        "petition": {"title": petition.title, "addressedTo": petition.addressed_to, "slug": petition.slug},
        "totalSignatures": petition.signature_count,
        "publiclyListed": (
            await session.execute(
                select(func.count())
                .select_from(PetitionSignature)
                .where(
                    PetitionSignature.petition_id == petition_id,
                    PetitionSignature.is_public.is_(True),
                )
            )
        ).scalar_one(),
        "byState": [{"state": state or "unspecified", "count": count} for state, count in by_state],
        "firstSignatureAt": first.isoformat() if first else None,
        "milestones": petition.milestones,
        "note": (
            "Signature identities are not exported. Every signature is tied to a verified member "
            "account and is unique per petition, enforced by a database constraint."
        ),
    }


# --------------------------------------------------------------------------
# DPDP erasure
# --------------------------------------------------------------------------
@erasure.register("petitions")
@erasure.covers("petitions")
async def _erase_petition_authorship(
    session: AsyncSession, email: str, citizen_id: Optional[str]
) -> dict:
    """Detach the author from petitions they started; do not delete the petitions.

    A petition with signatures belongs to everyone who signed it. Deleting it because
    its author left would erase other people's civic acts, and if it has already been
    handed to an office, the platform would be unable to account for a document that
    exists in the world.

    Their SIGNATURES are a different matter and are deleted -- those cascade from the
    citizens row, which core/erasure removes.
    """
    if not citizen_id:
        return {}
    rows = list(
        (
            await session.execute(select(Petition).where(Petition.citizen_id == citizen_id))
        ).scalars()
    )
    for row in rows:
        row.citizen_id = None
    return {"petitions_anonymised": len(rows)}
