"""Bulk import for the Research Centre and Knowledge Hub library.

    python -m backend.scripts.import_research --template
    python -m backend.scripts.import_research --file judgments.csv --dry-run
    python -m backend.scripts.import_research --file adr-reports.csv --publish

WHAT THIS FILLS. `research_documents` -- the judgments, affidavits, committee
reports, datasets and legislation behind the Research Centre, and the source
material the AI assistant grounds its answers in. Adding a document here makes it
searchable and citable across the platform, which is why the checks below matter
more than they look for what is nominally a library catalogue.

THE ONE FIELD THAT IS NOT OPTIONAL IS THE CITATION. `source_url` is
`nullable=False` on the model and required here, because a document row with no
link to where it originally appeared is an assertion that a document exists. The
Research Centre's whole claim is "every source, with its original" -- a catalogue
of unverifiable entries would be worse than an empty one.

LICENCE IS NOT A FORMALITY EITHER. `licence` decides whether this platform may
host a copy of the file or may only link to where it lives. It defaults to
`linked_only`, the conservative option: link to the original, host nothing. An
import that guessed `cc_by` for a copyrighted report would create a
redistribution problem that nobody would notice until a takedown arrived, so an
unrecognised licence value falls back to `linked_only` and says so, and a row
that supplies a `file_url` for hosting without an explicit licence is refused.

Everything lands unpublished unless --publish is typed. Re-running is safe:
documents match on slug, and an existing row is left alone rather than rewritten.
"""

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
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
from backend.core.geography import STATES_BY_CODE  # noqa: E402
from backend.core.rbac import Principal  # noqa: E402
from backend.core.security import slugify  # noqa: E402
from backend.modules.research.models import (  # noqa: E402
    DOCUMENT_KINDS,
    LICENCES,
    ResearchDocument,
)

IMPORT_ACTOR = Principal(
    id="research-importer",
    email="",
    name="Research library importer",
    permissions=frozenset(),
)

# The conservative default: link to the original, host nothing.
DEFAULT_LICENCE = "linked_only"

TEMPLATE = [
    {
        "title": "Judgment title, or the report's own title",
        "title_hi": "",
        "summary": "What it says, in a sentence or two. Not an argument about it.",
        "kind": "judgment",
        "authors": "Supreme Court of India",
        "publisher": "Supreme Court of India",
        "published_on": "2023-05-11",
        "source_url": "https://sci.gov.in/... (REQUIRED - where it originally appeared)",
        "file_url": "https://... (only if we may host a copy - see licence)",
        "licence": "public_record",
        "language": "en",
        "tags": "recall;electoral reform",
        "article_refs": "324;326",
        "state_code": "UT",
        "page_count": 48,
    }
]


