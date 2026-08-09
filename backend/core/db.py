"""Async SQLAlchemy engine and session factory for the relational side.

Serverless notes -- both of these matter on Vercel + Neon and are easy to get
wrong:

1. NullPool. A connection pool is worse than useless in a serverless function:
   the container is frozen between invocations, so pooled sockets are dead by
   the time the next request thaws them, and Neon's autosuspend (5 minutes idle
   on the free tier) closes them from the other side as well. NullPool opens a
   connection per session and closes it at the end, which is the correct
   trade-off here even though it costs a round-trip.

2. No prepared-statement cache. asyncpg caches prepared statements per
   connection by default; that breaks behind connection poolers such as Neon's
   pgbouncer endpoint, which may hand the same logical session different
   backends. `statement_cache_size=0` disables it.

The URL is normalised to the asyncpg driver so that a plain
`postgresql://...` string copied straight out of the Neon dashboard works
without editing.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core import config

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _connect_args(url: str) -> dict:
    if url.startswith("postgresql+asyncpg://"):
        return {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    return {}


def get_engine() -> Optional[AsyncEngine]:
    """The process-wide engine, or None when DATABASE_URL is unset."""
    global _engine, _sessionmaker
    if not config.postgres_enabled():
        return None
    if _engine is None:
        url = _normalise_url(config.DATABASE_URL)
        _engine = create_async_engine(
            url,
            poolclass=NullPool,
            connect_args=_connect_args(url),
            future=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
        logger.info("Postgres engine initialised (%s)", url.split("@")[-1])
    return _engine


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncSession]:
    """One session, committed on clean exit and rolled back on error.

        async with transaction() as session:
            ...            # return, break and raise all behave correctly

    USE THIS for startup hooks, scripts and background work. `session_scope`
    below is a generator and exists for the FastAPI dependency path; consuming it
    with `async for` outside that path has a trap that has already cost real
    writes:

        async for session in session_scope():
            session.add(thing)
            return                      # <-- `thing` is silently discarded

    A `return` or `break` there leaves the generator suspended at its `yield`.
    asyncio does not finalise it at that moment -- it defers to
    `loop.shutdown_asyncgens()` -- so the commit does not run when the caller
    thinks it does, and in a serverless function that may be never. No exception
    is raised either way, so the work simply vanishes.

    A context manager has no such ambiguity: `__aexit__` is called immediately,
    with the exception state, on every exit path.
    """
    get_engine()
    if _sessionmaker is None:
        raise RuntimeError("Postgres is not configured (DATABASE_URL is unset)")
    async with _sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Generator form, for the FastAPI dependency in core/deps.py.

    FastAPI resumes a generator dependency normally after the response, so the
    commit below is reached. Anywhere else, use `transaction()` -- see the warning
    in its docstring for what `async for ... return` does to your writes.
    """
    get_engine()
    if _sessionmaker is None:
        raise RuntimeError("Postgres is not configured (DATABASE_URL is unset)")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async for session in session_scope():
        yield session


async def dispose() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
