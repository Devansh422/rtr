"""Application assembly.

This file used to be the whole backend (963 lines of routes, models, helpers and
seeding). Phase 0 of IMPLEMENTATION_PLAN.md reduced it to its actual job:
create the app, mount the module routers, wire middleware and lifecycle. Every
route now lives in the module that owns it, under backend/modules/.

The public API contract is unchanged by that move -- same paths, same request
bodies, same response shapes -- because the frontend and the integration suite
both depend on it. New endpoints added since are additive.

Run locally with:
    uvicorn backend.server:app --reload
"""

from contextlib import asynccontextmanager
from typing import Optional
import logging

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware

from backend.core import bootstrap, config, db as database, mongo
from backend.core.deps import get_optional_session

# Importing this makes every module's tables visible on Base.metadata, which is what
# AUTO_CREATE_TABLES needs at startup. The routers below would each pull in their own
# models anyway; this makes the requirement explicit rather than incidental.
from backend import models_all, seed_modules  # noqa: F401
from backend.modules.academy import router as academy_router
from backend.modules.ai import router as ai_router
from backend.modules.analytics import router as analytics_router
from backend.modules.audit import router as audit_router
from backend.modules.auth import router as auth_router
from backend.modules.certificates import router as certificates_router
from backend.modules.cms import router as cms_router
from backend.modules.constitution import router as constitution_router
from backend.modules.corrections import router as corrections_router
from backend.modules.events import router as events_router
from backend.modules.forum import router as forum_router
from backend.modules.legal import router as legal_router
from backend.modules.members import router as members_router
from backend.modules.petitions import router as petitions_router
from backend.modules.reports import router as reports_router
from backend.modules.representatives import router as representatives_router
from backend.modules.research import router as research_router
from backend.modules.search import router as search_router
from backend.modules.staff import router as staff_router
from backend.modules.states import router as states_router
from backend.modules.submissions import router as submissions_router
from backend.modules.tools import router as tools_router
from backend.modules.uploads import router as uploads_router
from backend.modules.volunteers import router as volunteers_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Serverless note: on Vercel this runs on every cold start, and several cold
    # starts can happen at once. Everything both of these do is idempotent and
    # race-tolerant -- see the module docstrings in core/bootstrap.py and
    # seed_modules.py.
    #
    # Order matters: core bootstrap reconciles the permission registry and
    # geography, and module seeding writes rows that reference states.
    await bootstrap.run()
    try:
        await seed_modules.run()
    except Exception as e:  # pragma: no cover - defensive, same rationale as bootstrap
        logger.error("Module seeding failed; the platform will serve without it: %s", e)
    yield
    mongo.close()
    await database.dispose()


app = FastAPI(title="Right to Recall Movement API", lifespan=lifespan)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Right to Recall Movement API", "status": "ok"}


async def _schema_ready(session: Optional[AsyncSession]) -> bool:
    """Whether the migrations have actually been applied.

    `postgres: true` says only "DATABASE_URL is configured" -- nothing about
    whether the tables exist. Those are different failures with the same symptom
    (every data endpoint 500s), and the second is the common one: pushing to git
    deploys the code but not the schema, so a fresh deployment reports a healthy
    Postgres connection and then fails on the first real query.

    One cheap existence check turns that into a one-request answer.

    Takes the session rather than opening its own, so health uses the same
    connection path as every other endpoint -- and so this is reachable in tests,
    which is the whole reason it can be trusted.
    """
    if session is None:
        return False
    try:
        await session.execute(text("SELECT 1 FROM platform_meta LIMIT 1"))
        return True
    except Exception:
        # The failed statement leaves the transaction unusable, and the session is
        # committed at teardown. Roll back or that commit raises and turns a
        # diagnostic endpoint into a 500 -- exactly when it is most needed.
        await session.rollback()
        return False


@api_router.get("/health")
async def health(session: Optional[AsyncSession] = Depends(get_optional_session)):
    """Liveness, which backing stores this instance has, and whether it can use them.

    Worth an endpoint because the Phase 0 migration has two valid configurations,
    and "why is /api/states 503-ing" has a one-request answer when `postgres` is
    reported here as false -- or, when it is true but `schema` is false, "run
    `python -m backend.scripts.migrate`".
    """
    schema = await _schema_ready(session)
    return {
        "status": "ok",
        "mongo": True,
        "postgres": config.postgres_enabled(),
        # False with postgres true means the connection works and the tables are
        # missing. See DEPLOY.md step 1b.
        "schema": schema,
        "hint": (
            None
            if schema or session is None
            else "Tables are missing. Run: python -m backend.scripts.migrate"
        ),
        # Optional integrations, each of which degrades a feature rather than
        # breaking it. Reported here so "why is the assistant only listing
        # sources" and "why did no email arrive" both have a one-request answer.
        "features": {
            "search": "meilisearch" if config.meilisearch_enabled() else "postgres",
            "assistant": config.assistant_engine(),
            "email": config.email_enabled(),
        },
    }


# Order matters only where paths could shadow each other; these modules own
# disjoint prefixes, so this list is grouped by phase for readability instead.
for module_router in (
    # Phase 0 -- identity, CMS, geography, operations
    auth_router,
    members_router,
    staff_router,
    cms_router,
    states_router,
    submissions_router,
    uploads_router,
    analytics_router,
    audit_router,
    legal_router,
    # Phase 1 -- knowledge and accountability core
    constitution_router,
    representatives_router,
    corrections_router,
    search_router,
    # Phase 2-3 -- community and civic tools
    petitions_router,
    reports_router,
    forum_router,
    volunteers_router,
    events_router,
    tools_router,
    # Phase 4-5 -- knowledge scale-out and AI
    academy_router,
    research_router,
    certificates_router,
    ai_router,
):
    api_router.include_router(module_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
