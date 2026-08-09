"""Apply pending migrations, then reconcile the registry and seed data.

    python -m backend.scripts.migrate

Equivalent to `cd backend && alembic upgrade head` followed by the seeding the
app would otherwise do lazily on its next cold start. Running it explicitly is
what makes a deploy predictable: the schema and the role registry are correct
before the first request arrives, rather than during it.
"""

import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import config, db as database  # noqa: E402
from backend.core.bootstrap import run_postgres_bootstrap  # noqa: E402


def apply_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    ini = pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    command.upgrade(cfg, "head")


async def seed() -> None:
    await run_postgres_bootstrap()
    await database.dispose()


def main() -> None:
    if not config.postgres_enabled():
        raise SystemExit(
            "DATABASE_URL is not set. Point it at your Neon (or local) Postgres "
            "instance before running migrations."
        )

    # apply_migrations() must stay OUTSIDE asyncio.run(). Alembic's env.py opens
    # its own event loop to drive the async engine, and asyncio.run() refuses to
    # nest -- calling the two from one coroutine fails with "cannot be called
    # from a running event loop".
    apply_migrations()
    print("Schema at head.")

    asyncio.run(seed())
    print("Registry, geography and bootstrap admin reconciled.")


if __name__ == "__main__":
    main()
