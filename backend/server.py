from pathlib import Path

ROOT_DIR = Path(__file__).parent

# python-dotenv is a local-development convenience only: it loads variables from
# backend/.env into os.environ before mongo_url etc. are read below. In every
# deployed environment (Vercel included) the platform injects environment
# variables directly, there is no .env file in the bundle, and load_dotenv()
# would be a no-op even if it ran. Importing it defensively means a dependency
# resolution quirk that drops this dev-only package can never crash the app.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / '.env')
except ImportError:
    pass

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Body, UploadFile, File, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
import os
import re
import json
import base64
import logging
import secrets
import uuid
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta

CONTENT_DIR = ROOT_DIR / "content"

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Right to Recall Movement API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
MAX_UPLOAD = 6 * 1024 * 1024  # 6 MB
# "opportunities" is admin-managed content (like blogs/campaigns) that powers
# the volunteer dashboard's task board -- it reuses the generic content CRUD
# below rather than a bespoke endpoint.
CONTENT_TYPES = ["campaigns", "blogs", "news", "faq", "testimonials", "resources", "leaders", "jurisdictions", "myths", "opportunities"]
SORTED_BY_DATE = {"blogs", "news"}

# ---------- Admin RBAC ----------
# One permission per content type (editing blogs doesn't imply editing
# campaigns) plus three cross-cutting ones. A new admin user gets an explicit
# list of these; the bootstrap admin (see seed_admin) gets none stored at all,
# which has a specific meaning -- see has_permission.
ALL_PERMISSIONS = [f"content.{t}" for t in CONTENT_TYPES] + ["submissions.view", "analytics.view", "users.manage"]


def has_permission(user: dict, key: str) -> bool:
    """
    A `permissions` field absent entirely (None) means this account predates
    RBAC -- the original bootstrap admin -- and is treated as full access so
    shipping this feature can never lock out an already-deployed admin. Users
    created after RBAC exists always have an explicit list, even if empty.
    """
    perms = user.get("permissions")
    if perms is None:
        return True
    return key in perms


def require_permission(key: str):
    """
    A Depends() factory for permission keys that are fixed per-route (e.g.
    "submissions.view"). Content CRUD checks permission inline instead, since
    its key depends on the :ctype path parameter and can't be fixed at
    decoration time. Safe to reference get_current_admin here even though it's
    defined later in this file: the inner `checker` closure only resolves that
    name when FastAPI actually calls it per-request, by which point the whole
    module has finished loading.
    """
    async def checker(admin: dict = Depends(get_current_admin)) -> dict:
        if not has_permission(admin, key):
            raise HTTPException(status_code=403, detail="Your account does not have this permission")
        return admin
    return checker


# ---------- Helpers ----------
def load_content(name: str):
    path = CONTENT_DIR / f"{name}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return s[:60] or uuid.uuid4().hex[:8]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


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


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_member_token(email: str) -> str:
    """
    Member (supporter/volunteer) sessions are scoped by email only, not by
    "which role logged in" -- someone who is both a supporter and a volunteer
    should see both dashboards regardless of which record's code they typed.
    get_my_profile looks up both collections by this email.
    """
    payload = {
        "sub": email,
        "email": email,
        "type": "member",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def content_coll(ctype: str):
    return db[f"content_{ctype}"]


async def get_current_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth[7:]
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload.get("sub")})
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Not authorized")
        if user.get("active") is False:
            raise HTTPException(status_code=401, detail="This account has been deactivated")
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_member(request: Request) -> dict:
    """Auth for the supporter/volunteer dashboards -- a separate token type
    from admin sessions, so a member token can never be replayed against an
    admin-only endpoint or vice versa."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth[7:]
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "member":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return {"email": payload["email"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def list_content(ctype: str):
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")
    cursor = content_coll(ctype).find({}, {"_id": 0})
    if ctype in SORTED_BY_DATE:
        cursor = cursor.sort("date", -1)
    return await cursor.to_list(1000)


async def get_live_supporter_counts() -> dict:
    """Maps campaign_id -> real signup count, for campaigns with at least one."""
    counts = {}
    cursor = db.supporters.aggregate([
        {"$match": {"campaign_id": {"$ne": None}}},
        {"$group": {"_id": "$campaign_id", "count": {"$sum": 1}}},
    ])
    async for row in cursor:
        counts[row["_id"]] = row["count"]
    return counts


async def with_live_supporter_counts(campaigns: list) -> list:
    """
    Adds `liveSupporters` to each campaign dict: the admin-set `supporters` field
    (a baseline) plus real /join signups attributed to that campaign. This is
    additive on top of the admin's number rather than a replacement, so an
    admin's editorial baseline (e.g. offline signatures, momentum framing) isn't
    wiped out by a fresh deploy with zero online signups yet.

    Deliberately only called from the PUBLIC content route, not admin_list --
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


