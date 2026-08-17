"""Bulk import of the manifesto accountability chain: promises, RTIs, replies, records.

    python -m backend.scripts.import_manifesto --template
    python -m backend.scripts.import_manifesto --election uttarakhand-2022 \
        --promises promises.csv --rti rti.csv --questions questions.csv \
        --documents documents.csv --dry-run

WHY THIS EXISTS. The admin API takes one promise, then one RTI, then one
question at a time, which is right for the research desk correcting a single
record and hopeless for opening a state. A manifesto has a few hundred promises;
typing them through a form is how a module stays empty for a year.

WHAT IT WILL NOT DO, AND THIS IS THE POINT.

**It cannot publish an assessment or set a promise's status.** Those are the
platform's own conclusions about a government's performance, and §14 keeps them
in a separate table from the records precisely so that no bulk process can put
one there. Every promise this imports carries the default status -- "status not
established from available records" -- which is the honest description of a
promise nobody has assessed yet. A human writes the assessment, against the
records, through the admin API. There is no flag here to change that, and adding
one would defeat the module.

What it does import is the FACTUAL half of the chain: what the manifesto said,
what was asked, what came back, and which records were attached. Those are
quotations and transcriptions, and bulk entry of a transcription is exactly the
sort of work a script should do.

FOUR FILES, JOINED BY CODE, because that is the shape research actually arrives
in -- one spreadsheet tab per stage, each row referring to the promise it belongs
to. Any subset may be given: a run with only --documents attaches records to
promises that already exist. A single nested JSON file works too (--promises
pointed at the shape `--template` prints), for anyone generating it from code.

Everything lands unpublished unless --publish is typed, and re-running is safe:
promises match on code, RTIs on code, questions on (rti, number), documents on
code.
"""

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime, timedelta
from typing import Optional
import argparse
import asyncio
import csv
import io
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from backend.core import audit, config, db as database, search  # noqa: E402
from backend.core.citations import classify_source  # noqa: E402
from backend.core.security import slugify  # noqa: E402
from backend.modules.manifesto.models import (  # noqa: E402
    ANSWER_STATUSES,
    DOCUMENT_KINDS,
    RTI_STATUSES,
    GovernmentDocument,
    Manifesto,
    ManifestoElection,
    ManifestoPromise,
    RtiApplication,
    RtiQuestion,
    RtiResponse,
)
from backend.core.rbac import Principal  # noqa: E402

IMPORT_ACTOR = Principal(
    id="manifesto-importer",
    email="",
    name="Manifesto data importer",
    permissions=frozenset(),
)

# s.7(1) of the RTI Act. Used only to fill a reply-due date the file omits, and
# only when the filing date is known -- the same pre-fill the admin API does.
RTI_REPLY_DAYS = 30

AUDIT_ENTITY = "manifesto_promise"


TEMPLATE = {
    "promises": [
        {
            "code": "UK-2022-P001",
            "title": "Short heading for the promise",
            "title_hi": "",
            "promise_text": "The promise EXACTLY as printed in the manifesto. Never paraphrased.",
            "promise_text_hi": "",
            "manifesto_page": "12",
            "department": "Education",
            "category": "Education",
        }
    ],
    "rti": [
        {
            "code": "RTI-UK-001",
            "promise_code": "UK-2022-P001",
            "subject": "What the application asked about",
            "public_authority": "Directorate of School Education, Uttarakhand",
            "department": "Education",
            "pio_designation": "Public Information Officer",
            "application_number": "EDU/2025/0117",
            "filed_on": "2025-01-12",
            "status": "reply_received",
            "application_url": "https://.../application.pdf",
            "reply_received_on": "2025-02-08",
            "reply_authority": "PIO, Directorate of School Education",
            "reply_reference": "PIO/EDU/2025/441",
            "reply_url": "https://.../reply.pdf",
            "reply_summary": "Neutral note on what the reply is. Never an evaluation of it.",
        }
    ],
    "questions": [
        {
            "rti_code": "RTI-UK-001",
            "number": 1,
            "question": "The question exactly as put to the authority.",
            "answer": "The answer exactly as given. Quoted, never summarised.",
            "answer_status": "answered",
            "document_code": "DOC-UK-001",
        }
    ],
    "documents": [
        {
            "code": "DOC-UK-001",
            "promise_code": "UK-2022-P001",
            "title": "Government Order sanctioning ...",
            "kind": "government_order",
            "issuing_authority": "Department of School Education",
            "reference_number": "GO/EDU/2023/318",
            "issued_on": "2023-06-14",
            "file_url": "https://.../go.pdf",
            "source_note": "Received with the RTI reply dated 5 February 2025.",
        }
    ],
}


