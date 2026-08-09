"""Password hashing, token minting and the shared small utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import re
import secrets
import uuid

import bcrypt
import jwt

from backend.core import config


# ---------- Hashing ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_ip(ip: Optional[str]) -> Optional[str]:
    """One-way hash of a client IP for the audit log.

    Storing raw IPs of staff members would be personal data under the DPDP Act
    with no operational upside -- a salted digest still answers "were these two
    edits made from the same place" without retaining the address itself. The
    JWT secret doubles as the salt so it is never committed anywhere.
    """
    if not ip:
        return None
    return hashlib.sha256(f"{config.JWT_SECRET}:{ip}".encode("utf-8")).hexdigest()


# ---------- Tokens ----------
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.ADMIN_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_member_token(email: str) -> str:
    """
    Member (supporter/volunteer) sessions are scoped by email only, not by
    "which role logged in" -- someone who is both a supporter and a volunteer
    should see both dashboards regardless of which record's code they typed.
    """
    payload = {
        "sub": email,
        "email": email,
        "type": "member",
        "exp": datetime.now(timezone.utc) + timedelta(days=config.MEMBER_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError for the caller."""
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])


# ---------- Small shared helpers ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or uuid.uuid4().hex[:8]


def generate_access_code() -> str:
    """
    An 8-character login credential for supporters/volunteers, formatted
    XXXX-XXXX for readability. Alphabet excludes 0/O and 1/I, which are the
    pair most often misread when someone is typing a code back in from a
    screen rather than pasting it.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"
