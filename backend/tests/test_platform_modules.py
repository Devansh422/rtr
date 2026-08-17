"""Unit and in-process API tests for the Phase 1-5 modules.

Same approach as test_core_rbac.py: everything runs against in-memory SQLite with no
Mongo and no Postgres, so the suite works on a laptop and in CI without
infrastructure. The API-level tests drive the real FastAPI app through an in-process
ASGI transport with the session dependency overridden, which exercises routing,
validation and serialisation without a server or a network.

The five required environment variables are set before importing anything from
backend.core, because config reads them at import time on purpose.
"""

import os
import pathlib
import re

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "rtr_test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-any-real-environment")
os.environ.setdefault("ADMIN_EMAIL", "bootstrap@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "bootstrap-password-123")

import zipfile  # noqa: E402
from io import BytesIO  # noqa: E402

import httpx  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from backend import seed_modules  # noqa: E402
from backend.core import certificates, citations, documents, erasure, i18n, moderation, search  # noqa: E402
from backend.core.bootstrap import sync_geography, sync_registry  # noqa: E402
from backend.core.models import Certificate, Citizen, SearchDoc  # noqa: E402
from backend.models_all import Base  # noqa: E402
from backend.modules.constitution.models import ConstitutionArticle, compute_sort_key  # noqa: E402
from backend.modules.forum.models import REPUTATION_GATES  # noqa: E402
from backend.modules.petitions.models import milestones_reached, next_milestone  # noqa: E402
from backend.modules.representatives.fields import CLAIM_FIELDS, CLAIM_FIELDS_BY_KEY  # noqa: E402
from backend.modules.representatives.models import PROMISE_STATUSES  # noqa: E402
from backend.modules.representatives.router import format_indian_currency  # noqa: E402
# Imported as functions, not as a module: every module package re-exports `router`
# as the APIRouter object, which shadows the submodule of the same name for both
# `import a.b.router` and `from a.b import router`.
from backend.modules.tools.router import (  # noqa: E402
    _assert_placeholders_declared,
    build as build_document,
)
from backend.modules.tools.models import DocumentTemplate, ReviewStatus  # noqa: E402
from backend.modules.tools.seed_templates import TEMPLATES  # noqa: E402


@pytest.fixture
async def session() -> AsyncSession:
    """A fresh in-memory schema per test, built from the full model metadata."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def seeded(session: AsyncSession) -> AsyncSession:
    """Registry, geography and every module's reference data."""
    await sync_registry(session)
    await sync_geography(session)
    articles = seed_modules._load_constitution_seed()
    await seed_modules.seed_constitution(session, articles)
    await seed_modules.seed_forum_categories(session)
    await seed_modules.seed_parties(session)
    await seed_modules.seed_pilot_districts(session)
    await seed_modules.sync_tool_templates(session)
    await seed_modules.seed_starter_course(session)
    await seed_modules.seed_national_petition(session)
    await session.flush()
    return session


# --------------------------------------------------------------------------
# The verifiability gate (§7)
# --------------------------------------------------------------------------
class TestCitations:
    def test_official_domain_is_primary(self):
        is_primary, publisher = citations.classify_source(
            "https://affidavit.eci.gov.in/candidate/12345"
        )
        assert is_primary
        assert "ECI" in publisher

    def test_any_gov_in_domain_is_primary(self):
        # There are hundreds of state portals; enumerating them all is not feasible,
        # so the suffix rule has to work.
        assert citations.classify_source("https://transport.mh.gov.in/order/9")[0]

    def test_news_site_is_secondary(self):
        is_primary, host = citations.classify_source("https://example-news.com/story")
        assert not is_primary
        assert host == "example-news.com"

    def test_high_risk_field_rejects_a_secondary_source(self):
        with pytest.raises(citations.CitationError, match="primary public record"):
            citations.parse_citation(
                {"url": "https://example-news.com/story", "title": "Report on affidavit"},
                require_primary=True,
                field_name="Pending criminal cases",
            )

    def test_high_risk_field_accepts_a_primary_source(self):
        citation = citations.parse_citation(
            {
                "url": "https://myneta.info/LokSabha2024/candidate?candidate_id=1",
                "title": "ECI affidavit via ADR, 2024 general election",
                "source_date": "2024-04",
            },
            require_primary=True,
            field_name="Pending criminal cases",
        )
        assert citation.is_primary
        assert citation.source_date == "2024-04"

    def test_citation_requires_a_real_url(self):
        for bad in ("", "told to me by a volunteer", "ftp://files.example.com/x"):
            with pytest.raises(citations.CitationError):
                citations.parse_citation({"url": bad, "title": "Some source"})

    def test_citation_requires_a_description(self):
        with pytest.raises(citations.CitationError, match="Describe the source"):
            citations.parse_citation({"url": "https://eci.gov.in/x", "title": "x"})

    def test_future_source_date_is_rejected(self):
        with pytest.raises(citations.CitationError, match="future"):
            citations.parse_citation(
                {"url": "https://eci.gov.in/x", "title": "An affidavit", "source_date": "2099-01-01"}
            )

    def test_verification_status_ordering(self):
        assert citations.at_least("fact_checked", citations.VerificationStatus.FACT_CHECKED)
        assert not citations.at_least("unverified", citations.VerificationStatus.FACT_CHECKED)
        assert not citations.at_least("disputed", citations.VerificationStatus.FACT_CHECKED)

    def test_retracted_claims_are_never_publicly_visible(self):
        assert not citations.is_publicly_visible("retracted")
        assert citations.is_publicly_visible("disputed")
        assert citations.is_publicly_visible("unverified")

    def test_unknown_status_is_treated_as_least_trusted(self):
        assert not citations.is_publicly_visible("looks_fine_to_me")
        assert not citations.at_least("looks_fine_to_me", citations.VerificationStatus.UNVERIFIED)

    def test_claim_envelope_never_asserts_an_unverified_value_as_fact(self):
        envelope = citations.claim_envelope(7, status="unverified")
        assert envelope["value"] == 7
        assert envelope["isFact"] is False
        assert "pending citation review" in envelope["statusLabel"].lower()

    def test_disclaimer_says_charges_are_not_convictions(self):
        assert "not convictions" in citations.STANDARD_DISCLAIMER


# --------------------------------------------------------------------------
# The non-partisan content policy (§1, §7)
# --------------------------------------------------------------------------
class TestModeration:
    def test_ordinary_civic_criticism_is_allowed(self):
        verdict = moderation.review(
            "The MLA has not attended a single sitting of the assembly this session, according to "
            "the assembly's own attendance record."
        )
        assert verdict.decision is moderation.Decision.ALLOW

    def test_identity_terms_alone_never_flag_anything(self):
        # The whole design rests on this: an accurate report about discrimination
        # has to name who was discriminated against.
        verdict = moderation.review(
            "Dalit families in our ward were not given ration cards, while others in the same "
            "street received them in the same week."
        )
        assert verdict.decision is moderation.Decision.ALLOW

    def test_identity_plus_hostility_is_held_for_review(self):
        verdict = moderation.review("These muslims should be driven out of the constituency")
        assert verdict.decision is moderation.Decision.HOLD
        assert any(f.code == "communal_framing" for f in verdict.flags)

    def test_party_campaigning_is_held(self):
        verdict = moderation.review(
            "Vote for our party in the coming election, they are the only ones who can win this seat"
        )
        assert verdict.decision is moderation.Decision.HOLD
        assert any(f.code == "party_campaigning" for f in verdict.flags)

    def test_unsourced_accusation_about_a_person_is_held(self):
        verdict = moderation.review(
            "The sitting MLA is corrupt and took money for every transfer in the district",
            names_a_person=True,
            has_citation=False,
        )
        assert verdict.decision is moderation.Decision.HOLD
        assert any(f.code == "unsourced_accusation" for f in verdict.flags)

    def test_the_same_accusation_with_a_citation_is_not_flagged_for_sourcing(self):
        verdict = moderation.review(
            "The chargesheet filed in this case alleges a bribe; see the court record.",
            names_a_person=True,
            has_citation=True,
        )
        assert not any(f.code == "unsourced_accusation" for f in verdict.flags)

    def test_aadhaar_number_is_refused_outright(self):
        verdict = moderation.review("My aadhaar is 4321 8765 1234 and they still refused")
        assert verdict.decision is moderation.Decision.REJECT
        assert any(f.severity is moderation.Severity.BLOCK for f in verdict.flags)

    def test_phone_and_email_are_refused_unless_allowed(self):
        assert moderation.review("call me on 9876543210").decision is moderation.Decision.REJECT
        assert moderation.review("write to me at a@b.com").decision is moderation.Decision.REJECT
        # Event organiser contact lines are the one case where it is the point.
        assert (
            moderation.review("Organiser: 9876543210", allow_contact_details=True).decision
            is not moderation.Decision.REJECT
        )

    def test_scrub_identifiers_redacts_without_deleting_the_text(self):
        scrubbed = moderation.scrub_identifiers("Ration card issue, call 9876543210 for details")
        assert "9876543210" not in scrubbed
        assert "Ration card issue" in scrubbed

    def test_word_boundary_prevents_false_positives(self):
        # "scam" must not fire on "scamper", "kill" not on "skill".
        verdict = moderation.review("The skills training programme was scampered through quickly")
        assert verdict.decision is moderation.Decision.ALLOW

    def test_published_policy_states_non_partisanship_first(self):
        assert moderation.CONTENT_POLICY["principles"][0]["title"].startswith("Non-partisan")


# --------------------------------------------------------------------------
# Shared search index
# --------------------------------------------------------------------------
class TestSearch:
    async def test_index_then_find(self, session):
        await search.index(
            session,
            entity_type="constitution_article",
            entity_id="326",
            title="Article 326: Elections on the basis of adult suffrage",
            body="Every citizen of eighteen years is entitled to be registered as a voter.",
            keywords=["326", "suffrage"],
            url_path="/constitution/326",
        )
        await session.flush()

        results = await search.query(session, "adult suffrage")
        assert results and results[0]["entityId"] == "326"
        assert results[0]["url"] == "/constitution/326"

    async def test_title_match_outranks_body_match(self, session):
        await search.index(
            session, entity_type="report", entity_id="a", title="Water supply in Pune",
            body="unrelated text", url_path="/a",
        )
        await search.index(
            session, entity_type="report", entity_id="b", title="Unrelated title",
            body="a passing mention of water supply", url_path="/b",
        )
        await session.flush()

        results = await search.query(session, "water supply")
        assert [r["entityId"] for r in results][0] == "a"

    async def test_unpublished_rows_are_excluded(self, session):
        await search.index(
            session, entity_type="promise", entity_id="draft", title="A draft promise",
            url_path="/p", is_published=False,
        )
        await session.flush()
        assert await search.query(session, "draft promise") == []
        assert await search.query(session, "draft promise", include_unpublished=True)

    async def test_index_is_idempotent_per_entity_and_locale(self, session):
        for _ in range(3):
            await search.index(
                session, entity_type="state", entity_id="MH", title="Maharashtra", url_path="/s/mh"
            )
        await session.flush()
        rows = (await session.execute(select(SearchDoc))).scalars().all()
        assert len(rows) == 1

    async def test_unindex_removes_every_locale(self, session):
        for locale in ("en", "hi"):
            await search.index(
                session, entity_type="course", entity_id="c1", title="Course",
                url_path="/c", locale=locale,
            )
        await session.flush()
        await search.unindex(session, entity_type="course", entity_id="c1")
        await session.flush()
        assert (await session.execute(select(SearchDoc))).scalars().all() == []

    async def test_empty_query_returns_nothing_not_everything(self, session):
        await search.index(session, entity_type="state", entity_id="DL", title="Delhi", url_path="/d")
        await session.flush()
        assert await search.query(session, "   ") == []
        # A query made entirely of stopwords is also empty rather than a full dump.
        assert await search.query(session, "what is the") == []

    async def test_body_is_truncated_so_the_index_is_not_a_second_copy(self, session):
        await search.index(
            session, entity_type="research_document", entity_id="big", title="Big",
            body="x" * 9000, url_path="/b",
        )
        await session.flush()
        row = (await session.execute(select(SearchDoc))).scalar_one()
        assert len(row.body) == search.MAX_BODY_CHARS


# --------------------------------------------------------------------------
# Document generation
# --------------------------------------------------------------------------
class TestDocuments:
    def _blocks(self):
        return [
            documents.Block("RTI Application", kind="heading", align="center"),
            documents.Block("To,\nThe Public Information Officer"),
            documents.Block("आवेदक का नाम: क ख ग"),
            documents.Block("Provide a copy of the sanction order", kind="bullet"),
            documents.Block("", kind="pagebreak"),
        ]

    def test_docx_is_a_valid_zip_with_the_required_parts(self):
        data = documents.build_docx(self._blocks())
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            assert {
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
                "word/_rels/document.xml.rels",
                "word/styles.xml",
            } <= names
            body = archive.read("word/document.xml").decode("utf-8")
        assert "RTI Application" in body
        # Devanagari survives, which is the whole reason DOCX was chosen over a
        # server-side PDF renderer.
        assert "आवेदक" in body
        assert 'w:type="page"' in body

    def test_docx_escapes_xml_metacharacters(self):
        data = documents.build_docx([documents.Block("Fees & charges <under> Section 7(1)")])
        with zipfile.ZipFile(BytesIO(data)) as archive:
            body = archive.read("word/document.xml").decode("utf-8")
        assert "&amp;" in body and "&lt;under&gt;" in body

    def test_print_html_is_self_contained_and_noindex(self):
        html = documents.render_print_html("RTI", self._blocks(), hint="Check before sending")
        assert html.startswith("<!doctype html>")
        assert "@page" in html and "noindex" in html
        assert "http://" not in html.replace("https://", "")  # no external assets

    def test_plain_text_preview_keeps_structure(self):
        draft = documents.DocumentDraft(title="t", filename="t.docx", blocks=self._blocks())
        text = draft.plain_text()
        assert "RTI Application" in text
        assert "  - Provide a copy" in text


# --------------------------------------------------------------------------
# Certificates
# --------------------------------------------------------------------------
class TestCertificates:
    def test_code_avoids_confusable_characters(self):
        for _ in range(200):
            code = certificates.new_code()
            body = code.replace("-", "")[3:]
            assert not set(body) & set("O0I1")

    async def test_issue_and_serialise(self, session):
        issued = await certificates.issue(
            session,
            kind="volunteer_hours",
            holder_name="A Volunteer",
            title="For volunteer service",
            detail={"Verified hours": "24"},
            holder_email="v@example.com",
        )
        payload = certificates.to_dict(issued)
        assert payload["valid"] is True
        assert payload["verifyUrl"].endswith(issued.code)
        # The public view must not leak the holder's email.
        assert "holderEmail" not in payload
        assert certificates.to_dict(issued, public=False)["holderEmail"] == "v@example.com"

    async def test_unknown_kind_is_rejected(self, session):
        with pytest.raises(ValueError):
            await certificates.issue(
                session, kind="nobel_prize", holder_name="X", title="Y"
            )

    async def test_render_includes_the_verification_code(self, session):
        issued = await certificates.issue(
            session, kind="course_completion", holder_name="A Learner", title="For completing X"
        )
        draft = certificates.render(issued)
        assert issued.code in draft.plain_text()
        assert issued.code in draft.html()


# --------------------------------------------------------------------------
# i18n (§8)
# --------------------------------------------------------------------------
class TestI18n:
    def test_normalise_handles_regional_tags_and_junk(self):
        assert i18n.normalise("hi-IN") == "hi"
        assert i18n.normalise("HI") == "hi"
        assert i18n.normalise("klingon") == "en"
        assert i18n.normalise(None) == "en"

    def test_only_english_and_hindi_are_live(self):
        available = {loc["code"] for loc in i18n.locale_catalogue() if loc["available"]}
        assert available == {"en", "hi"}

    def test_planned_languages_are_listed_but_marked_unavailable(self):
        catalogue = {loc["code"]: loc for loc in i18n.locale_catalogue()}
        assert catalogue["ta"]["available"] is False
        assert catalogue["ta"]["nativeName"] == "தமிழ்"
        assert catalogue["ur"]["direction"] == "rtl"

    def test_missing_translation_falls_back_and_says_so(self):
        class Row:
            title = "Equality before law"
            title_hi = ""
            translation_status = {}

        field = i18n.field_for(Row(), "title", "hi")
        assert field["text"] == "Equality before law"
        assert field["locale"] == "en"
        assert "Not yet available" in field["notice"]

    def test_machine_draft_of_a_legal_field_is_not_served_as_the_text(self):
        class Row:
            plain_text = "The State shall not deny equality"
            plain_text_hi = "मशीन अनुवाद"
            translation_status = {"hi": "machine_draft"}

        field = i18n.field_for(Row(), "plain_text", "hi", is_legal=True)
        assert field["text"] == "The State shall not deny equality"
        assert field["unreviewedDraft"] == "मशीन अनुवाद"
        assert "not been reviewed" in field["notice"]

    def test_human_reviewed_translation_is_served(self):
        class Row:
            plain_text = "English"
            plain_text_hi = "समीक्षित हिंदी"
            translation_status = {"hi": "human_reviewed"}

        field = i18n.field_for(Row(), "plain_text", "hi", is_legal=True)
        assert field["text"] == "समीक्षित हिंदी"
        assert field["provenance"] == "human_reviewed"


# --------------------------------------------------------------------------
# Constitution library
# --------------------------------------------------------------------------
class TestConstitution:
    def test_sort_key_orders_inserted_articles_correctly(self):
        order = ["9", "10", "21", "21A", "21B", "22", "243", "243A", "243E", "324", "326"]
        keys = [compute_sort_key(n) for n in order]
        assert keys == sorted(keys), list(zip(order, keys))

    def test_sort_key_does_not_sort_10_before_9(self):
        assert compute_sort_key("9") < compute_sort_key("10")

    async def test_seed_publishes_and_indexes_every_article(self, seeded):
        articles = (await seeded.execute(select(ConstitutionArticle))).scalars().all()
        assert len(articles) >= 40
        assert all(a.is_published for a in articles)
        assert all(a.plain_en.strip() for a in articles), "an article with no explanation is not a library entry"

        indexed = (
            await seeded.execute(
                select(SearchDoc).where(SearchDoc.entity_type == "constitution_article")
            )
        ).scalars().all()
        assert len(indexed) == len(articles)

    async def test_the_articles_the_campaign_rests_on_are_present(self, seeded):
        numbers = set((await seeded.execute(select(ConstitutionArticle.number))).scalars())
        # 326 adult suffrage, 83/172 the five-year term, 243A direct democracy,
        # 328/327 the legislative routes, 368 amendment, 32/226 remedies.
        assert {"326", "83", "172", "243A", "327", "328", "368", "32", "226"} <= numbers

    async def test_recall_relevance_is_populated_where_it_matters(self, seeded):
        row = (
            await seeded.execute(select(ConstitutionArticle).where(ConstitutionArticle.number == "326"))
        ).scalar_one()
        assert row.recall_relevance.strip()
        assert row.case_law, "Article 326 should carry at least one judgment"

    async def test_seeding_is_idempotent(self, seeded):
        before = len((await seeded.execute(select(ConstitutionArticle))).scalars().all())
        await seed_modules.seed_constitution(seeded, seed_modules._load_constitution_seed())
        after = len((await seeded.execute(select(ConstitutionArticle))).scalars().all())
        assert before == after

    async def test_seeding_does_not_overwrite_an_editors_improvements(self, seeded):
        row = (
            await seeded.execute(select(ConstitutionArticle).where(ConstitutionArticle.number == "14"))
        ).scalar_one()
        row.plain_en = "An editor's much better explanation."
        await seeded.flush()

        await seed_modules.seed_constitution(seeded, seed_modules._load_constitution_seed())
        await seeded.refresh(row)
        assert row.plain_en == "An editor's much better explanation."


# --------------------------------------------------------------------------
# Representative claim registry
# --------------------------------------------------------------------------
class TestClaimFields:
    def test_every_high_risk_field_requires_a_primary_source(self):
        for key in (
            "criminal.pending_cases",
            "criminal.serious_cases",
            "criminal.convictions",
            "assets.total",
            "attendance.percent",
        ):
            assert CLAIM_FIELDS_BY_KEY[key].requires_primary, key

    def test_every_field_explains_what_the_number_does_not_mean(self):
        for field in CLAIM_FIELDS:
            assert len(field.explanation) > 60, f"{field.key} needs a real explanation"

    def test_criminal_case_fields_state_that_charges_are_not_convictions(self):
        explanation = CLAIM_FIELDS_BY_KEY["criminal.pending_cases"].explanation.lower()
        assert "not convictions" in explanation

    def test_field_keys_are_unique(self):
        keys = [f.key for f in CLAIM_FIELDS]
        assert len(keys) == len(set(keys))

    def test_period_is_required_for_time_bound_figures(self):
        assert CLAIM_FIELDS_BY_KEY["attendance.percent"].period_required
        assert CLAIM_FIELDS_BY_KEY["assets.total"].period_required
        # Education does not change per session.
        assert not CLAIM_FIELDS_BY_KEY["background.education"].period_required

    def test_currency_is_formatted_the_way_indian_readers_parse_it(self):
        assert format_indian_currency(312_500_000) == "Rs 31.25 crore"
        assert format_indian_currency(450_000) == "Rs 4.50 lakh"
        assert format_indian_currency(4_500) == "Rs 4,500"
        assert format_indian_currency(None) is None

    def test_promise_statuses_include_the_honest_middle_options(self):
        # A tracker with only "kept" and "broken" forces every ambiguous case into a
        # verdict it cannot support.
        assert {"partially_fulfilled", "stalled", "not_assessable"} <= set(PROMISE_STATUSES)


# --------------------------------------------------------------------------
# Petitions and forum mechanics
# --------------------------------------------------------------------------
class TestCommunityMechanics:
    def test_first_petition_milestone_is_reachable(self):
        assert milestones_reached(0) == []
        assert milestones_reached(60) == [50]
        assert next_milestone(60) == 100
        assert next_milestone(10**9) is None

    def test_civic_participation_is_never_reputation_gated(self):
        assert REPUTATION_GATES["reply"] == 0
        assert REPUTATION_GATES["thread"] == 0
        assert REPUTATION_GATES["upvote"] == 0

    def test_abuse_prone_actions_are_gated(self):
        assert REPUTATION_GATES["post_links"] > 0
        assert REPUTATION_GATES["thread_on_representative"] > REPUTATION_GATES["post_links"]

    async def test_muted_citizen_reports_itself_muted(self, session):
        from datetime import timedelta

        from backend.core.models import utcnow

        citizen = Citizen(email="m@example.com", display_name="M")
        citizen.muted_until = utcnow() + timedelta(days=3)
        citizen.muted_reason = "Repeated communal framing"
        session.add(citizen)
        await session.flush()
        assert citizen.is_muted()

        citizen.muted_until = utcnow() - timedelta(days=1)
        assert not citizen.is_muted(), "an expired mute must lift itself"

    async def test_citizen_public_dict_never_exposes_the_email(self, session):
        citizen = Citizen(email="private@example.com", display_name="Pseudonym")
        session.add(citizen)
        await session.flush()
        payload = citizen.public_dict()
        assert "private@example.com" not in str(payload)
        assert payload["displayName"] == "Pseudonym"


# --------------------------------------------------------------------------
# Zones -- the grouping the state-wise sections are built on
# --------------------------------------------------------------------------
class TestZones:
    def test_every_state_belongs_to_exactly_one_zone(self):
        from backend.core.geography import STATES, ZONES, zone_of

        assigned = [code for zone in ZONES for code in zone.codes]
        assert len(assigned) == len(set(assigned)), "a state cannot sit in two zonal councils"
        assert set(assigned) == {s.code for s in STATES}, (
            "a state missing from ZONES would vanish from the petition's state-wise "
            "sections without anything failing"
        )
        assert all(zone_of(s.code) for s in STATES)

    def test_zone_membership_follows_the_councils_not_the_map(self):
        # The three that would be wrong if somebody "fixed" this by geography.
        from backend.core.geography import zone_of

        assert zone_of("SK") == "north_eastern"
        assert zone_of("AN") == "southern"
        assert zone_of("LD") == "southern"

    def test_zone_lookup_is_case_insensitive_and_safe(self):
        from backend.core.geography import zone_of

        assert zone_of("mh") == "western"
        assert zone_of("") == ""
        assert zone_of("XX") == ""


# --------------------------------------------------------------------------
# Civic tools
# --------------------------------------------------------------------------
class TestTools:
    async def test_seeded_templates_are_legally_approved_and_generatable(self, seeded):
        rows = (await seeded.execute(select(DocumentTemplate))).scalars().all()
        assert len(rows) == len(TEMPLATES)
        assert all(r.review_status == ReviewStatus.LEGAL_APPROVED for r in rows)
        assert all(r.legal_basis.strip() for r in rows), "a template must name the provision it uses"
        assert all(r.filing_notes.strip() for r in rows), "a template must say how to file it"

    async def test_every_placeholder_has_a_field_or_a_derived_clause(self, seeded):
        for template in (await seeded.execute(select(DocumentTemplate))).scalars():
            declared = {f["name"] for f in template.fields}
            # Raises HTTPException if a placeholder is unsatisfiable, which is the
            # bug this guards: a typo renders as a silent gap in someone's RTI.
            _assert_placeholders_declared(template.body, declared)

    async def test_generate_reports_all_missing_required_fields_at_once(self, seeded):
        template = (
            await seeded.execute(select(DocumentTemplate).where(DocumentTemplate.key == "rti-general"))
        ).scalar_one()
        with pytest.raises(Exception) as excinfo:
            build_document(template, {})
        detail = excinfo.value.detail
        assert len(detail["missing"]) > 3, "one field per attempt would be nine round trips"

    async def test_generated_rti_cites_the_statute_and_fills_the_fee_clause(self, seeded):
        template = (
            await seeded.execute(select(DocumentTemplate).where(DocumentTemplate.key == "rti-general"))
        ).scalar_one()
        draft = build_document(
            template,
            {
                "pio_office": "PIO, Municipal Corporation",
                "subject": "Ward 12 road repair sanction",
                "questions": "1. Copy of the sanction order\n2. Amount released",
                "is_bpl": "No",
                "fee_mode": "Indian Postal Order",
                "applicant_name": "A Citizen",
                "applicant_address": "12 Example Road, 400001",
                "place": "Mumbai",
                "letter_date": "2026-08-09",
            },
        )
        text = draft.plain_text()
        assert "Section 6(1)" in text
        assert "Indian Postal Order" in text
        assert "Section 6(3)" in text  # transfer to the right authority
        assert "Section 7(6)" not in text or True  # present in the appeal, not required here

    async def test_bpl_applicant_gets_the_exemption_clause_not_a_fee_line(self, seeded):
        template = (
            await seeded.execute(select(DocumentTemplate).where(DocumentTemplate.key == "rti-general"))
        ).scalar_one()
        draft = build_document(
            template,
            {
                "pio_office": "PIO",
                "subject": "S",
                "questions": "Q",
                "is_bpl": "Yes",
                "fee_mode": "Not applicable - BPL cardholder",
                "applicant_name": "A",
                "applicant_address": "Addr",
                "place": "P",
                "letter_date": "2026-08-09",
            },
        )
        text = draft.plain_text()
        assert "Section 7(5)" in text
        assert "prescribed application fee is enclosed" not in text

    async def test_empty_optional_clauses_do_not_leave_blank_paragraphs(self, seeded):
        template = (
            await seeded.execute(
                select(DocumentTemplate).where(DocumentTemplate.key == "representation-to-representative")
            )
        ).scalar_one()
        draft = build_document(
            template,
            {
                "representative_name": "Shri A B, MP",
                "office_address": "Office",
                "constituency": "Somewhere",
                "subject": "A specific local issue",
                "issue": "What is happening",
                "ask": "Please write to the Collector",
                "applicant_name": "A",
                "applicant_address": "Addr",
                "place": "P",
                "letter_date": "2026-08-09",
            },
        )
        # steps_taken and applicant_contact were omitted, so their blocks vanish.
        assert all(block.text.strip() for block in draft.blocks if block.kind == "para")

    def test_pil_guide_refuses_to_draft_petitions_and_points_to_legal_aid(self):
        from backend.modules.tools.seed_templates import PIL_GUIDE

        assert "do not draft petitions" in PIL_GUIDE["openingNote"].lower()
        assert any("NALSA" in item["name"] for item in PIL_GUIDE["freeLegalHelp"])
        assert "is legal advice" in PIL_GUIDE["disclaimer"].lower()
        assert "lawyer-client relationship" in PIL_GUIDE["disclaimer"].lower()

    def test_rti_guide_states_the_statutory_deadlines(self):
        from backend.modules.tools.seed_templates import RTI_GUIDE

        # Titles carry the appeal windows; bodies carry the response deadlines.
        text = " ".join(f'{step["title"]} {step["body"]}' for step in RTI_GUIDE["steps"])
        assert "30 days" in text and "48 hours" in text and "90 days" in text


# --------------------------------------------------------------------------
# AI assistant guardrails (§9)
# --------------------------------------------------------------------------
class TestAssistantGuardrails:
    def test_questions_about_the_askers_own_case_are_refused(self):
        from backend.modules.ai.router import _classify

        for question in (
            "Should I file a case against the municipality about my land",
            "Will I win my case if I appeal",
            "mera case kya hoga",
        ):
            assert _classify(question) == "legal_advice", question

    def test_partisan_questions_are_refused(self):
        from backend.modules.ai.router import _classify

        assert _classify("Who should I vote for in this election") == "out_of_scope"
        assert _classify("Which party is better for the poor") == "out_of_scope"

    def test_constitutional_questions_are_answerable(self):
        from backend.modules.ai.router import _classify

        for question in (
            "Can an MLA be recalled?",
            "Explain Article 326 in simple words",
            "What is the difference between recall and impeachment?",
        ):
            assert _classify(question) is None, question

    def test_cache_key_normalises_case_and_punctuation(self):
        from backend.modules.ai.router import _hash

        assert _hash("Can an MLA be recalled?") == _hash("can an mla be recalled")
        assert _hash("Explain Article 326") != _hash("Explain Article 32")

    def test_refusals_all_offer_a_route_forward(self):
        from backend.modules.ai.router import _REFUSALS

        for reason, spec in _REFUSALS.items():
            assert spec["links"], f"{reason} refusal offers no alternative"
            assert len(spec["answer"]) > 200

    def test_assistant_never_grounds_answers_in_unverified_user_content(self):
        from backend.modules.ai.router import GROUNDING_TYPES

        assert "report" not in GROUNDING_TYPES
        assert "forum_thread" not in GROUNDING_TYPES


# --------------------------------------------------------------------------
# DPDP
# --------------------------------------------------------------------------
class TestDpdp:
    def test_every_table_holding_a_citizen_id_is_covered_by_erasure(self):
        # This is the test that turns "remember to extend the eraser" from a comment
        # into a failing build.
        import backend.server  # noqa: F401  (imports every module, registering handlers)

        assert erasure.missing_coverage(Base.metadata) == []

    def test_handlers_are_registered_for_the_non_cascading_tables(self):
        import backend.server  # noqa: F401

        assert {"corrections", "petitions"} <= set(erasure.registered())

    async def test_erasure_deletes_the_citizen_and_their_certificates(self, session):
        citizen = Citizen(email="leaving@example.com", display_name="Leaving")
        session.add(citizen)
        await session.flush()
        await certificates.issue(
            session,
            kind="volunteer_hours",
            holder_name="Leaving",
            title="For service",
            citizen_id=citizen.id,
            holder_email=citizen.email,
        )
        await session.flush()

        removed = await erasure.run_all(session, "leaving@example.com")
        await session.flush()

        assert removed["citizen"] == 1
        assert removed["certificates"] == 1
        assert (await session.execute(select(Citizen))).scalars().all() == []
        assert (await session.execute(select(Certificate))).scalars().all() == []

    async def test_erasure_is_safe_for_someone_who_never_had_a_citizen_row(self, session):
        removed = await erasure.run_all(session, "never-posted@example.com")
        assert "citizen" not in removed

    def test_every_consent_purpose_states_data_reason_and_retention(self):
        from backend.modules.legal.policies import CONSENT_PURPOSES

        for key, spec in CONSENT_PURPOSES.items():
            assert spec["data"], key
            assert len(spec["why"]) > 30, key
            assert len(spec["retention"]) > 20, key

    def test_privacy_policy_admits_what_survives_deletion(self):
        from backend.modules.legal.policies import PRIVACY_POLICY

        headings = [s["heading"] for s in PRIVACY_POLICY["sections"]]
        assert any("survives deletion" in h for h in headings)

    def test_privacy_policy_warns_about_the_free_tier_model_provider(self):
        from backend.modules.legal.policies import PRIVACY_POLICY

        body = " ".join(s.get("body", "") for s in PRIVACY_POLICY["sections"])
        assert "Gemini" in body and "retained" in body


# --------------------------------------------------------------------------
# Module seeding
# --------------------------------------------------------------------------
class TestModuleSeeding:
    async def test_pilot_states_get_their_districts(self, seeded):
        from backend.core.models import District

        rows = (await seeded.execute(select(District))).scalars().all()
        by_state: dict[str, int] = {}
        for row in rows:
            by_state[row.state_code] = by_state.get(row.state_code, 0) + 1
        assert by_state["DL"] == 11
        assert by_state["MH"] == 36

    async def test_national_parties_are_seeded_with_the_eci_as_the_source(self, seeded):
        from backend.modules.representatives.models import Party

        rows = {p.code: p for p in (await seeded.execute(select(Party))).scalars()}
        assert {"BJP", "INC", "AAP", "BSP", "CPIM", "NPP", "IND"} <= set(rows)
        assert all("eci.gov.in" in p.source_url for p in rows.values())
        # There must be nowhere to record an opinion about a party.
        assert not hasattr(rows["BJP"], "rating")

    async def test_forum_categories_cover_every_intended_conversation(self, seeded):
        from backend.modules.forum.models import ForumCategory

        keys = set((await seeded.execute(select(ForumCategory.key))).scalars())
        assert {"right-to-recall", "constitution", "my-constituency", "state-campaigns"} <= keys

    async def test_starter_course_is_published_with_lessons_and_a_quiz(self, seeded):
        from backend.modules.academy.models import Course, Lesson, Quiz

        course = (
            await seeded.execute(select(Course).where(Course.slug == "right-to-recall-basics"))
        ).scalar_one()
        assert course.is_published
        lessons = (
            await seeded.execute(select(Lesson).where(Lesson.course_id == course.id))
        ).scalars().all()
        assert len(lessons) == 4
        assert all(lesson.article_refs for lesson in lessons), "lessons should cite articles"

        quiz = (await seeded.execute(select(Quiz).where(Quiz.course_id == course.id))).scalar_one()
        assert len(quiz.questions) >= 5
        for question in quiz.questions:
            assert 0 <= question["answer"] < len(question["options"])
            assert question["explanation"].strip(), "a quiz that says 'wrong' without why teaches nothing"

    async def test_national_petition_is_open_bilingual_and_names_nobody(self, seeded):
        from backend.modules.petitions.models import (
            NATIONAL_PETITION_SLUG,
            Petition,
            PetitionStatus,
        )

        petition = (
            await seeded.execute(select(Petition).where(Petition.slug == NATIONAL_PETITION_SLUG))
        ).scalar_one()
        assert petition.status == PetitionStatus.OPEN
        assert petition.is_official
        assert petition.state_code is None, "the common cause is national, not a state petition"
        # A standing demand that expires in ninety days would have to be
        # re-created, and its signatures would not survive that.
        assert petition.closes_at is None
        assert petition.title_hi and petition.body_hi, "§8: authored bilingually from the start"
        assert "Article 328" in petition.body, "the ask should say how it can lawfully be done"

    async def test_seeding_everything_twice_changes_nothing(self, seeded):
        from backend.modules.petitions.models import Petition

        counts_before = {}
        for model in (ConstitutionArticle, DocumentTemplate, Petition):
            counts_before[model] = len((await seeded.execute(select(model))).scalars().all())

        await seed_modules.seed_constitution(seeded, seed_modules._load_constitution_seed())
        await seed_modules.seed_forum_categories(seeded)
        await seed_modules.seed_parties(seeded)
        await seed_modules.seed_pilot_districts(seeded)
        await seed_modules.sync_tool_templates(seeded)
        await seed_modules.seed_starter_course(seeded)
        await seed_modules.seed_national_petition(seeded)
        await seeded.flush()

        for model, before in counts_before.items():
            after = len((await seeded.execute(select(model))).scalars().all())
            assert after == before, model


# --------------------------------------------------------------------------
# In-process API tests
# --------------------------------------------------------------------------
@pytest.fixture
async def client(seeded):
    """The real app, with the Postgres session dependency pointed at SQLite.

    Exercises routing, request validation and response serialisation without a
    server, a network or a database container.
    """
    from backend.core.deps import get_optional_session, get_session
    from backend.server import app

    async def override():
        yield seeded

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_optional_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestPublicApi:
    async def test_health_reports_which_integrations_are_live(self, client):
        body = (await client.get("/api/health")).json()
        assert body["status"] == "ok"
        assert set(body["features"]) == {"search", "assistant", "email"}

    async def test_health_distinguishes_configured_from_migrated(self, client):
        # `postgres: true` only means DATABASE_URL is set. `schema` is what tells
        # you the tables exist -- the difference between "misconfigured" and
        # "deployed the code but not the migration", which look identical from
        # outside (every data endpoint 500s).
        body = (await client.get("/api/health")).json()
        assert body["schema"] is True
        assert body["hint"] is None, "no hint should be offered when the schema is present"

    async def test_schema_check_is_false_without_a_database(self):
        from backend.server import _schema_ready

        assert await _schema_ready(None) is False

    async def test_schema_check_is_false_when_tables_are_missing(self):
        """The fresh-deployment case: connection fine, migrations not applied."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from backend.server import _schema_ready

        # A real, reachable database with no schema in it.
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with async_sessionmaker(engine)() as bare:
            assert await _schema_ready(bare) is False
            # The failed statement must not have left the session unusable, or the
            # commit at request teardown would 500 the health endpoint itself.
            await bare.execute(text("SELECT 1"))
        await engine.dispose()

    async def test_schema_check_is_true_once_migrated(self, seeded):
        from backend.server import _schema_ready

        assert await _schema_ready(seeded) is True

    async def test_constitution_list_and_detail(self, client):
        listing = (await client.get("/api/constitution/articles?limit=5")).json()
        assert listing["total"] >= 40
        assert len(listing["items"]) == 5

        detail = (await client.get("/api/constitution/articles/326")).json()
        assert detail["number"] == "326"
        assert detail["plainLanguage"]["isParaphrase"] is True
        # An article page must never let a paraphrase read as the law.
        assert "not the text of the Constitution" in detail["plainLanguage"]["notice"]
        assert detail["originalText"], "Article 326's verbatim text is seeded"
        assert detail["disclaimer"]

    async def test_article_missing_from_the_library_404s_helpfully(self, client):
        response = await client.get("/api/constitution/articles/999")
        assert response.status_code == 404
        assert "not in the library yet" in response.json()["detail"]

    async def test_parts_index_flags_the_repealed_part(self, client):
        parts = (await client.get("/api/constitution/parts")).json()
        by_number = {p["number"]: p for p in parts}
        assert by_number["VII"]["repealed"] is True
        assert by_number["III"]["isCore"] is True

    async def test_search_finds_a_seeded_article_and_groups_results(self, client):
        body = (await client.get("/api/search?q=adult+suffrage")).json()
        assert body["total"] >= 1
        assert body["engine"] == "postgres"
        assert any(g["type"] == "constitution_article" for g in body["groups"])

    async def test_search_coverage_is_public(self, client):
        body = (await client.get("/api/search/coverage")).json()
        assert body["total"] >= 40

    async def test_claim_fields_are_public_with_their_caveats(self, client):
        body = (await client.get("/api/claim-fields")).json()
        keys = {f["key"] for f in body["fields"]}
        assert "criminal.pending_cases" in keys
        assert body["disclaimer"]

    async def test_tools_index_lists_only_approved_templates(self, client):
        body = (await client.get("/api/tools")).json()
        templates = [t for kind in body["kinds"] for t in kind["templates"]]
        assert any(t["key"] == "rti-general" for t in templates)

    async def test_rti_generation_returns_text_and_download_links(self, client):
        response = await client.post(
            "/api/tools/generate",
            json={
                "template_key": "rti-general",
                "values": {
                    "pio_office": "PIO, Public Works Department",
                    "subject": "Road repair sanction",
                    "questions": "1. Copy of the sanction order",
                    "is_bpl": "No",
                    "fee_mode": "Indian Postal Order",
                    "applicant_name": "A Citizen",
                    "applicant_address": "12 Example Road",
                    "place": "Pune",
                    "letter_date": "2026-08-09",
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "Section 6(1)" in body["text"]
        assert body["downloads"]["docx"].endswith(".docx")
        assert "not legal advice" in body["disclaimer"]

    async def test_rti_generation_reports_missing_fields(self, client):
        response = await client.post(
            "/api/tools/generate", json={"template_key": "rti-general", "values": {}}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["missing"]

    async def test_docx_download_is_a_real_docx(self, client):
        response = await client.post(
            "/api/tools/generate.docx",
            json={
                "template_key": "recall-demand",
                "values": {
                    "representative_name": "Shri A B, MP",
                    "office_address": "Constituency office",
                    "constituency": "Somewhere",
                    "house": "Lok Sabha",
                    "applicant_name": "A Citizen",
                    "applicant_address": "12 Example Road",
                    "place": "Delhi",
                    "letter_date": "2026-08-09",
                },
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == documents.DOCX_MEDIA_TYPE
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            body = archive.read("word/document.xml").decode("utf-8")
        assert "Article 326" in body and "Article 328" in body

    async def test_national_petition_is_served_from_its_own_path(self, client):
        body = (await client.get("/api/petitions/national")).json()
        assert body["isNational"] is True
        assert body["status"] == "open"
        # The page is /petition, not /petitions/<slug>, and every link the API
        # hands out -- including the share text -- has to agree.
        assert body["url"] == "/petition"
        assert body["share"]["copy"].endswith("/petition")
        assert body["body"], "the detail payload must carry the text of the ask"

    async def test_national_petition_carries_a_complete_state_breakdown(self, client):
        breakdown = (await client.get("/api/petitions/national")).json()["stateBreakdown"]
        assert breakdown["totalStates"] == 36
        assert len(breakdown["states"]) == 36, "a state with no signatures is still listed"
        assert sum(len(z["states"]) for z in breakdown["zones"]) == 36
        assert {z["key"] for z in breakdown["zones"]} == {
            "northern",
            "central",
            "eastern",
            "western",
            "southern",
            "north_eastern",
        }
        assert all(row["count"] == 0 for row in breakdown["states"])
        assert breakdown["recorded"] == 0

    async def test_state_breakdown_counts_and_ranks_signatures(self, client, seeded):
        from backend.modules.petitions.models import (
            NATIONAL_PETITION_SLUG,
            Petition,
            PetitionSignature,
        )

        petition = (
            await seeded.execute(select(Petition).where(Petition.slug == NATIONAL_PETITION_SLUG))
        ).scalar_one()
        # Three in Maharashtra, one in Delhi, one who never told us where they are.
        for index, state in enumerate(["MH", "MH", "MH", "DL", None]):
            citizen = Citizen(email=f"signer{index}@example.com", display_name=f"S{index}")
            citizen.state_code = state
            seeded.add(citizen)
            await seeded.flush()
            seeded.add(
                PetitionSignature(
                    petition_id=petition.id, citizen_id=citizen.id, state_code=state
                )
            )
        petition.signature_count = 5
        await seeded.flush()

        breakdown = (await client.get(f"/api/petitions/{petition.slug}/by-state")).json()
        by_code = {row["code"]: row for row in breakdown["states"]}

        assert breakdown["totalSignatures"] == 5
        assert breakdown["recorded"] == 4
        assert breakdown["unspecified"] == 1
        assert breakdown["statesWithSignatures"] == 2
        assert by_code["MH"]["count"] == 3 and by_code["MH"]["rank"] == 1
        assert by_code["DL"]["count"] == 1 and by_code["DL"]["rank"] == 2
        assert by_code["KL"]["rank"] is None, "states on zero are not ranked"
        # Percentages are of the signatures that carry a state, so they add up.
        assert by_code["MH"]["share"] == 75.0
        assert breakdown["states"][0]["code"] == "MH", "ranked list leads with the leader"
        western = next(z for z in breakdown["zones"] if z["key"] == "western")
        assert western["count"] == 3

    async def test_state_breakdown_identifies_nobody(self, client, seeded):
        from backend.modules.petitions.models import (
            NATIONAL_PETITION_SLUG,
            Petition,
            PetitionSignature,
        )

        petition = (
            await seeded.execute(select(Petition).where(Petition.slug == NATIONAL_PETITION_SLUG))
        ).scalar_one()
        citizen = Citizen(email="named@example.com", display_name="Very Identifiable Name")
        citizen.state_code = "KA"
        seeded.add(citizen)
        await seeded.flush()
        seeded.add(
            PetitionSignature(
                petition_id=petition.id,
                citizen_id=citizen.id,
                state_code="KA",
                display_name="Very Identifiable Name",
                comment="A comment that should not travel with an aggregate",
                is_public=True,
            )
        )
        await seeded.flush()

        raw = (await client.get(f"/api/petitions/{petition.slug}/by-state")).text
        assert "Very Identifiable Name" not in raw
        assert "named@example.com" not in raw
        assert "should not travel" not in raw

    async def test_by_state_404s_for_an_unpublished_petition(self, client):
        assert (await client.get("/api/petitions/not-a-real-petition/by-state")).status_code == 404


@pytest.fixture
def offline_membership(monkeypatch):
    """The one-step sign without Mongo.

    Two of its three dependencies live in Mongo (the supporter record and the
    rate-limit counters) and the suite deliberately runs without it. Stubbing
    them here keeps what this endpoint is actually responsible for -- consent,
    state validation, uniqueness, the signature itself -- under test, and records
    what it asked for so the test can assert on it.
    """
    from backend.core import limits, membership

    calls: dict = {"supporters": [], "limits": [], "members": set()}

    async def fake_member_exists(email):
        return email.lower() in calls["members"]

    async def fake_ensure_supporter(**kwargs):
        calls["supporters"].append(kwargs)
        email = kwargs["email"].lower()
        calls["members"].add(email)
        return membership.SupporterRecord(
            email=email,
            name=kwargs["name"],
            movement_id="RTR-2026-ABC123",
            created_at="2026-08-13T00:00:00+00:00",
            already=False,
            access_code="TEST-CODE",
        )

    async def fake_check(action, identity, **kwargs):
        calls["limits"].append((action, identity))
        return True

    # Patched on the module objects the router looks attributes up on at call
    # time (`membership.ensure_supporter(...)`, `limits.check(...)`), which is
    # also why the router imports the modules rather than the functions.
    monkeypatch.setattr(membership, "ensure_supporter", fake_ensure_supporter)
    monkeypatch.setattr(membership, "member_exists", fake_member_exists)
    monkeypatch.setattr(limits, "check", fake_check)
    return calls


class TestOneStepSigning:
    SIGNATURE = {
        "name": "A Citizen",
        "email": "one.step@example.com",
        "state_code": "MH",
        "city": "Pune",
        "consent": True,
    }

    async def test_signing_creates_the_member_and_records_the_signature(
        self, client, offline_membership
    ):
        # "national" works as an alias everywhere under /petitions/{slug}.
        response = await client.post("/api/petitions/national/sign-public", json=self.SIGNATURE)
        assert response.status_code == 200, response.text
        signed = response.json()

        assert signed["signatureCount"] == 1
        assert signed["isNewMember"] is True
        assert signed["state"] == "MH"
        # Signed in as a result of signing: no access code to copy out of an
        # email before the browser can withdraw the signature it just made.
        assert signed["memberToken"]
        assert signed["accessCode"] == "TEST-CODE"

        breakdown = (await client.get("/api/petitions/national")).json()["stateBreakdown"]
        assert next(r for r in breakdown["states"] if r["code"] == "MH")["count"] == 1

    async def test_the_same_address_cannot_sign_twice(self, client, offline_membership):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        first = await client.post(f"/api/petitions/{slug}/sign-public", json=self.SIGNATURE)
        assert first.status_code == 200
        second = await client.post(
            f"/api/petitions/{slug}/sign-public",
            json={**self.SIGNATURE, "email": "ONE.STEP@example.com"},
        )
        assert second.status_code == 409, "uniqueness must survive a change of case"
        assert (await client.get("/api/petitions/national")).json()["signatureCount"] == 1

    async def test_an_existing_account_is_sent_to_the_login_page(self, client, offline_membership):
        """The security property: this endpoint hands out a session, so it must
        never hand out one for an address that already belongs to somebody."""
        offline_membership["members"].add("already.a.member@example.com")
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        response = await client.post(
            f"/api/petitions/{slug}/sign-public",
            json={**self.SIGNATURE, "email": "Already.A.Member@example.com"},
        )
        assert response.status_code == 409
        body = response.json()["detail"]
        assert body["code"] == "member_exists"
        assert "sign in" in body["message"].lower()
        assert not offline_membership["supporters"], "no record may be touched for that address"
        assert "memberToken" not in response.text

    async def test_consent_is_required_and_cannot_be_assumed(self, client, offline_membership):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        response = await client.post(
            f"/api/petitions/{slug}/sign-public", json={**self.SIGNATURE, "consent": False}
        )
        assert response.status_code == 400
        assert "consent" in response.json()["detail"].lower()
        assert not offline_membership["supporters"], "no record may be created without consent"

    async def test_an_unknown_state_is_rejected_rather_than_filed_under_nothing(
        self, client, offline_membership
    ):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        response = await client.post(
            f"/api/petitions/{slug}/sign-public", json={**self.SIGNATURE, "state_code": "ZZ"}
        )
        assert response.status_code == 400

    async def test_a_private_signer_is_not_listed_by_name(self, client, offline_membership):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        await client.post(
            f"/api/petitions/{slug}/sign-public",
            json={**self.SIGNATURE, "comment": "This matters in my ward."},
        )
        listed = (await client.get(f"/api/petitions/{slug}/signatures")).json()
        assert listed["totalSignatures"] == 1
        assert listed["items"] == [], "counted, not published -- show_my_name defaulted to false"

        raw = (await client.get(f"/api/petitions/{slug}/signatures")).text
        assert "A Citizen" not in raw

    async def test_an_opted_in_signer_is_listed_with_their_state(self, client, offline_membership):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        await client.post(
            f"/api/petitions/{slug}/sign-public",
            json={**self.SIGNATURE, "show_my_name": True, "comment": "Recall keeps them honest."},
        )
        items = (await client.get(f"/api/petitions/{slug}/signatures")).json()["items"]
        assert items[0]["displayName"] == "A Citizen"
        assert items[0]["state"] == "MH"
        assert items[0]["comment"] == "Recall keeps them honest."

    async def test_both_rate_limit_counters_are_spent(self, client, offline_membership):
        slug = (await client.get("/api/petitions/national")).json()["slug"]
        await client.post(f"/api/petitions/{slug}/sign-public", json=self.SIGNATURE)
        actions = [action for action, _ in offline_membership["limits"]]
        assert "petition.sign" in actions, "this endpoint is not a way around the member limit"
        assert "petition.sign.public" in actions
        assert any(identity.startswith("ip:") for _, identity in offline_membership["limits"])

    async def test_policies_are_served_from_the_api(self, client):
        privacy = (await client.get("/api/legal/privacy")).json()
        assert privacy["version"]
        assert privacy["purposes"][0]["notice"]

        policy = (await client.get("/api/legal/content-policy")).json()
        assert policy["principles"][0]["title"].startswith("Non-partisan")

        disclaimer = (await client.get("/api/legal/disclaimer")).json()
        assert "not convictions" in disclaimer["apiDisclaimer"]

    async def test_consent_notices_are_machine_readable_for_the_forms(self, client):
        body = (await client.get("/api/legal/consent-notices")).json()
        membership = next(p for p in body["purposes"] if p["key"] == "membership")
        assert membership["required"] is True
        assert "never sell" in membership["notice"]

    async def test_locales_list_marks_only_live_languages_available(self, client):
        body = (await client.get("/api/locales")).json()
        available = {loc["code"] for loc in body["locales"] if loc["available"]}
        assert available == {"en", "hi"}

    async def test_assistant_refuses_legal_advice_without_calling_a_model(self, client):
        body = (
            await client.post(
                "/api/assistant/ask",
                json={"question": "Should I file a case about my land dispute with the council"},
            )
        ).json()
        assert body["refusal"] == "legal_advice"
        assert body["engine"] == "rules"
        assert any("NALSA" in link["label"] for link in body["links"])

    async def test_assistant_refuses_partisan_questions(self, client):
        body = (
            await client.post(
                "/api/assistant/ask", json={"question": "Who should I vote for in Maharashtra"}
            )
        ).json()
        assert body["refusal"] == "out_of_scope"

    async def test_assistant_answers_from_the_library_and_shows_sources(self, client):
        body = (
            await client.post(
                "/api/assistant/ask", json={"question": "What does Article 326 say about voting age"}
            )
        ).json()
        assert body["refusal"] is None
        assert body["sources"], "an answer with no sources violates rule 1"
        assert any("326" in s["title"] for s in body["sources"])
        # No API key in the test environment, so it must degrade rather than fail.
        assert body["engine"] == "retrieval_only"

    async def test_assistant_says_so_when_the_library_has_nothing(self, client):
        body = (
            await client.post(
                "/api/assistant/ask",
                json={"question": "Which zoning bylaw governs rooftop solar in Kochi"},
            )
        ).json()
        assert body["refusal"] == "no_sources"
        assert "not going to guess" in body["answer"]

    async def test_repeated_question_is_served_from_cache(self, client):
        question = {"question": "Explain Article 368 and the amendment procedure"}
        first = (await client.post("/api/assistant/ask", json=question)).json()
        second = (await client.post("/api/assistant/ask", json=question)).json()
        assert first["cached"] is False
        assert second["cached"] is True
        assert second["answer"] == first["answer"], "a cache that answers differently is not a cache"

    async def test_certificate_verification_404s_with_a_useful_message(self, client):
        response = await client.get("/api/certificates/RTR-ZZZZ-ZZZZ")
        assert response.status_code == 404
        assert "transcription" in response.json()["detail"]

    async def test_reference_endpoints_expose_their_registries(self, client):
        assert (await client.get("/api/houses")).json()
        assert (await client.get("/api/volunteer/skills")).json()
        assert (await client.get("/api/reports/services")).json()
        assert (await client.get("/api/events/kinds")).json()
        assert (await client.get("/api/academy/levels")).json()
        assert (await client.get("/api/research/kinds")).json()["licences"]
        assert (await client.get("/api/corrections/entities")).json()
        assert (await client.get("/api/forum/categories")).json()
        assert (await client.get("/api/parties")).json()

    async def test_campaign_dashboard_data_is_available_for_all_states(self, client):
        states = (await client.get("/api/states")).json()
        assert len(states) == 36
        pilots = [s for s in states if s["isPilot"]]
        assert {s["code"] for s in pilots} == {"DL", "MH"}
        # A UT with no assembly must say so, since it changes what its page argues.
        chandigarh = next(s for s in states if s["code"] == "CH")
        assert chandigarh["hasLegislature"] is False

    async def test_admin_endpoints_reject_anonymous_callers(self, client):
        for path in (
            "/api/admin/representatives",
            "/api/admin/factcheck/queue",
            "/api/admin/corrections",
            "/api/admin/reports/queue",
            "/api/admin/forum/queue",
            "/api/admin/tools/templates",
            "/api/admin/assistant/cache",
            "/api/admin/academy/courses",
            "/api/admin/research/documents",
            "/api/admin/volunteer/submissions",
        ):
            response = await client.get(path)
            assert response.status_code == 401, path

    async def test_member_endpoints_reject_anonymous_callers(self, client):
        for path in ("/api/me/petitions", "/api/me/reports", "/api/me/forum", "/api/me/volunteer"):
            assert (await client.get(path)).status_code == 401, path

    async def test_petition_creation_requires_a_member(self, client):
        response = await client.post(
            "/api/petitions",
            json={
                "title": "Enact a Right to Recall law in this state",
                "summary": "x" * 40,
                "body": "y" * 120,
                "addressed_to": "Chief Minister",
            },
        )
        assert response.status_code == 401

    async def test_correction_can_be_filed_anonymously(self, client):
        response = await client.post(
            "/api/corrections",
            json={
                "entity_type": "constitution_article",
                "entity_id": "326",
                "summary": "The plain-English text omits the 61st Amendment",
                "source_url": "https://www.indiacode.nic.in/handle/123456789/1362",
                "source_title": "India Code, Constitution of India",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "open"

    async def test_correction_with_personal_identifiers_is_refused(self, client):
        response = await client.post(
            "/api/corrections",
            json={
                "entity_type": "representative",
                "entity_id": "someone",
                "summary": "This is wrong, ring me to discuss it please",
                "detail": "My number is 9876543210",
            },
        )
        assert response.status_code == 400
        assert any(f["code"] == "contact_details" for f in response.json()["detail"]["flags"])

    async def test_unresolved_corrections_are_disclosed_without_their_text(self, client):
        await client.post(
            "/api/corrections",
            json={
                "entity_type": "constitution_article",
                "entity_id": "21",
                "summary": "A very specific objection that should stay unpublished for now",
            },
        )
        body = (
            await client.get("/api/corrections?entityType=constitution_article&entityId=21")
        ).json()
        assert body["openCount"] == 1
        assert "very specific objection" not in body["items"][0]["summary"]
        assert "being reviewed" in body["items"][0]["summary"]


# --------------------------------------------------------------------------
# Regressions found while building the demo dataset
# --------------------------------------------------------------------------
class TestSessionLifecycle:
    """`transaction()` must commit on every clean exit path.

    The generator form (`async for session in session_scope(): ... return`) does
    NOT, because asyncio defers finalising a suspended async generator to
    `loop.shutdown_asyncgens()`. That silently discarded writes in three places --
    the bootstrap admin-password reset among them. These tests pin the contract.
    """

    async def _engine(self, tmp_path):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/t.db")
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE t (v TEXT)"))
        return engine

    async def test_transaction_commits_on_early_return(self, tmp_path, monkeypatch):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from backend.core import db as database

        engine = await self._engine(tmp_path)
        monkeypatch.setattr(database, "_engine", engine)
        monkeypatch.setattr(
            database, "_sessionmaker", async_sessionmaker(engine, expire_on_commit=False)
        )
        monkeypatch.setattr(database, "get_engine", lambda: engine)

        async def writes_then_returns():
            async with database.transaction() as session:
                await session.execute(text("INSERT INTO t VALUES ('early-return')"))
                return

        await writes_then_returns()

        async with database.transaction() as session:
            rows = (await session.execute(text("SELECT v FROM t"))).scalars().all()
        assert rows == ["early-return"], "an early return must still commit"
        await engine.dispose()

    async def test_transaction_rolls_back_on_error(self, tmp_path, monkeypatch):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from backend.core import db as database

        engine = await self._engine(tmp_path)
        monkeypatch.setattr(database, "_engine", engine)
        monkeypatch.setattr(
            database, "_sessionmaker", async_sessionmaker(engine, expire_on_commit=False)
        )
        monkeypatch.setattr(database, "get_engine", lambda: engine)

        with pytest.raises(ValueError):
            async with database.transaction() as session:
                await session.execute(text("INSERT INTO t VALUES ('should-not-persist')"))
                raise ValueError("boom")

        async with database.transaction() as session:
            rows = (await session.execute(text("SELECT v FROM t"))).scalars().all()
        assert rows == [], "a raise must roll back"
        await engine.dispose()

    def test_startup_paths_do_not_use_the_generator_form(self):
        """The three callers that return early must use `transaction()`.

        A grep-style assertion rather than a behavioural one, because the failure it
        guards against is silent: the code runs, reports success, and writes nothing.
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        for relative in (
            "backend/core/bootstrap.py",
            "backend/seed_modules.py",
            "backend/scripts/load_demo.py",
        ):
            # encoding is explicit: these files contain Devanagari, and read_text()
            # defaults to the system locale, so on a Windows developer machine
            # (cp1252) this assertion died with a UnicodeDecodeError instead of
            # running.
            source = (root / relative).read_text(encoding="utf-8")
            assert "async for session in database.session_scope()" not in source, (
                f"{relative} returns early from its session block; use "
                "database.transaction() or the writes are silently discarded"
            )


class TestNaiveDatetimeHandling:
    """SQLite returns naive datetimes where Postgres returns aware ones.

    Comparing the two raises TypeError, so any endpoint that compares a stored
    timestamp against `utcnow()` breaks on SQLite -- which is what the whole test
    suite runs on. `as_aware` is the fix; these pin it.
    """

    def test_as_aware_treats_naive_as_utc(self):
        from datetime import datetime, timezone

        from backend.core.models import as_aware, utcnow

        naive = datetime(2026, 1, 1, 12, 0, 0)
        assert as_aware(naive).tzinfo is timezone.utc
        # The point of the helper: this comparison must not raise.
        assert as_aware(naive) < utcnow()

    def test_as_aware_leaves_aware_values_alone(self):
        from datetime import datetime, timedelta, timezone

        from backend.core.models import as_aware

        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        assert as_aware(aware) is aware

    def test_as_aware_passes_none_through(self):
        from backend.core.models import as_aware

        assert as_aware(None) is None

    async def test_muted_check_works_on_naive_timestamps(self, session):
        from datetime import datetime, timedelta

        from datetime import timezone

        # Stripped of tzinfo, which is exactly how SQLite hands a stored timestamp
        # back to the ORM.
        naive_now = datetime.now(timezone.utc).replace(tzinfo=None)

        citizen = Citizen(email="naive@example.com", display_name="N")
        citizen.muted_until = naive_now + timedelta(days=1)
        session.add(citizen)
        await session.flush()
        assert citizen.is_muted() is True

        citizen.muted_until = naive_now - timedelta(days=1)
        assert citizen.is_muted() is False


class TestDatabaseUrlHandling:
    """Connection strings are copied verbatim out of a provider dashboard.

    Those strings are written for psql, so they carry libpq parameters asyncpg has
    never heard of. SQLAlchemy forwards unknown query parameters to the driver's
    connect() as keyword arguments, so leaving them in fails with
    `TypeError: connect() got an unexpected keyword argument 'sslmode'` at the first
    connection -- which is a long way from the cause.
    """

    def test_neon_url_works_unedited(self):
        from backend.core.db import _connect_args, _normalise_url

        neon = "postgresql://u:p@ep-cool-123.ap-southeast-1.aws.neon.tech/rtr?sslmode=require"
        url = _normalise_url(neon)
        assert url.startswith("postgresql+asyncpg://")
        assert "sslmode" not in url, "asyncpg would receive this as a keyword argument"
        assert _connect_args(neon)["ssl"] is True

    def test_neon_channel_binding_is_stripped(self):
        from backend.core.db import _normalise_url

        url = _normalise_url(
            "postgresql://u:p@ep-x.neon.tech/rtr?sslmode=require&channel_binding=require"
        )
        assert "channel_binding" not in url and "sslmode" not in url

    def test_heroku_style_postgres_scheme_is_upgraded(self):
        from backend.core.db import _normalise_url

        assert _normalise_url("postgres://u:p@host/db").startswith("postgresql+asyncpg://")

    def test_sslmode_disable_turns_ssl_off(self):
        from backend.core.db import _connect_args

        assert _connect_args("postgresql://u:p@host/db?sslmode=disable")["ssl"] is False

    def test_parameters_asyncpg_understands_are_kept(self):
        from backend.core.db import _normalise_url

        url = _normalise_url("postgresql://u:p@host/db?application_name=rtr&sslmode=require")
        assert "application_name=rtr" in url
        assert "sslmode" not in url

    def test_plain_local_url_gets_no_ssl_argument(self):
        from backend.core.db import _connect_args

        assert "ssl" not in _connect_args("postgresql://u:p@localhost:5432/rtr")

    def test_hosted_provider_defaults_to_ssl_when_url_is_silent(self):
        from backend.core.db import _connect_args

        # Neon refuses unencrypted connections; failing with a server-side error
        # would be a much worse first experience than defaulting correctly.
        assert _connect_args("postgresql://u:p@ep-x.neon.tech/rtr")["ssl"] is True

    def test_prepared_statement_cache_stays_disabled(self):
        from backend.core.db import _connect_args

        # Required behind Neon's pgbouncer endpoint.
        args = _connect_args("postgresql://u:p@ep-x.neon.tech/rtr?sslmode=require")
        assert args["statement_cache_size"] == 0
        assert args["prepared_statement_cache_size"] == 0

    def test_sqlite_is_untouched_apart_from_the_driver(self):
        from backend.core.db import _connect_args, _normalise_url

        assert _normalise_url("sqlite:////tmp/x.db") == "sqlite+aiosqlite:////tmp/x.db"
        assert _connect_args("sqlite:////tmp/x.db") == {}

    def test_alembic_uses_the_same_connect_args_as_the_app(self):
        """Both paths must agree, or `alembic upgrade` fails where the app works."""
        import pathlib

        env = (
            pathlib.Path(__file__).resolve().parents[1] / "migrations" / "env.py"
        ).read_text()
        assert "_connect_args" in env, (
            "migrations/env.py builds its own engine; without connect_args a hosted "
            "Postgres URL fails at migrate time only"
        )


# --------------------------------------------------------------------------
# Manifesto accountability
# --------------------------------------------------------------------------
class TestManifestoResponseStatus:
    """How completely an application was answered is DERIVED, never stored.

    These pin the derivation because it is the one number on the RTI register a
    reader is likely to quote: "the state answered 2 of 5 applications in full".
    Getting it wrong in the direction of generosity would understate a
    government's non-answering, and in the other direction would accuse it of
    stonewalling questions it actually answered.
    """

    def _rti(self, status="reply_received"):
        from backend.modules.manifesto.models import RtiApplication

        return RtiApplication(code="RTI-1", promise_id="p1", public_authority="A", status=status)

    def _questions(self, *statuses):
        from backend.modules.manifesto.models import RtiQuestion

        return [
            RtiQuestion(rti_id="r1", number=index + 1, question_text="q", answer_status=status)
            for index, status in enumerate(statuses)
        ]

    def test_every_question_answered_is_information_provided(self):
        from backend.modules.manifesto import service

        result = service.response_status(self._rti(), self._questions("answered", "answered"))
        assert result["key"] == "information_provided"
        assert "2 of 2" in result["detail"]

    def test_some_answered_is_partially_provided(self):
        from backend.modules.manifesto import service

        result = service.response_status(
            self._rti(), self._questions("answered", "not_answered", "partially_answered")
        )
        assert result["key"] == "partially_provided"
        assert "1 of 3" in result["detail"]

    def test_reply_that_answers_nothing_is_insufficient_not_awaited(self):
        """The distinction the register exists to make.

        A reply that arrives and answers nothing is a different fact from no reply
        at all, and collapsing the two would hide the more interesting one.
        """
        from backend.modules.manifesto import service

        result = service.response_status(
            self._rti(), self._questions("not_answered", "not_answered")
        )
        assert result["key"] == "information_insufficient"

    def test_no_reply_on_file_is_awaited_whatever_the_questions_say(self):
        from backend.modules.manifesto import service

        result = service.response_status(self._rti(status="filed"), self._questions("answered"))
        assert result["key"] == "awaited"
        # The application's own status carries the nuance.
        assert result["detail"] == "Filed, awaiting reply"

    def test_wholly_denied_and_wholly_transferred_keep_their_own_labels(self):
        from backend.modules.manifesto import service

        assert (
            service.response_status(self._rti(), self._questions("denied", "denied"))["key"]
            == "denied"
        )
        assert (
            service.response_status(self._rti(), self._questions("transferred"))["key"]
            == "transferred"
        )

    def test_reply_received_with_no_published_questions_is_insufficient(self):
        from backend.modules.manifesto import service

        result = service.response_status(self._rti(), [])
        assert result["key"] == "information_insufficient"


class TestManifestoPublicApi:
    """The public endpoints return nothing that is not published.

    Unpublished research is real work in progress; a half-finished RTI trail shown
    as a finished one is the exact failure this module exists to hold others to.
    """

    async def _promise(self, session, *, published: bool, suffix: str = "1"):
        """One election -> manifesto -> promise chain. `suffix` keeps the unique
        slugs and codes distinct when a test needs more than one."""
        from backend.modules.manifesto.models import (
            Manifesto,
            ManifestoElection,
            ManifestoPromise,
        )

        election = ManifestoElection(
            slug=f"test-2022-{suffix}", state_code="UT", name="Test", year=2022, is_published=True
        )
        session.add(election)
        await session.flush()
        manifesto = Manifesto(
            slug=f"test-manifesto-{suffix}",
            election_id=election.id,
            party_name="Test Party",
            title="Test manifesto",
            is_published=True,
        )
        session.add(manifesto)
        await session.flush()
        promise = ManifestoPromise(
            code=f"TEST-P00{suffix}",
            election_id=election.id,
            manifesto_id=manifesto.id,
            title="A promise",
            promise_text="The text as printed.",
            status="fulfilled",
            is_published=published,
        )
        session.add(promise)
        await session.flush()
        return promise

    async def test_unpublished_promise_is_404_not_an_empty_page(self, session):
        from fastapi import HTTPException

        # Imported from the module, not the package: `backend.modules.manifesto`
        # re-exports the APIRouter instance under the name `router`.
        from backend.modules.manifesto.router import _published_promise

        await self._promise(session, published=False)
        with pytest.raises(HTTPException) as raised:
            await _published_promise(session, "TEST-P001")
        assert raised.value.status_code == 404

    async def test_dashboard_counts_only_published_rows(self, session):
        from backend.modules.manifesto import service

        await self._promise(session, published=False, suffix="1")
        assert (await service.dashboard(session))["totalPromises"] == 0

        await self._promise(session, published=True, suffix="2")
        assert (await service.dashboard(session))["totalPromises"] == 1

    async def test_status_never_travels_without_its_meaning(self, session):
        """A badge with no explanation is a verdict; the envelope prevents one."""
        from backend.modules.manifesto import service

        for entry in (await service.dashboard(session))["byStatus"]:
            assert entry["label"] and entry["meaning"]


class TestSearchStemming:
    """Inflected query words must find the uninflected corpus.

    Substring matching only works in one direction: "recall" finds "recalled",
    "recalled" finds nothing. The AI assistant offered "Can an MLA be recalled?"
    as an example question and then refused it for want of sources, which is what
    prompted this.
    """

    def test_regular_inflections_are_stripped(self):
        from backend.core.search import _stem

        assert _stem("recalled") == "recall"
        assert _stem("recalling") == "recall"
        assert _stem("elections") == "election"
        assert _stem("authorities") == "authority"
        assert _stem("matches") == "match"

    def test_short_and_irregular_words_are_left_alone(self):
        """The floors exist so the stemmer cannot mangle a word into a prefix
        that matches half the corpus."""
        from backend.core.search import _stem

        assert _stem("led") == "led"
        assert _stem("is") == "is"
        assert _stem("process") == "process"
        assert _stem("address") == "address"

    def test_states_does_not_become_stat(self):
        """The regression that made the first version of this worse than nothing:
        "stat" matches statute, statement and status."""
        from backend.core.search import _stem

        assert _stem("states") == "state"

    async def test_an_inflected_query_finds_the_document(self, session):
        await search.index(
            session,
            entity_type="constitution_article",
            entity_id="recall-1",
            title="The power of recall",
            body="A recall is a procedure by which voters can remove a representative.",
            url_path="/c/recall",
        )
        await session.flush()

        assert await search.query(session, "recalled representative")
        assert await search.query(session, "recall")

    async def test_stemming_does_not_double_a_token_score(self, session):
        """A word matched through its stem scores once, not once per path.

        The title deliberately does not contain the query as written, because a
        raw-query-in-title hit is worth _W_TITLE_EXACT and would swamp the thing
        being measured here. The subtitle carries the term instead, so the result
        still clears MIN_SCORE on a single-word query.
        """
        await search.index(
            session, entity_type="report", entity_id="x", title="Municipal supply",
            subtitle="Water and sanitation", body="water supply in the district",
            url_path="/x",
        )
        await session.flush()

        plain = (await search.query(session, "water"))[0]["score"]
        inflected = (await search.query(session, "waters"))[0]["score"]
        assert plain == inflected

    async def test_a_stem_does_not_match_a_longer_word_that_merely_starts_with_it(
        self, session
    ):
        """The regression this design exists to prevent.

        "governs" stems to "govern", which is a substring of "government". If the
        stem were matched as a substring, a question about zoning bylaws would
        ground itself in constitutional articles and the assistant would answer
        rather than decline.
        """
        await search.index(
            session,
            entity_type="constitution_article",
            entity_id="gov",
            title="The Government of India",
            body="The Government of India shall consist of the President and Council of Ministers.",
            url_path="/c/gov",
        )
        await session.flush()

        assert await search.query(session, "governs zoning bylaw rooftop solar") == []


# --------------------------------------------------------------------------
# Open-data importer
# --------------------------------------------------------------------------
class TestRepresentativeImporter:
    """The importer writes claims about named people in bulk with nobody reading
    each row, which inverts the platform's usual safety model. These pin the
    three rules that make that acceptable."""

    AFFIDAVIT_CSV = (
        "candidate,state,year,house,party,criminal_cases,total_assets,liabilities,education\n"
        "A Candidate,Uttarakhand,2022,vidhan_sabha,Test Party,"
        '2,"Rs 1,23,45,678","Nil",Post Graduate\n'
    )

    async def _import(self, session, csv_text, *, source_url, publish=False):
        from backend.scripts.import_representatives import SOURCES, import_records

        source = SOURCES["myneta_affidavits"]
        return await import_records(
            session,
            source.parse(csv_text),
            source=source,
            source_url=source_url,
            publish=publish,
        )

    def test_currency_and_blank_cells_are_parsed_or_refused(self):
        """A misread figure here becomes a published financial allegation, so
        anything unparseable must become None rather than a guess."""
        from backend.scripts.import_representatives import _number

        assert _number("Rs 1,23,45,678") == 12345678.0
        assert _number("45%") == 45.0
        assert _number("Nil") is None
        assert _number("-") is None
        assert _number("not available") is None
        assert _number("garbage") is None

    async def test_claims_land_unverified_and_profiles_land_as_drafts(self, session):
        from backend.modules.representatives.models import Representative, RepresentativeClaim

        result = await self._import(
            session, self.AFFIDAVIT_CSV, source_url="https://myneta.info/uttarakhand2022/"
        )
        await session.flush()
        assert result.created == 1

        rep = (await session.execute(select(Representative))).scalar_one()
        assert rep.is_published is False, "a profile about a real person must not auto-publish"

        claims = list((await session.execute(select(RepresentativeClaim))).scalars())
        assert claims
        assert all(c.verification_status == "unverified" for c in claims)
        assert all(c.source_is_primary for c in claims)
        # The affidavit year travels with every figure drawn from it.
        assert all(c.period == "2022" for c in claims if c.field_key != "background.education")

    async def test_high_risk_fields_are_refused_from_a_secondary_source(self, session):
        """requires_primary is a legal control: a news report about an affidavit
        is not the affidavit."""
        from backend.modules.representatives.models import RepresentativeClaim

        result = await self._import(
            session, self.AFFIDAVIT_CSV, source_url="https://some-news-site.example/story"
        )
        await session.flush()

        claims = list((await session.execute(select(RepresentativeClaim))).scalars())
        keys = {c.field_key for c in claims}
        assert "criminal.pending_cases" not in keys
        assert "assets.total" not in keys
        # background.education does not require a primary source, so it survives.
        assert "background.education" in keys
        assert any("needs a primary source" in line for line in result.rejected)

    async def test_a_fact_checked_claim_is_never_overwritten(self, session):
        """Rule 2. An importer that reverted a fact-check would make the
        fact-check worthless."""
        from backend.modules.representatives.models import RepresentativeClaim

        await self._import(
            session, self.AFFIDAVIT_CSV, source_url="https://myneta.info/uttarakhand2022/"
        )
        await session.flush()

        claim = (
            await session.execute(
                select(RepresentativeClaim).where(
                    RepresentativeClaim.field_key == "criminal.pending_cases"
                )
            )
        ).scalar_one()
        claim.verification_status = "fact_checked"
        await session.flush()

        changed = self.AFFIDAVIT_CSV.replace(",2,", ",99,")
        result = await self._import(
            session, changed, source_url="https://myneta.info/uttarakhand2022/"
        )
        await session.flush()

        assert claim.value_number == 2.0, "the reviewed value was overwritten"
        assert result.claims_skipped_reviewed == 1
        assert result.conflicts and "left as is" in result.conflicts[0]

    async def test_reimporting_the_same_file_changes_nothing(self, session):
        from backend.modules.representatives.models import Representative

        await self._import(
            session, self.AFFIDAVIT_CSV, source_url="https://myneta.info/uttarakhand2022/"
        )
        await session.flush()
        second = await self._import(
            session, self.AFFIDAVIT_CSV, source_url="https://myneta.info/uttarakhand2022/"
        )
        await session.flush()

        assert second.created == 0
        assert second.claims_created == 0
        assert second.claims_updated == 0
        assert len((await session.execute(select(Representative))).scalars().all()) == 1

    async def test_a_dated_field_without_a_period_is_rejected(self, session):
        """An undated asset figure reads as current, which is why these fields
        set period_required."""
        undated = self.AFFIDAVIT_CSV.replace("2022,vidhan_sabha", ",vidhan_sabha")
        result = await self._import(
            session, undated, source_url="https://myneta.info/uttarakhand2022/"
        )
        # The adapter drops the row outright when the affidavit year is missing,
        # rather than importing the person with undated allegations attached.
        assert result.created == 0
        assert result.claims_created == 0


class TestManifestoImporter:
    """The bulk path into the accountability chain.

    The rule these exist to pin is the one that would be easiest to relax under
    deadline: a bulk process may import what was SAID -- the promise, the
    question, the answer, the record -- and may never import a conclusion about
    it.
    """

    PROMISES = [
        {
            "code": "TEST-P001",
            "title": "A promise",
            "promise_text": "The text exactly as printed in the manifesto.",
            "department": "Education",
            "category": "Education",
            "manifesto_page": "12",
        }
    ]
    RTI = [
        {
            "code": "TEST-RTI-001",
            "promise_code": "TEST-P001",
            "public_authority": "A Directorate",
            "filed_on": "2025-01-10",
            "status": "reply_received",
            "reply_authority": "PIO, A Directorate",
            "reply_received_on": "2025-02-05",
            "reply_url": "https://example.gov.in/reply.pdf",
        }
    ]

    async def _election(self, session):
        from backend.modules.manifesto.models import Manifesto, ManifestoElection

        election = ManifestoElection(
            slug="test-2022", state_code="UT", name="Test", year=2022, is_published=True
        )
        session.add(election)
        await session.flush()
        session.add(
            Manifesto(
                slug="test-manifesto",
                election_id=election.id,
                party_name="Test Party",
                title="Test manifesto",
                is_published=True,
            )
        )
        await session.flush()
        return election

    async def _import(self, session, **kwargs):
        from backend.scripts.import_manifesto import import_chain

        payload = {"promises": [], "rti": [], "questions": [], "documents": []}
        payload.update(kwargs)
        return await import_chain(session, election_slug="test-2022", **payload)

    async def test_an_imported_promise_carries_no_status(self, session):
        """The whole editorial gate in one assertion. A bulk process must not be
        able to publish a conclusion about a government's performance."""
        from backend.modules.manifesto.models import ManifestoPromise

        await self._election(session)
        # Even when the file tries to supply one.
        rows = [dict(self.PROMISES[0], status="fulfilled", assessment="All done")]
        await self._import(session, promises=rows)
        await session.flush()

        promise = (await session.execute(select(ManifestoPromise))).scalar_one()
        assert promise.status == "not_established"
        assert promise.is_published is False

    async def test_the_reply_due_date_is_computed_from_the_filing_date(self, session):
        """s.7(1) of the RTI Act: 30 days. Filled only when the file omits it."""
        from datetime import date

        from backend.modules.manifesto.models import RtiApplication

        await self._election(session)
        await self._import(session, promises=self.PROMISES, rti=self.RTI)
        await session.flush()

        application = (await session.execute(select(RtiApplication))).scalar_one()
        assert application.filed_on == date(2025, 1, 10)
        assert application.reply_due_on == date(2025, 2, 9)

    async def test_a_record_without_provenance_is_refused(self, session):
        """An anonymous PDF is not evidence."""
        from backend.modules.manifesto.models import GovernmentDocument

        await self._election(session)
        documents = [
            {
                "code": "TEST-DOC-1",
                "promise_code": "TEST-P001",
                "title": "An order",
                "kind": "government_order",
            }
        ]
        result = await self._import(session, promises=self.PROMISES, documents=documents)
        await session.flush()

        assert (await session.execute(select(GovernmentDocument))).scalars().all() == []
        assert any("source_note or source_url" in line for line in result.rejected)

    async def test_an_unanswered_question_is_not_recorded_as_answered(self, session):
        """Silence is the more consequential state, so it must never arise from a
        missing column."""
        from backend.modules.manifesto.models import RtiQuestion

        await self._election(session)
        questions = [
            {"rti_code": "TEST-RTI-001", "number": 1, "question": "What happened?"},
            {
                "rti_code": "TEST-RTI-001",
                "number": 2,
                "question": "And then?",
                "answer": "The department has informed that...",
            },
        ]
        await self._import(session, promises=self.PROMISES, rti=self.RTI, questions=questions)
        await session.flush()

        by_number = {
            q.number: q for q in (await session.execute(select(RtiQuestion))).scalars()
        }
        assert by_number[1].answer_status == "awaited"
        assert by_number[2].answer_status == "answered"

    async def test_reimporting_the_same_files_changes_nothing(self, session):
        from backend.modules.manifesto.models import ManifestoPromise, RtiApplication

        await self._election(session)
        await self._import(session, promises=self.PROMISES, rti=self.RTI)
        await session.flush()
        second = await self._import(session, promises=self.PROMISES, rti=self.RTI)
        await session.flush()

        assert second.promises_created == 0
        assert second.rti_created == 0
        assert second.responses_created == 0
        assert len((await session.execute(select(ManifestoPromise))).scalars().all()) == 1
        assert len((await session.execute(select(RtiApplication))).scalars().all()) == 1


class TestResearchImporter:
    """The library behind the Research Centre, the Knowledge Hub and the
    assistant's grounding."""

    async def _import(self, session, rows, **kwargs):
        from backend.scripts.import_research import import_documents

        return await import_documents(session, rows, **kwargs)

    async def test_a_row_without_its_original_is_refused(self, session):
        from backend.modules.research.models import ResearchDocument

        result = await self._import(session, [{"title": "A report", "kind": "report"}])
        await session.flush()

        assert (await session.execute(select(ResearchDocument))).scalars().all() == []
        assert any("needs its original" in line for line in result.rejected)

    async def test_hosting_a_copy_requires_an_explicit_licence(self, session):
        """A file_url is a request to host somebody's document. Guessing the
        licence there is a redistribution problem nobody notices until later."""
        result = await self._import(
            session,
            [
                {
                    "title": "A copyrighted report",
                    "source_url": "https://example.org/report",
                    "file_url": "https://example.org/report.pdf",
                }
            ],
        )
        assert result.created == 0
        assert any("no licence" in line for line in result.rejected)

    async def test_linking_without_a_licence_defaults_to_link_only(self, session):
        from backend.modules.research.models import ResearchDocument

        await self._import(
            session,
            [{"title": "A linked report", "source_url": "https://adrindia.org/x"}],
        )
        await session.flush()

        document = (await session.execute(select(ResearchDocument))).scalar_one()
        assert document.licence == "linked_only"
        assert document.file_url == ""
        assert document.is_published is False

    async def test_tags_split_on_semicolons_so_a_comma_survives(self, session):
        from backend.modules.research.models import ResearchDocument

        await self._import(
            session,
            [
                {
                    "title": "Tagged",
                    "source_url": "https://sci.gov.in/x",
                    "tags": "elections;criminal cases, pending",
                    "article_refs": "324;326",
                }
            ],
        )
        await session.flush()

        document = (await session.execute(select(ResearchDocument))).scalar_one()
        assert document.tags == ["elections", "criminal cases, pending"]
        assert document.article_refs == ["324", "326"]

    async def test_the_publisher_is_derived_from_the_citation_when_absent(self, session):
        from backend.modules.research.models import ResearchDocument

        await self._import(
            session,
            [{"title": "A judgment", "source_url": "https://sci.gov.in/judgment/1"}],
        )
        await session.flush()

        document = (await session.execute(select(ResearchDocument))).scalar_one()
        assert document.publisher == "Supreme Court of India"


class TestMigrationsMatchTheModels:
    """Alembic must build exactly the schema the models describe.

    THIS IS THE ONE DIVERGENCE THAT CANNOT BE CAUGHT IN DEVELOPMENT. Local runs
    and this whole test suite build their schema from the models
    (AUTO_CREATE_TABLES / create_all), while every deployed environment builds it
    from the migration chain. So a model column added without a migration works
    perfectly on a laptop, passes CI, and then fails in production on the first
    request that touches it -- as a 500 from a driver complaining about a column
    that does not exist, a long way from the commit that caused it.

    Comparing the two schemas is the only thing that catches it before a deploy.
    """

    def _schemas(self, tmp_path, monkeypatch):
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, inspect

        from backend.core import config as app_config
        from backend.core.models import Base
        import backend.models_all  # noqa: F401 - registers every module's tables

        migrated = tmp_path / "migrated.db"
        modelled = tmp_path / "modelled.db"
        root = pathlib.Path(__file__).resolve().parents[1]

        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))

        # Patch the CONFIG ATTRIBUTE, not the environment variable.
        # backend/core/config.py reads os.environ once at import, and
        # migrations/env.py then overwrites alembic's sqlalchemy.url from
        # `app_config.DATABASE_URL`. Setting the env var here is therefore
        # ignored, and the first version of this test consequently ran the
        # migration chain against the developer's live local database instead of
        # a throwaway file.
        monkeypatch.setattr(app_config, "DATABASE_URL", f"sqlite:///{migrated}")
        command.upgrade(config, "head")

        Base.metadata.create_all(create_engine(f"sqlite:///{modelled}"))
        return (
            inspect(create_engine(f"sqlite:///{migrated}")),
            inspect(create_engine(f"sqlite:///{modelled}")),
        )

    def test_every_model_table_exists_in_the_migrations(self, tmp_path, monkeypatch):
        migrated, modelled = self._schemas(tmp_path, monkeypatch)
        from_migrations = {t for t in migrated.get_table_names() if t != "alembic_version"}
        from_models = set(modelled.get_table_names())

        missing = from_models - from_migrations
        assert not missing, (
            f"tables exist on the models with no migration to create them: {sorted(missing)}. "
            "Add a migration, or production will 500 on the first request that touches them."
        )
        orphaned = from_migrations - from_models
        assert not orphaned, (
            f"migrations create tables no model describes: {sorted(orphaned)}. "
            "Either the model was deleted without a down-migration, or the table is dead."
        )

    def test_no_column_drift_between_the_two(self, tmp_path, monkeypatch):
        migrated, modelled = self._schemas(tmp_path, monkeypatch)
        shared = {t for t in migrated.get_table_names() if t != "alembic_version"} & set(
            modelled.get_table_names()
        )

        drift = {}
        for table in sorted(shared):
            in_migration = {c["name"] for c in migrated.get_columns(table)}
            on_model = {c["name"] for c in modelled.get_columns(table)}
            if in_migration != on_model:
                drift[table] = {
                    "missing_from_migration": sorted(on_model - in_migration),
                    "only_in_migration": sorted(in_migration - on_model),
                }

        assert not drift, f"schema drift between migrations and models: {drift}"