# ---------- Models ----------
class VolunteerCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: str = Field(..., min_length=6)
    state: str
    profession: str
    reason: str = Field(..., min_length=5)


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    subject: str = Field(..., min_length=2)
    message: str = Field(..., min_length=5)


class NewsletterCreate(BaseModel):
    email: EmailStr


class SupporterCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    state: str = Field(..., min_length=2)
    city: Optional[str] = None
    mobile: Optional[str] = None
    pledge: bool = True
    # Which campaign's "join" CTA the supporter came through, if any (the generic
    # navbar/footer "Join Movement" action leaves this unset). Recorded once at
    # signup; scope decision: a supporter is one record keyed by email, so a
    # returning supporter clicking a DIFFERENT campaign's CTA is not
    # re-attributed -- see the "already exists" branch in join_movement. Multi-
    # campaign attribution would need a separate join table, which isn't
    # justified for four campaigns.
    campaign_id: Optional[str] = None
    # movement_id of the supporter who referred this signup, if they arrived via
    # a personal referral link (/join?ref=<movement_id>) rather than a generic
    # or campaign CTA. Powers the referral count shown on the referrer's own
    # supporter dashboard.
    referred_by: Optional[str] = None


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class MemberLoginPayload(BaseModel):
    email: EmailStr
    code: str


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    permissions: List[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)


class PageviewCreate(BaseModel):
    path: str = Field(..., max_length=200)
    referrer_path: Optional[str] = Field(default=None, max_length=200)
    session_id: str = Field(..., max_length=64)


# ---------- Auth routes ----------
@api_router.post("/auth/login")
async def login(payload: LoginPayload):
    email = payload.email.lower()
    identifier = f"login:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 10:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.get("active") is False:
        raise HTTPException(status_code=401, detail="This account has been deactivated")

    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(user["id"], user["email"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "name": user.get("name"), "role": user.get("role")},
    }


@api_router.get("/auth/me")
async def auth_me(admin: dict = Depends(get_current_admin)):
    # permissions: None signals "legacy full access" to the frontend, exactly
    # like has_permission's server-side interpretation -- see that function.
    return {
        "id": admin["id"],
        "email": admin["email"],
        "name": admin.get("name"),
        "role": admin.get("role"),
        "permissions": admin.get("permissions"),
    }


# ---------- Member auth (supporters / volunteers) ----------
@api_router.post("/auth/member-login")
async def member_login(payload: MemberLoginPayload):
    email = payload.email.lower()
    code = payload.code.strip().upper()
    identifier = f"member-login:{email}"

    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 10:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")

    supporter = await db.supporters.find_one({"email": email})
    volunteer = await db.volunteers.find_one({"email": email})

    ok = (
        (supporter is not None and verify_password(code, supporter.get("access_code_hash") or ""))
        or (volunteer is not None and verify_password(code, volunteer.get("access_code_hash") or ""))
    )

    if not ok:
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or access code")

    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_member_token(email)
    roles = [role for role, present in (("supporter", supporter), ("volunteer", volunteer)) if present]
    return {"access_token": token, "token_type": "bearer", "roles": roles}


@api_router.get("/me")
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


