"""Bulk import of representative identity and sourced claims from open data.

    python -m backend.scripts.import_representatives --list-sources
    python -m backend.scripts.import_representatives --source sansad_members --file members.csv --dry-run
    python -m backend.scripts.import_representatives --source myneta_affidavits --file mh2024.csv

WHY AN IMPORTER RATHER THAN A SCRAPER, which is what this was asked for.
IMPLEMENTATION_PLAN.md §124 lists the sources for this data -- ECI, PRS, Sansad,
MyNeta/ADR, data.gov.in -- and then says the thing that decided this design:
"check each source's reuse/attribution terms before bulk scraping; prefer
official open-data downloads over scraping". Every one of those sources
publishes the same data as a file you are permitted to download. Parsing that
file is stable, attributable and does not breach anybody's terms; parsing their
HTML is none of those things and breaks the week they change a stylesheet.

So this takes a FILE and maps it. `--url` will fetch one over HTTPS, which is
the supported way to point it at a published dataset. What it will not do is
walk a site, follow links or defeat a rate limit, and adding that is not a small
change to this file -- it is a different decision, with a licence review in
front of it.

THREE RULES THIS ENFORCES, WHICH ARE THE REASON IT IS NOT A ONE-OFF SCRIPT.
This writes claims about named, living people -- the most defamation-exposed
surface on the platform (§7) -- from a machine, in bulk, with nobody reading
each row. That inverts the safety model the rest of the platform relies on, so:

1. **Nothing it writes is presented as fact.** Every claim lands as UNVERIFIED
   and renders behind a "pending citation review" marker until a human Fact
   Checker follows the source. The importer cannot set any other status; there
   is no flag for it.
2. **It never overwrites human judgement.** A claim a Fact Checker has already
   accepted, disputed or retracted is left exactly as it is, and the difference
   is reported as a conflict for a person to look at. An importer that silently
   reverted a fact-check would make the fact-check worthless.
3. **Profiles arrive as drafts.** A new representative is created unpublished.
   Publishing a profile about a real person is a human decision, and `--publish`
   exists so that decision is explicit and typed rather than a default.

Re-running is safe: representatives match on slug, claims on (representative,
field, period), and anything unchanged is left untouched rather than rewritten.
"""

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
from typing import Callable, Iterable, Optional
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
from backend.core.citations import VerificationStatus, classify_source  # noqa: E402
from backend.core.geography import STATES_BY_CODE  # noqa: E402
from backend.core.rbac import Principal  # noqa: E402
from backend.core.security import slugify  # noqa: E402
from backend.modules.representatives.fields import CLAIM_FIELDS_BY_KEY  # noqa: E402
from backend.modules.representatives.models import (  # noqa: E402
    Constituency,
    Party,
    Representative,
    RepresentativeClaim,
)

# The actor recorded against every audit entry. A named non-human actor, so the
# public history of a profile says "imported from the Sansad members list" rather
# than attributing bulk data entry to whichever staff member ran the command.
IMPORT_ACTOR = Principal(
    id="data-importer",
    email="",
    name="Open data importer",
    permissions=frozenset(),
)

VALID_HOUSES = {"lok_sabha", "rajya_sabha", "vidhan_sabha", "vidhan_parishad"}


# ==========================================================================
# The canonical record every adapter produces
# ==========================================================================
@dataclass
class IncomingClaim:
    field_key: str
    period: str
    value_number: Optional[float] = None
    value_text: str = ""


@dataclass
class IncomingRepresentative:
    full_name: str
    house: str
    state_code: str
    constituency_code: Optional[str] = None
    party_code: Optional[str] = None
    party_name: str = ""
    name_hi: str = ""
    office: str = ""
    official_email: str = ""
    official_page_url: str = ""
    term_start: Optional[date] = None
    is_sitting: bool = True
    claims: list[IncomingClaim] = dataclass_field(default_factory=list)

    @property
    def slug(self) -> str:
        """Name plus constituency: two MLAs share a name often enough to matter,
        and a slug collision would merge two people's records into one."""
        parts = [self.full_name, self.constituency_code or self.state_code]
        return slugify("-".join(p for p in parts if p))


@dataclass(frozen=True)
class Source:
    """One dataset, its citation, and how to read it."""

    key: str
    label: str
    # The page the data was published on. Becomes the citation on every row, so
    # a reader can go to the same file and check the number themselves.
    source_url: str
    source_title: str
    parse: Callable[[str], list[IncomingRepresentative]]
    notes: str = ""


