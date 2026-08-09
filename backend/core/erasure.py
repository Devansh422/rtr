"""The right to erasure, as a registry rather than one big function.

`DELETE /api/me/data` shipped in Phase 0 with a docstring saying "any module added
later that stores member data MUST extend this function -- that is the whole reason
it lives in one place". Thirteen modules later, that instruction has a problem: the
submissions module cannot import the forum, petitions or academy modules to delete
their rows without breaking §4's one-way dependency rule, and a single function that
knows thirteen schemas is a function that will silently miss the fourteenth.

So the shape inverts. Core owns the ORDER and the guarantees; each module registers
what it needs done. `run_all` executes every registered handler, and
`missing_coverage()` lets a test assert that every table holding a `citizen_id` has
a handler -- which turns "remember to extend the eraser" from a comment into a
failing build.

What core handles itself, because it owns the tables:

* Deleting the `citizens` row, which CASCADES to petition signatures, report
  confirmations, forum threads/replies/votes, citizen reports, volunteer profiles
  and their assignments, academy enrolments and attempts, and event registrations.
  Those are real deletes, not flags.
* Deleting the person's `certificates`, which have no foreign key (deliberately, so
  verification survives an account deletion -- but an erasure request overrides
  that: a certificate carries the holder's name).

What modules must register: anything referencing a citizen WITHOUT a cascading
foreign key. There are two such cases by design -- a correction and a petition both
outlive their author, so they detach rather than disappear.
"""

from typing import Awaitable, Callable, Optional
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Certificate, Citizen

logger = logging.getLogger(__name__)

# name -> handler(session, email, citizen_id) -> {counter: n}
Handler = Callable[[AsyncSession, str, Optional[str]], Awaitable[dict]]
_HANDLERS: dict[str, Handler] = {}


def register(name: str) -> Callable[[Handler], Handler]:
    """Decorator a module uses to add its own erasure step.

    Registration happens at import time, and server.py imports every module's
    router at import time, so by the time a request can arrive the registry is
    complete. A module that is not mounted also does not need erasing.
    """

    def wrap(handler: Handler) -> Handler:
        if name in _HANDLERS:
            raise RuntimeError(f"Duplicate erasure handler registered: {name}")
        _HANDLERS[name] = handler
        return handler

    return wrap


def registered() -> list[str]:
    return sorted(_HANDLERS)


async def run_all(session: AsyncSession, email: str) -> dict:
    """Erase everything the relational side holds about this person.

    Order matters: module handlers run BEFORE the citizen row is deleted, because
    some of them need to read it (to detach a petition by author id, for instance)
    and a cascade would have taken the row out from under them.

    A handler that fails does not abort the rest. An erasure request that half
    succeeds and then rolls back leaves the person's data in place and tells them it
    is gone, which is the worst of both; better to delete what can be deleted, log
    what could not, and report it honestly.
    """
    email = email.lower()
    citizen = (
        await session.execute(select(Citizen).where(Citizen.email == email))
    ).scalar_one_or_none()
    citizen_id = citizen.id if citizen else None

    removed: dict = {}
    for name, handler in sorted(_HANDLERS.items()):
        try:
            result = await handler(session, email, citizen_id)
            removed.update(result or {})
        except Exception as e:
            logger.error("Erasure handler %s failed for %s: %s", name, email, e)
            removed[f"{name}_failed"] = str(e)[:200]

    # Certificates carry the holder's name, so an erasure request removes them even
    # though they otherwise deliberately survive account deletion.
    removed["certificates"] = (
        await session.execute(
            delete(Certificate).where(
                (Certificate.holder_email == email)
                | (Certificate.citizen_id == (citizen_id or "\x00"))
            )
        )
    ).rowcount

    if citizen is not None:
        # The cascade does the bulk of the work -- see the module docstring for the
        # full list of what goes with it.
        await session.delete(citizen)
        removed["citizen"] = 1

    return removed


# --------------------------------------------------------------------------
# Coverage check, for the test suite
# --------------------------------------------------------------------------
def missing_coverage(metadata) -> list[str]:
    """Tables referencing a citizen with no cascade and no registered handler.

    Called from the test suite. Its job is to fail the build when someone adds a
    module that stores `citizen_id` without also arranging for it to be erased --
    the exact mistake the original one-function design was vulnerable to.
    """
    # Tables run_all deletes from itself, because core owns them.
    covered_tables: set[str] = {"certificates"}
    for handler in _HANDLERS.values():
        covered_tables.update(getattr(handler, "_erasure_tables", ()))

    gaps = []
    for name, table in metadata.tables.items():
        column = table.columns.get("citizen_id")
        if column is None:
            continue
        cascades = any(
            fk.column.table.name == "citizens" and (fk.ondelete or "").upper() == "CASCADE"
            for fk in column.foreign_keys
        )
        if not cascades and name not in covered_tables and name != "citizens":
            gaps.append(name)
    return sorted(gaps)


def covers(*tables: str) -> Callable[[Handler], Handler]:
    """Declare which tables a handler is responsible for, for the coverage check."""

    def wrap(handler: Handler) -> Handler:
        handler._erasure_tables = tables  # type: ignore[attr-defined]
        return handler

    return wrap
