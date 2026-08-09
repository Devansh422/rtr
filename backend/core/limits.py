"""Rate limits for citizen-facing writes.

Same reasoning as modules/auth/throttle.py, generalised: these are high-churn,
disposable counters written on every attempt. Putting them in Mongo keeps them
off a metered Neon instance, and losing the collection costs nothing but a reset
window.

Why this exists at all: the moment the platform accepts forum posts, petition
signatures, citizen reports and correction suggestions from the public, it has
an abuse surface that no amount of moderation policy addresses -- a script can
file ten thousand reports faster than eleven volunteer moderators can read one.
The limits below are per-identity and generous for a human, hostile to a loop.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from fastapi import HTTPException

from backend.core.mongo import db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limit:
    """`count` actions per `window_minutes`, and what to call the action."""

    action: str
    count: int
    window_minutes: int
    label: str


# Tuned to what an engaged citizen does in an afternoon, not to what is
# theoretically safe. A limit that a real contributor hits is a limit that gets
# raised in a hurry, so these are set where genuine use never reaches them.
LIMITS: dict[str, Limit] = {
    "forum.thread": Limit("forum.thread", 5, 60, "new discussions"),
    "forum.reply": Limit("forum.reply", 30, 60, "replies"),
    "forum.vote": Limit("forum.vote", 200, 60, "votes"),
    "report.create": Limit("report.create", 5, 180, "citizen reports"),
    "petition.create": Limit("petition.create", 3, 1440, "petitions"),
    "petition.sign": Limit("petition.sign", 40, 60, "signatures"),
    "correction.suggest": Limit("correction.suggest", 10, 180, "correction suggestions"),
    "ai.ask": Limit("ai.ask", 20, 60, "assistant questions"),
    "tools.generate": Limit("tools.generate", 20, 60, "document drafts"),
    "event.register": Limit("event.register", 15, 1440, "event registrations"),
    "quiz.attempt": Limit("quiz.attempt", 30, 1440, "quiz attempts"),
}


def _key(action: str, identity: str) -> str:
    return f"{action}:{identity}"


async def check(action: str, identity: str, *, raise_on_limit: bool = True) -> bool:
    """Consume one unit of `action` for `identity`.

    A fixed window rather than a true sliding one: it needs a single indexed
    upsert instead of a per-event document, which is the difference between a
    rate limiter that costs nothing and one that becomes the largest collection
    in the database.

    Fails OPEN. If Mongo is unreachable, a citizen filing a report is not the
    thing to break -- and an attacker who can take Mongo down does not need to
    bother with the rate limiter.
    """
    limit = LIMITS.get(action)
    if limit is None:
        return True

    now = datetime.now(timezone.utc)
    key = _key(action, identity)

    try:
        doc = await db.rate_limits.find_one({"_id": key})
        window_start = (
            datetime.fromisoformat(doc["window_start"]) if doc and doc.get("window_start") else None
        )

        if window_start is None or now - window_start > timedelta(minutes=limit.window_minutes):
            await db.rate_limits.update_one(
                {"_id": key},
                {"$set": {"window_start": now.isoformat(), "count": 1}},
                upsert=True,
            )
            return True

        if doc.get("count", 0) >= limit.count:
            retry_after = int(
                (window_start + timedelta(minutes=limit.window_minutes) - now).total_seconds()
            )
            if raise_on_limit:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"You have reached the limit of {limit.count} {limit.label} "
                        f"in {limit.window_minutes} minutes. Try again in "
                        f"{max(1, retry_after // 60)} minute(s)."
                    ),
                    headers={"Retry-After": str(max(1, retry_after))},
                )
            return False

        await db.rate_limits.update_one({"_id": key}, {"$inc": {"count": 1}})
        return True
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rate limit check failed for %s, allowing: %s", key, e)
        return True


async def reset(action: str, identity: str) -> None:
    """Clear one counter. Used when an action is undone (an unvote, a withdrawn
    signature) so a citizen is not charged for a mistake they corrected."""
    try:
        await db.rate_limits.delete_one({"_id": _key(action, identity)})
    except Exception:
        pass


def identity_for(request, *, email: Optional[str] = None) -> str:
    """Who to count against.

    A signed-in member is counted by email, which survives IP changes and mobile
    networks. Anonymous callers fall back to the client IP -- weaker, since it is
    shared behind carrier NAT, but the anonymous endpoints are read-mostly and
    the alternative is not limiting them at all.
    """
    if email:
        return f"m:{email.lower()}"
    client = getattr(request, "client", None)
    return f"ip:{client.host if client else 'unknown'}"