# ==========================================================================
# Reading
# ==========================================================================
def _rows(text: str) -> list[dict]:
    stripped = text.lstrip()
    if stripped.startswith(("[", "{")):
        data = json.loads(stripped)
        if isinstance(data, dict):
            for key in ("records", "documents", "rows", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
        return data
    return list(csv.DictReader(io.StringIO(text)))


def _get(row: dict, *names: str, default: str = "") -> str:
    for name in names:
        for key in (name, name.lower(), name.upper()):
            if key in row and row[key] not in (None, ""):
                value = row[key]
                return str(value).strip() if not isinstance(value, list) else ";".join(map(str, value))
    return default


def _list(raw: str) -> list[str]:
    """Tags and article references: semicolon or comma separated.

    Semicolon first, because a document title or a tag can legitimately contain
    a comma and splitting on it silently shreds the value.
    """
    if not raw:
        return []
    separator = ";" if ";" in raw else ","
    return [part.strip() for part in raw.split(separator) if part.strip()]


def _date(raw: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y"):
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
    created: int = 0
    unchanged: int = 0
    rejected: list[str] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "documents_created": self.created,
            "documents_already_present": self.unchanged,
            "rows_rejected": len(self.rejected),
            "imported_with_warnings": len(self.warnings),
        }


# ==========================================================================
# Import
# ==========================================================================
async def import_documents(
    session: AsyncSession,
    rows: list[dict],
    *,
    publish: bool = False,
    default_kind: str = "report",
) -> Result:
    result = Result()

    for row in rows:
        title = _get(row, "title", "name")
        source_url = _get(row, "source_url", "url", "link")

        if not title:
            result.rejected.append(f"row has no title: {row!r:.120}")
            continue
        if not source_url:
            # The Research Centre's entire claim is "every source, with its
            # original". A row without one is an unverifiable assertion that a
            # document exists.
            result.rejected.append(f"{title}: no source_url; a catalogue entry needs its original")
            continue

        kind = _get(row, "kind", "type", default=default_kind)
        if kind not in DOCUMENT_KINDS:
            result.warnings.append(f"{title}: unknown kind {kind!r}, stored as {default_kind!r}")
            kind = default_kind

        licence = _get(row, "licence", "license")
        file_url = _get(row, "file_url", "hosted_url")
        if licence and licence not in LICENCES:
            result.warnings.append(
                f"{title}: unknown licence {licence!r}, stored as {DEFAULT_LICENCE!r} "
                "(link only, no hosted copy)"
            )
            licence = DEFAULT_LICENCE
        if not licence:
            if file_url:
                # Refused rather than defaulted: a file_url is a request to host a
                # copy, and hosting somebody's report under a guessed licence is a
                # redistribution problem nobody notices until a takedown arrives.
                result.rejected.append(
                    f"{title}: supplies file_url but no licence. State the licence that "
                    "permits hosting a copy, or drop file_url and link to the original."
                )
                continue
            licence = DEFAULT_LICENCE

        state_code = _get(row, "state_code", "state").upper() or None
        if state_code and state_code not in STATES_BY_CODE:
            result.warnings.append(f"{title}: unknown state {state_code!r}, left unset")
            state_code = None

        slug = _get(row, "slug") or slugify(title)[:200]
        existing = (
            await session.execute(select(ResearchDocument).where(ResearchDocument.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            result.unchanged += 1
            continue

        _, publisher = classify_source(source_url)
        document = ResearchDocument(
            slug=slug,
            title=title,
            title_hi=_get(row, "title_hi"),
            summary=_get(row, "summary", "description"),
            summary_hi=_get(row, "summary_hi"),
            kind=kind,
            authors=_get(row, "authors", "author"),
            publisher=_get(row, "publisher") or publisher or "",
            published_on=_date(_get(row, "published_on", "date", "year")),
            source_url=source_url,
            file_url=file_url,
            file_type=_get(row, "file_type") or ("pdf" if ".pdf" in file_url.lower() else ""),
            file_size_kb=_int(_get(row, "file_size_kb")),
            page_count=_int(_get(row, "page_count", "pages")),
            licence=licence,
            language=_get(row, "language", default="en"),
            tags=_list(_get(row, "tags")),
            article_refs=_list(_get(row, "article_refs", "articles")),
            state_code=state_code,
            is_published=publish,
            uploaded_by=IMPORT_ACTOR.id,
        )
        session.add(document)
        await session.flush()
        result.created += 1

        await audit.record(
            session,
            actor=IMPORT_ACTOR,
            action="create",
            entity_type="research_document",
            entity_id=document.slug,
            summary=f"Imported into the library: {document.title}",
            source_url=source_url,
            is_public=True,
        )

        # Indexed so it is findable AND so the assistant can ground answers in
        # it -- research_document is one of the four grounding types.
        await search.index(
            session,
            entity_type="research_document",
            entity_id=document.slug,
            title=document.title,
            subtitle=f"{DOCUMENT_KINDS.get(kind, kind)} - {document.publisher or document.authors}",
            body=document.summary,
            keywords=[*document.tags, *document.article_refs],
            state_code=state_code,
            is_published=document.is_published,
            url_path=f"/research/documents/{document.slug}",
        )

    return result


# ==========================================================================
# Entry point
# ==========================================================================
async def _run(args) -> None:
    text = pathlib.Path(args.file).read_text(encoding="utf-8")
    rows = _rows(text)
    if not rows:
        raise SystemExit("No rows found in the file.")

    async with database.transaction() as session:
        result = await import_documents(
            session, rows, publish=args.publish, default_kind=args.default_kind
        )
        if args.dry_run:
            await session.rollback()

    print(f"\n{'DRY RUN - nothing was written' if args.dry_run else 'Imported'}\n")
    print(f"  {'rows in file':34} {len(rows)}")
    for key, value in result.as_dict().items():
        print(f"  {key:34} {value}")

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

    if not args.dry_run and not args.publish:
        print("\nEverything was imported unpublished. Re-run with --publish when reviewed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import documents into the Research Centre / Knowledge Hub library.",
        epilog="source_url is required on every row; licence decides whether a copy may be hosted.",
    )
    parser.add_argument("--file", help="CSV or JSON file of documents")
    parser.add_argument(
        "--default-kind",
        default="report",
        choices=sorted(DOCUMENT_KINDS),
        help="kind for rows that do not state one",
    )
    parser.add_argument("--publish", action="store_true", help="publish what is imported")
    parser.add_argument("--dry-run", action="store_true", help="report what would change")
    parser.add_argument("--template", action="store_true", help="print the expected shape and exit")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2, ensure_ascii=False))
        print(
            f"\nkinds:    {', '.join(sorted(DOCUMENT_KINDS))}"
            f"\nlicences: {', '.join(sorted(LICENCES))}"
            "\n\ntags and article_refs are semicolon-separated in CSV, or arrays in JSON.",
            file=sys.stderr,
        )
        return

    if not args.file:
        raise SystemExit("--file is required (or --template)")
    if not config.postgres_enabled():
        raise SystemExit("DATABASE_URL is not set; there is nothing to import into.")

    asyncio.run(_run(args))
    asyncio.run(database.dispose())


if __name__ == "__main__":
    main()
