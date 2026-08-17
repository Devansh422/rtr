"""Load, inspect and purge the demo dataset.

    python -m backend.scripts.load_demo --status
    python -m backend.scripts.load_demo --load
    python -m backend.scripts.load_demo --purge

Read backend/content/demo/README.md before running --load anywhere public. Short
version: this platform publishes claims about named people, and fabricated data on a
live accountability site is the exact failure its controls exist to prevent. Every
record here is marked so it cannot be mistaken for real data, and --purge removes all
of it.

WHY THIS IS NOT PART OF SEEDING. `backend/seed_modules.py` runs on every cold start
and its content is reference data — the states of India, the text of the Constitution.
This is fabricated. It shares no code path with seeding and nothing in the deploy
pipeline calls it, so it can only exist if somebody ran this command deliberately.

HOW IT WRITES. Through the ORM, but also calling `audit.record` and `search.index` the
way the routers do. Writing straight to the tables would be shorter and would leave
every demo profile with an empty history tab and nothing in search — which would
undemo two of the features this dataset exists to demonstrate.

HOW PURGE FINDS ITS OWN RECORDS. By the markers listed in the README and by nothing
else: the `demo-` slug prefix, the `DMO` party prefix, the `@demo.rtr.invalid` email
domain. Real records cannot collide with any of them. State campaign stages are the
one thing modified rather than created, so the loader stores each state's previous
values in `platform_meta` and --purge restores them exactly.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
import argparse
import asyncio
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from backend.core import audit, certificates, config, db as database, search  # noqa: E402
from backend.core.citations import VerificationStatus, classify_source  # noqa: E402
from backend.core.models import (  # noqa: E402
    Certificate,
    Citizen,
    District,
    PlatformMeta,
    State,
    utcnow,
)
from backend.core.mongo import db as mongo_db  # noqa: E402
from backend.core.rbac import Principal  # noqa: E402
from backend.core.security import hash_password  # noqa: E402
from backend.modules.academy.models import Course, Enrollment, Lesson, Quiz  # noqa: E402
from backend.modules.corrections.models import Correction, CorrectionStatus  # noqa: E402
from backend.modules.events.models import (  # noqa: E402
    Event,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from backend.modules.forum.models import ForumReply, ForumThread, PostStatus  # noqa: E402
from backend.modules.manifesto.models import (  # noqa: E402
    GovernmentDocument,
    Manifesto,
    ManifestoElection,
    ManifestoPromise,
    PromiseAssessment,
    PromiseEvidence,
    RtiApplication,
    RtiQuestion,
    RtiResponse,
)
from backend.modules.petitions.models import (  # noqa: E402
    Petition,
    PetitionSignature,
    milestones_reached,
)
from backend.modules.reports.models import CitizenReport, ReportStatus  # noqa: E402
from backend.modules.representatives.fields import CLAIM_FIELDS_BY_KEY  # noqa: E402
from backend.modules.representatives.models import (  # noqa: E402
    Constituency,
    Party,
    Promise,
    Representative,
    RepresentativeClaim,
)
from backend.modules.research.models import ResearchDocument  # noqa: E402
from backend.modules.tools.models import DocumentTemplate  # noqa: E402
from backend.modules.volunteers.models import (  # noqa: E402
    AssignmentStatus,
    TaskAssignment,
    TaskStatus,
    VolunteerProfile,
    VolunteerTask,
)

DEMO_DIR = config.BACKEND_DIR / "content" / "demo"

SLUG_PREFIX = "demo-"
PARTY_PREFIX = "DMO"
# RFC 2606 reserves example.com for documentation and IANA holds it, so nothing
# here can ever reach a real inbox -- the same guarantee `.invalid` gave.
#
# It is example.com rather than `.invalid` because `.invalid` cost us the one
# feature this dataset promises: `email-validator`, behind pydantic's EmailStr,
# rejects special-use TLDs outright, so every demo member login documented in
# the README failed at validation with a 422 before it ever reached the password
# check. Relaxing EmailStr on the login endpoint to accommodate fixture data
# would have been the wrong trade -- the address format is worth validating on a
# real endpoint, and the fixture is the part that should bend.
EMAIL_DOMAIN = "demo-rtr.example.com"
# One shared access code across every demo member, printed by --load so it can be
# handed to whoever is testing. Valid format for the member login (XXXX-XXXX, no
# confusable characters).
ACCESS_CODE = "DEMO-USER"
STATE_BACKUP_KEY = "demo_state_backup"

# The actor recorded against demo audit entries. Not a real staff account, so the
# history tab shows a name that is obviously part of the dataset.
DEMO_ACTOR = Principal(
    id="demo-loader",
    email="demo-loader@demo.rtr.invalid",
    name="Demo data loader",
    permissions=frozenset(),
)


def _load(name: str) -> dict:
    with open(DEMO_DIR / f"{name}.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def _citation(url: str, label: str) -> dict:
    """A demo citation whose TITLE carries the warning.

    The title is what renders next to the figure on a profile, so putting the marker
    there means a reader sees it exactly where they are looking at the number.
    """
    is_primary, publisher = classify_source(url)
    return {
        "url": url,
        "title": f"DEMO RECORD - not a real source: {label}",
        "publisher": publisher or "Demo",
        "is_primary": is_primary,
    }


def _demo_source(path: str) -> str:
    """A source URL that classifies as a primary public record but resolves nowhere.

    A subdomain of a genuinely official domain, so `classify_source` treats it the way
    it would treat the real thing and the high-risk claim gate can be demonstrated.
    The host does not exist, so clicking the link fails — which is correct behaviour
    for evidence that does not exist.
    """
    return f"https://demo.data.gov.in/records/{path}"


def _email(handle: str) -> str:
    return f"{handle}@{EMAIL_DOMAIN}"


async def _mongo_reachable() -> bool:
    """One short probe, rather than letting every insert wait out the default timeout.

    Member sign-in is the only part of this dataset that needs Mongo. Without the
    probe, fourteen inserts against an unreachable server each block for the driver's
    30-second server-selection timeout, and a command that should take two seconds
    takes seven minutes before reporting the same thing.
    """
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        probe = AsyncIOMotorClient(config.MONGO_URL, serverSelectionTimeoutMS=1500)
        await probe.admin.command("ping")
        probe.close()
        return True
    except Exception:
        return False


# ==========================================================================
# Load
# ==========================================================================
async def load_reference(session: AsyncSession) -> dict:
    data = _load("reference")
    counts = {"states": 0, "parties": 0, "constituencies": 0}

    # --- States: modify, and back up what was there so purge can restore it ---
    backup = {}
    for spec in data["states"]:
        row = (
            await session.execute(select(State).where(State.code == spec["code"]))
        ).scalar_one_or_none()
        if row is None:
            continue
        backup[row.code] = {
            "stage": row.campaign_stage,
            "note": row.campaign_note,
            "source_url": row.campaign_source_url,
            "updated_at": row.campaign_updated_at.isoformat() if row.campaign_updated_at else None,
        }
        row.campaign_stage = spec["stage"]
        row.campaign_note = spec["note"]
        row.campaign_source_url = spec["source_url"]
        row.campaign_updated_at = utcnow()

        await audit.record(
            session,
            actor=DEMO_ACTOR,
            action="campaign_stage",
            entity_type="state",
            entity_id=row.code,
            summary=f"DEMO: {row.name} moved to {spec['stage'].replace('_', ' ')}",
            changes={"stage": {"before": backup[row.code]["stage"], "after": spec["stage"]}},
            source_url=spec["source_url"],
            is_public=True,
        )
        counts["states"] += 1

    existing_backup = (
        await session.execute(select(PlatformMeta).where(PlatformMeta.key == STATE_BACKUP_KEY))
    ).scalar_one_or_none()
    if existing_backup is None:
        session.add(PlatformMeta(key=STATE_BACKUP_KEY, value=json.dumps(backup)))
    # If a backup already exists a previous load was not purged; keep the ORIGINAL
    # one, or purge would restore demo values as if they were real.

    # --- Parties ---
    for spec in data["parties"]:
        if (
            await session.execute(select(Party).where(Party.code == spec["code"]))
        ).scalar_one_or_none():
            continue
        session.add(
            Party(
                code=spec["code"],
                name=spec["name"],
                name_hi=spec.get("name_hi", ""),
                eci_status=spec.get("eci_status", "registered_unrecognised"),
                founded_year=spec.get("founded_year"),
                source_url="https://demo.rtr.invalid/parties",
            )
        )
        counts["parties"] += 1

    # --- Constituencies ---
    prefixes = {"lok_sabha": "LS", "assembly": "AC", "rajya_sabha": "RS", "council": "MLC"}
    for spec in data["constituencies"]:
        code = f"{spec['state']}-{prefixes[spec['house']]}-{spec['number']:03d}"
        if (
            await session.execute(select(Constituency).where(Constituency.code == code))
        ).scalar_one_or_none():
            continue
        session.add(
            Constituency(
                code=code,
                state_code=spec["state"],
                district_code=spec.get("district"),
                house=spec["house"],
                number=spec["number"],
                name=spec["name"],
                name_hi=spec.get("name_hi", ""),
                slug=f"{SLUG_PREFIX}{spec['name'].lower().replace(' ', '-')}",
                reserved_for=spec.get("reserved_for"),
                electors=spec.get("electors"),
                source_url=_demo_source("delimitation-order"),
            )
        )
        counts["constituencies"] += 1

    await session.flush()
    return counts


async def load_accountability(session: AsyncSession) -> dict:
    data = _load("accountability")
    counts = {"representatives": 0, "claims": 0, "promises": 0}
    by_slug: dict[str, Representative] = {}

    for spec in data["representatives"]:
        if (
            await session.execute(select(Representative).where(Representative.slug == spec["slug"]))
        ).scalar_one_or_none():
            continue

        rep = Representative(
            full_name=spec["full_name"],
            name_hi=spec.get("name_hi", ""),
            slug=spec["slug"],
            house=spec["house"],
            state_code=spec["state"],
            constituency_code=spec.get("constituency"),
            party_code=spec.get("party"),
            term_start=date.fromisoformat(spec["term_start"]) if spec.get("term_start") else None,
            is_sitting=spec.get("is_sitting", True),
            office=spec.get("office", ""),
            official_email=spec.get("official_email", ""),
            office_address=spec.get("office_address", ""),
            official_page_url=spec.get("official_page_url", ""),
            source_url=_demo_source(f"member-record-{spec['slug']}"),
            source_title="DEMO RECORD - not a real source: House member record",
            is_published=spec.get("published", False),
            published_at=utcnow() if spec.get("published") else None,
            updated_by=DEMO_ACTOR.id,
        )
        session.add(rep)
        await session.flush()
        by_slug[spec["slug"]] = rep
        counts["representatives"] += 1

        await audit.record(
            session,
            actor=DEMO_ACTOR,
            action="create",
            entity_type="representative",
            entity_id=rep.slug,
            summary=f"DEMO: created profile for {rep.full_name}",
            source_url=rep.source_url,
            is_public=True,
        )

        for claim_spec in spec.get("claims", []):
            definition = CLAIM_FIELDS_BY_KEY.get(claim_spec["field"])
            if definition is None:
                continue
            citation = _citation(
                _demo_source(f"{claim_spec['field'].replace('.', '-')}-{spec['slug']}"),
                definition.label.lower(),
            )
            status = claim_spec.get("status", VerificationStatus.UNVERIFIED.value)
            claim = RepresentativeClaim(
                representative_id=rep.id,
                field_key=claim_spec["field"],
                period=claim_spec.get("period", ""),
                value_number=claim_spec.get("number"),
                value_text=claim_spec.get("text", ""),
                source_url=citation["url"],
                source_title=citation["title"],
                source_date=claim_spec.get("source_date", "2025"),
                source_publisher=citation["publisher"],
                source_is_primary=citation["is_primary"],
                verification_status=status,
                review_note=claim_spec.get("review_note", ""),
                submitted_by=DEMO_ACTOR.id,
                reviewed_by=(
                    "demo-fact-checker"
                    if status != VerificationStatus.UNVERIFIED.value
                    else None
                ),
                reviewed_at=utcnow() if status != VerificationStatus.UNVERIFIED.value else None,
            )
            session.add(claim)
            counts["claims"] += 1

            await audit.record(
                session,
                actor=DEMO_ACTOR,
                action="claim_create",
                entity_type="representative",
                entity_id=rep.slug,
                summary=f"DEMO: {definition.label} recorded for {rep.full_name}",
                changes={
                    "value": {
                        "before": None,
                        "after": claim_spec.get("number", claim_spec.get("text")),
                    }
                },
                source_url=citation["url"],
                is_public=True,
            )

        await session.flush()
        parties = {rep.party_code} if rep.party_code else set()
        party = (
            (await session.execute(select(Party).where(Party.code.in_(parties)))).scalar_one_or_none()
            if parties
            else None
        )
        await search.index(
            session,
            entity_type="representative",
            entity_id=rep.slug,
            title=rep.full_name,
            subtitle=f"{'MP' if rep.house == 'lok_sabha' else 'MLA'}"
            + (f" - {rep.office}" if rep.office else ""),
            body=f"{rep.name_hi} {party.name if party else ''} {rep.office}",
            keywords=[rep.state_code, rep.house, rep.party_code or "", rep.constituency_code or ""],
            state_code=rep.state_code,
            is_published=rep.is_published,
            url_path=f"/representatives/{rep.slug}",
        )

    # --- Promises ---
    for spec in data["promises"]:
        if (
            await session.execute(select(Promise).where(Promise.slug == spec["slug"]))
        ).scalar_one_or_none():
            continue
        rep = by_slug.get(spec.get("representative", ""))
        citation = _citation(_demo_source(f"promise-{spec['slug']}"), "the commitment as made")
        status_source = (
            _demo_source(f"promise-status-{spec['slug']}") if spec.get("status_note") else ""
        )
        promise = Promise(
            slug=spec["slug"],
            representative_id=rep.id if rep else None,
            party_code=spec.get("party"),
            state_code=spec.get("state"),
            title=spec["title"],
            promise_text=spec["promise_text"],
            category=spec.get("category", "general"),
            made_on=date.fromisoformat(spec["made_on"]) if spec.get("made_on") else None,
            made_context=spec.get("made_context", ""),
            deadline=date.fromisoformat(spec["deadline"]) if spec.get("deadline") else None,
            source_url=citation["url"],
            source_title=citation["title"],
            status=spec.get("status", "promised"),
            status_note=spec.get("status_note", ""),
            status_source_url=status_source,
            status_updated_at=utcnow() if spec.get("status_note") else None,
            verification_status=(
                VerificationStatus.FACT_CHECKED.value
                if spec.get("published")
                else VerificationStatus.UNVERIFIED.value
            ),
            evidence=[{"url": citation["url"], "title": citation["title"]}],
            is_published=spec.get("published", False),
            updated_by=DEMO_ACTOR.id,
        )
        session.add(promise)
        await session.flush()
        counts["promises"] += 1

        await audit.record(
            session,
            actor=DEMO_ACTOR,
            action="create",
            entity_type="promise",
            entity_id=promise.slug,
            summary=f"DEMO: logged promise '{promise.title}'",
            source_url=citation["url"],
            is_public=True,
        )
        await search.index(
            session,
            entity_type="promise",
            entity_id=promise.slug,
            title=promise.title,
            subtitle=f"Promise - {promise.status.replace('_', ' ')}",
            body=promise.promise_text,
            keywords=[promise.category, promise.party_code or "", promise.state_code or ""],
            state_code=promise.state_code,
            is_published=promise.is_published,
            url_path=f"/promises/{promise.slug}",
        )

    return counts


async def load_community(session: AsyncSession) -> dict:
    data = _load("community")
    mongo_up = await _mongo_reachable()
    counts: dict = {"citizens": 0, "petitions": 0, "signatures": 0, "reports": 0, "threads": 0, "replies": 0, "corrections": 0}
    citizens: dict[str, Citizen] = {}

    # --- Members ---
    for spec in data["citizens"]:
        email = _email(spec["handle"])
        row = (
            await session.execute(select(Citizen).where(Citizen.email == email))
        ).scalar_one_or_none()
        if row is None:
            row = Citizen(
                email=email,
                display_name=spec["display_name"],
                state_code=spec.get("state"),
                reputation=spec.get("reputation", 0),
                contributions={"demo": True},
            )
            session.add(row)
            await session.flush()
            counts["citizens"] += 1
        citizens[spec["handle"]] = row

        # Matching Mongo supporter record so the account can actually sign in at
        # /login and the member-only flows can be walked through.
        #
        # Best-effort: member sign-in is the only thing that needs Mongo, and the
        # rest of the dataset is worth loading without it. A local machine with no
        # Mongo still gets every page populated; only "log in as citizen1" is lost,
        # and the warning below says so.
        if not mongo_up:
            counts.setdefault("login_setup_failed", "MongoDB unreachable")
            continue
        try:
            if not await mongo_db.supporters.find_one({"email": email}):
                await mongo_db.supporters.insert_one(
                    {
                        "id": f"demo-{spec['handle']}",
                        "movement_id": f"RTR-DEMO-{spec['handle'][-3:].upper()}",
                        "name": spec["display_name"],
                        "email": email,
                        "state": spec.get("state", ""),
                        "city": "",
                        "mobile": None,
                        "pledge": True,
                        "access_code_hash": hash_password(ACCESS_CODE),
                        "created_at": utcnow().isoformat(),
                        "is_demo": True,
                    }
                )
                counts["logins"] = counts.get("logins", 0) + 1
        except Exception as e:
            counts.setdefault("login_setup_failed", str(e)[:60])

    # --- Petitions and signatures ---
    for spec in data["petitions"]:
        if (
            await session.execute(select(Petition).where(Petition.slug == spec["slug"]))
        ).scalar_one_or_none():
            continue
        author = citizens.get(spec.get("author", ""))
        petition = Petition(
            slug=spec["slug"],
            title=spec["title"],
            summary=spec["summary"],
            body=spec["body"],
            addressed_to=spec["addressed_to"],
            state_code=spec.get("state"),
            category=spec.get("category", "right-to-recall"),
            target_signatures=spec.get("target", 1000),
            citizen_id=author.id if author else None,
            is_official=spec.get("official", False),
            status=spec.get("status", "open"),
            status_note=spec.get("status_note", ""),
            outcome_source_url=spec.get("outcome_source_url", ""),
            closes_at=utcnow() + timedelta(days=75),
            reviewed_by=DEMO_ACTOR.id,
        )
        session.add(petition)
        await session.flush()
        counts["petitions"] += 1

        for signature in spec.get("signatures", []):
            citizen = citizens.get(signature["citizen"])
            if citizen is None:
                continue
            session.add(
                PetitionSignature(
                    petition_id=petition.id,
                    citizen_id=citizen.id,
                    display_name=citizen.display_name,
                    state_code=citizen.state_code,
                    comment=signature.get("comment", ""),
                    is_public=signature.get("public", False),
                )
            )
            counts["signatures"] += 1

        await session.flush()
        petition.signature_count = (
            await session.execute(
                select(func.count())
                .select_from(PetitionSignature)
                .where(PetitionSignature.petition_id == petition.id)
            )
        ).scalar_one()
        petition.milestones = [
            {"count": m, "reachedAt": (utcnow() - timedelta(days=7)).isoformat()}
            for m in milestones_reached(petition.signature_count)
        ]

        await search.index(
            session,
            entity_type="petition",
            entity_id=petition.slug,
            title=petition.title,
            subtitle=f"Petition to {petition.addressed_to}",
            body=petition.summary,
            keywords=[petition.category, petition.state_code or ""],
            state_code=petition.state_code,
            url_path=f"/petitions/{petition.slug}",
        )

    # --- Citizen reports ---
    for spec in data["reports"]:
        if (
            await session.execute(select(CitizenReport).where(CitizenReport.slug == spec["slug"]))
        ).scalar_one_or_none():
            continue
        citizen = citizens.get(spec["citizen"])
        if citizen is None:
            continue
        status = spec.get("status", ReportStatus.PUBLISHED)
        report = CitizenReport(
            slug=spec["slug"],
            citizen_id=citizen.id,
            show_author=spec.get("show_author", False),
            title=spec["title"],
            body=spec["body"],
            service=spec["service"],
            state_code=spec["state"],
            district_code=spec.get("district"),
            constituency_code=spec.get("constituency"),
            locality=spec.get("locality", ""),
            rating=spec.get("rating"),
            evidence=[],
            status=status,
            verification_note=spec.get("verification_note", ""),
            verified_by=DEMO_ACTOR.id,
            verified_at=utcnow() - timedelta(days=4),
            response_text=spec.get("response_text", ""),
            response_from=spec.get("response_from", ""),
            response_source_url=spec.get("response_source_url", ""),
            response_at=utcnow() - timedelta(days=2) if spec.get("response_text") else None,
        )
        session.add(report)
        counts["reports"] += 1

        await search.index(
            session,
            entity_type="report",
            entity_id=report.slug,
            title=report.title,
            subtitle=f"Citizen report - {report.service}",
            body=report.body,
            keywords=[report.service, report.state_code, report.locality],
            state_code=report.state_code,
            url_path=f"/reports/{report.slug}",
        )

    # --- Forum ---
    for spec in data["forum"]:
        if (
            await session.execute(select(ForumThread).where(ForumThread.slug == spec["slug"]))
        ).scalar_one_or_none():
            continue
        citizen = citizens.get(spec["citizen"])
        if citizen is None:
            continue
        replies = spec.get("replies", [])
        thread = ForumThread(
            slug=spec["slug"],
            category_key=spec["category"],
            citizen_id=citizen.id,
            title=spec["title"],
            body=spec["body"],
            state_code=spec.get("state"),
            status=PostStatus.PUBLISHED,
            reply_count=len(replies),
            upvotes=spec.get("upvotes", 0),
            last_activity_at=utcnow() - timedelta(hours=6),
        )
        session.add(thread)
        await session.flush()
        counts["threads"] += 1

        for index, reply_spec in enumerate(replies):
            reply_citizen = citizens.get(reply_spec["citizen"])
            if reply_citizen is None:
                continue
            session.add(
                ForumReply(
                    thread_id=thread.id,
                    citizen_id=reply_citizen.id,
                    body=reply_spec["body"],
                    status=PostStatus.PUBLISHED,
                    upvotes=reply_spec.get("upvotes", 0),
                    created_at=utcnow() - timedelta(hours=24 - index * 3),
                )
            )
            counts["replies"] += 1

    # --- Corrections ---
    for spec in data["corrections"]:
        citizen = citizens.get(spec.get("citizen", ""))
        status = spec.get("status", CorrectionStatus.OPEN)
        resolved = status in (
            CorrectionStatus.ACCEPTED,
            CorrectionStatus.REJECTED,
            CorrectionStatus.DUPLICATE,
        )
        session.add(
            Correction(
                entity_type=spec["entity_type"],
                entity_id=spec["entity_id"],
                field_key=spec.get("field_key", ""),
                summary=spec["summary"],
                detail=spec.get("detail", ""),
                proposed_value=spec.get("proposed_value", ""),
                source_url=spec.get("source_url", ""),
                source_title=spec.get("source_title", ""),
                citizen_id=citizen.id if citizen else None,
                contact_email=citizen.email if citizen else "",
                status=status,
                resolution_note=spec.get("resolution_note", ""),
                reviewed_by=DEMO_ACTOR.id if resolved else None,
                reviewed_at=utcnow() - timedelta(days=3) if resolved else None,
            )
        )
        counts["corrections"] += 1

    await session.flush()
    return counts


async def load_participation(session: AsyncSession) -> dict:
    data = _load("participation")
    counts = {"events": 0, "registrations": 0, "attended": 0, "profiles": 0, "tasks": 0, "assignments": 0, "certificates": 0}

    citizens = {
        row.email.split("@")[0]: row
        for row in (
            await session.execute(
                select(Citizen).where(Citizen.email.like(f"%@{EMAIL_DOMAIN}"))
            )
        ).scalars()
    }

    # --- Events ---
    for spec in data["events"]:
        if (await session.execute(select(Event).where(Event.slug == spec["slug"]))).scalar_one_or_none():
            continue
        # Offsets rather than fixed dates, so "upcoming" and "past" are both populated
        # regardless of when this is run.
        starts = utcnow() + timedelta(days=spec["days_from_now"])
        is_past = spec["days_from_now"] < 0
        event = Event(
            slug=spec["slug"],
            title=spec["title"],
            title_hi=spec.get("title_hi", ""),
            description=spec.get("description", ""),
            kind=spec.get("kind", "workshop"),
            state_code=spec.get("state"),
            district_code=spec.get("district"),
            is_online=spec.get("is_online", False),
            venue=spec.get("venue", ""),
            address=spec.get("address", ""),
            meeting_url=spec.get("meeting_url", ""),
            starts_at=starts,
            ends_at=starts + timedelta(hours=spec.get("duration_hours", 2)),
            capacity=spec.get("capacity"),
            organiser_name=spec.get("organiser_name", ""),
            organiser_contact=spec.get("organiser_contact", ""),
            status=EventStatus.COMPLETED if is_past else EventStatus.PUBLISHED,
            created_by=DEMO_ACTOR.id,
        )
        session.add(event)
        await session.flush()
        counts["events"] += 1

        for registration_spec in spec.get("registrations", []):
            citizen = citizens.get(registration_spec["citizen"])
            if citizen is None:
                continue
            attended = registration_spec.get("attended", False)
            session.add(
                EventRegistration(
                    event_id=event.id,
                    citizen_id=citizen.id,
                    ticket_code=certificates.new_code("TKT"),
                    name_snapshot=citizen.display_name,
                    status=RegistrationStatus.ATTENDED if attended else RegistrationStatus.REGISTERED,
                    checked_in_at=starts if attended else None,
                    checked_in_by=DEMO_ACTOR.id if attended else None,
                )
            )
            counts["registrations"] += 1
            if attended:
                counts["attended"] += 1
                issued = await certificates.issue(
                    session,
                    kind="event_attendance",
                    holder_name=citizen.display_name,
                    title=f"For attending {event.title}",
                    detail={
                        "Event": event.title,
                        "Date": starts.date().isoformat(),
                        "Venue": "Online" if event.is_online else (event.venue or "-"),
                        "eventSlug": event.slug,
                    },
                    citizen_id=citizen.id,
                    holder_email=citizen.email,
                    issued_by=DEMO_ACTOR.id,
                )
                counts["certificates"] += 1

        await session.flush()
        event.registration_count = len(spec.get("registrations", []))
        event.attended_count = sum(1 for r in spec.get("registrations", []) if r.get("attended"))

        await search.index(
            session,
            entity_type="event",
            entity_id=event.slug,
            title=event.title,
            subtitle=f"{event.kind} - {starts.date().isoformat()}",
            body=event.description,
            keywords=[event.kind, event.state_code or "", event.venue],
            state_code=event.state_code,
            is_published=not is_past,
            url_path=f"/events/{event.slug}",
        )

    # --- Volunteer profiles ---
    profiles: dict[str, VolunteerProfile] = {}
    for spec in data["volunteer_profiles"]:
        citizen = citizens.get(spec["citizen"])
        if citizen is None:
            continue
        existing = (
            await session.execute(
                select(VolunteerProfile).where(VolunteerProfile.citizen_id == citizen.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            profiles[spec["citizen"]] = existing
            continue
        profile = VolunteerProfile(
            citizen_id=citizen.id,
            skills=spec.get("skills", []),
            languages=spec.get("languages", []),
            hours_per_week=spec.get("hours_per_week"),
            state_code=spec.get("state"),
            city=spec.get("city", ""),
            bio=spec.get("bio", ""),
        )
        session.add(profile)
        await session.flush()
        profiles[spec["citizen"]] = profile
        counts["profiles"] += 1

    # --- Tasks ---
    tasks: dict[str, VolunteerTask] = {}
    for spec in data["tasks"]:
        existing = (
            await session.execute(select(VolunteerTask).where(VolunteerTask.slug == spec["slug"]))
        ).scalar_one_or_none()
        if existing is not None:
            tasks[spec["slug"]] = existing
            continue
        task = VolunteerTask(
            slug=spec["slug"],
            title=spec["title"],
            description=spec["description"],
            skill=spec["skill"],
            acceptance_criteria=spec.get("acceptance_criteria", ""),
            state_code=spec.get("state"),
            is_remote=spec.get("is_remote", True),
            estimated_hours=spec.get("estimated_hours", 1),
            capacity=spec.get("capacity", 1),
            due_on=(date.today() + timedelta(days=spec["due_in_days"])) if spec.get("due_in_days") else None,
            created_by=DEMO_ACTOR.id,
        )
        session.add(task)
        await session.flush()
        tasks[spec["slug"]] = task
        counts["tasks"] += 1

    # --- Assignments ---
    for spec in data["assignments"]:
        task = tasks.get(spec["task"])
        profile = profiles.get(spec["citizen"])
        if task is None or profile is None:
            continue
        existing = (
            await session.execute(
                select(TaskAssignment).where(
                    TaskAssignment.task_id == task.id, TaskAssignment.profile_id == profile.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        status = spec.get("status", AssignmentStatus.CLAIMED)
        verified = status == AssignmentStatus.VERIFIED
        session.add(
            TaskAssignment(
                task_id=task.id,
                profile_id=profile.id,
                status=status,
                submission_note=spec.get("note", ""),
                submission_url=spec.get("url", ""),
                hours_claimed=spec.get("hours_claimed", 0),
                hours_verified=spec.get("hours_verified", 0) if verified else 0,
                review_note=spec.get("review_note", ""),
                verified_by=DEMO_ACTOR.id if status in (AssignmentStatus.VERIFIED, AssignmentStatus.RETURNED) else None,
                verified_at=utcnow() - timedelta(days=5)
                if status in (AssignmentStatus.VERIFIED, AssignmentStatus.RETURNED)
                else None,
            )
        )
        counts["assignments"] += 1

    await session.flush()

    # Recompute the denormalised counters the same way the routers do, rather than
    # trusting the numbers in the JSON.
    for profile in profiles.values():
        totals = (
            await session.execute(
                select(func.coalesce(func.sum(TaskAssignment.hours_verified), 0.0), func.count())
                .select_from(TaskAssignment)
                .where(
                    TaskAssignment.profile_id == profile.id,
                    TaskAssignment.status == AssignmentStatus.VERIFIED,
                )
            )
        ).one()
        profile.verified_hours = float(totals[0] or 0.0)
        profile.completed_tasks = int(totals[1] or 0)

    for task in tasks.values():
        task.claimed_count = (
            await session.execute(
                select(func.count())
                .select_from(TaskAssignment)
                .where(TaskAssignment.task_id == task.id)
            )
        ).scalar_one()
        task.status = TaskStatus.FULL if task.claimed_count >= task.capacity else TaskStatus.OPEN

    return counts


async def load_library(session: AsyncSession) -> dict:
    data = _load("library")
    counts = {"documents": 0, "courses": 0, "lessons": 0}

    for spec in data["documents"]:
        if (
            await session.execute(
                select(ResearchDocument).where(ResearchDocument.slug == spec["slug"])
            )
        ).scalar_one_or_none():
            continue
        document = ResearchDocument(
            slug=spec["slug"],
            title=spec["title"],
            summary=spec.get("summary", ""),
            kind=spec["kind"],
            authors=spec.get("authors", ""),
            publisher=spec.get("publisher", ""),
            published_on=date.fromisoformat(spec["published_on"]) if spec.get("published_on") else None,
            source_url=spec["source_url"],
            file_url=spec.get("file_url", ""),
            file_type=spec.get("file_type", ""),
            page_count=spec.get("page_count"),
            licence=spec.get("licence", "linked_only"),
            language=spec.get("language", "en"),
            tags=spec.get("tags", []),
            state_code=spec.get("state"),
            article_refs=spec.get("article_refs", []),
            is_published=True,
            uploaded_by=DEMO_ACTOR.id,
        )
        session.add(document)
        await session.flush()
        counts["documents"] += 1

        await search.index(
            session,
            entity_type="research_document",
            entity_id=document.slug,
            title=document.title,
            subtitle=f"{document.kind} - {document.publisher}",
            body=document.summary,
            keywords=[document.kind, document.authors, *document.tags],
            state_code=document.state_code,
            url_path=f"/research/{document.slug}",
        )

    # Constitution articles come from seeding rather than from the admin API, so
    # they carry no audit trail and the history tab on an article page is empty.
    # These entries make the Wikipedia-History feature visible. They describe edits
    # to OUR OWN explanation of a provision, not claims about any person.
    counts["article_edits"] = 0
    from backend.core.models import AuditLog

    # The audit log is append-only, so unlike every other step here a second --load
    # would stack a duplicate set of edits onto each article. Check first.
    already = {
        (row.entity_id, row.summary)
        for row in (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "constitution_article",
                    AuditLog.actor_email == DEMO_ACTOR.email,
                )
            )
        ).scalars()
    }
    for spec in data.get("constitution_edits", []):
        for entry in spec["entries"]:
            if (spec["article"], entry["summary"]) in already:
                continue
            await audit.record(
                session,
                actor=DEMO_ACTOR,
                action=entry["action"],
                entity_type="constitution_article",
                entity_id=spec["article"],
                summary=entry["summary"],
                changes=entry.get("changes"),
                source_url="https://www.indiacode.nic.in/handle/123456789/1362",
                is_public=True,
            )
            counts["article_edits"] += 1
    await session.flush()

    # Back-date them, so the history reads as a sequence rather than as fifteen
    # edits made in the same second.
    rows = list(
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "constitution_article",
                    AuditLog.actor_email == DEMO_ACTOR.email,
                )
            )
        ).scalars()
    )
    offsets = {
        (spec["article"], entry["summary"]): entry["days_ago"]
        for spec in data.get("constitution_edits", [])
        for entry in spec["entries"]
    }
    for row in rows:
        days = offsets.get((row.entity_id, row.summary))
        if days is not None:
            row.created_at = utcnow() - timedelta(days=days)

    course_spec = data.get("course")
    if course_spec and not (
        await session.execute(select(Course).where(Course.slug == course_spec["slug"]))
    ).scalar_one_or_none():
        course = Course(
            slug=course_spec["slug"],
            title=course_spec["title"],
            title_hi=course_spec.get("title_hi", ""),
            summary=course_spec.get("summary", ""),
            level=course_spec.get("level", "beginner"),
            estimated_minutes=course_spec.get("estimated_minutes", 30),
            tags=course_spec.get("tags", []),
            sort_order=2,
            is_published=True,
        )
        session.add(course)
        await session.flush()
        counts["courses"] += 1

        for order, lesson_spec in enumerate(course_spec.get("lessons", []), start=1):
            session.add(
                Lesson(
                    course_id=course.id,
                    slug=lesson_spec["slug"],
                    title=lesson_spec["title"],
                    body=lesson_spec["body"],
                    article_refs=lesson_spec.get("article_refs", []),
                    sort_order=order,
                    minutes=lesson_spec.get("minutes", 5),
                )
            )
            counts["lessons"] += 1

        quiz_spec = course_spec.get("quiz")
        if quiz_spec:
            session.add(
                Quiz(
                    course_id=course.id,
                    title=quiz_spec.get("title", "Check your understanding"),
                    pass_percent=quiz_spec.get("pass_percent", 70),
                    questions=quiz_spec.get("questions", []),
                )
            )

        await session.flush()
        await search.index(
            session,
            entity_type="course",
            entity_id=course.slug,
            title=course.title,
            subtitle="Course - Start here",
            body=course.summary,
            keywords=course.tags,
            url_path=f"/academy/{course.slug}",
        )

        # Enrol one member and finish the course, so the certificate flow and the
        # "your progress" panel both have something to show.
        learner = (
            await session.execute(
                select(Citizen).where(Citizen.email == _email("citizen1"))
            )
        ).scalar_one_or_none()
        if learner is not None:
            lesson_ids = [
                row.id
                for row in (
                    await session.execute(select(Lesson).where(Lesson.course_id == course.id))
                ).scalars()
            ]
            session.add(
                Enrollment(
                    course_id=course.id,
                    citizen_id=learner.id,
                    completed_lessons=lesson_ids,
                    completed_at=utcnow() - timedelta(days=6),
                )
            )
            await certificates.issue(
                session,
                kind="course_completion",
                holder_name=learner.display_name,
                title=f"For completing {course.title}",
                detail={
                    "Course": course.title,
                    "Level": "Start here",
                    "Score": "83%",
                    "courseSlug": course.slug,
                },
                citizen_id=learner.id,
                holder_email=learner.email,
                issued_by=DEMO_ACTOR.id,
            )

    return counts


async def load_manifesto(session: AsyncSession) -> dict:
    """The manifesto accountability chain, end to end, for six demo promises.

    MARKED HARDER THAN ANYTHING ELSE IN THIS DATASET, and deliberately so. The
    other loaders fabricate claims about fictional people; this one fabricates a
    quotation from a party's manifesto and a government's answer to an RTI. Both
    of those are documents that exist in the real world and that people are
    entitled to rely on, so every promise text opens with `[DEMO PROMISE - NOT A
    REAL MANIFESTO COMMITMENT]`, every answer with `[DEMO ANSWER]`, the party is
    fictional, and every identifier starts with `DEMO-`. There is no view in the
    module where one of those markers is not on screen.

    It attaches to the genuine `uttarakhand-2022` election row rather than
    inventing an election, because the election is a matter of public record and
    a second fake one in the selector would be the confusing option. Purge
    removes the promises by their `DEMO-` code prefix; the election row is left
    alone because the loader did not create it.

    Written through the ORM plus `audit.record`, like the rest of this file, so
    the public "Record history" panel on each promise has the real chronology in
    it -- RTI filed, reply received, document added, status published -- which is
    one of the things the module exists to show.
    """
    data = _load("manifesto")
    counts = {
        "manifesto_promises": 0,
        "manifesto_rtis": 0,
        "manifesto_questions": 0,
        "manifesto_documents": 0,
        "manifesto_evidence": 0,
        "manifesto_assessments": 0,
    }

    election = (
        await session.execute(
            select(ManifestoElection).where(ManifestoElection.slug == "uttarakhand-2022")
        )
    ).scalar_one_or_none()
    if election is None:
        # seed_modules opens this row on boot. Without it there is nothing to
        # hang the dataset off, and inventing an election here would put a
        # fabricated poll date in a selector of real ones.
        return {"manifesto_promises": 0, "manifesto_skipped": "election row not seeded"}

    spec = data["manifesto"]
    manifesto = (
        await session.execute(select(Manifesto).where(Manifesto.slug == spec["slug"]))
    ).scalar_one_or_none()
    if manifesto is None:
        manifesto = Manifesto(
            slug=spec["slug"],
            election_id=election.id,
            party_code=spec["party_code"],
            party_name=spec["party_name"],
            title=spec["title"],
            title_hi=spec.get("title_hi", ""),
            published_on=date.fromisoformat(spec["published_on"]),
            total_pages=spec.get("total_pages"),
            source_url=_demo_source("manifesto/demo-progressive-party-2022.pdf"),
            source_note=spec["source_note"],
            is_published=True,
        )
        session.add(manifesto)
        await session.flush()

    for promise_spec in data["promises"]:
        if (
            await session.execute(
                select(ManifestoPromise).where(ManifestoPromise.code == promise_spec["code"])
            )
        ).scalar_one_or_none():
            continue

        promise = ManifestoPromise(
            code=promise_spec["code"],
            election_id=election.id,
            manifesto_id=manifesto.id,
            title=promise_spec["title"],
            title_hi=promise_spec.get("title_hi", ""),
            promise_text=promise_spec["promise_text"],
            promise_text_hi=promise_spec.get("promise_text_hi", ""),
            manifesto_page=promise_spec.get("manifesto_page", ""),
            manifesto_page_url=_demo_source(
                f"manifesto/page-{promise_spec.get('manifesto_page', '1')}.pdf"
            ),
            department=promise_spec.get("department", ""),
            category=promise_spec.get("category", "Other"),
            status=promise_spec["status"],
            sort_order=counts["manifesto_promises"],
            is_published=True,
        )
        session.add(promise)
        await session.flush()
        counts["manifesto_promises"] += 1

        await audit.record(
            session,
            actor=DEMO_ACTOR,
            action="create",
            entity_type="manifesto_promise",
            entity_id=promise.code,
            summary=f"DEMO: published promise {promise.code} from {manifesto.title}",
            source_url=manifesto.source_url,
            is_public=True,
        )

        # ---- Documents first: questions and evidence reference them by code ----
        #
        # `uploaded_at` is set from the date the reply arrived rather than left to
        # default to now(). The timeline derives "Documents received" from that
        # column, so defaulting it would date every demo document to whenever the
        # loader happened to run and show a chain whose steps are out of order --
        # which would misrepresent the one feature the timeline exists to
        # demonstrate.
        received_on = (promise_spec.get("rti") or {}).get("response", {}).get("received_on")
        documents_received_at = (
            datetime.fromisoformat(received_on).replace(tzinfo=timezone.utc)
            if received_on
            else utcnow()
        )
        documents_by_code: dict[str, GovernmentDocument] = {}
        for document_spec in promise_spec.get("documents", []):
            url = _demo_source(f"documents/{document_spec['code'].lower()}.pdf")
            is_primary, publisher = classify_source(url)
            document = GovernmentDocument(
                code=document_spec["code"],
                promise_id=promise.id,
                title=document_spec["title"],
                kind=document_spec["kind"],
                issuing_authority=document_spec["issuing_authority"],
                department=document_spec.get("department", ""),
                reference_number=document_spec.get("reference_number", ""),
                issued_on=(
                    date.fromisoformat(document_spec["issued_on"])
                    if document_spec.get("issued_on")
                    else None
                ),
                file_url=url,
                source_url=url,
                source_note=(
                    "DEMO RECORD - not a real source. Received with the demo RTI reply."
                ),
                obtained_via="rti",
                is_primary_source=is_primary,
                publisher=publisher or "Demo",
                page_count=document_spec.get("page_count"),
                is_published=True,
                uploaded_at=documents_received_at,
            )
            session.add(document)
            await session.flush()
            documents_by_code[document.code] = document
            counts["manifesto_documents"] += 1

            await audit.record(
                session,
                actor=DEMO_ACTOR,
                action="document_uploaded",
                entity_type="manifesto_promise",
                entity_id=promise.code,
                summary=f"DEMO: added {document.title}",
                source_url=url,
                is_public=True,
            )

        # ---- The RTI application, its questions and its reply ----
        questions_by_number: dict[int, RtiQuestion] = {}
        rti_spec = promise_spec.get("rti")
        if rti_spec:
            rti = RtiApplication(
                code=rti_spec["code"],
                promise_id=promise.id,
                subject=rti_spec.get("subject", ""),
                public_authority=rti_spec["public_authority"],
                department=rti_spec.get("department", ""),
                pio_designation=rti_spec.get("pio_designation", ""),
                application_number=rti_spec.get("application_number", ""),
                prepared_on=(
                    date.fromisoformat(rti_spec["prepared_on"])
                    if rti_spec.get("prepared_on")
                    else None
                ),
                filed_on=(
                    date.fromisoformat(rti_spec["filed_on"]) if rti_spec.get("filed_on") else None
                ),
                reply_due_on=(
                    date.fromisoformat(rti_spec["reply_due_on"])
                    if rti_spec.get("reply_due_on")
                    else None
                ),
                status=rti_spec["status"],
                application_url=_demo_source(f"rti/{rti_spec['code'].lower()}-application.pdf"),
                filing_proof_url=_demo_source(f"rti/{rti_spec['code'].lower()}-receipt.pdf"),
                is_published=True,
            )
            session.add(rti)
            await session.flush()
            counts["manifesto_rtis"] += 1

            if rti.filed_on:
                await audit.record(
                    session,
                    actor=DEMO_ACTOR,
                    action="rti_filed",
                    entity_type="manifesto_promise",
                    entity_id=promise.code,
                    summary=f"DEMO: RTI {rti.code} filed with {rti.public_authority}",
                    source_url=rti.filing_proof_url,
                    is_public=True,
                )

            response = None
            response_spec = rti_spec.get("response")
            if response_spec:
                response = RtiResponse(
                    rti_id=rti.id,
                    received_on=(
                        date.fromisoformat(response_spec["received_on"])
                        if response_spec.get("received_on")
                        else None
                    ),
                    reply_dated=(
                        date.fromisoformat(response_spec["reply_dated"])
                        if response_spec.get("reply_dated")
                        else None
                    ),
                    replying_authority=response_spec["replying_authority"],
                    department=response_spec.get("department", ""),
                    reference_number=response_spec.get("reference_number", ""),
                    document_url=_demo_source(f"rti/{rti_spec['code'].lower()}-reply.pdf"),
                    page_count=response_spec.get("page_count"),
                    summary=response_spec.get("summary", ""),
                    is_published=True,
                )
                session.add(response)
                await session.flush()

                await audit.record(
                    session,
                    actor=DEMO_ACTOR,
                    action="reply_received",
                    entity_type="manifesto_promise",
                    entity_id=promise.code,
                    summary=(
                        f"DEMO: reply received from {response.replying_authority} "
                        f"({response.reference_number})"
                    ),
                    source_url=response.document_url,
                    is_public=True,
                )

            for question_spec in rti_spec.get("questions", []):
                question = RtiQuestion(
                    rti_id=rti.id,
                    number=question_spec["number"],
                    question_text=question_spec["question"],
                    question_text_hi=question_spec.get("question_hi", ""),
                    answer_text=question_spec.get("answer", ""),
                    answer_status=question_spec.get("answer_status", "awaited"),
                    response_id=response.id if response else None,
                    supporting_document_id=(
                        documents_by_code[question_spec["document"]].id
                        if question_spec.get("document") in documents_by_code
                        else None
                    ),
                )
                session.add(question)
                await session.flush()
                questions_by_number[question.number] = question
                counts["manifesto_questions"] += 1

        # ---- What the records state ----
        for order, evidence_spec in enumerate(promise_spec.get("evidence", [])):
            evidence = PromiseEvidence(
                promise_id=promise.id,
                document_id=(
                    documents_by_code[evidence_spec["document"]].id
                    if evidence_spec.get("document") in documents_by_code
                    else None
                ),
                statement=evidence_spec["statement"],
                statement_hi=evidence_spec.get("statement_hi", ""),
                locator=evidence_spec.get("locator", ""),
                recorded_on=(
                    date.fromisoformat(evidence_spec["recorded_on"])
                    if evidence_spec.get("recorded_on")
                    else None
                ),
                sort_order=order,
                is_published=True,
            )
            session.add(evidence)
            await session.flush()
            counts["manifesto_evidence"] += 1

        # ---- The assessment, kept separate from all of the above ----
        assessment_spec = promise_spec.get("assessment")
        if assessment_spec:
            sources = [
                {"kind": "document", "id": document.id, "label": document.title}
                for document in documents_by_code.values()
            ]
            assessment = PromiseAssessment(
                promise_id=promise.id,
                status=assessment_spec["status"],
                rationale=assessment_spec.get("rationale", ""),
                method_note=assessment_spec.get("method_note", ""),
                sources=sources,
                assessed_on=(
                    date.fromisoformat(assessment_spec["assessed_on"])
                    if assessment_spec.get("assessed_on")
                    else None
                ),
                assessed_by=DEMO_ACTOR.id,
                version=1,
                is_current=True,
                is_published=True,
            )
            session.add(assessment)
            await session.flush()
            counts["manifesto_assessments"] += 1

            await audit.record(
                session,
                actor=DEMO_ACTOR,
                action="status_changed",
                entity_type="manifesto_promise",
                entity_id=promise.code,
                summary=f"DEMO: assessment published - {assessment_spec['status']}",
                is_public=True,
            )

        # Same shape the router's own indexer writes, so a demo promise is
        # findable in site search exactly as a real one would be.
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

    return counts


async def issue_volunteer_certificates(session: AsyncSession) -> int:
    """Certificates for demo volunteers who cleared the verified-hours threshold.

    Uses the same threshold the real endpoint applies, so nobody gets one who would
    not have earned it.
    """
    from backend.modules.volunteers.models import CERTIFICATE_HOURS_THRESHOLD

    issued = 0
    rows = (
        await session.execute(
            select(VolunteerProfile, Citizen)
            .join(Citizen, Citizen.id == VolunteerProfile.citizen_id)
            .where(
                Citizen.email.like(f"%@{EMAIL_DOMAIN}"),
                VolunteerProfile.verified_hours >= CERTIFICATE_HOURS_THRESHOLD,
            )
        )
    ).all()
    for profile, citizen in rows:
        existing = [
            c
            for c in (
                await session.execute(
                    select(Certificate).where(
                        Certificate.citizen_id == citizen.id,
                        Certificate.kind == "volunteer_hours",
                    )
                )
            ).scalars()
        ]
        if existing:
            continue
        await certificates.issue(
            session,
            kind="volunteer_hours",
            holder_name=citizen.display_name,
            title="For volunteer service to the Right to Recall Movement",
            detail={
                "Verified hours": f"{profile.verified_hours:g}",
                "Tasks completed": profile.completed_tasks,
            },
            citizen_id=citizen.id,
            holder_email=citizen.email,
            issued_by=DEMO_ACTOR.id,
        )
        issued += 1
    return issued


# ==========================================================================
# Purge
# ==========================================================================
async def purge(session: AsyncSession) -> dict:
    """Remove every record the loader created, and restore what it modified.

    Identifies its own records only by the markers documented in the README. Deletes
    parents and lets the database cascade to children (claims, signatures, replies,
    registrations, assignments, enrolments), which is both correct and much less
    error-prone than enumerating them.
    """
    removed: dict[str, int] = {}

    async def drop(model, condition, label, slug_attr="slug", index_type=None):
        rows = list((await session.execute(select(model).where(condition))).scalars())
        for row in rows:
            if index_type:
                await search.unindex(
                    session, entity_type=index_type, entity_id=getattr(row, slug_attr)
                )
            await session.delete(row)
        removed[label] = len(rows)

    demo_slug = f"{SLUG_PREFIX}%"

    await drop(Promise, Promise.slug.like(demo_slug), "promises", index_type="promise")
    await drop(
        Representative,
        Representative.slug.like(demo_slug),
        "representatives",
        index_type="representative",
    )
    await drop(Petition, Petition.slug.like(demo_slug), "petitions", index_type="petition")
    await drop(CitizenReport, CitizenReport.slug.like(demo_slug), "reports", index_type="report")
    await drop(ForumThread, ForumThread.slug.like(demo_slug), "forum_threads")
    await drop(Event, Event.slug.like(demo_slug), "events", index_type="event")
    await drop(VolunteerTask, VolunteerTask.slug.like(demo_slug), "volunteer_tasks")
    await drop(
        ResearchDocument,
        ResearchDocument.slug.like(demo_slug),
        "research_documents",
        index_type="research_document",
    )
    await drop(Course, Course.slug.like(demo_slug), "courses", index_type="course")
    await drop(Constituency, Constituency.slug.like(demo_slug), "constituencies")
    await drop(Party, Party.code.like(f"{PARTY_PREFIX}%"), "parties", slug_attr="code")

    # Manifesto promises cascade to their RTI applications, questions, replies,
    # documents, evidence and assessments. The election row is NOT touched: the
    # loader attached to it rather than creating it, and it is real reference
    # data seeded on boot.
    await drop(
        ManifestoPromise,
        ManifestoPromise.code.like("DEMO-%"),
        "manifesto_promises",
        slug_attr="code",
        index_type="manifesto_promise",
    )
    await drop(Manifesto, Manifesto.slug.like(demo_slug), "manifestos")

    # Corrections reference demo entities but have no slug of their own.
    demo_entities = [
        r["entity_id"] for r in _load("community")["corrections"]
    ]
    removed["corrections"] = (
        await session.execute(
            delete(Correction).where(
                Correction.entity_id.in_(demo_entities), Correction.summary.like("DEMO:%")
            )
        )
    ).rowcount

    removed["certificates"] = (
        await session.execute(
            delete(Certificate).where(Certificate.holder_email.like(f"%@{EMAIL_DOMAIN}"))
        )
    ).rowcount

    # Citizens last: everything else referencing them is gone, and the cascade
    # cleans up anything missed.
    await drop(Citizen, Citizen.email.like(f"%@{EMAIL_DOMAIN}"), "members", slug_attr="email")

    try:
        if not await _mongo_reachable():
            raise RuntimeError("MongoDB unreachable")
        removed["demo_logins"] = (
            await mongo_db.supporters.delete_many({"email": {"$regex": f"@{EMAIL_DOMAIN}$"}})
        ).deleted_count
    except Exception as e:
        # The relational side is already purged; a Mongo outage must not leave the
        # command looking like it failed.
        removed["demo_logins"] = f"skipped ({str(e)[:40]})"

    # Restore the campaign stages this dataset changed.
    backup_row = (
        await session.execute(select(PlatformMeta).where(PlatformMeta.key == STATE_BACKUP_KEY))
    ).scalar_one_or_none()
    restored = 0
    if backup_row is not None:
        for code, values in json.loads(backup_row.value).items():
            state = (
                await session.execute(select(State).where(State.code == code))
            ).scalar_one_or_none()
            if state is None:
                continue
            state.campaign_stage = values["stage"]
            state.campaign_note = values["note"]
            state.campaign_source_url = values["source_url"]
            state.campaign_updated_at = (
                datetime.fromisoformat(values["updated_at"]) if values["updated_at"] else None
            )
            restored += 1
        await session.delete(backup_row)
    removed["states_restored"] = restored

    # Audit entries written by the demo actor. The log is append-only for real
    # activity; these are removed because they describe records that no longer exist,
    # and leaving them would make the history tabs reference deleted profiles.
    from backend.core.models import AuditLog

    removed["audit_entries"] = (
        await session.execute(
            delete(AuditLog).where(AuditLog.actor_email == DEMO_ACTOR.email)
        )
    ).rowcount

    return removed


# ==========================================================================
# Status
# ==========================================================================
async def status(session: AsyncSession) -> dict:
    async def count(model, condition):
        return (
            await session.execute(select(func.count()).select_from(model).where(condition))
        ).scalar_one()

    demo_slug = f"{SLUG_PREFIX}%"
    return {
        "representatives": await count(Representative, Representative.slug.like(demo_slug)),
        "promises": await count(Promise, Promise.slug.like(demo_slug)),
        "petitions": await count(Petition, Petition.slug.like(demo_slug)),
        "reports": await count(CitizenReport, CitizenReport.slug.like(demo_slug)),
        "forum_threads": await count(ForumThread, ForumThread.slug.like(demo_slug)),
        "events": await count(Event, Event.slug.like(demo_slug)),
        "volunteer_tasks": await count(VolunteerTask, VolunteerTask.slug.like(demo_slug)),
        "research_documents": await count(ResearchDocument, ResearchDocument.slug.like(demo_slug)),
        "courses": await count(Course, Course.slug.like(demo_slug)),
        "members": await count(Citizen, Citizen.email.like(f"%@{EMAIL_DOMAIN}")),
        "parties": await count(Party, Party.code.like(f"{PARTY_PREFIX}%")),
        "constituencies": await count(Constituency, Constituency.slug.like(demo_slug)),
        "certificates": await count(Certificate, Certificate.holder_email.like(f"%@{EMAIL_DOMAIN}")),
        "manifesto_promises": await count(
            ManifestoPromise, ManifestoPromise.code.like("DEMO-%")
        ),
        "manifesto_rtis": await count(RtiApplication, RtiApplication.code.like("DEMO-%")),
        "manifesto_documents": await count(
            GovernmentDocument, GovernmentDocument.code.like("DEMO-%")
        ),
    }


# ==========================================================================
# Entry point
# ==========================================================================
BANNER = """
--------------------------------------------------------------------------
  DEMO DATA
