"""Representative Database, Promise Tracker and the fact-check queue.

Every write path here goes through the same four gates, in this order: does the
caller hold the permission, is the citation acceptable for this field, does the
change get recorded in the audit log, and does the public serialiser mark the
result honestly. The order matters -- checking the citation after writing the
value would leave an unsourced number in the database for the length of a
transaction, and §7 is a rule about what exists, not about what is displayed.

The draft/publish split is stricter than the Constitution Library's. There,
publishing an unfinished explanation is embarrassing. Here, publishing an
unverified criminal-case count next to a living person's name is actionable, so
`representatives.publish` is a separate permission held by Fact Checkers, and the
publish endpoint refuses profiles whose high-risk claims have not been reviewed.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, search
from backend.core.citations import (
    STANDARD_DISCLAIMER,
    CitationError,
    VerificationStatus,
    claim_envelope,
    is_publicly_visible,
    parse_citation,
)
from backend.core.deps import get_session, require_permission, require_state_scope
from backend.core.models import State, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.representatives.fields import (
    CATEGORY_ORDER,
    CLAIM_FIELDS_BY_KEY,
    catalogue,
)
from backend.modules.representatives.models import (
    ADVERSE_STATUSES,
    DIRECTLY_ELECTED,
    HOUSES,
    PROMISE_STATUSES,
    Constituency,
    Party,
    Promise,
    Representative,
    RepresentativeClaim,
)

router = APIRouter(tags=["representatives"])


# --------------------------------------------------------------------------
# Payloads
# --------------------------------------------------------------------------
class CitationIn(BaseModel):
    url: str
    title: str
    source_date: Optional[str] = None
    publisher: Optional[str] = None


class RepresentativeIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    house: str
    state_code: str
    name_hi: str = ""
    constituency_code: Optional[str] = None
    party_code: Optional[str] = None
    term_start: Optional[date] = None
    term_end: Optional[date] = None
    is_sitting: bool = True
    office: str = ""
    photo_url: str = ""
    official_email: str = ""
    office_address: str = ""
    official_page_url: str = ""
    # Not optional. A profile of a named person with no source at all is the one
    # thing §7 exists to prevent, so it is required at the type level.
    source: CitationIn


class RepresentativeUpdate(BaseModel):
    full_name: Optional[str] = None
    name_hi: Optional[str] = None
    house: Optional[str] = None
    state_code: Optional[str] = None
    constituency_code: Optional[str] = None
    party_code: Optional[str] = None
    term_start: Optional[date] = None
    term_end: Optional[date] = None
    is_sitting: Optional[bool] = None
    office: Optional[str] = None
    photo_url: Optional[str] = None
    official_email: Optional[str] = None
    office_address: Optional[str] = None
    official_page_url: Optional[str] = None
    source: Optional[CitationIn] = None


class ClaimIn(BaseModel):
    field_key: str
    period: str = ""
    value_number: Optional[float] = None
    value_text: str = ""
    source: CitationIn


class ClaimReview(BaseModel):
    status: str
    note: str = ""


class PartyIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=2, max_length=200)
    name_hi: str = ""
    eci_status: str = "registered_unrecognised"
    symbol: str = ""
    founded_year: Optional[int] = None
    source_url: str = ""


class ConstituencyIn(BaseModel):
    state_code: str
    house: str
    name: str = Field(..., min_length=2, max_length=160)
    number: Optional[int] = None
    name_hi: str = ""
    district_code: Optional[str] = None
    reserved_for: Optional[str] = None
    electors: Optional[int] = None
    source_url: str = ""


class PromiseIn(BaseModel):
    title: str = Field(..., min_length=6, max_length=300)
    promise_text: str = Field(..., min_length=10)
    representative_id: Optional[str] = None
    party_code: Optional[str] = None
    state_code: Optional[str] = None
    constituency_code: Optional[str] = None
    title_hi: str = ""
    promise_text_hi: str = ""
    category: str = "general"
    made_on: Optional[date] = None
    made_context: str = ""
    deadline: Optional[date] = None
    source: CitationIn


class PromiseStatusIn(BaseModel):
    status: str
    note: str = Field(..., min_length=10)
    source: CitationIn


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _citation(payload: CitationIn, *, require_primary: bool, field_name: str):
    try:
        return parse_citation(payload.model_dump(), require_primary=require_primary, field_name=field_name)
    except CitationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def format_indian_currency(value: Optional[float]) -> Optional[str]:
    """Rupee figures in crore/lakh, which is how they are read in India.

    A declared asset figure rendered as "312500000" is technically correct and
    practically unreadable; "Rs 31.25 crore" is the same fact in the form every
    Indian reader parses instantly.
    """
    if value is None:
        return None
    if value >= 1_00_00_000:
        return f"Rs {value / 1_00_00_000:,.2f} crore"
    if value >= 1_00_000:
        return f"Rs {value / 1_00_000:,.2f} lakh"
    return f"Rs {value:,.0f}"


def _claim_dict(claim: RepresentativeClaim) -> dict:
    definition = CLAIM_FIELDS_BY_KEY.get(claim.field_key)
    value = claim.value_number if claim.value_number is not None else (claim.value_text or None)

    display = None
    if definition and claim.value_number is not None:
        if definition.kind == "currency":
            display = format_indian_currency(claim.value_number)
        elif definition.kind == "percent":
            display = f"{claim.value_number:g}%"
        else:
            display = f"{claim.value_number:g}"

    envelope = claim_envelope(
        value,
        status=claim.verification_status,
        citation={
            "url": claim.source_url,
            "title": claim.source_title,
            "sourceDate": claim.source_date or None,
            "publisher": claim.source_publisher or None,
            "isPrimary": claim.source_is_primary,
        },
        updated_at=claim.updated_at,
    )
    envelope.update(
        {
            "id": claim.id,
            "fieldKey": claim.field_key,
            "label": definition.label if definition else claim.field_key,
            "category": definition.category if definition else "Other",
            "kind": definition.kind if definition else "text",
            "explanation": definition.explanation if definition else "",
            "period": claim.period or None,
            "display": display,
            # Only shown for disputed/retracted claims by the serialiser below --
            # a bare "disputed" with no reason is an insinuation.
            "reviewNote": claim.review_note or None,
        }
    )
    return envelope


def _group_claims(claims: list[RepresentativeClaim]) -> list[dict]:
    """Public claim view, grouped by category in a fixed order."""
    visible = [c for c in claims if is_publicly_visible(c.verification_status)]
    grouped: dict[str, list[dict]] = {}
    for claim in visible:
        payload = _claim_dict(claim)
        if payload["status"] == VerificationStatus.FACT_CHECKED.value:
            payload.pop("reviewNote", None)
        grouped.setdefault(payload["category"], []).append(payload)

    ordered = []
    for category in CATEGORY_ORDER:
        if category in grouped:
            ordered.append(
                {
                    "category": category,
                    "items": sorted(grouped.pop(category), key=lambda c: (c["period"] or "", c["label"])),
                }
            )
    for category, items in sorted(grouped.items()):
        ordered.append({"category": category, "items": items})
    return ordered


def _rep_summary(rep: Representative, party: Optional[Party], seat: Optional[Constituency]) -> dict:
    return {
        "id": rep.id,
        "slug": rep.slug,
        "name": rep.full_name,
        "nameHi": rep.name_hi,
        "photoUrl": rep.photo_url,
        "house": rep.house,
        "houseLabel": HOUSES.get(rep.house, rep.house),
        # Stated plainly because it decides whether a recall right could reach
        # this seat at all -- see the note on Article 80 in the library.
        "isDirectlyElected": rep.house in DIRECTLY_ELECTED,
        "state": rep.state_code,
        "constituency": (
            {"code": seat.code, "name": seat.name, "number": seat.number, "reservedFor": seat.reserved_for}
            if seat
            else None
        ),
        "party": (
            {"code": party.code, "name": party.name, "nameHi": party.name_hi, "eciStatus": party.eci_status}
            if party
            else None
        ),
        "office": rep.office,
        "isSitting": rep.is_sitting,
        "termStart": rep.term_start.isoformat() if rep.term_start else None,
        "termEnd": rep.term_end.isoformat() if rep.term_end else None,
        "url": f"/representatives/{rep.slug}",
    }


async def _load_related(
    session: AsyncSession, reps: list[Representative]
) -> tuple[dict[str, Party], dict[str, Constituency]]:
    """One query each for parties and seats, instead of one per representative."""
    party_codes = {r.party_code for r in reps if r.party_code}
    seat_codes = {r.constituency_code for r in reps if r.constituency_code}
    parties = (
        {p.code: p for p in (await session.execute(select(Party).where(Party.code.in_(party_codes)))).scalars()}
        if party_codes
        else {}
    )
    seats = (
        {
            c.code: c
            for c in (
                await session.execute(select(Constituency).where(Constituency.code.in_(seat_codes)))
            ).scalars()
        }
        if seat_codes
        else {}
    )
    return parties, seats


async def _index_representative(session: AsyncSession, rep: Representative, party: Optional[Party]) -> None:
    await search.index(
        session,
        entity_type="representative",
        entity_id=rep.slug,
        title=rep.full_name,
        subtitle=f"{HOUSES.get(rep.house, rep.house)}"
        + (f" - {rep.office}" if rep.office else ""),
        body=f"{rep.name_hi} {party.name if party else ''} {rep.office}",
        keywords=[rep.state_code, rep.house, rep.party_code or "", rep.constituency_code or ""],
        state_code=rep.state_code,
        is_published=rep.is_published,
        url_path=f"/representatives/{rep.slug}",
    )


async def _unique_slug(session: AsyncSession, model, base: str) -> str:
    slug = slugify(base)
    candidate, suffix = slug, 2
    while (
        await session.execute(select(model).where(model.slug == candidate))
    ).scalar_one_or_none() is not None:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


# --------------------------------------------------------------------------
# Public: reference data
# --------------------------------------------------------------------------
@router.get("/parties")
async def list_parties(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Party).order_by(Party.name))).scalars()
    return [
        {
            "code": p.code,
            "name": p.name,
            "nameHi": p.name_hi,
            "eciStatus": p.eci_status,
            "symbol": p.symbol,
            "foundedYear": p.founded_year,
            "sourceUrl": p.source_url,
        }
        for p in rows
        if p.is_active
    ]


@router.get("/houses")
async def list_houses():
    return [
        {"key": key, "label": label, "isDirectlyElected": key in DIRECTLY_ELECTED}
        for key, label in HOUSES.items()
    ]


@router.get("/claim-fields")
async def list_claim_fields():
    """What the platform tracks, and what each figure does and does not mean.

    Public rather than admin-only on purpose: the explanations are the difference
    between publishing a number and publishing a fact, and a reader should be
    able to check how we define "attendance" without taking our word for it.
    """
    return {"fields": catalogue(), "disclaimer": STANDARD_DISCLAIMER}


@router.get("/constituencies")
async def list_constituencies(
    state: Optional[str] = None,
    house: Optional[str] = None,
    q: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Constituency).order_by(Constituency.state_code, Constituency.house, Constituency.number)
    if state:
        stmt = stmt.where(Constituency.state_code == state.upper())
    if house:
        stmt = stmt.where(Constituency.house == house)
    if q:
        stmt = stmt.where(func.lower(Constituency.name).like(f"%{q.lower()}%"))
    rows = (await session.execute(stmt.limit(600))).scalars()
    return [
        {
            "code": c.code,
            "state": c.state_code,
            "district": c.district_code,
            "house": c.house,
            "number": c.number,
            "name": c.name,
            "nameHi": c.name_hi,
            "slug": c.slug,
            "reservedFor": c.reserved_for,
            "electors": c.electors,
        }
        for c in rows
    ]


# --------------------------------------------------------------------------
# Public: representatives
# --------------------------------------------------------------------------
@router.get("/representatives")
async def list_representatives(
    state: Optional[str] = None,
    house: Optional[str] = None,
    party: Optional[str] = None,
    constituency: Optional[str] = None,
    sitting: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Representative).where(Representative.is_published.is_(True))
    if state:
        stmt = stmt.where(Representative.state_code == state.upper())
    if house:
        stmt = stmt.where(Representative.house == house)
    if party:
        stmt = stmt.where(Representative.party_code == party.upper())
    if constituency:
        stmt = stmt.where(Representative.constituency_code == constituency.upper())
    if sitting is not None:
        stmt = stmt.where(Representative.is_sitting.is_(sitting))
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Representative.full_name).like(needle), Representative.name_hi.like(needle))
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = list(
        (
            await session.execute(stmt.order_by(Representative.full_name).offset(offset).limit(limit))
        ).scalars()
    )
    parties, seats = await _load_related(session, rows)
    return {
        "total": total,
        "items": [
            _rep_summary(r, parties.get(r.party_code), seats.get(r.constituency_code)) for r in rows
        ],
    }


@router.get("/representatives/{slug}")
async def get_representative(slug: str, session: AsyncSession = Depends(get_session)):
    rep = (
        await session.execute(
            select(Representative).where(
                Representative.slug == slug, Representative.is_published.is_(True)
            )
        )
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="This profile is not published yet")

    parties, seats = await _load_related(session, [rep])
    claims = list(
        (
            await session.execute(
                select(RepresentativeClaim).where(RepresentativeClaim.representative_id == rep.id)
            )
        ).scalars()
    )
    promises = list(
        (
            await session.execute(
                select(Promise)
                .where(Promise.representative_id == rep.id, Promise.is_published.is_(True))
                .order_by(Promise.made_on.desc().nullslast())
            )
        ).scalars()
    )

    payload = _rep_summary(rep, parties.get(rep.party_code), seats.get(rep.constituency_code))
    payload.update(
        {
            "contact": {
                # Official channels only. See the note on the model: these are
                # published by the House so citizens can write to the office.
                "email": rep.official_email or None,
                "officeAddress": rep.office_address or None,
                "officialPage": rep.official_page_url or None,
            },
            "source": {"url": rep.source_url, "title": rep.source_title},
            "claims": _group_claims(claims),
            "claimSummary": {
                "total": len([c for c in claims if is_publicly_visible(c.verification_status)]),
                "factChecked": len(
                    [c for c in claims if c.verification_status == VerificationStatus.FACT_CHECKED.value]
                ),
                "unverified": len(
                    [c for c in claims if c.verification_status == VerificationStatus.UNVERIFIED.value]
                ),
                "disputed": len(
                    [c for c in claims if c.verification_status == VerificationStatus.DISPUTED.value]
                ),
            },
            "promises": [_promise_summary(p) for p in promises],
            "promiseTally": _tally(promises),
            "disclaimer": STANDARD_DISCLAIMER,
            "historyUrl": f"/api/representatives/{rep.slug}/history",
            "correctionUrl": f"/api/corrections?entityType=representative&entityId={rep.slug}",
            "updatedAt": rep.updated_at.isoformat() if rep.updated_at else None,
        }
    )
    return payload


@router.get("/representatives/{slug}/history")
async def representative_history(slug: str, session: AsyncSession = Depends(get_session)):
    """Public, per-profile edit history. §7's Wikipedia-History pillar.

    Actor identity is omitted. Anyone can see that an asset figure changed, when,
    and on what source; naming the volunteer who typed it invites pressure on the
    volunteer and is not part of what transparency requires.
    """
    entries = await audit.history(session, entity_type="representative", entity_id=slug)
    return [audit.to_dict(e, include_actor=False) for e in entries]


@router.get("/my-representatives")
async def who_represents_me(
    state: str,
    constituency: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """"Who represents me" -- the question the landing page promises to answer.

    Returns the state's directly elected representatives, narrowed to one
    constituency when given. Deliberately reports what is MISSING as well as what
    is present: a page that silently shows two of a state's forty MPs looks
    complete and is not.
    """
    state_code = state.upper()
    row = (await session.execute(select(State).where(State.code == state_code))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown state code")

    stmt = select(Representative).where(
        Representative.state_code == state_code,
        Representative.is_published.is_(True),
        Representative.is_sitting.is_(True),
    )
    if constituency:
        stmt = stmt.where(Representative.constituency_code == constituency.upper())
    reps = list((await session.execute(stmt.order_by(Representative.house))).scalars())
    parties, seats = await _load_related(session, reps)

    by_house: dict[str, list[dict]] = {}
    for rep in reps:
        by_house.setdefault(rep.house, []).append(
            _rep_summary(rep, parties.get(rep.party_code), seats.get(rep.constituency_code))
        )

    return {
        "state": {"code": row.code, "name": row.name, "hasLegislature": row.has_legislature},
        "houses": [
            {
                "key": house,
                "label": HOUSES[house],
                "expected": {
                    "lok_sabha": row.lok_sabha_seats,
                    "rajya_sabha": row.rajya_sabha_seats,
                    "assembly": row.assembly_seats,
                }.get(house),
                "published": len(by_house.get(house, [])),
                "items": by_house.get(house, []),
            }
            for house in HOUSES
            if by_house.get(house) or house != "council"
        ],
        "dataComplete": row.is_pilot,
        "helpText": (
            "Profiles are added constituency by constituency, each one sourced from public "
            "records before it is published. If a seat you care about is missing, you can help "
            "research it."
            if not row.is_pilot
            else None
        ),
    }


# --------------------------------------------------------------------------
# Public: promises
# --------------------------------------------------------------------------
def _promise_summary(promise: Promise) -> dict:
    return {
        "id": promise.id,
        "slug": promise.slug,
        "title": promise.title,
        "titleHi": promise.title_hi,
        "category": promise.category,
        "status": promise.status,
        "statusLabel": PROMISE_STATUSES.get(promise.status, promise.status),
        "verificationStatus": promise.verification_status,
        "madeOn": promise.made_on.isoformat() if promise.made_on else None,
        "madeContext": promise.made_context,
        "deadline": promise.deadline.isoformat() if promise.deadline else None,
        "state": promise.state_code,
        "party": promise.party_code,
        "url": f"/promises/{promise.slug}",
    }


def _tally(promises: list[Promise]) -> dict:
    tally = {key: 0 for key in PROMISE_STATUSES}
    for promise in promises:
        tally[promise.status] = tally.get(promise.status, 0) + 1
    return {
        "counts": tally,
        "total": len(promises),
        # Reported as a fraction of ASSESSED promises, not of all promises.
        # Including "cannot be assessed yet" in the denominator quietly deflates
        # every representative's record, which would be a thumb on the scale.
        "assessed": sum(
            tally[k] for k in ("fulfilled", "partially_fulfilled", "broken", "stalled")
        ),
    }


@router.get("/promises")
async def list_promises(
    representative: Optional[str] = None,
    party: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Promise).where(Promise.is_published.is_(True))
    if representative:
        stmt = stmt.where(Promise.representative_id == representative)
    if party:
        stmt = stmt.where(Promise.party_code == party.upper())
    if state:
        stmt = stmt.where(Promise.state_code == state.upper())
    if status:
        stmt = stmt.where(Promise.status == status)
    if category:
        stmt = stmt.where(Promise.category == category)

    rows = list((await session.execute(stmt)).scalars())
    window = sorted(rows, key=lambda p: (p.made_on or date.min), reverse=True)[offset : offset + limit]
    return {
        "total": len(rows),
        "tally": _tally(rows),
        "statuses": [{"key": k, "label": v} for k, v in PROMISE_STATUSES.items()],
        "items": [_promise_summary(p) for p in window],
    }


@router.get("/promises/{slug}")
async def get_promise(slug: str, session: AsyncSession = Depends(get_session)):
    promise = (
        await session.execute(
            select(Promise).where(Promise.slug == slug, Promise.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if promise is None:
        raise HTTPException(status_code=404, detail="Promise not found")

    rep = None
    if promise.representative_id:
        row = (
            await session.execute(
                select(Representative).where(Representative.id == promise.representative_id)
            )
        ).scalar_one_or_none()
        if row is not None and row.is_published:
            rep = {"name": row.full_name, "slug": row.slug, "url": f"/representatives/{row.slug}"}

    payload = _promise_summary(promise)
    payload.update(
        {
            "promiseText": promise.promise_text,
            "promiseTextHi": promise.promise_text_hi,
            "statusNote": promise.status_note,
            "representative": rep,
            "source": {"url": promise.source_url, "title": promise.source_title},
            # Two separate citations: one that the promise was made, one for what
            # became of it. See the model docstring for why both are required.
            "statusSource": {"url": promise.status_source_url} if promise.status_source_url else None,
            "evidence": promise.evidence,
            "statusUpdatedAt": promise.status_updated_at.isoformat() if promise.status_updated_at else None,
            "disclaimer": STANDARD_DISCLAIMER,
            "historyUrl": f"/api/history/promise/{promise.slug}",
        }
    )
    return payload


# --------------------------------------------------------------------------
# Admin: reference data
# --------------------------------------------------------------------------
@router.post("/admin/parties")
async def create_party(
    payload: PartyIn,
    request: Request,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    code = payload.code.upper()
    if (await session.execute(select(Party).where(Party.code == code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Party {code} already exists")

    party = Party(
        code=code,
        name=payload.name.strip(),
        name_hi=payload.name_hi.strip(),
        eci_status=payload.eci_status,
        symbol=payload.symbol,
        founded_year=payload.founded_year,
        source_url=payload.source_url,
    )
    session.add(party)
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="party",
        entity_id=code,
        summary=f"Added party {payload.name}",
        source_url=payload.source_url or None,
        is_public=True,
        request=request,
    )
    return {"code": party.code, "name": party.name}


@router.post("/admin/constituencies")
async def create_constituency(
    payload: ConstituencyIn,
    request: Request,
    admin: Principal = Depends(require_permission("states.edit")),
    session: AsyncSession = Depends(get_session),
):
    state_code = payload.state_code.upper()
    require_state_scope(admin, state_code)
    if payload.house not in HOUSES:
        raise HTTPException(status_code=400, detail=f"house must be one of {list(HOUSES)}")

    house_prefix = {"lok_sabha": "LS", "assembly": "AC", "rajya_sabha": "RS", "council": "MLC"}[payload.house]
    number = payload.number
    code = f"{state_code}-{house_prefix}-{number:03d}" if number else f"{state_code}-{house_prefix}-{slugify(payload.name)}"

    if (await session.execute(select(Constituency).where(Constituency.code == code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Constituency {code} already exists")

    seat = Constituency(
        code=code,
        state_code=state_code,
        district_code=payload.district_code,
        house=payload.house,
        number=number,
        name=payload.name.strip(),
        name_hi=payload.name_hi.strip(),
        slug=await _unique_slug(session, Constituency, f"{payload.name}-{state_code}"),
        reserved_for=payload.reserved_for,
        electors=payload.electors,
        source_url=payload.source_url,
    )
    session.add(seat)
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="constituency",
        entity_id=code,
        summary=f"Added constituency {payload.name} ({state_code})",
        source_url=payload.source_url or None,
        is_public=True,
        request=request,
    )
    return {"code": seat.code, "slug": seat.slug, "name": seat.name}


@router.post("/admin/constituencies/bulk")
async def bulk_create_constituencies(
    payload: list[ConstituencyIn],
    request: Request,
    admin: Principal = Depends(require_permission("states.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Import a state's seat list in one call.

    Skips rows that already exist rather than failing the batch: an import is
    usually re-run after a partial failure or a corrected source file, and an
    all-or-nothing import of 288 assembly seats is an import nobody dares re-run.
    """
    if len(payload) > 600:
        raise HTTPException(status_code=400, detail="Import at most 600 seats per request")

    created, skipped = [], []
    for row in payload:
        try:
            result = await create_constituency(row, request, admin, session)
            created.append(result["code"])
        except HTTPException as e:
            if e.status_code == 409:
                skipped.append(row.name)
                continue
            raise
    return {"created": len(created), "skipped": len(skipped), "skippedNames": skipped[:20]}


