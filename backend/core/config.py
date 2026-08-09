"""Single place where environment variables are read.

Before this module existed, `os.environ['MONGO_URL']` was evaluated at import
time in server.py, so a missing variable turned every request into an opaque
500 with a KeyError buried in the function logs. Reading them here keeps that
behaviour for the genuinely required ones (failing loudly at boot is correct --
a backend with no database cannot serve anything) while giving the optional
ones documented defaults.
"""

from pathlib import Path
import os

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BACKEND_DIR / "content"

# python-dotenv is a local-development convenience only: it loads variables from
# backend/.env into os.environ. In every deployed environment (Vercel included)
# the platform injects environment variables directly, there is no .env file in
# the bundle, and load_dotenv() would be a no-op even if it ran. Importing it
# defensively means a dependency resolution quirk that drops this dev-only
# package can never crash the app.
try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass


def _required(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError:
        raise RuntimeError(
            f"Required environment variable {name} is not set. "
            f"See backend/.env.example for the full list."
        ) from None


# ---------- Required ----------
MONGO_URL = _required("MONGO_URL")
DB_NAME = _required("DB_NAME")
JWT_SECRET = _required("JWT_SECRET")
ADMIN_EMAIL = _required("ADMIN_EMAIL").lower()
ADMIN_PASSWORD = _required("ADMIN_PASSWORD")

# ---------- Optional ----------
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

# Postgres (Neon) connection string. OPTIONAL ON PURPOSE, and this is the one
# piece of transitional scaffolding in the Phase 0 refactor:
#
#   set   -> Postgres is the authority for identity, RBAC and the audit log.
#   unset -> the app falls back to the pre-Phase-0 Mongo-only auth path.
#
# The fallback exists so that deploying this refactor cannot break a running
# site that has not had DATABASE_URL added yet, and so the test suite and local
# dev can run without a Postgres instance. It is NOT a permanent dual-database
# design.
#
# REMOVAL TRIGGER: once DATABASE_URL is set in every environment (local, preview,
# production) and `users` has been backfilled, delete the legacy branches marked
# `LEGACY FALLBACK` in core/rbac.py and modules/auth/service.py, and make this
# variable required.
DATABASE_URL = os.environ.get("DATABASE_URL") or None

# ---------- Optional integrations ----------
# Every one of these degrades a single feature when unset rather than breaking the
# app, and `GET /api/health` reports which are live. Keeping them here rather than
# in the modules that use them is this file's whole purpose: one place to look for
# "what does this deployment actually have".

# Public origin, used to build absolute links inside emails and certificates.
# Relative paths are meaningless in an inbox.
SITE_URL = (os.environ.get("SITE_URL") or "https://righttorecall.in").rstrip("/")

# Brevo: 300 transactional emails/day free. Unset -> every send is a logged no-op.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY") or None
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "no-reply@righttorecall.in")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Right to Recall Movement")

# Self-hosted Meilisearch. Unset -> search runs on Postgres, which is adequate at
# this corpus size (see core/search.py for the switch-over trigger).
MEILISEARCH_URL = (os.environ.get("MEILISEARCH_URL") or "").rstrip("/") or None
MEILISEARCH_KEY = os.environ.get("MEILISEARCH_KEY") or None
MEILISEARCH_INDEX = os.environ.get("MEILISEARCH_INDEX", "rtr")

# Google Gemini free tier for the Constitution Assistant. Unset -> the assistant
# returns the retrieved sources instead of a written answer, which is still useful.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or None
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

JWT_ALGORITHM = "HS256"
ADMIN_TOKEN_TTL_HOURS = 12
MEMBER_TOKEN_TTL_DAYS = 30
MAX_UPLOAD_BYTES = 6 * 1024 * 1024  # 6 MB

# Failed logins tolerated per email before a temporary lockout, and how long
# that lockout lasts.
LOGIN_MAX_ATTEMPTS = 10
LOGIN_LOCKOUT_MINUTES = 15


def postgres_enabled() -> bool:
    return DATABASE_URL is not None


def email_enabled() -> bool:
    return BREVO_API_KEY is not None


def meilisearch_enabled() -> bool:
    return MEILISEARCH_URL is not None


def assistant_engine() -> str:
    return "gemini" if GEMINI_API_KEY else "retrieval_only"