# ==========================================================================
# Reading
# ==========================================================================
def _rows(text: str) -> list[dict]:
    stripped = text.lstrip()
    if stripped.startswith(("[", "{")):
        data = json.loads(stripped)
        return data if isinstance(data, list) else [data]
    return list(csv.DictReader(io.StringIO(text)))


def _load(path: Optional[str]) -> list[dict]:
    if not path:
        return []
    return _rows(pathlib.Path(path).read_text(encoding="utf-8"))


def _get(row: dict, *names: str, default: str = "") -> str:
    for name in names:
        for key in (name, name.lower(), name.upper()):
            if key in row and row[key] not in (None, ""):
                return str(row[key]).strip()
    return default


def _date(raw: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _int(raw: str) -> Optional[int]:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


@dataclass
class Result:
    promises_created: int = 0
    promises_updated: int = 0
    rti_created: int = 0
    rti_updated: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    responses_created: int = 0
    documents_created: int = 0
    rejected: list[str] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "promises_created": self.promises_created,
            "promises_updated": self.promises_updated,
            "rti_applications_created": self.rti_created,
            "rti_applications_updated": self.rti_updated,
            "questions_created": self.questions_created,
            "questions_updated": self.questions_updated,
            "replies_created": self.responses_created,
            "documents_created": self.documents_created,
            "rows_rejected": len(self.rejected),
            "imported_with_warnings": len(self.warnings),
        }


# ==========================================================================
# Import
# ==========================================================================
async def import_chain(
    session: AsyncSession,
    *,
    election_slug: str,
    promises: list[dict],
    rti: list[dict],
    questions: list[dict],
    documents: list[dict],
    manifesto_slug: Optional[str] = None,
    publish: bool = False,
) -> Result:
    result = Result()

    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.slug == election_slug)
        )
    ).scalar_one_or_none()
    if election is None:
        raise SystemExit(
            f"No election with slug {election_slug!r}. "
            "Seeded elections are opened by backend/seed_modules.py; "
            "add a new one through the admin API first."
        )

    manifesto = None
    if promises:
        manifesto = await _manifesto_for(session, election, manifesto_slug)
        if manifesto is None:
            raise SystemExit(
                f"No published manifesto for {election_slug!r}. A promise is a quotation "
                "from a specific party's document, so the manifesto must exist first "
                "(POST /api/admin/manifesto/manifestos)."
            )

    # ---- Promises ----
    for row in promises:
        code = _get(row, "code", "promise_code").upper()
        text = _get(row, "promise_text", "text", "promise")
        if not code or not text:
            result.rejected.append(f"promise row missing code or promise_text: {row!r:.120}")
            continue

        existing = (
            await session.execute(
                select(ManifestoPromise).where(ManifestoPromise.code == code)
            )
        ).scalar_one_or_none()

        if existing is None:
            promise = ManifestoPromise(
                code=code,
                election_id=election.id,
                manifesto_id=manifesto.id,
                title=_get(row, "title") or text[:120],
                title_hi=_get(row, "title_hi"),
                promise_text=text,
                promise_text_hi=_get(row, "promise_text_hi"),
                manifesto_page=_get(row, "manifesto_page", "page"),
                manifesto_page_url=_get(row, "manifesto_page_url"),
                department=_get(row, "department"),
                category=_get(row, "category", default="Other"),
                # NOT settable from the file. See the module docstring: a status
                # is the platform's conclusion, and this process does not draw
                # conclusions. It stays at the model default until a human
                # publishes an assessment.
                is_published=publish,
            )
            session.add(promise)
            await session.flush()
            result.promises_created += 1
            await audit.record(
                session,
                actor=IMPORT_ACTOR,
                action="create",
                entity_type=AUDIT_ENTITY,
                entity_id=promise.code,
                summary=f"Imported promise {promise.code} from {manifesto.title}",
                source_url=manifesto.source_url or None,
                is_public=True,
            )
        else:
            promise = existing
            changed = False
            for attribute, incoming in (
                ("title_hi", _get(row, "title_hi")),
                ("promise_text_hi", _get(row, "promise_text_hi")),
                ("manifesto_page", _get(row, "manifesto_page", "page")),
                ("manifesto_page_url", _get(row, "manifesto_page_url")),
                ("department", _get(row, "department")),
            ):
                if incoming and not getattr(promise, attribute):
                    setattr(promise, attribute, incoming)
                    changed = True
            if changed:
                result.promises_updated += 1

        await _index_promise(session, promise)

    # ---- Documents before questions: a question may cite one ----
    documents_by_code: dict[str, GovernmentDocument] = {}
    for row in documents:
        document = await _upsert_document(session, row, publish=publish, result=result)
        if document is not None:
            documents_by_code[document.code] = document

    # ---- RTI applications, and the covering reply on the same row ----
    for row in rti:
        await _upsert_rti(session, row, publish=publish, result=result)

    # ---- Questions and answers ----
    for row in questions:
        await _upsert_question(
            session, row, documents_by_code=documents_by_code, result=result
        )

    return result