# --------------------------------------------------------------------------
# Admin: representatives
# --------------------------------------------------------------------------
@router.get("/admin/representatives")
async def admin_list_representatives(
    state: Optional[str] = None,
    published: Optional[bool] = None,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Representative).order_by(Representative.full_name)
    if state:
        stmt = stmt.where(Representative.state_code == state.upper())
    if published is not None:
        stmt = stmt.where(Representative.is_published.is_(published))
    rows = list((await session.execute(stmt)).scalars())
    parties, seats = await _load_related(session, rows)

    claim_counts = dict(
        (
            await session.execute(
                select(RepresentativeClaim.representative_id, func.count())
                .where(RepresentativeClaim.representative_id.in_([r.id for r in rows] or [""]))
                .group_by(RepresentativeClaim.representative_id)
            )
        ).all()
    )
    return [
        {
            **_rep_summary(r, parties.get(r.party_code), seats.get(r.constituency_code)),
            "isPublished": r.is_published,
            "claimCount": claim_counts.get(r.id, 0),
        }
        for r in rows
    ]


@router.post("/admin/representatives")
async def create_representative(
    payload: RepresentativeIn,
    request: Request,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    if payload.house not in HOUSES:
        raise HTTPException(status_code=400, detail=f"house must be one of {list(HOUSES)}")
    state_code = payload.state_code.upper()
    require_state_scope(admin, state_code)

    # Identity facts do not need a primary source -- a reputable directory of
    # who holds a seat is adequate, and demanding an ECI PDF to record a name
    # would stall the whole database. The claim endpoint is where the bar rises.
    citation = _citation(payload.source, require_primary=False, field_name="this profile")

    rep = Representative(
        full_name=payload.full_name.strip(),
        name_hi=payload.name_hi.strip(),
        slug=await _unique_slug(session, Representative, f"{payload.full_name}-{state_code}"),
        house=payload.house,
        state_code=state_code,
        constituency_code=payload.constituency_code.upper() if payload.constituency_code else None,
        party_code=payload.party_code.upper() if payload.party_code else None,
        term_start=payload.term_start,
        term_end=payload.term_end,
        is_sitting=payload.is_sitting,
        office=payload.office,
        photo_url=payload.photo_url,
        official_email=payload.official_email,
        office_address=payload.office_address,
        official_page_url=payload.official_page_url,
        source_url=citation.url,
        source_title=citation.title,
        is_published=False,
        updated_by=admin.id,
    )
    session.add(rep)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="representative",
        entity_id=rep.slug,
        summary=f"Created profile for {rep.full_name} ({HOUSES[rep.house]}, {state_code})",
        changes=audit.diff(
            None,
            {
                "name": rep.full_name,
                "house": rep.house,
                "state": state_code,
                "constituency": rep.constituency_code,
                "party": rep.party_code,
            },
        ),
        source_url=citation.url,
        is_public=True,
        request=request,
    )
    parties, _ = await _load_related(session, [rep])
    await _index_representative(session, rep, parties.get(rep.party_code))
    return {**_rep_summary(rep, parties.get(rep.party_code), None), "isPublished": False}


