"""State and union territory pages, and the campaign status pipeline.

This module is small on purpose -- Phase 1 fills in representatives, volunteers,
events and news per state. What it establishes now is the shape everything else
hangs off: stable state codes, the eight-stage pipeline, and a write path that
exercises the full Phase 0 stack (permission gate -> geographic scope check ->
required citation -> audited change -> public history).

If the campaign-status endpoint below works correctly, so will every scoped,
sourced, audited write added after it. That is why it exists this early.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit
from backend.core.deps import get_session, require_permission, require_state_scope
from backend.core.geography import CAMPAIGN_STAGES, CAMPAIGN_STAGE_KEYS, CAMPAIGN_STAGE_LABELS, stage_index
from backend.core.models import State, utcnow
from backend.core.rbac import Principal

router = APIRouter(tags=["states"])


class CampaignStageUpdate(BaseModel):
    stage: str
    note: str = Field(..., min_length=10)
    # Required, not optional. Moving Maharashtra to "Bill Introduced" is a
    # factual claim about the legislature; §7 says no such claim ships without
    # a link to a public record, and a field the caller may omit is a field
    # that will be omitted.
    source_url: str = Field(..., min_length=8)


def _serialise(state: State) -> dict:
    return {
        "code": state.code,
        "name": state.name,
        "nameHi": state.name_hi,
        "slug": state.slug,
        "isUnionTerritory": state.is_union_territory,
        "hasLegislature": state.has_legislature,
        "seats": {
            "lokSabha": state.lok_sabha_seats,
            "rajyaSabha": state.rajya_sabha_seats,
            "assembly": state.assembly_seats,
        },
        "isPilot": state.is_pilot,
        "campaign": {
            "stage": state.campaign_stage,
            "stageLabel": CAMPAIGN_STAGE_LABELS.get(state.campaign_stage, state.campaign_stage),
            "stageIndex": stage_index(state.campaign_stage),
            "totalStages": len(CAMPAIGN_STAGE_KEYS),
            "note": state.campaign_note,
            "sourceUrl": state.campaign_source_url,
            "updatedAt": state.campaign_updated_at.isoformat() if state.campaign_updated_at else None,
        },
        # Drives the "help us build this page" state rather than showing an
        # empty page that reads as neglect.
        "dataComplete": state.is_pilot,
    }


@router.get("/campaign-stages")
async def list_campaign_stages():
    """The pipeline definition, so the frontend renders it from one source."""
    return [
        {"key": key, "label": label, "index": idx}
        for idx, (key, label) in enumerate(CAMPAIGN_STAGES)
    ]


@router.get("/states")
async def list_states(session: AsyncSession = Depends(get_session)):
    states = (await session.execute(select(State).order_by(State.name))).scalars()
    return [_serialise(s) for s in states]


@router.get("/states/{slug}")
async def get_state(slug: str, session: AsyncSession = Depends(get_session)):
    state = (await session.execute(select(State).where(State.slug == slug))).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")
    return _serialise(state)


@router.get("/states/{slug}/history")
async def state_history(slug: str, session: AsyncSession = Depends(get_session)):
    """Public change history for a state's campaign status.

    The transparency claim in §7, made concrete: anyone can see every time this
    state's status moved, when, and on what evidence. Actor identity is omitted
    -- naming the volunteer who filed the update invites harassment and is not
    part of what transparency requires.
    """
    state = (await session.execute(select(State).where(State.slug == slug))).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")
    entries = await audit.history(session, entity_type="state", entity_id=state.code)
    return [audit.to_dict(e, include_actor=False) for e in entries]


@router.put("/admin/states/{code}/campaign")
async def update_campaign_stage(
    code: str,
    payload: CampaignStageUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("campaigns.status")),
    session: AsyncSession = Depends(get_session),
):
    if payload.stage not in CAMPAIGN_STAGE_KEYS:
        raise HTTPException(
            status_code=400, detail=f"Unknown stage. Expected one of: {CAMPAIGN_STAGE_KEYS}"
        )

    state = (await session.execute(select(State).where(State.code == code.upper()))).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")

    # A State Admin may only move their own state.
    require_state_scope(admin, state.code)

    if not state.has_legislature and stage_index(payload.stage) >= stage_index("bill_introduced"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{state.name} has no legislative assembly, so a state bill cannot be "
                "introduced or passed there. Track this under Parliament instead."
            ),
        )

    before = {
        "stage": state.campaign_stage,
        "note": state.campaign_note,
        "source_url": state.campaign_source_url,
    }
    state.campaign_stage = payload.stage
    state.campaign_note = payload.note
    state.campaign_source_url = payload.source_url
    state.campaign_updated_at = utcnow()
    after = {"stage": payload.stage, "note": payload.note, "source_url": payload.source_url}

    if before == after:
        raise HTTPException(status_code=400, detail="No changes provided")

    await audit.record(
        session,
        actor=admin,
        action="campaign_stage",
        entity_type="state",
        entity_id=state.code,
        summary=(
            f"{state.name}: {CAMPAIGN_STAGE_LABELS.get(before['stage'], before['stage'])}"
            f" -> {CAMPAIGN_STAGE_LABELS[payload.stage]}"
        ),
        changes=audit.diff(before, after),
        source_url=payload.source_url,
        is_public=True,
        request=request,
    )
    return _serialise(state)
