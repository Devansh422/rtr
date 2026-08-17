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
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core import config

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


# Query parameters that libpq (psql, psycopg2) understands and asyncpg does not.
#
# Every hosted Postgres provider puts at least `sslmode=require` in the connection
# string it hands you, because that string is written for psql. SQLAlchemy forwards
# unknown query parameters to the driver's connect() as keyword arguments, so
# leaving them in produces `TypeError: connect() got an unexpected keyword argument
# 'sslmode'` at the first connection -- not at startup, and not anywhere near the
# thing that caused it.
#
# They are stripped from the URL here and, where they mean something, translated
# into asyncpg's own arguments below.
_LIBPQ_ONLY_PARAMS = frozenset(
    {
        "sslmode",
        "sslrootcert",
        "sslcert",
        "sslkey",
        "channel_binding",  # Neon adds this one
        "gssencmode",
        "target_session_attrs",
        "options",
    }
)

# sslmode values that mean "encrypt the connection".
_SSL_REQUIRED = frozenset({"require", "verify-ca", "verify-full"})


def _libpq_params(url: str) -> dict[str, str]:
    query = urlsplit(url).query
    return {k: v[0] for k, v in parse_qs(query).items() if k in _LIBPQ_ONLY_PARAMS}


def _normalise_url(url: str) -> str:
    """Driver prefix, plus removal of parameters asyncpg cannot accept.

    Lets a connection string copied verbatim out of the Neon (or Supabase, or RDS)
    dashboard work unedited, which is what every deployment guide assumes.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        kept = [
            (k, v)
            for k, values in parse_qs(parts.query).items()
            for v in values
            if k not in _LIBPQ_ONLY_PARAMS
        ]
        url = urlunsplit(parts._replace(query=urlencode(kept)))
    return url


def _connect_args(url: str) -> dict:
    """asyncpg connect arguments, including SSL translated from `sslmode`.

    Pass the ORIGINAL url, not the normalised one -- the parameters this reads have
    been removed from the latter.
    """
    if not url.startswith(("postgresql://", "postgres://", "postgresql+asyncpg://")):
        return {}

    args: dict = {
        # asyncpg caches prepared statements per connection, which breaks behind a
        # connection pooler such as Neon's pgbouncer endpoint.
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

    params = _libpq_params(url)
    sslmode = params.get("sslmode")
    if sslmode is not None:
        # asyncpg takes `ssl`: True/False, or an SSLContext for certificate
        # verification. `verify-ca` and `verify-full` additionally want a root
        # certificate, which needs an SSLContext the caller supplies; the
        # connection is still encrypted here, so this is a downgrade in
        # verification only, and it is logged.
        args["ssl"] = sslmode in _SSL_REQUIRED
        if sslmode in {"verify-ca", "verify-full"}:
            logger.warning(
                "sslmode=%s requested: the connection is encrypted, but certificate "
                "verification needs an SSLContext this app does not construct.",
                sslmode,
            )
    elif ".neon.tech" in url or "supabase" in url:
        # Hosted Postgres refuses unencrypted connections. If the URL says nothing,
        # default to SSL rather than failing with a confusing server-side error.
        args["ssl"] = True

    return args


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
            # From the ORIGINAL url: _normalise_url has stripped the parameters
            # this needs to read.
            connect_args=_connect_args(config.DATABASE_URL),
            future=True,
        )
        if url.startswith("sqlite"):
            _enforce_sqlite_foreign_keys(_engine)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
        logger.info("Postgres engine initialised (%s)", url.split("@")[-1])
    return _engine


def _enforce_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """Turn on `PRAGMA foreign_keys` for the SQLite development database.

    SQLite parses `ON DELETE CASCADE` and then ignores it unless this pragma is
    set per connection, so without this a local database silently keeps every
    child row whose parent was deleted -- orphaned RTI applications, documents
    and signatures that Postgres would have removed. That is a nastier problem
    than it sounds: the divergence only shows up as a unique-constraint failure
    the next time the same fixture is loaded, a long way from the delete that
    caused it, and it makes local behaviour differ from production in exactly the
    area (referential integrity) where local testing is supposed to be
    trustworthy.

    Guarded on the driver, so this is a no-op for the Postgres deployments.
    """
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # pragma: no cover - driver callback
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