# ==========================================================================
# Parsing helpers
# ==========================================================================
def _rows(text: str) -> list[dict]:
    """CSV or JSON, whichever it is. Both are published by these sources."""
    stripped = text.lstrip()
    if stripped.startswith(("[", "{")):
        data = json.loads(stripped)
        if isinstance(data, dict):
            # data.gov.in wraps its payload in {"records": [...]}.
            for key in ("records", "rows", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            raise ValueError("JSON object contained no records/rows/data/items array")
        return data
    return list(csv.DictReader(io.StringIO(text)))


def _get(row: dict, *names: str, default: str = "") -> str:
    """First non-empty value among several possible column names.

    Column headings differ between the same dataset's yearly releases far more
    often than the data does, so every adapter lists the spellings it has seen
    rather than pinning one.
    """
    for name in names:
        for key in (name, name.lower(), name.upper(), name.title()):
            if key in row and row[key] not in (None, ""):
                return str(row[key]).strip()
    return default


def _number(raw: str) -> Optional[float]:
    """A figure from a spreadsheet cell.

    Handles the shapes these files actually contain: "Rs 1,23,45,678", "45%",
    "12", "Nil", "-". Returns None for anything it cannot read rather than
    guessing, because a wrong number here becomes a published allegation.
    """
    if not raw:
        return None
    cleaned = raw.replace(",", "").replace("%", "").replace("₹", "")
    cleaned = cleaned.replace("Rs", "").replace("rs", "").strip()
    if cleaned.lower() in {"", "nil", "none", "na", "n/a", "-", "--", "not available"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _state_code(raw: str) -> Optional[str]:
    """Accept either the ISO code or the state's name, as the files use both."""
    if not raw:
        return None
    candidate = raw.strip()
    if candidate.upper() in STATES_BY_CODE:
        return candidate.upper()
    wanted = candidate.lower()
    for code, state in STATES_BY_CODE.items():
        if state.name.lower() == wanted:
            return code
    return None


def _date(raw: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


# ==========================================================================
# Adapters
# ==========================================================================
def _parse_members(text: str) -> list[IncomingRepresentative]:
    """Identity rows: a House members list or an ECI winners file.

    Identity only -- name, seat, party, term. No claims, because a members list
    makes no assertions about anybody beyond who holds the seat, which is what
    the Representative row is for.
    """
    out = []
    for row in _rows(text):
        name = _get(row, "name", "member_name", "full_name", "candidate", "winner")
        state = _state_code(_get(row, "state", "state_code", "state_name"))
        if not name or not state:
            continue
        out.append(
            IncomingRepresentative(
                full_name=name,
                name_hi=_get(row, "name_hi", "name_hindi"),
                house=_get(row, "house", default="lok_sabha").lower().replace(" ", "_"),
                state_code=state,
                constituency_code=_get(row, "constituency_code", "pc_code", "ac_code") or None,
                party_code=_get(row, "party_code", "party_abbr") or None,
                party_name=_get(row, "party", "party_name"),
                office=_get(row, "office", "portfolio"),
                official_email=_get(row, "email", "official_email"),
                official_page_url=_get(row, "profile_url", "url", "member_url"),
                term_start=_date(_get(row, "term_start", "date_of_election", "election_date")),
                is_sitting=_get(row, "is_sitting", default="true").lower()
                not in {"false", "0", "no"},
            )
        )
    return out


def _parse_affidavits(text: str) -> list[IncomingRepresentative]:
    """ADR/MyNeta affidavit transcriptions: criminal cases, assets, liabilities.

    THE HIGHEST-RISK IMPORT ON THE PLATFORM. Every number here is a criminal or
    financial allegation about a named person, taken from what that person swore
    to the Election Commission. Three things follow, and none is optional:

    * The period is the affidavit's election year, always. An asset figure with
      no year is worse than no figure -- it invites the reader to assume it is
      current, and `period_required=True` on these fields exists to stop that.
    * A row missing the year is skipped rather than imported undated.
    * The claim explanation shown to readers ("pending cases are allegations, not
      convictions") comes from CLAIM_FIELDS and is not this importer's to soften.
    """
    out = []
    for row in _rows(text):
        name = _get(row, "candidate", "name", "candidate_name")
        state = _state_code(_get(row, "state", "state_name"))
        year = _get(row, "year", "election_year", "poll_year")
        if not name or not state or not year:
            continue

        claims = []
        for column_names, field_key in (
            (("criminal_cases", "pending_cases", "cases"), "criminal.pending_cases"),
            (("serious_ipc", "serious_cases"), "criminal.serious_cases"),
            (("convictions", "convicted_cases"), "criminal.convictions"),
            (("total_assets", "assets"), "assets.total"),
            (("movable_assets", "movable"), "assets.movable"),
            (("immovable_assets", "immovable"), "assets.immovable"),
            (("liabilities", "total_liabilities"), "liabilities.total"),
        ):
            value = _number(_get(row, *column_names))
            if value is not None:
                claims.append(
                    IncomingClaim(field_key=field_key, period=year, value_number=value)
                )

        education = _get(row, "education", "educational_qualification")
        if education:
            claims.append(
                IncomingClaim(
                    field_key="background.education", period="", value_text=education
                )
            )

        out.append(
            IncomingRepresentative(
                full_name=name,
                house=_get(row, "house", default="vidhan_sabha").lower().replace(" ", "_"),
                state_code=state,
                constituency_code=_get(row, "constituency_code", "ac_code", "pc_code") or None,
                party_name=_get(row, "party", "party_name"),
                claims=claims,
            )
        )
    return out


def _parse_attendance(text: str) -> list[IncomingRepresentative]:
    """PRS-style performance rows: attendance, questions, debates, bills."""
    out = []
    for row in _rows(text):
        name = _get(row, "mp_name", "name", "member")
        state = _state_code(_get(row, "state", "state_name"))
        period = _get(row, "session", "period", "term", "year")
        if not name or not state or not period:
            continue

        claims = []
        for column_names, field_key in (
            (("attendance", "attendance_percent"), "attendance.percent"),
            (("questions", "questions_asked"), "performance.questions_asked"),
            (("debates", "debates_participated"), "performance.debates"),
            (("private_member_bills", "bills"), "performance.private_member_bills"),
        ):
            value = _number(_get(row, *column_names))
            if value is not None:
                claims.append(
                    IncomingClaim(field_key=field_key, period=period, value_number=value)
                )

        out.append(
            IncomingRepresentative(
                full_name=name,
                house=_get(row, "house", default="lok_sabha").lower().replace(" ", "_"),
                state_code=state,
                constituency_code=_get(row, "constituency_code", "pc_code") or None,
                party_name=_get(row, "party", "party_name"),
                claims=claims,
            )
        )
    return out


SOURCES: dict[str, Source] = {
    source.key: source
    for source in (
        Source(
            key="sansad_members",
            label="Parliament of India - members list",
            source_url="https://sansad.in/ls/members",
            source_title="Lok Sabha members list, Parliament of India",
            parse=_parse_members,
            notes="Identity only. Also fits Rajya Sabha and state assembly rosters "
            "with --source-url pointed at the right roster.",
        ),
        Source(
            key="eci_results",
            label="Election Commission of India - constituency results",
            source_url="https://results.eci.gov.in/",
            source_title="Constituency-wise results, Election Commission of India",
            parse=_parse_members,
            notes="Winners as identity rows. Margins and vote shares are separate "
            "claim fields and are not read from this file yet.",
        ),
        Source(
            key="myneta_affidavits",
            label="ADR / MyNeta - candidate affidavit transcriptions",
            source_url="https://myneta.info/",
            source_title="Candidate affidavit summary, ADR / MyNeta",
            parse=_parse_affidavits,
            notes="Criminal cases, assets and liabilities, as declared by the "
            "candidate to the ECI. Allegations, never findings.",
        ),
        Source(
            key="prs_attendance",
            label="PRS Legislative Research - MP performance",
            source_url="https://prsindia.org/mptrack",
            source_title="MP attendance and performance, PRS Legislative Research",
            parse=_parse_attendance,
        ),
        Source(
            key="data_gov_in",
            label="data.gov.in - generic members dataset",
            source_url="https://data.gov.in/",
            source_title="Open Government Data Platform India",
            parse=_parse_members,
            notes="Reads the {'records': [...]} envelope the platform's APIs return.",
        ),
    )
}


# ==========================================================================
# Import
# ==========================================================================
@dataclass
class Result:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    claims_created: int = 0
    claims_updated: int = 0
    claims_skipped_reviewed: int = 0
    conflicts: list[str] = dataclass_field(default_factory=list)
    # Rows or claims that were NOT written. Kept apart from `warnings` because
    # the two demand different responses: a rejection means data is missing and
    # somebody must fix the file, a warning means the row went in with a gap.
    rejected: list[str] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "representatives_created": self.created,
            "representatives_updated": self.updated,
            "representatives_unchanged": self.unchanged,
            "claims_created": self.claims_created,
            "claims_updated": self.claims_updated,
            "claims_left_alone_because_reviewed": self.claims_skipped_reviewed,
            "conflicts_needing_a_human": len(self.conflicts),
            "rows_rejected": len(self.rejected),
            "imported_with_warnings": len(self.warnings),
        }


def _validate(record: IncomingRepresentative) -> Optional[str]:
    """Why this row cannot be imported, or None."""
    if len(record.full_name) < 3:
        return f"name too short: {record.full_name!r}"
    if record.house not in VALID_HOUSES:
        return f"{record.full_name}: unknown house {record.house!r}"
    if record.state_code not in STATES_BY_CODE:
        return f"{record.full_name}: unknown state {record.state_code!r}"
    for claim in record.claims:
        definition = CLAIM_FIELDS_BY_KEY.get(claim.field_key)
        if definition is None:
            return f"{record.full_name}: unknown claim field {claim.field_key!r}"
        if definition.period_required and not claim.period:
            # The reason this is fatal rather than a warning: an undated asset or
            # case figure reads as current, and these fields set
            # period_required=True precisely so that cannot happen.
            return (
                f"{record.full_name}: {claim.field_key} needs a period "
                "(the affidavit or session it refers to) and the row has none"
            )
    return None


async def _ensure_party(session: AsyncSession, record: IncomingRepresentative) -> Optional[str]:
    """Match a party by code or name; create nothing.

    Deliberately does not invent party rows. Party codes appear on ballots and in
    the campaign pipeline, and an importer minting "BJP2" from a spelling variant
    in one spreadsheet would quietly fork a party's record in two.
    """
    if record.party_code:
        existing = (
            await session.execute(select(Party).where(Party.code == record.party_code))
        ).scalar_one_or_none()
        if existing is not None:
            return existing.code
    if record.party_name:
        existing = (
            await session.execute(select(Party).where(Party.name == record.party_name))
        ).scalar_one_or_none()
        if existing is not None:
            return existing.code
    return None


async def _resolve_constituency(
    session: AsyncSession, record: IncomingRepresentative, result: Result
) -> Optional[str]:
    """The seat code if it exists in the constituencies table, else None.

    `constituency_code` is a foreign key, so an unrecognised code does not
    degrade gracefully -- it aborts the whole transaction on the insert. That is
    the correct database behaviour and the wrong import behaviour: a members file
    routinely arrives before the seat roster for a new delimitation, and losing
    two hundred valid profiles because six seat codes are unknown helps nobody.

    So the profile is imported with the seat left unset and the code reported. It
    does NOT invent the constituency: a Constituency row carries a name, a type
    and a state, and a stub minted from a code column would be indistinguishable
    from a real seat everywhere else in the platform.
    """
    if not record.constituency_code:
        return None
    exists = (
        await session.execute(
            select(Constituency.code).where(Constituency.code == record.constituency_code)
        )
    ).scalar_one_or_none()
    if exists:
        return exists
    result.warnings.append(
        f"{record.full_name}: constituency {record.constituency_code!r} is not in the "
        "seat roster; profile imported without a seat"
    )
    return None


async def import_records(
    session: AsyncSession,
    records: Iterable[IncomingRepresentative],
    *,
    source: Source,
    source_url: str,
    publish: bool = False,
    dry_run: bool = False,
) -> Result:
    result = Result()
    is_primary, publisher = classify_source(source_url)
    today = date.today().isoformat()

    for record in records:
        problem = _validate(record)
        if problem:
            result.rejected.append(problem)
            continue

        existing = (
            await session.execute(
                select(Representative).where(Representative.slug == record.slug)
            )
        ).scalar_one_or_none()

        party_code = await _ensure_party(session, record)
        constituency_code = await _resolve_constituency(session, record, result)

        if existing is None:
            representative = Representative(
                full_name=record.full_name,
                name_hi=record.name_hi,
                slug=record.slug,
                house=record.house,
                state_code=record.state_code,
                constituency_code=constituency_code,
                party_code=party_code,
                term_start=record.term_start,
                is_sitting=record.is_sitting,
                office=record.office,
                official_email=record.official_email,
                official_page_url=record.official_page_url,
                source_url=source_url,
                source_title=source.source_title,
                # Draft unless the operator typed --publish. See rule 3.
                is_published=publish,
                updated_by=IMPORT_ACTOR.id,
            )
            if not dry_run:
                session.add(representative)
                await session.flush()
                await audit.record(
                    session,
                    actor=IMPORT_ACTOR,
                    action="create",
                    entity_type="representative",
                    entity_id=representative.slug,
                    summary=f"Imported from {source.label}",
                    source_url=source_url,
                    is_public=True,
                )
            result.created += 1
        else:
            representative = existing
            # Only fill gaps. An importer that overwrites a field a researcher
            # corrected by hand turns every correction into a race with the next
            # import run.
            changed = False
            for attribute, incoming in (
                ("name_hi", record.name_hi),
                ("office", record.office),
                ("official_email", record.official_email),
                ("official_page_url", record.official_page_url),
                ("constituency_code", constituency_code),
                ("party_code", party_code),
            ):
                if incoming and not getattr(representative, attribute):
                    if not dry_run:
                        setattr(representative, attribute, incoming)
                    changed = True
            if changed:
                result.updated += 1
            else:
                result.unchanged += 1

        if dry_run and existing is None:
            # Nothing was flushed, so there is no id to hang claims off. The
            # counts below would be guesses; report the claims as pending instead.
            result.claims_created += len(record.claims)
            continue

        for claim in record.claims:
            await _upsert_claim(
                session,
                representative=representative,
                claim=claim,
                source=source,
                source_url=source_url,
                is_primary=is_primary,
                publisher=publisher or "",
                source_date=today,
                result=result,
                dry_run=dry_run,
            )

        if not dry_run:
            await search.index(
                session,
                entity_type="representative",
                entity_id=representative.slug,
                title=representative.full_name,
                subtitle=f"{representative.house} - {representative.state_code}",
                body=representative.office,
                keywords=[representative.state_code, representative.party_code or ""],
                is_published=representative.is_published,
                url_path=f"/representatives/{representative.slug}",
            )

    return result


async def _upsert_claim(
    session: AsyncSession,
    *,
    representative: Representative,
    claim: IncomingClaim,
    source: Source,
    source_url: str,
    is_primary: bool,
    publisher: str,
    source_date: str,
    result: Result,
    dry_run: bool,
) -> None:
    definition = CLAIM_FIELDS_BY_KEY[claim.field_key]

    # requires_primary is a legal control, not a preference: for these fields the
    # platform's defence is "this is what the public record says", and a news
    # report about an affidavit is not the affidavit.
    if definition.requires_primary and not is_primary:
        result.rejected.append(
            f"{representative.full_name}: {claim.field_key} needs a primary source; "
            f"{source_url} classifies as secondary"
        )
        return

    existing = (
        await session.execute(
            select(RepresentativeClaim).where(
                RepresentativeClaim.representative_id == representative.id,
                RepresentativeClaim.field_key == claim.field_key,
                RepresentativeClaim.period == claim.period,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        same = (
            existing.value_number == claim.value_number
            and existing.value_text == claim.value_text
        )
        if same:
            return
        if existing.verification_status != VerificationStatus.UNVERIFIED.value:
            # Rule 2. A human has ruled on this figure; the importer reports the
            # disagreement and changes nothing.
            result.claims_skipped_reviewed += 1
            result.conflicts.append(
                f"{representative.full_name} [{claim.field_key} {claim.period}]: "
                f"stored {existing.value_number or existing.value_text!r} "
                f"({existing.verification_status}) != incoming "
                f"{claim.value_number or claim.value_text!r} -- left as is"
            )
            return
        if not dry_run:
            existing.value_number = claim.value_number
            existing.value_text = claim.value_text
            existing.source_url = source_url
            existing.source_title = source.source_title
            existing.source_date = source_date
            existing.source_publisher = publisher
            existing.source_is_primary = is_primary
        result.claims_updated += 1
        return

    if not dry_run:
        session.add(
            RepresentativeClaim(
                representative_id=representative.id,
                field_key=claim.field_key,
                period=claim.period,
                value_number=claim.value_number,
                value_text=claim.value_text,
                source_url=source_url,
                source_title=source.source_title,
                source_date=source_date,
                source_publisher=publisher,
                source_is_primary=is_primary,
                # Rule 1. Not a parameter, and there is no flag to change it.
                verification_status=VerificationStatus.UNVERIFIED.value,
                submitted_by=IMPORT_ACTOR.id,
            )
        )
    result.claims_created += 1


# ==========================================================================
# Entry point
# ==========================================================================
def _read_input(path: Optional[str], url: Optional[str]) -> str:
    if path:
        return pathlib.Path(path).read_text(encoding="utf-8")
    try:
        import httpx
    except ImportError:  # pragma: no cover
        raise SystemExit("--url needs httpx installed (pip install httpx)")
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def _run(args) -> None:
    source = SOURCES[args.source]
    text = _read_input(args.file, args.url)
    total_rows = len(_rows(text))
    records = source.parse(text)
    if not records:
        raise SystemExit("No usable rows found. Check the column headings against the adapter.")

    # An adapter drops any row it cannot identify -- no name, no recognisable
    # state. Reporting the count matters more than it looks: the usual cause is a
    # renamed column in a new release of the same dataset, and the symptom of that
    # is a quiet, partial import that nobody notices until a profile is missing.
    unreadable = total_rows - len(records)

    source_url = args.source_url or args.url or source.source_url

    async with database.transaction() as session:
        result = await import_records(
            session,
            records,
            source=source,
            source_url=source_url,
            publish=args.publish,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            # Nothing should reach the database on a dry run, and rolling back
            # explicitly is cheaper than trusting every branch above to have
            # honoured the flag.
            await session.rollback()

    print(f"\n{'DRY RUN - nothing was written' if args.dry_run else 'Imported'}")
    print(f"Source: {source.label}\nCitation: {source_url}\n")
    print(f"  {'rows in file':38} {total_rows}")
    for key, value in result.as_dict().items():
        print(f"  {key:38} {value}")

    if unreadable:
        print(
            f"\n  {unreadable} row(s) had no usable name or state and were skipped by the "
            f"adapter.\n  If that number is unexpected, the file's column headings have "
            f"probably changed."
        )

    if result.rejected:
        print(f"\nNOT imported ({len(result.rejected)}):")
        for line in result.rejected[:20]:
            print(f"  - {line}")
        if len(result.rejected) > 20:
            print(f"  ... and {len(result.rejected) - 20} more")

    if result.warnings:
        print(f"\nImported, with a gap worth knowing about ({len(result.warnings)}):")
        for line in result.warnings[:20]:
            print(f"  - {line}")
        if len(result.warnings) > 20:
            print(f"  ... and {len(result.warnings) - 20} more")

    if result.conflicts:
        print(f"\nConflicts with reviewed claims ({len(result.conflicts)}) - NOT overwritten:")
        for line in result.conflicts[:20]:
            print(f"  - {line}")

    if not args.dry_run:
        print(
            "\nEvery imported claim is UNVERIFIED and renders with a 'pending citation "
            "review' marker.\nA Fact Checker must follow the source before any of it "
            "reads as established fact."
        )
        if not args.publish:
            print("New profiles were created as drafts. Publish them from the admin API.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import representatives and sourced claims from open government data.",
        epilog="Prefers official open-data downloads to scraping - see the module docstring.",
    )
    parser.add_argument("--source", choices=sorted(SOURCES), help="which dataset this file is")
    parser.add_argument("--file", help="path to a downloaded CSV or JSON file")
    parser.add_argument("--url", help="HTTPS URL of a published dataset to fetch")
    parser.add_argument(
        "--source-url",
        help="citation URL recorded on every row (defaults to --url, else the source's own page)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish new profiles instead of creating them as drafts",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would change")
    parser.add_argument("--list-sources", action="store_true", help="list the supported datasets")
    args = parser.parse_args()

    if args.list_sources:
        for source in SOURCES.values():
            print(f"\n  {source.key}\n    {source.label}\n    {source.source_url}")
            if source.notes:
                print(f"    {source.notes}")
        return

    if not args.source or not (args.file or args.url):
        raise SystemExit("--source and one of --file / --url are required (or --list-sources)")

    if not config.postgres_enabled():
        raise SystemExit("DATABASE_URL is not set; there is nothing to import into.")

    asyncio.run(_run(args))
    asyncio.run(database.dispose())


if __name__ == "__main__":
    main()
