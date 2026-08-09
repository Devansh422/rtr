"""Supporter and volunteer dashboards.

Members are citizens who joined the movement, not staff. They authenticate with
an access code, hold no permissions, and their records stay in Mongo -- there is
nothing relational about them yet. That changes if and when the Forum gives
every citizen an account (Phase 3), at which point member identity earns its own
table rather than being bolted onto the staff `users` one.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.core.deps import get_current_member
from backend.core.mongo import content_coll, db
from backend.core.security import now_iso
from backend.core.models import new_id

router = APIRouter(tags=["members"])


def supporter_badge(referral_count: int) -> str:
    if referral_count >= 20:
        return "Gold Advocate"
    if referral_count >= 5:
        return "Silver Advocate"
    if referral_count >= 1:
        return "Bronze Advocate"
    return "Supporter"


def volunteer_badge(completed_count: int) -> str:
    if completed_count >= 15:
        return "Gold Contributor"
    if completed_count >= 5:
        return "Silver Contributor"
    if completed_count >= 1:
        return "Bronze Contributor"
    return "Volunteer"


async def _require_volunteer(email: str) -> dict:
    volunteer = await db.volunteers.find_one({"email": email})
    if not volunteer:
        raise HTTPException(status_code=403, detail="This account has no volunteer profile")
    return volunteer


@router.get("/me")
async def get_my_profile(member: dict = Depends(get_current_member)):
    email = member["email"]
    supporter = await db.supporters.find_one({"email": email}, {"_id": 0, "access_code_hash": 0})
    volunteer = await db.volunteers.find_one({"email": email}, {"_id": 0, "access_code_hash": 0})
    if not supporter and not volunteer:
        raise HTTPException(status_code=404, detail="Profile not found")

    result = {"email": email}
    if supporter:
        referral_count = await db.supporters.count_documents({"referred_by": supporter.get("movement_id")})
        supporter["referralCount"] = referral_count
        supporter["badge"] = supporter_badge(referral_count)
        result["supporter"] = supporter
    if volunteer:
        completed_count = await db.volunteer_contributions.count_documents({"volunteer_id": volunteer["id"]})
        volunteer["completedCount"] = completed_count
        volunteer["badge"] = volunteer_badge(completed_count)
        result["volunteer"] = volunteer
    return result


@router.get("/me/opportunities")
async def list_my_opportunities(member: dict = Depends(get_current_member)):
    volunteer = await _require_volunteer(member["email"])
    opportunities = await content_coll("opportunities").find({}, {"_id": 0}).to_list(500)
    done_ids = set(
        await db.volunteer_contributions.distinct("opportunity_id", {"volunteer_id": volunteer["id"]})
    )
    for o in opportunities:
        o["completed"] = o.get("id") in done_ids
    return opportunities


@router.post("/me/opportunities/{opportunity_id}/complete")
async def complete_opportunity(opportunity_id: str, member: dict = Depends(get_current_member)):
    volunteer = await _require_volunteer(member["email"])
    if not await content_coll("opportunities").find_one({"id": opportunity_id}):
        raise HTTPException(status_code=404, detail="Opportunity not found")

    existing = await db.volunteer_contributions.find_one(
        {"volunteer_id": volunteer["id"], "opportunity_id": opportunity_id}
    )
    if not existing:
        await db.volunteer_contributions.insert_one(
            {
                "id": new_id(),
                "volunteer_id": volunteer["id"],
                "opportunity_id": opportunity_id,
                "created_at": now_iso(),
            }
        )
    return {"ok": True}


@router.delete("/me/opportunities/{opportunity_id}/complete")
async def uncomplete_opportunity(opportunity_id: str, member: dict = Depends(get_current_member)):
    volunteer = await _require_volunteer(member["email"])
    await db.volunteer_contributions.delete_one(
        {"volunteer_id": volunteer["id"], "opportunity_id": opportunity_id}
    )
    return {"ok": True}