async def _manifesto_for(
    session: AsyncSession, election: ManifestoElection, slug: Optional[str]
) -> Optional[Manifesto]:
    stmt = select(Manifesto).where(Manifesto.election_id == election.id)
    if slug:
        stmt = stmt.where(Manifesto.slug == slug)
    return (await session.execute(stmt)).scalars().first()


async def _index_promise(session: AsyncSession, promise: ManifestoPromise) -> None:
    await search.index(
        session,
        entity_type="manifesto_promise",
        entity_id=promise.code,
        title=f"{promise.code}: {promise.title}",
        subtitle=f"Manifesto promise - {promise.department or 'department not stated'}",
        body=promise.promise_text,
        keywords=[promise.category, promise.department],
        is_published=promise.is_published,
        url_path=f"/manifesto/promise/{promise.code}",
    )


async def _upsert_document(
    session: AsyncSession, row: dict, *, publish: bool, result: Result
) -> Optional[GovernmentDocument]:
    code = _get(row, "code", "document_code").upper()
    title = _get(row, "title")
    if not code or not title:
        result.rejected.append(f"document row missing code or title: {row!r:.120}")
        return None

    source_note = _get(row, "source_note", "provenance")
    source_url = _get(row, "source_url")
    file_url = _get(row, "file_url", "url")
    if not source_note and not source_url:
        # The module's own rule: a published record must say where it came from.
        # An anonymous PDF is not evidence.
        result.rejected.append(
            f"{code}: needs source_note or source_url saying where this copy came from"
        )
        return None

    kind = _get(row, "kind", default="other")
    if kind not in DOCUMENT_KINDS:
        result.warnings.append(f"{code}: unknown kind {kind!r}, stored as 'other'")
        kind = "other"

    existing = (
        await session.execute(
            select(GovernmentDocument).where(GovernmentDocument.code == code)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    promise = await _promise_by_code(session, _get(row, "promise_code"))
    if promise is None:
        result.rejected.append(
            f"{code}: promise {_get(row, 'promise_code')!r} not found; "
            "import the promise first"
        )
        return None

    is_primary, publisher = classify_source(source_url or file_url)
    document = GovernmentDocument(
        code=code,
        promise_id=promise.id,
        title=title,
        kind=kind,
        issuing_authority=_get(row, "issuing_authority", "authority"),
        department=_get(row, "department"),
        reference_number=_get(row, "reference_number", "reference"),
        issued_on=_date(_get(row, "issued_on", "date")),
        file_url=file_url,
        source_url=source_url,
        source_note=source_note,
        obtained_via=_get(row, "obtained_via", default="rti"),
        is_primary_source=is_primary,
        publisher=publisher or "",
        page_count=_int(_get(row, "page_count")),
        is_published=publish,
    )
    session.add(document)
    await session.flush()
    result.documents_created += 1

    await audit.record(
        session,
        actor=IMPORT_ACTOR,
        action="document_uploaded",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Imported record: {document.title}",
        source_url=source_url or file_url or None,
        is_public=True,
    )
    return document


async def _promise_by_code(
    session: AsyncSession, code: str
) -> Optional[ManifestoPromise]:
    if not code:
        return None
    return (
        await session.execute(
            select(ManifestoPromise).where(ManifestoPromise.code == code.upper())
        )
    ).scalar_one_or_none()


async def _upsert_rti(
    session: AsyncSession, row: dict, *, publish: bool, result: Result
) -> None:
    code = _get(row, "code", "rti_code").upper()
    authority = _get(row, "public_authority", "authority")
    if not code or not authority:
        result.rejected.append(f"RTI row missing code or public_authority: {row!r:.120}")
        return

    promise = await _promise_by_code(session, _get(row, "promise_code"))
    if promise is None:
        result.rejected.append(
            f"{code}: promise {_get(row, 'promise_code')!r} not found; import it first"
        )
        return

    status = _get(row, "status", default="filed")
    if status not in RTI_STATUSES:
        result.warnings.append(f"{code}: unknown RTI status {status!r}, stored as 'filed'")
        status = "filed"

    filed_on = _date(_get(row, "filed_on", "filed"))
    reply_due = _date(_get(row, "reply_due_on"))
    if filed_on and not reply_due:
        reply_due = filed_on + timedelta(days=RTI_REPLY_DAYS)

    existing = (
        await session.execute(select(RtiApplication).where(RtiApplication.code == code))
    ).scalar_one_or_none()

    if existing is None:
        application = RtiApplication(
            code=code,
            promise_id=promise.id,
            subject=_get(row, "subject"),
            public_authority=authority,
            department=_get(row, "department"),
            pio_designation=_get(row, "pio_designation", "pio"),
            application_number=_get(row, "application_number"),
            prepared_on=_date(_get(row, "prepared_on")),
            filed_on=filed_on,
            reply_due_on=reply_due,
            status=status,
            application_url=_get(row, "application_url"),
            filing_proof_url=_get(row, "filing_proof_url"),
            notes=_get(row, "notes"),
            is_published=publish,
        )
        session.add(application)
        await session.flush()
        result.rti_created += 1
        if filed_on:
            await audit.record(
                session,
                actor=IMPORT_ACTOR,
                action="rti_filed",
                entity_type=AUDIT_ENTITY,
                entity_id=promise.code,
                summary=f"Imported RTI {code} filed with {authority}",
                source_url=_get(row, "filing_proof_url") or None,
                is_public=True,
            )
    else:
        application = existing
        if application.status != status:
            application.status = status
            result.rti_updated += 1

    # The covering reply, where the same row carries one. Kept on the RTI row
    # because that is how a tracking spreadsheet is actually laid out -- one line
    # per application, with the reply's details in later columns.
    reply_authority = _get(row, "reply_authority", "replying_authority")
    reply_url = _get(row, "reply_url", "reply_document_url")
    received_on = _date(_get(row, "reply_received_on", "received_on"))
    if not (reply_authority or reply_url or received_on):
        return

    already = (
        await session.execute(
            select(RtiResponse).where(RtiResponse.rti_id == application.id)
        )
    ).scalars().first()
    if already is not None:
        return

    if not reply_url:
        # A reply nobody can read is a claim about a reply.
        result.warnings.append(
            f"{code}: reply recorded without a document URL; it will show as a "
            "reply with no original attached"
        )

    session.add(
        RtiResponse(
            rti_id=application.id,
            received_on=received_on,
            reply_dated=_date(_get(row, "reply_dated")),
            replying_authority=reply_authority or authority,
            department=_get(row, "reply_department", "department"),
            reference_number=_get(row, "reply_reference", "reference_number"),
            document_url=reply_url,
            page_count=_int(_get(row, "reply_page_count")),
            summary=_get(row, "reply_summary"),
            is_appeal_reply=_get(row, "is_appeal_reply").lower() in {"1", "true", "yes"},
            is_published=publish,
        )
    )
    result.responses_created += 1
    await audit.record(
        session,
        actor=IMPORT_ACTOR,
        action="reply_received",
        entity_type=AUDIT_ENTITY,
        entity_id=promise.code,
        summary=f"Imported reply to {code} from {reply_authority or authority}",
        source_url=reply_url or None,
        is_public=True,
    )


async def _upsert_question(
    session: AsyncSession,
    row: dict,
    *,
    documents_by_code: dict[str, GovernmentDocument],
    result: Result,
) -> None:
    rti_code = _get(row, "rti_code", "code").upper()
    number = _int(_get(row, "number", "q_no", "question_number")) or 0
    text = _get(row, "question", "question_text")
    if not rti_code or not number or not text:
        result.rejected.append(
            f"question row needs rti_code, number and question text: {row!r:.120}"
        )
        return

    application = (
        await session.execute(select(RtiApplication).where(RtiApplication.code == rti_code))
    ).scalar_one_or_none()
    if application is None:
        result.rejected.append(f"question {number}: RTI {rti_code!r} not found")
        return

    answer_status = _get(row, "answer_status", default="")
    answer = _get(row, "answer", "answer_text")
    if not answer_status:
        # Derived rather than defaulted to "answered": an unanswered question is
        # the more consequential state and must not be created by omission.
        answer_status = "answered" if answer else "awaited"
    if answer_status not in ANSWER_STATUSES:
        result.warnings.append(
            f"{rti_code} q{number}: unknown answer_status {answer_status!r}, stored as 'awaited'"
        )
        answer_status = "awaited"

    document = documents_by_code.get(_get(row, "document_code").upper())
    if document is None and _get(row, "document_code"):
        found = (
            await session.execute(
                select(GovernmentDocument).where(
                    GovernmentDocument.code == _get(row, "document_code").upper()
                )
            )
        ).scalar_one_or_none()
        document = found

    existing = (
        await session.execute(
            select(RtiQuestion).where(
                RtiQuestion.rti_id == application.id, RtiQuestion.number == number
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        changed = False
        if answer and not existing.answer_text:
            existing.answer_text = answer
            existing.answer_status = answer_status
            changed = True
        if document is not None and not existing.supporting_document_id:
            existing.supporting_document_id = document.id
            changed = True
        if changed:
            result.questions_updated += 1
        return

    session.add(
        RtiQuestion(
            rti_id=application.id,
            number=number,
            question_text=text,
            question_text_hi=_get(row, "question_hi", "question_text_hi"),
            answer_text=answer,
            answer_status=answer_status,
            supporting_document_id=document.id if document is not None else None,
        )
    )
    result.questions_created += 1


# ==========================================================================
# Entry point
# ==========================================================================
async def _run(args) -> None:
    promises = _load(args.promises)
    rti = _load(args.rti)
    questions = _load(args.questions)
    documents = _load(args.documents)

    # A single nested JSON file, as --template prints, given to --promises.
    if promises and isinstance(promises[0], dict) and "promises" in promises[0]:
        bundle = promises[0]
        promises = bundle.get("promises", [])
        rti = rti or bundle.get("rti", [])
        questions = questions or bundle.get("questions", [])
        documents = documents or bundle.get("documents", [])

    if not any((promises, rti, questions, documents)):
        raise SystemExit("Nothing to import. Give at least one of --promises/--rti/--questions/--documents.")

    async with database.transaction() as session:
        result = await import_chain(
            session,
            election_slug=args.election,
            promises=promises,
            rti=rti,
            questions=questions,
            documents=documents,
            manifesto_slug=args.manifesto,
            publish=args.publish,
        )
        if args.dry_run:
            await session.rollback()

    print(f"\n{'DRY RUN - nothing was written' if args.dry_run else 'Imported'}")
    print(f"Election: {args.election}\n")
    for key, value in result.as_dict().items():
        print(f"  {key:32} {value}")

    if result.rejected:
        print(f"\nNOT imported ({len(result.rejected)}):")
        for line in result.rejected[:20]:
            print(f"  - {line}")
        if len(result.rejected) > 20:
            print(f"  ... and {len(result.rejected) - 20} more")

    if result.warnings:
        print(f"\nImported, with something worth knowing ({len(result.warnings)}):")
        for line in result.warnings[:20]:
            print(f"  - {line}")

    if not args.dry_run:
        print(
            "\nNo status or assessment was set. Every imported promise reads "
            "'status not established\n from available records' until a human "
            "publishes an assessment against the records."
        )
        if not args.publish:
            print("Everything was imported unpublished. Re-run with --publish, or publish from the admin API.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import manifesto promises, RTI applications, replies and records.",
        epilog="Never imports a status or an assessment - see the module docstring.",
    )
    parser.add_argument("--election", default="uttarakhand-2022", help="election slug")
    parser.add_argument("--manifesto", help="manifesto slug, when the election has more than one")
    parser.add_argument("--promises", help="CSV/JSON of promises (or the nested bundle)")
    parser.add_argument("--rti", help="CSV/JSON of RTI applications, with reply columns")
    parser.add_argument("--questions", help="CSV/JSON of questions and answers")
    parser.add_argument("--documents", help="CSV/JSON of government records")
    parser.add_argument("--publish", action="store_true", help="publish what is imported")
    parser.add_argument("--dry-run", action="store_true", help="report what would change")
    parser.add_argument("--template", action="store_true", help="print the expected shape and exit")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2, ensure_ascii=False))
        print(
            "\nAs CSV: one file per top-level key, columns named as the keys above.\n"
            "As JSON: this whole object in one file, passed to --promises.",
            file=sys.stderr,
        )
        return

    if not config.postgres_enabled():
        raise SystemExit("DATABASE_URL is not set; there is nothing to import into.")

    asyncio.run(_run(args))
    asyncio.run(database.dispose())


if __name__ == "__main__":
    main()