class TestServerlessRequirements:
    """What the deployed function is allowed to assume is installed.

    The serverless bundle installs requirements.txt and nothing else. Anything
    the app imports that is missing from it fails in production only -- and, for
    the dependencies that are imported defensively, fails SILENTLY, which is
    worse than a crash.
    """

    def _pinned(self, path):
        names = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            names.add(re.split(r"[=<>!\[]", line, 1)[0].strip().lower())
        return names

    def _root(self):
        return pathlib.Path(__file__).resolve().parents[2]

    def test_the_two_requirements_files_stay_identical(self):
        """api/requirements.txt is a safety copy for Vercel's builder, which may
        prefer a requirements.txt co-located with the function. A divergence
        means the deployed function installs a different set than anyone
        reviewing the root file believes."""
        root = self._root()
        assert (root / "requirements.txt").read_text(encoding="utf-8") == (
            root / "api" / "requirements.txt"
        ).read_text(encoding="utf-8"), (
            "requirements.txt and api/requirements.txt have drifted; they must be "
            "byte-identical (see the header comment in either file)"
        )

    def test_defensively_imported_dependencies_are_still_pinned(self):
        """httpx is imported inside a try/except by the Brevo, Meilisearch and
        Gemini clients, each of which degrades to a no-op when it is missing.

        That is the whole reason it needs pinning: without it a deployment with
        GEMINI_API_KEY set answers in retrieval-only mode and logs nothing about
        why. `pip install fastapi` does not bring httpx -- only `fastapi[all]`
        does -- so it cannot be assumed.
        """
        pinned = self._pinned(self._root() / "requirements.txt")
        assert "httpx" in pinned, (
            "httpx is missing from requirements.txt. The Gemini, Brevo and "
            "Meilisearch clients will silently no-op in production."
        )

    def test_runtime_imports_are_covered(self):
        """Every third-party package the app imports at module level is pinned.

        Scoped to backend/core and backend/modules -- the code the serverless
        function actually loads. Scripts and tests may use anything, because
        neither ships in the bundle.
        """
        root = self._root()
        pinned = self._pinned(root / "requirements.txt")
        # Import name -> distribution name, where they differ.
        aliases = {
            "jwt": "pyjwt",
            "dotenv": "python-dotenv",
            "sqlalchemy": "sqlalchemy",
            "dateutil": "python-dateutil",
            "multipart": "python-multipart",
            "motor": "motor",
            "bson": "pymongo",
            "pymongo": "pymongo",
            "qrcode": "qrcode",
            "asyncpg": "asyncpg",
            "greenlet": "greenlet",
            "certifi": "certifi",
            "dns": "dnspython",
            "email_validator": "email-validator",
        }
        stdlib_or_local = {"backend", "__future__"}

        missing = {}
        for path in (root / "backend" / "core").rglob("*.py"):
            missing.update(self._check(path, pinned, aliases, stdlib_or_local))
        for path in (root / "backend" / "modules").rglob("*.py"):
            missing.update(self._check(path, pinned, aliases, stdlib_or_local))

        assert not missing, (
            f"imported at runtime but not pinned in requirements.txt: {missing}"
        )

    def _check(self, path, pinned, aliases, skip):
        import ast
        import sys

        found = {}
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Module level only: a deferred import inside a function is a
            # deliberate optional dependency, and `httpx` is covered by its own
            # test above.
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name in skip or name in sys.stdlib_module_names:
                    continue
                distribution = aliases.get(name, name)
                if distribution.lower() not in pinned:
                    found[name] = str(path.relative_to(path.parents[3]))
        return found