@api_router.get("/me/opportunities")
async def list_my_opportunities(member: dict = Depends(get_current_member)):
    volunteer = await db.volunteers.find_one({"email": member["email"]})
    if not volunteer:
        raise HTTPException(status_code=403, detail="This account has no volunteer profile")

    opportunities = await content_coll("opportunities").find({}, {"_id": 0}).to_list(500)
    done_ids = set(
        await db.volunteer_contributions.distinct("opportunity_id", {"volunteer_id": volunteer["id"]})
    )
    for o in opportunities:
        o["completed"] = o.get("id") in done_ids
    return opportunities


@api_router.post("/me/opportunities/{opportunity_id}/complete")
async def complete_opportunity(opportunity_id: str, member: dict = Depends(get_current_member)):
    volunteer = await db.volunteers.find_one({"email": member["email"]})
    if not volunteer:
        raise HTTPException(status_code=403, detail="This account has no volunteer profile")
    if not await content_coll("opportunities").find_one({"id": opportunity_id}):
        raise HTTPException(status_code=404, detail="Opportunity not found")

    existing = await db.volunteer_contributions.find_one(
        {"volunteer_id": volunteer["id"], "opportunity_id": opportunity_id}
    )
    if not existing:
        await db.volunteer_contributions.insert_one({
            "id": str(uuid.uuid4()),
            "volunteer_id": volunteer["id"],
            "opportunity_id": opportunity_id,
            "created_at": now_iso(),
        })
    return {"ok": True}


@api_router.delete("/me/opportunities/{opportunity_id}/complete")
async def uncomplete_opportunity(opportunity_id: str, member: dict = Depends(get_current_member)):
    volunteer = await db.volunteers.find_one({"email": member["email"]})
    if not volunteer:
        raise HTTPException(status_code=403, detail="This account has no volunteer profile")
    await db.volunteer_contributions.delete_one(
        {"volunteer_id": volunteer["id"], "opportunity_id": opportunity_id}
    )
    return {"ok": True}


# ---------- Admin user management ----------
@api_router.get("/admin/users")
async def list_admin_users(admin: dict = Depends(require_permission("users.manage"))):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(500)


@api_router.post("/admin/users")
async def create_admin_user(payload: AdminUserCreate, admin: dict = Depends(require_permission("users.manage"))):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    invalid = [p for p in payload.permissions if p not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown permissions: {invalid}")

    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": "admin",
        "permissions": payload.permissions,
        "active": True,
        "created_at": now_iso(),
        "created_by": admin["id"],
    }
    await db.users.insert_one(dict(doc))
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


