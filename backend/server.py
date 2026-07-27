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
CONTENT_TYPES = ["campaigns", "blogs", "news", "faq", "testimonials", "resources", "leaders", "jurisdictions", "myths"]
SORTED_BY_DATE = {"blogs", "news"}


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
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
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


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


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

    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(user["id"], user["email"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "name": user.get("name"), "role": user.get("role")},
    }


@api_router.get("/auth/me")
async def auth_me(admin: dict = Depends(get_current_admin)):
    return {"email": admin["email"], "name": admin.get("name"), "role": admin.get("role")}


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
    return await list_content(ctype)


@api_router.get("/stats")
async def get_stats():
    return {
        "supporters": await db.supporters.count_documents({}),
        "volunteers": await db.volunteers.count_documents({}),
        "campaigns": await content_coll("campaigns").count_documents({}),
    }


# ---------- Admin content CRUD ----------
@api_router.get("/admin/content/{ctype}")
async def admin_list(ctype: str, admin: dict = Depends(get_current_admin)):
    return await list_content(ctype)


@api_router.post("/admin/content/{ctype}")
async def admin_create(ctype: str, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    if ctype not in CONTENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown content type")
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
async def admin_submissions(kind: str, admin: dict = Depends(get_current_admin)):
    coll_map = {"volunteers": db.volunteers, "contacts": db.contacts, "supporters": db.supporters, "newsletter": db.newsletter}
    if kind not in coll_map:
        raise HTTPException(status_code=404, detail="Unknown kind")
    return await coll_map[kind].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


# ---------- Submission routes ----------
@api_router.post("/volunteers")
async def create_volunteer(payload: VolunteerCreate):
    doc = {"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": now_iso()}
    await db.volunteers.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info(f"New volunteer: {payload.email}")
    return doc


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
    existing = await db.supporters.find_one({"email": payload.email})
    if existing:
        return {
            "message": "You're already part of the movement!",
            "already": True,
            "movement_id": existing.get("movement_id"),
            "name": existing.get("name"),
            "created_at": existing.get("created_at"),
        }
    movement_id = f"RTR-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"
    created_at = now_iso()
    await db.supporters.insert_one({
        "id": str(uuid.uuid4()),
        "movement_id": movement_id,
        "name": payload.name,
        "email": payload.email,
        "state": payload.state,
        "city": payload.city,
        "mobile": payload.mobile,
        "pledge": payload.pledge,
        "created_at": created_at,
    })
    if not await db.newsletter.find_one({"email": payload.email}):
        await db.newsletter.insert_one({"id": str(uuid.uuid4()), "email": payload.email, "source": "supporter", "created_at": created_at})
    logger.info(f"New supporter: {payload.email} ({movement_id})")
    return {
        "message": "You're in! Welcome to the movement.",
        "already": False,
        "movement_id": movement_id,
        "name": payload.name,
        "created_at": created_at,
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