@router.put("/admin/representatives/{rep_id}")
async def update_representative(
    rep_id: str,
    payload: RepresentativeUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    rep = (
        await session.execute(select(Representative).where(Representative.id == rep_id))
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")
    require_state_scope(admin, rep.state_code)

    updates = payload.model_dump(exclude_unset=True, exclude={"source"})
    before, after = {}, {}
    for field, value in updates.items():
        if value is None:
            continue
        if field in ("constituency_code", "party_code", "state_code", "house"):
            value = value.upper() if field != "house" else value
        current = getattr(rep, field)
        if current != value:
            before[field] = current.isoformat() if hasattr(current, "isoformat") else current
            after[field] = value.isoformat() if hasattr(value, "isoformat") else value
            setattr(rep, field, value)

    if payload.source is not None:
        citation = _citation(payload.source, require_primary=False, field_name="this profile")
        if (rep.source_url, rep.source_title) != (citation.url, citation.title):
            before["source_url"] = rep.source_url
            after["source_url"] = citation.url
            rep.source_url, rep.source_title = citation.url, citation.title

    if not after:
        raise HTTPException(status_code=400, detail="No changes provided")

    rep.updated_by = admin.id
    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type="representative",
        entity_id=rep.slug,
        summary=f"Updated profile for {rep.full_name}",
        changes=audit.diff(before, after),
        source_url=rep.source_url,
        is_public=True,
        request=request,
    )
    parties, seats = await _load_related(session, [rep])
    await _index_representative(session, rep, parties.get(rep.party_code))
    return _rep_summary(rep, parties.get(rep.party_code), seats.get(rep.constituency_code))


@router.post("/admin/representatives/{rep_id}/publish")
async def publish_representative(
    rep_id: str,
    request: Request,
    publish: bool = True,
    admin: Principal = Depends(require_permission("representatives.publish")),
    session: AsyncSession = Depends(get_session),
):
    """Make a profile public. Held by Fact Checkers, not by the Research Team.

    Refuses while any high-risk claim on the profile is still unverified. A
    criminal-case count next to a living person's name, published before anyone
    checked it against the affidavit, is exactly the failure §7 was written to
    prevent -- so the gate is mechanical rather than a matter of remembering.
    """
    rep = (
        await session.execute(select(Representative).where(Representative.id == rep_id))
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")
    require_state_scope(admin, rep.state_code)

    if publish:
        claims = list(
            (
                await session.execute(
                    select(RepresentativeClaim).where(RepresentativeClaim.representative_id == rep.id)
                )
            ).scalars()
        )
        blocking = [
            c.field_key
            for c in claims
            if c.verification_status == VerificationStatus.UNVERIFIED.value
            and CLAIM_FIELDS_BY_KEY.get(c.field_key)
            and CLAIM_FIELDS_BY_KEY[c.field_key].requires_primary
        ]
        if blocking:
            raise HTTPException(
                status_code=400,
                detail=(
                    "These claims must be fact-checked before this profile can be published: "
                    f"{sorted(set(blocking))}. Either verify them or remove them."
                ),
            )

    if rep.is_published == publish:
        raise HTTPException(status_code=400, detail="Already in that state")

    rep.is_published = publish
    rep.published_at = utcnow() if publish else None

    await audit.record(
        session,
        actor=admin,
        action="publish" if publish else "unpublish",
        entity_type="representative",
        entity_id=rep.slug,
        summary=f"{'Published' if publish else 'Unpublished'} profile for {rep.full_name}",
        changes={"is_published": {"before": not publish, "after": publish}},
        is_public=True,
        request=request,
    )
    parties, seats = await _load_related(session, [rep])
    await _index_representative(session, rep, parties.get(rep.party_code))
    return _rep_summary(rep, parties.get(rep.party_code), seats.get(rep.constituency_code))


# --------------------------------------------------------------------------
# Admin: claims
# --------------------------------------------------------------------------
@router.get("/admin/representatives/{rep_id}/claims")
async def list_claims(
    rep_id: str,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    claims = (
        await session.execute(
            select(RepresentativeClaim)
            .where(RepresentativeClaim.representative_id == rep_id)
            .order_by(RepresentativeClaim.field_key, RepresentativeClaim.period)
        )
    ).scalars()
    return [_claim_dict(c) for c in claims]


@router.put("/admin/representatives/{rep_id}/claims")
async def upsert_claim(
    rep_id: str,
    payload: ClaimIn,
    request: Request,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Record or correct one sourced fact.

    Always lands as UNVERIFIED, including when a Fact Checker is the one typing
    it. Self-verification is not verification, and the review step is where the
    citation is actually opened and read.
    """
    definition = CLAIM_FIELDS_BY_KEY.get(payload.field_key)
    if definition is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field '{payload.field_key}'. See GET /api/claim-fields.",
        )

    rep = (
        await session.execute(select(Representative).where(Representative.id == rep_id))
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")
    require_state_scope(admin, rep.state_code)

    if definition.period_required and not payload.period.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{definition.label}' needs a period (e.g. '18th Lok Sabha' or '2024'). "
                "The same figure means different things in different terms."
            ),
        )
    if payload.value_number is None and not payload.value_text.strip():
        raise HTTPException(status_code=400, detail="Provide a value")
    if definition.kind in ("count", "currency", "percent") and payload.value_number is None:
        raise HTTPException(status_code=400, detail=f"'{definition.label}' expects a number")
    if definition.kind == "percent" and not (0 <= (payload.value_number or 0) <= 100):
        raise HTTPException(status_code=400, detail="A percentage must be between 0 and 100")
    if definition.kind in ("count", "currency") and (payload.value_number or 0) < 0:
        raise HTTPException(status_code=400, detail="This figure cannot be negative")

    citation = _citation(
        payload.source, require_primary=definition.requires_primary, field_name=definition.label
    )

    period = payload.period.strip()
    claim = (
        await session.execute(
            select(RepresentativeClaim).where(
                RepresentativeClaim.representative_id == rep_id,
                RepresentativeClaim.field_key == payload.field_key,
                RepresentativeClaim.period == period,
            )
        )
    ).scalar_one_or_none()

    before = (
        {
            "value": claim.value_number if claim.value_number is not None else claim.value_text,
            "source_url": claim.source_url,
            "verification_status": claim.verification_status,
        }
        if claim
        else None
    )

    if claim is None:
        claim = RepresentativeClaim(
            representative_id=rep_id, field_key=payload.field_key, period=period
        )
        session.add(claim)

    claim.value_number = payload.value_number
    claim.value_text = payload.value_text.strip()
    claim.source_url = citation.url
    claim.source_title = citation.title
    claim.source_date = citation.source_date or ""
    claim.source_publisher = citation.publisher or ""
    claim.source_is_primary = citation.is_primary
    # Any edit resets verification. A figure corrected after fact-checking is a
    # new figure, and inheriting the old approval would let a reviewed claim be
    # quietly replaced by an unreviewed one.
    claim.verification_status = VerificationStatus.UNVERIFIED.value
    claim.review_note = ""
    claim.reviewed_by = None
    claim.reviewed_at = None
    claim.submitted_by = admin.id
    await session.flush()

    after = {
        "value": payload.value_number if payload.value_number is not None else payload.value_text,
        "source_url": citation.url,
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    await audit.record(
        session,
        actor=admin,
        action="claim_update" if before else "claim_create",
        entity_type="representative",
        entity_id=rep.slug,
        summary=f"{definition.label}{f' ({period})' if period else ''} for {rep.full_name}",
        changes=audit.diff(before, after),
        source_url=citation.url,
        is_public=True,
        request=request,
    )
    return _claim_dict(claim)


@router.delete("/admin/representatives/{rep_id}/claims/{claim_id}")
async def delete_claim(
    rep_id: str,
    claim_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("representatives.edit")),
    session: AsyncSession = Depends(get_session),
):
    claim = (
        await session.execute(
            select(RepresentativeClaim).where(
                RepresentativeClaim.id == claim_id, RepresentativeClaim.representative_id == rep_id
            )
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    rep = (
        await session.execute(select(Representative).where(Representative.id == rep_id))
    ).scalar_one_or_none()
    require_state_scope(admin, rep.state_code)

    field_key, period = claim.field_key, claim.period
    await session.delete(claim)
    await audit.record(
        session,
        actor=admin,
        action="claim_delete",
        entity_type="representative",
        entity_id=rep.slug,
        summary=f"Removed {field_key}{f' ({period})' if period else ''} from {rep.full_name}",
        changes={"field": {"before": field_key, "after": None}},
        is_public=True,
        request=request,
    )
    return {"ok": True}


# --------------------------------------------------------------------------
# Admin: the fact-check queue -- §7's verifiability gate, as a screen
# --------------------------------------------------------------------------
@router.get("/admin/factcheck/queue")
async def factcheck_queue(
    state: Optional[str] = None,
    only_high_risk: bool = False,
    limit: int = Query(default=100, ge=1, le=300),
    admin: Principal = Depends(require_permission("factcheck.approve")),
    session: AsyncSession = Depends(get_session),
):
    """Unverified and disputed claims, oldest first.

    Oldest first rather than newest: a queue worked newest-first grows a tail of
    claims nobody ever reaches, and those are precisely the ones sitting
    unverified on a public profile.
    """
    stmt = (
        select(RepresentativeClaim, Representative)
        .join(Representative, Representative.id == RepresentativeClaim.representative_id)
        .where(
            RepresentativeClaim.verification_status.in_(
                [VerificationStatus.UNVERIFIED.value, VerificationStatus.DISPUTED.value]
            )
        )
        .order_by(RepresentativeClaim.created_at)
        .limit(limit)
    )
    if state:
        stmt = stmt.where(Representative.state_code == state.upper())

    rows = (await session.execute(stmt)).all()
    items = []
    for claim, rep in rows:
        definition = CLAIM_FIELDS_BY_KEY.get(claim.field_key)
        if only_high_risk and not (definition and definition.requires_primary):
            continue
        if not admin.can_in_state(rep.state_code):
            continue
        items.append(
            {
                **_claim_dict(claim),
                "representative": {
                    "id": rep.id,
                    "name": rep.full_name,
                    "slug": rep.slug,
                    "state": rep.state_code,
                    "isPublished": rep.is_published,
                },
                # Surfaced because an unverified high-risk claim on a LIVE
                # profile is the urgent case, and it is invisible in a queue
                # sorted only by age.
                "isLive": rep.is_published,
                "requiresPrimarySource": bool(definition and definition.requires_primary),
            }
        )
    return {"total": len(items), "items": items}


@router.post("/admin/factcheck/claims/{claim_id}")
async def review_claim(
    claim_id: str,
    payload: ClaimReview,
    request: Request,
    admin: Principal = Depends(require_permission("factcheck.approve")),
    session: AsyncSession = Depends(get_session),
):
    allowed = {
        VerificationStatus.FACT_CHECKED.value,
        VerificationStatus.DISPUTED.value,
        VerificationStatus.RETRACTED.value,
    }
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")

    claim = (
        await session.execute(select(RepresentativeClaim).where(RepresentativeClaim.id == claim_id))
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    rep = (
        await session.execute(
            select(Representative).where(Representative.id == claim.representative_id)
        )
    ).scalar_one()
    require_state_scope(admin, rep.state_code)

    if payload.status != VerificationStatus.FACT_CHECKED.value and len(payload.note.strip()) < 10:
        # "Disputed" or "retracted" with no explanation is an insinuation, and
        # both are shown publicly.
        raise HTTPException(
            status_code=400,
            detail="Explain why this claim is disputed or retracted -- the note is shown publicly.",
        )
    if claim.submitted_by and claim.submitted_by == admin.id:
        raise HTTPException(
            status_code=400,
            detail=(
                "You entered this claim, so you cannot also verify it. Ask another Fact Checker "
                "to review it."
            ),
        )

    before = claim.verification_status
    claim.verification_status = payload.status
    claim.review_note = payload.note.strip()
    claim.reviewed_by = admin.id
    claim.reviewed_at = utcnow()

    definition = CLAIM_FIELDS_BY_KEY.get(claim.field_key)
    await audit.record(
        session,
        actor=admin,
        action="factcheck",
        entity_type="representative",
        entity_id=rep.slug,
        summary=(
            f"{definition.label if definition else claim.field_key}: {before} -> {payload.status}"
        ),
        changes={
            "verification_status": {"before": before, "after": payload.status},
            "review_note": {"before": None, "after": claim.review_note or None},
        },
        source_url=claim.source_url,
        is_public=True,
        request=request,
    )
    return _claim_dict(claim)


# --------------------------------------------------------------------------
# Admin: promises
# --------------------------------------------------------------------------
@router.get("/admin/promises")
async def admin_list_promises(
    state: Optional[str] = None,
    published: Optional[bool] = None,
    admin: Principal = Depends(require_permission("promises.edit")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Promise).order_by(Promise.created_at.desc())
    if state:
        stmt = stmt.where(Promise.state_code == state.upper())
    if published is not None:
        stmt = stmt.where(Promise.is_published.is_(published))
    rows = (await session.execute(stmt.limit(400))).scalars()
    return [{**_promise_summary(p), "isPublished": p.is_published} for p in rows]


@router.post("/admin/promises")
async def create_promise(
    payload: PromiseIn,
    request: Request,
    admin: Principal = Depends(require_permission("promises.edit")),
    session: AsyncSession = Depends(get_session),
):
    if not payload.representative_id and not payload.party_code:
        raise HTTPException(
            status_code=400,
            detail="A promise must be attached to a representative, a party, or both.",
        )

    rep = None
    if payload.representative_id:
        rep = (
            await session.execute(
                select(Representative).where(Representative.id == payload.representative_id)
            )
        ).scalar_one_or_none()
        if rep is None:
            raise HTTPException(status_code=404, detail="Representative not found")
        require_state_scope(admin, rep.state_code)

    state_code = (payload.state_code or (rep.state_code if rep else None) or "").upper() or None
    if state_code:
        require_state_scope(admin, state_code)

    citation = _citation(payload.source, require_primary=False, field_name="this promise")

    promise = Promise(
        slug=await _unique_slug(session, Promise, payload.title),
        representative_id=payload.representative_id,
        party_code=payload.party_code.upper() if payload.party_code else None,
        state_code=state_code,
        constituency_code=payload.constituency_code.upper() if payload.constituency_code else None,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        promise_text=payload.promise_text.strip(),
        promise_text_hi=payload.promise_text_hi.strip(),
        category=payload.category,
        made_on=payload.made_on,
        made_context=payload.made_context,
        deadline=payload.deadline,
        source_url=citation.url,
        source_title=citation.title,
        status="promised",
        evidence=[citation.as_dict()],
        updated_by=admin.id,
    )
    session.add(promise)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="promise",
        entity_id=promise.slug,
        summary=f"Logged promise: {promise.title}",
        changes=audit.diff(None, {"title": promise.title, "status": "promised"}),
        source_url=citation.url,
        is_public=True,
        request=request,
    )
    await search.index(
        session,
        entity_type="promise",
        entity_id=promise.slug,
        title=promise.title,
        subtitle=f"Promise - {PROMISE_STATUSES['promised']}",
        body=promise.promise_text,
        keywords=[promise.category, promise.party_code or "", state_code or ""],
        state_code=state_code,
        is_published=False,
        url_path=f"/promises/{promise.slug}",
    )
    return _promise_summary(promise)


@router.post("/admin/promises/{promise_id}/status")
async def update_promise_status(
    promise_id: str,
    payload: PromiseStatusIn,
    request: Request,
    admin: Principal = Depends(require_permission("promises.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Move a promise along its lifecycle, with evidence for the move.

    "Not delivered" and "stalled" are findings against a named person, so they
    need a PRIMARY source for the status itself -- the scheme's own progress
    report, a budget document, an RTI reply. A news article saying a promise was
    broken is a report of someone else's assessment, not the record.
    """
    if payload.status not in PROMISE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {list(PROMISE_STATUSES)}")

    promise = (
        await session.execute(select(Promise).where(Promise.id == promise_id))
    ).scalar_one_or_none()
    if promise is None:
        raise HTTPException(status_code=404, detail="Promise not found")
    if promise.state_code:
        require_state_scope(admin, promise.state_code)

    citation = _citation(
        payload.source,
        require_primary=payload.status in ADVERSE_STATUSES,
        field_name=f"the '{PROMISE_STATUSES[payload.status]}' status",
    )

    before = {"status": promise.status, "status_note": promise.status_note}
    promise.status = payload.status
    promise.status_note = payload.note.strip()
    promise.status_source_url = citation.url
    promise.status_updated_at = utcnow()
    promise.verification_status = VerificationStatus.UNVERIFIED.value
    promise.evidence = [*(promise.evidence or []), {**citation.as_dict(), "status": payload.status}]
    promise.updated_by = admin.id

    await audit.record(
        session,
        actor=admin,
        action="promise_status",
        entity_type="promise",
        entity_id=promise.slug,
        summary=(
            f"{promise.title}: {PROMISE_STATUSES.get(before['status'], before['status'])} -> "
            f"{PROMISE_STATUSES[payload.status]}"
        ),
        changes=audit.diff(before, {"status": payload.status, "status_note": promise.status_note}),
        source_url=citation.url,
        is_public=True,
        request=request,
    )
    return _promise_summary(promise)


@router.post("/admin/promises/{promise_id}/publish")
async def publish_promise(
    promise_id: str,
    request: Request,
    publish: bool = True,
    admin: Principal = Depends(require_permission("promises.publish")),
    session: AsyncSession = Depends(get_session),
):
    promise = (
        await session.execute(select(Promise).where(Promise.id == promise_id))
    ).scalar_one_or_none()
    if promise is None:
        raise HTTPException(status_code=404, detail="Promise not found")
    if promise.state_code:
        require_state_scope(admin, promise.state_code)

    if publish and promise.status in ADVERSE_STATUSES and not promise.status_source_url:
        raise HTTPException(
            status_code=400,
            detail="A promise marked as not delivered or stalled needs a source for that status before publishing.",
        )
    if promise.is_published == publish:
        raise HTTPException(status_code=400, detail="Already in that state")

    promise.is_published = publish
    if publish:
        # Publishing IS the fact-check for a promise: the permission that allows
        # it (`promises.publish`) is held by Fact Checkers and the Legal Team, so
        # a separate review step would be the same person clicking twice.
        promise.verification_status = VerificationStatus.FACT_CHECKED.value

    await audit.record(
        session,
        actor=admin,
        action="publish" if publish else "unpublish",
        entity_type="promise",
        entity_id=promise.slug,
        summary=f"{'Published' if publish else 'Unpublished'} promise: {promise.title}",
        changes={"is_published": {"before": not publish, "after": publish}},
        source_url=promise.status_source_url or promise.source_url,
        is_public=True,
        request=request,
    )
    await search.index(
        session,
        entity_type="promise",
        entity_id=promise.slug,
        title=promise.title,
        subtitle=f"Promise - {PROMISE_STATUSES.get(promise.status, promise.status)}",
        body=promise.promise_text,
        keywords=[promise.category, promise.party_code or "", promise.state_code or ""],
        state_code=promise.state_code,
        is_published=publish,
        url_path=f"/promises/{promise.slug}",
    )
    return _promise_summary(promise)