--------------------------------------------------------------------------
  This loads FABRICATED representatives, claims, reports and petitions.

  Every record is marked so it cannot be mistaken for real data:
    - names begin with [DEMO]
    - parties and constituencies are fictional
    - every citation is titled "DEMO RECORD - not a real source"
    - member emails end in @demo.rtr.invalid

  Do not load this on a production site that the public can see.
  Run with --purge to remove every trace of it.
--------------------------------------------------------------------------
"""


async def _run(action: str) -> None:
    # transaction(), not `async for session_scope()`: every branch below returns
    # from inside the block, which a generator-based scope would not commit.
    async with database.transaction() as session:
        if action == "status":
            counts = await status(session)
            total = sum(counts.values())
            print(f"Demo records present: {total}\n")
            for key, value in counts.items():
                print(f"  {key:22} {value}")
            if total == 0:
                print("\nNothing loaded. Run with --load to add it.")
            return

        if action == "purge":
            removed = await purge(session)
            print("Purged:\n")
            for key, value in removed.items():
                print(f"  {key:22} {value}")
            print("\nRun --status to confirm nothing is left.")
            return

        # --- load ---
        results = {}
        results.update(await load_reference(session))
        results.update(await load_accountability(session))
        results.update(await load_community(session))
        results.update(await load_participation(session))
        results.update(await load_library(session))
        results.update(await load_manifesto(session))
        results["volunteer_certificates"] = await issue_volunteer_certificates(session)

        print("Loaded:\n")
        for key, value in results.items():
            print(f"  {key:22} {value}")
        if results.get("login_setup_failed"):
            print(
                "\nNOTE: member sign-in was not set up because MongoDB was unreachable."
                "\nEvery page still has data; only 'log in as a demo member' is unavailable."
                "\nRe-run --load once Mongo is reachable to add it."
            )
            return
        print(
            f"\nSign in at /login as any of citizen1..citizen14@{EMAIL_DOMAIN}"
            f"\nwith the access code: {ACCESS_CODE}"
            "\n\ncitizen1 has the most activity (petitions, reports, forum posts,"
            "\nvolunteer hours, event tickets and a course certificate)."
            "\n\nRun --purge to remove all of it."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load, inspect or purge the demo dataset.",
        epilog="Read backend/content/demo/README.md first.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--load", action="store_true", help="load the demo dataset")
    group.add_argument("--purge", action="store_true", help="remove every demo record")
    group.add_argument("--status", action="store_true", help="report what is currently loaded")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt (for scripted use)",
    )
    args = parser.parse_args()

    if not config.postgres_enabled():
        raise SystemExit(
            "DATABASE_URL is not set. The demo dataset lives entirely in the relational "
            "database, so there is nothing to load without it."
        )

    if args.load:
        print(BANNER)
        if not args.yes:
            answer = input("Type 'load demo data' to continue: ").strip()
            if answer != "load demo data":
                raise SystemExit("Cancelled.")

    action = "load" if args.load else "purge" if args.purge else "status"
    asyncio.run(_run(action))
    asyncio.run(database.dispose())


if __name__ == "__main__":
    main()
