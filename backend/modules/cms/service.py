"""Content read helpers shared by the public and admin CMS routes."""

from fastapi import HTTPException

from backend.core.mongo import content_coll, db
from backend.core.permissions import CONTENT_TYPES, SORTED_BY_DATE


def assert_known_type(ctype: str) -> None:
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")


async def list_content(ctype: str) -> list[dict]:
    assert_known_type(ctype)
    cursor = content_coll(ctype).find({}, {"_id": 0})
    if ctype in SORTED_BY_DATE:
        cursor = cursor.sort("date", -1)
    return await cursor.to_list(1000)


async def get_live_supporter_counts() -> dict:
    """Maps campaign_id -> real signup count, for campaigns with at least one."""
    counts: dict[str, int] = {}
    cursor = db.supporters.aggregate(
        [
            {"$match": {"campaign_id": {"$ne": None}}},
            {"$group": {"_id": "$campaign_id", "count": {"$sum": 1}}},
        ]
    )
    async for row in cursor:
        counts[row["_id"]] = row["count"]
    return counts


async def with_live_supporter_counts(campaigns: list) -> list:
    """
    Adds `liveSupporters` to each campaign dict: the admin-set `supporters` field
    (a baseline) plus real /join signups attributed to that campaign. This is
    additive on top of the admin's number rather than a replacement, so an
    admin's editorial baseline (e.g. offline signatures) isn't wiped out by a
    fresh deploy with zero online signups yet.

    Deliberately only called from the PUBLIC content route, not the admin list --
    the admin CMS edits the baseline and should never round-trip a computed
    value back into storage as if it were real data.
    """
    counts = await get_live_supporter_counts()
    for c in campaigns:
        try:
            baseline = int(c.get("supporters") or 0)
        except (TypeError, ValueError):
            baseline = 0
        c["liveSupporters"] = baseline + counts.get(c.get("id"), 0)
    return campaigns
