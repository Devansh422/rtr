"""Failed-login throttling.

Deliberately kept in Mongo even though identity now lives in Postgres. This is
high-churn, disposable counter data written on every failed attempt -- exactly
the traffic you do not want burning metered compute-hours on a free-tier Neon
instance, and exactly the shape Mongo handles cheaply. Losing the collection
entirely would cost nothing but a reset counter.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from backend.core import config
from backend.core.mongo import db


async def assert_not_locked(identifier: str) -> None:
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if not attempt or attempt.get("count", 0) < config.LOGIN_MAX_ATTEMPTS:
        return
    locked_until = attempt.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")


async def record_failure(identifier: str) -> None:
    until = datetime.now(timezone.utc) + timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"locked_until": until.isoformat()}},
        upsert=True,
    )


async def clear(identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})