@api_router.put("/admin/users/{user_id}")
async def update_admin_user(
    user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_permission("users.manage"))
):
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.permissions is not None:
        invalid = [p for p in payload.permissions if p not in ALL_PERMISSIONS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unknown permissions: {invalid}")
        updates["permissions"] = payload.permissions
    if payload.active is not None:
        if user_id == admin["id"] and not payload.active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        updates["active"] = payload.active
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)
    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    res = await db.users.update_one({"id": user_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@api_router.delete("/admin/users/{user_id}")
async def delete_admin_user(user_id: str, admin: dict = Depends(require_permission("users.manage"))):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


# ---------- Pageview tracking + analytics ----------
@api_router.post("/track/pageview")
async def track_pageview(payload: PageviewCreate):
    # Public and fire-and-forget from the frontend: a transient DB hiccup here
    # must never surface as an error to the visitor or break navigation.
    try:
        await db.pageviews.insert_one({
            "id": str(uuid.uuid4()),
            "path": payload.path,
            "referrer_path": payload.referrer_path,
            "session_id": payload.session_id,
            "created_at": now_iso(),
        })
    except Exception as e:
        logger.warning(f"track_pageview failed: {e}")
    return {"ok": True}


@api_router.get("/admin/analytics/pageviews")
async def analytics_pageviews(days: int = 30, admin: dict = Depends(require_permission("analytics.view"))):
    days = max(1, min(days, 365))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    total = await db.pageviews.count_documents({"created_at": {"$gte": since}})
    unique_sessions = len(await db.pageviews.distinct("session_id", {"created_at": {"$gte": since}}))

    top_pages = [
        {"path": row["_id"], "views": row["views"]}
        async for row in db.pageviews.aggregate([
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$path", "views": {"$sum": 1}}},
            {"$sort": {"views": -1}},
            {"$limit": 10},
        ])
    ]

    top_flows = [
        {"from": row["_id"]["from"], "to": row["_id"]["to"], "count": row["count"]}
        async for row in db.pageviews.aggregate([
            {"$match": {"created_at": {"$gte": since}, "referrer_path": {"$ne": None}}},
            {"$group": {"_id": {"from": "$referrer_path", "to": "$path"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 15},
        ])
    ]

    return {
        "days": days,
        "total": total,
        "uniqueSessions": unique_sessions,
        "topPages": top_pages,
        "topFlows": top_flows,
    }


# ---------- Public content routes ----------
@api_router.get("/")
async def root():
    return {"message": "Right to Recall Movement API", "status": "ok"}


@api_router.get("/content/blogs/{blog_id}")
async def get_blog(blog_id: str):
    doc = await content_coll("blogs").find_one({"id": blog_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Blog not found")
    return doc


@api_router.get("/content/{ctype}")
async def get_content(ctype: str):
    items = await list_content(ctype)
    if ctype == "campaigns":
        items = await with_live_supporter_counts(items)
    return items


@api_router.get("/stats")
async def get_stats():
    return {
        "supporters": await db.supporters.count_documents({}),
        "volunteers": await db.volunteers.count_documents({}),
        "campaigns": await content_coll("campaigns").count_documents({}),
    }


# ---------- Admin content CRUD ----------
# Permission is checked inline (not via a Depends() factory) because the
# required key -- content.<ctype> -- depends on the :ctype path parameter,
# which isn't known until the request arrives; require_permission's fixed-key
# Depends() form can't express that.
@api_router.get("/admin/content/{ctype}")
async def admin_list(ctype: str, admin: dict = Depends(get_current_admin)):
    if not has_permission(admin, f"content.{ctype}"):
        raise HTTPException(status_code=403, detail="Your account does not have this permission")
    return await list_content(ctype)


@api_router.post("/admin/content/{ctype}")
async def admin_create(ctype: str, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")
    if not has_permission(admin, f"content.{ctype}"):
        raise HTTPException(status_code=403, detail="Your account does not have this permission")
    payload.pop("_id", None)
    if not payload.get("id"):
        base = payload.get("title") or payload.get("question") or payload.get("place") or payload.get("name") or payload.get("myth")
        payload["id"] = slugify(base)
    if await content_coll(ctype).find_one({"id": payload["id"]}):
        payload["id"] = f'{payload["id"]}-{uuid.uuid4().hex[:4]}'
    if ctype in SORTED_BY_DATE and not payload.get("date"):
        payload["date"] = datetime.now(timezone.utc).date().isoformat()
    payload["created_at"] = now_iso()
    await content_coll(ctype).insert_one(payload)
    payload.pop("_id", None)
    return payload


@api_router.put("/admin/content/{ctype}/{item_id}")
async def admin_update(ctype: str, item_id: str, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")
    if not has_permission(admin, f"content.{ctype}"):
        raise HTTPException(status_code=403, detail="Your account does not have this permission")
    payload.pop("_id", None)
    payload.pop("id", None)
    res = await content_coll(ctype).update_one({"id": item_id}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return await content_coll(ctype).find_one({"id": item_id}, {"_id": 0})


@api_router.delete("/admin/content/{ctype}/{item_id}")
async def admin_delete(ctype: str, item_id: str, admin: dict = Depends(get_current_admin)):
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")
    if not has_permission(admin, f"content.{ctype}"):
        raise HTTPException(status_code=403, detail="Your account does not have this permission")
    res = await content_coll(ctype).delete_one({"id": item_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ---------- Uploads ----------
@api_router.post("/admin/uploads")
async def admin_upload(file: UploadFile = File(...), admin: dict = Depends(get_current_admin)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File too large (max 6MB)")
    uid = uuid.uuid4().hex
    await db.uploads.insert_one({
        "id": uid,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "data": base64.b64encode(data).decode("utf-8"),
        "created_at": now_iso(),
    })
    return {"id": uid, "filename": file.filename, "url": f"/api/uploads/{uid}"}


@api_router.get("/uploads/{uid}")
async def get_upload(uid: str):
    doc = await db.uploads.find_one({"id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=base64.b64decode(doc["data"]), media_type=doc["content_type"])


# ---------- Admin submissions (read-only) ----------
@api_router.get("/admin/submissions/{kind}")
async def admin_submissions(kind: str, admin: dict = Depends(require_permission("submissions.view"))):
    coll_map = {"volunteers": db.volunteers, "contacts": db.contacts, "supporters": db.supporters, "newsletter": db.newsletter}
    if kind not in coll_map:
        raise HTTPException(status_code=404, detail="Unknown kind")
    # access_code_hash is a bcrypt hash, not a plaintext secret, but there is no
    # reason for it to ever leave the database -- excluding it here means a
    # future frontend change can't accidentally render or log it.
    return await coll_map[kind].find({}, {"_id": 0, "access_code_hash": 0}).sort("created_at", -1).to_list(2000)


# ---------- Submission routes ----------
@api_router.post("/volunteers")
async def create_volunteer(payload: VolunteerCreate):
    email = payload.email.lower()
    existing = await db.volunteers.find_one({"email": email})
    if existing:
        # Dedupe by email, same shape as join_movement: a volunteer dashboard
        # login is keyed by email, so there can only be one record per address.
        # No new access code here -- the original signup's code still works.
        return {
            "message": "You're already registered as a volunteer!",
            "already": True,
            "volunteer_id": existing.get("volunteer_id"),
            "name": existing.get("name"),
            "created_at": existing.get("created_at"),
        }

    volunteer_id = f"RTR-VOL-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"
    access_code = generate_access_code()
    created_at = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "volunteer_id": volunteer_id,
        **payload.model_dump(exclude={"email"}),
        "email": email,
        "access_code_hash": hash_password(access_code),
        "created_at": created_at,
    }
    await db.volunteers.insert_one(dict(doc))
    logger.info(f"New volunteer: {email} ({volunteer_id})")
    return {
        "message": "You're in! Welcome to the movement.",
        "already": False,
        "volunteer_id": volunteer_id,
        "name": payload.name,
        "created_at": created_at,
        # Plaintext exists only in this one response -- only the bcrypt hash is
        # ever stored. The frontend must show this once and never re-fetch it.
        "access_code": access_code,
    }


@api_router.post("/contact")
async def create_contact(payload: ContactCreate):
    doc = {"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": now_iso()}
    await db.contacts.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info(f"New contact message from: {payload.email}")
    return doc


@api_router.post("/newsletter")
async def subscribe_newsletter(payload: NewsletterCreate):
    existing = await db.newsletter.find_one({"email": payload.email})
    if existing:
        return {"message": "You are already subscribed!", "already": True}
    await db.newsletter.insert_one({"id": str(uuid.uuid4()), "email": payload.email, "created_at": now_iso()})
    return {"message": "Subscribed! Welcome to the movement.", "already": False}


@api_router.post("/supporters")
async def join_movement(payload: SupporterCreate):
    # Lowercased for storage so it matches how member_login looks emails up
    # (also lowercased) -- previously this endpoint stored whatever case the
    # visitor typed, which would have silently broken dashboard login for any
    # supporter whose email wasn't already all-lowercase.
    email = payload.email.lower()
    existing = await db.supporters.find_one({"email": email})
    if existing:
        # No new access code on a repeat join -- their original one still
        # works, and reissuing here would silently invalidate it.
        return {
            "message": "You're already part of the movement!",
            "already": True,
            "movement_id": existing.get("movement_id"),
            "name": existing.get("name"),
            "created_at": existing.get("created_at"),
        }
    movement_id = f"RTR-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"
    access_code = generate_access_code()
    created_at = now_iso()
    await db.supporters.insert_one({
        "id": str(uuid.uuid4()),
        "movement_id": movement_id,
        "name": payload.name,
        "email": email,
        "state": payload.state,
        "city": payload.city,
        "mobile": payload.mobile,
        "pledge": payload.pledge,
        "campaign_id": payload.campaign_id,
        "referred_by": payload.referred_by,
        "access_code_hash": hash_password(access_code),
        "created_at": created_at,
    })
    if not await db.newsletter.find_one({"email": email}):
        await db.newsletter.insert_one({"id": str(uuid.uuid4()), "email": email, "source": "supporter", "created_at": created_at})
    logger.info(f"New supporter: {email} ({movement_id})")
    return {
        "message": "You're in! Welcome to the movement.",
        "already": False,
        "movement_id": movement_id,
        "name": payload.name,
        "created_at": created_at,
        # Plaintext exists only in this one response -- only the bcrypt hash is
        # ever stored. The frontend must show this once and never re-fetch it.
        "access_code": access_code,
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Startup seeding ----------
# Serverless note: on Vercel this app is a serverless function, so these startup
# hooks run on EVERY cold start, and several cold starts can happen concurrently
# (e.g. a burst of traffic after a deploy). Everything below must therefore be
# idempotent and tolerant of another instance doing the same work at the same
# time: writes are atomic upserts, and duplicate-key errors are treated as "the
# other instance already did it" rather than as failures.
async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    try:
        # $setOnInsert + upsert is a single atomic operation, so two concurrent
        # cold starts cannot both create the admin user.
        result = await db.users.update_one(
            {"email": email},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "password_hash": hash_password(password),
                "name": "Admin",
                "role": "admin",
                "created_at": now_iso(),
            }},
            upsert=True,
        )
        if result.upserted_id is not None:
            logger.info(f"Seeded admin user: {email}")
            return
    except DuplicateKeyError:
        # Another cold start inserted the user between our filter and the write.
        pass

    existing = await db.users.find_one({"email": email})
    if existing and not verify_password(password, existing.get("password_hash") or ""):
        # ADMIN_PASSWORD stays the source of truth: rewriting the hash here is the
        # documented way to reset the admin password. Safe under concurrency because
        # every instance writes a valid hash of the same password, so whichever
        # write lands last still leaves the account usable.
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
        logger.info(f"Updated admin password: {email}")


async def seed_content():
    for ctype in CONTENT_TYPES:
        coll = content_coll(ctype)
        if await coll.count_documents({}) != 0:
            continue
        items = load_content(ctype)
        if not items:
            continue
        # Deterministic _id per seeded item makes the insert idempotent: if two
        # cold starts race, the loser's writes are rejected as duplicate keys
        # instead of creating a second copy of the seed data. ordered=False lets
        # the non-conflicting documents through. _id is never exposed by the API
        # (every read projects it away).
        docs = []
        for idx, it in enumerate(items):
            doc = dict(it)
            doc["_id"] = f"seed:{ctype}:{doc.get('id') or idx}"
            docs.append(doc)
        try:
            await coll.insert_many(docs, ordered=False)
            logger.info(f"Seeded content_{ctype} with {len(docs)} items")
        except BulkWriteError as e:
            non_duplicate = [err for err in e.details.get("writeErrors", []) if err.get("code") != 11000]
            if non_duplicate:
                logger.warning(f"seed content_{ctype}: {non_duplicate}")
            else:
                logger.info(f"content_{ctype} already seeded by another instance")
        except DuplicateKeyError:
            logger.info(f"content_{ctype} already seeded by another instance")


@app.on_event("startup")
async def on_startup():
    try:
        await db.users.create_index("email", unique=True)
    except (DuplicateKeyError, OperationFailure) as e:
        # Pre-existing duplicate emails, or a concurrent create_index from another
        # cold start. The app still works without the index, so only log it.
        logger.warning(f"users index: {e}")
    except Exception as e:
        # e.g. the database is briefly unreachable on this cold start.
        logger.warning(f"users index skipped: {e}")
    # Seeding must never take the whole function down on a cold start: a transient
    # database error here would otherwise turn every request into a 500.
    try:
        await seed_admin()
    except Exception as e:
        logger.warning(f"seed_admin: {e}")
    try:
        await seed_content()
    except Exception as e:
        logger.warning(f"seed_content: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
