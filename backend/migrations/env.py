"""Alembic environment.

Reads DATABASE_URL from the environment (via backend.core.config, so a local
backend/.env works too) rather than from alembic.ini, keeping credentials out of
version control. Runs against the async engine because the models are declared
with the async ORM.
"""

import asyncio
import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import config as app_config  # noqa: E402
from backend.core.db import _normalise_url  # noqa: E402

# Not `from backend.core.models import Base`: that only registers the core tables,
# and autogenerate would then propose DROPPING every feature module's table. See
# backend/models_all.py.
from backend.models_all import Base  # noqa: E402

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

if not app_config.DATABASE_URL:
    raise SystemExit(
        "DATABASE_URL is not set. Point it at your Neon (or local) Postgres "
        "instance before running migrations."
    )

alembic_config.set_main_option("sqlalchemy.url", _normalise_url(app_config.DATABASE_URL))


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Without this, autogenerate never notices a column changing width or
        # nullability -- it would only ever see added and dropped columns.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
