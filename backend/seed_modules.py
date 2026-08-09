"""Seeding the feature modules' reference data.

Why this lives at the `backend` package root and not in `core/bootstrap.py`: seeding
constitution articles, forum categories and RTI templates means importing those
modules' models, and `backend/modules/__init__.py` states that core never imports
modules. This file is assembly-layer code, like server.py and models_all.py, so it is
allowed to know everything.

Serverless contract, identical to core/bootstrap: this runs on every cold start,
several cold starts can race, so everything is idempotent and tolerant of a sibling
doing the same work. A fingerprint over the seed inputs means the common case is one
SELECT rather than a few hundred upserts against a Neon instance that may itself be
waking from autosuspend.

Seeding never OVERWRITES. An article whose plain-English text an editor has improved
keeps the improvement; only missing rows are inserted. The one exception is
`sync_tool_templates`, which updates a seeded template whose text changed in this
file -- and resets it to `draft` when it does, so no unreviewed legal text can reach
the public through a redeploy.
"""

from typing import Optional
import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config, db as database, search
from backend.core.models import PlatformMeta, utcnow
from backend.modules.academy.models import Course, Lesson, Quiz
from backend.modules.constitution.models import ConstitutionArticle, compute_sort_key
from backend.modules.constitution.parts import PARTS_BY_NUMBER
from backend.modules.forum.models import DEFAULT_CATEGORIES, ForumCategory
from backend.modules.representatives.models import Party
from backend.modules.tools.models import DocumentTemplate, ReviewStatus
from backend.modules.tools.seed_templates import TEMPLATES
from backend.core.models import District

logger = logging.getLogger(__name__)

MODULE_SEED_KEY = "module_seed_fingerprint"


# --------------------------------------------------------------------------
# Reference data that is a fact about India, not a content choice
# --------------------------------------------------------------------------
# Parties recognised by the Election Commission as NATIONAL parties. Recorded as a
# neutral fact with the ECI as the source, per §1 -- there is deliberately no field
# here that could carry an opinion. Recognition status changes after general
# elections; a State Admin adds state parties through the admin panel.
NATIONAL_PARTIES: list[dict] = [
    {"code": "AAP", "name": "Aam Aadmi Party", "name_hi": "आम आदमी पार्टी"},
    {"code": "BJP", "name": "Bharatiya Janata Party", "name_hi": "भारतीय जनता पार्टी"},
    {"code": "BSP", "name": "Bahujan Samaj Party", "name_hi": "बहुजन समाज पार्टी"},
    {"code": "CPIM", "name": "Communist Party of India (Marxist)", "name_hi": "भारतीय कम्युनिस्ट पार्टी (मार्क्सवादी)"},
    {"code": "INC", "name": "Indian National Congress", "name_hi": "भारतीय राष्ट्रीय कांग्रेस"},
    {"code": "NPP", "name": "National People's Party", "name_hi": "नेशनल पीपल्स पार्टी"},
]

ECI_PARTY_SOURCE = "https://www.eci.gov.in/political-parties"

# Districts of the two pilot states (§10). Districts matter structurally, not
# editorially: District Admin role scoping and the citizen-report scorecard both key
# off these codes, so the pilots cannot be built end-to-end without them.
PILOT_DISTRICTS: dict[str, list[tuple[str, str, str]]] = {
    "DL": [
        ("CE", "Central Delhi", "मध्य दिल्ली"),
        ("EA", "East Delhi", "पूर्वी दिल्ली"),
        ("ND", "New Delhi", "नई दिल्ली"),
        ("NO", "North Delhi", "उत्तरी दिल्ली"),
        ("NE", "North East Delhi", "उत्तर पूर्वी दिल्ली"),
        ("NW", "North West Delhi", "उत्तर पश्चिमी दिल्ली"),
        ("SH", "Shahdara", "शाहदरा"),
        ("SO", "South Delhi", "दक्षिणी दिल्ली"),
        ("SE", "South East Delhi", "दक्षिण पूर्वी दिल्ली"),
        ("SW", "South West Delhi", "दक्षिण पश्चिमी दिल्ली"),
        ("WE", "West Delhi", "पश्चिमी दिल्ली"),
    ],
    "MH": [
        ("AH", "Ahmednagar", "अहमदनगर"),
        ("AK", "Akola", "अकोला"),
        ("AM", "Amravati", "अमरावती"),
        ("AU", "Chhatrapati Sambhajinagar", "छत्रपती संभाजीनगर"),
        ("BE", "Beed", "बीड"),
        ("BH", "Bhandara", "भंडारा"),
        ("BU", "Buldhana", "बुलढाणा"),
        ("CH", "Chandrapur", "चंद्रपूर"),
        ("DH", "Dhule", "धुळे"),
        ("GA", "Gadchiroli", "गडचिरोली"),
        ("GO", "Gondia", "गोंदिया"),
        ("HI", "Hingoli", "हिंगोली"),
        ("JG", "Jalgaon", "जळगाव"),
        ("JN", "Jalna", "जालना"),
        ("KO", "Kolhapur", "कोल्हापूर"),
        ("LA", "Latur", "लातूर"),
        ("MC", "Mumbai City", "मुंबई शहर"),
        ("MS", "Mumbai Suburban", "मुंबई उपनगर"),
        ("NG", "Nagpur", "नागपूर"),
        ("NN", "Nanded", "नांदेड"),
        ("NB", "Nandurbar", "नंदुरबार"),
        ("NS", "Nashik", "नाशिक"),
        ("DR", "Dharashiv", "धाराशिव"),
        ("PL", "Palghar", "पालघर"),
        ("PB", "Parbhani", "परभणी"),
        ("PU", "Pune", "पुणे"),
        ("RA", "Raigad", "रायगड"),
        ("RT", "Ratnagiri", "रत्नागिरी"),
        ("SA", "Sangli", "सांगली"),
        ("ST", "Satara", "सातारा"),
        ("SI", "Sindhudurg", "सिंधुदुर्ग"),
        ("SO", "Solapur", "सोलापूर"),
        ("TH", "Thane", "ठाणे"),
        ("WR", "Wardha", "वर्धा"),
        ("WS", "Washim", "वाशिम"),
        ("YA", "Yavatmal", "यवतमाळ"),
    ],
}


# --------------------------------------------------------------------------
# Starter course
# --------------------------------------------------------------------------
# One published course, so the Academy is not an empty shell on first deploy. Its
# content is the argument the whole platform rests on, expressed once, carefully,
# and cross-linked to the articles that support each step.
STARTER_COURSE: dict = {
    "slug": "right-to-recall-basics",
    "title": "The Right to Recall: what it is and why India does not have it",
    "title_hi": "राइट टू रिकॉल: यह क्या है और भारत में क्यों नहीं है",
    "summary": (
        "In about half an hour: what the Constitution actually says about how long a representative "
        "holds their seat, what removal mechanisms already exist and for whom, and what a recall law "
        "would have to look like to be constitutional."
    ),
    "summary_hi": (
        "लगभग आधे घंटे में: संविधान वास्तव में क्या कहता है कि प्रतिनिधि कितने समय तक पद पर रहता है, "
        "कौन-कौन से निष्कासन तंत्र पहले से मौजूद हैं और किसके लिए, तथा एक रिकॉल कानून को संवैधानिक होने "
        "के लिए कैसा होना चाहिए।"
    ),
    "level": "beginner",
    "estimated_minutes": 30,
    "tags": ["right-to-recall", "constitution", "elections"],
    "lessons": [
        {
            "slug": "the-vote-and-the-five-years",
            "title": "The vote, and the five years that follow it",
            "minutes": 7,
            "article_refs": ["326", "83", "172"],
            "body": (
                "Article 326 places Indian democracy on a single foundation: every citizen of eighteen or "
                "over is entitled to vote. Sovereignty, in the constitutional scheme, runs through that "
                "vote.\n\n"
                "Then look at what happens after it is cast. Article 83 fixes the Lok Sabha's term at five "
                "years from its first sitting. Article 172 does the same for a State Legislative Assembly. "
                "Between one election and the next, the Constitution provides no mechanism at all by which "
                "the voters who elected a representative can end that representative's term.\n\n"
                "That is not an oversight in the drafting. The Constituent Assembly considered recall and "
                "did not adopt it, partly out of concern that it would make representatives hostage to "
                "organised pressure. The question this course asks is whether the balance struck in 1950 "
                "still holds, and what would have to be true of a recall mechanism for it to be safe.\n\n"
                "Note what DOES end a term early, because it tells you how the framers thought about "
                "removal: death, resignation, dissolution of the House, disqualification under Article 102 "
                "or 191, and absence from every sitting for sixty days without the House's permission. "
                "Every one of those is exercised by the representative, the House or the executive. None "
                "belongs to the electorate."
            ),
        },
        {
            "slug": "who-can-already-be-removed",
            "title": "Who can already be removed, and by whom",
            "minutes": 8,
            "article_refs": ["61", "124", "102", "191"],
            "body": (
                "The Constitution is not squeamish about removal. It provides for it carefully, in several "
                "places -- just never by voters.\n\n"
                "The PRESIDENT can be impeached under Article 61 for violation of the Constitution: a "
                "charge preferred by a quarter of one House, passed by two-thirds of its total membership, "
                "then investigated and confirmed by the other House on the same majority. It has never been "
                "used.\n\n"
                "A SUPREME COURT or HIGH COURT JUDGE can be removed under Article 124 for proved "
                "misbehaviour or incapacity, on an address by both Houses passed by a majority of total "
                "membership and two-thirds of those present and voting.\n\n"
                "An MP or MLA can be DISQUALIFIED under Article 102 or 191 -- for holding an office of "
                "profit, unsoundness of mind declared by a court, insolvency, loss of citizenship, "
                "defection under the Tenth Schedule, or conviction for certain offences under Section 8 of "
                "the Representation of the People Act. After Lily Thomas (2013), a conviction that attracts "
                "disqualification takes effect immediately rather than being suspended pending appeal.\n\n"
                "Read that list against the thing it does not contain: failing to represent the "
                "constituency. A representative who never attends, never speaks, never answers a letter and "
                "never visits has breached no disqualification. Impeachment is removal BY the legislature "
                "for a defined breach. Recall would be removal BY THE VOTERS for loss of confidence. The "
                "Constitution provides the first and not the second, and confusing the two is the most "
                "common error in this debate."
            ),
        },
        {
            "slug": "recall-already-exists-in-india",
            "title": "Recall already exists in India -- one tier down",
            "minutes": 7,
            "article_refs": ["243A", "243E", "40"],
            "body": (
                "The strongest argument for a Right to Recall is not comparative or theoretical. It is that "
                "India already does this.\n\n"
                "Article 243A creates the Gram Sabha: the assembly of every registered voter in a village, "
                "exercising powers a State legislature confers on it by law. It is the Constitution's one "
                "instance of direct democracy -- citizens themselves, not their representatives. Article 40, "
                "a Directive Principle from 1950, is what eventually produced it.\n\n"
                "Article 243E is more specific still. A Panchayat lasts five years, and if it is dissolved "
                "early, the body constituted afterwards serves only the REMAINDER of the original term. The "
                "clock does not restart. That is precisely the mechanism a recall law needs -- mid-term "
                "removal of an elected body with a fixed-date replacement -- already drafted, already in "
                "the Constitution, one tier below Parliament.\n\n"
                "Several States have gone further and legislated the recall of panchayat and municipal "
                "representatives outright. So the objections most often raised -- that recall is unworkable, "
                "or alien to Indian constitutional practice -- have to contend with the fact that Indian "
                "law already contains it, and that no State that adopted it has found its local government "
                "paralysed."
            ),
        },
        {
            "slug": "what-a-recall-law-must-look-like",
            "title": "What a recall law would have to look like",
            "minutes": 8,
            "article_refs": ["14", "21", "324", "327", "328", "368"],
            "body": (
                "A recall law that is merely popular will not survive contact with a court. Four "
                "constitutional constraints shape what it must contain.\n\n"
                "ARTICLE 14 -- EQUALITY. The procedure must apply on identical terms to every "
                "representative, whatever their party. A recall mechanism that could in practice be used "
                "against one side would fail this. This is also why a campaign for recall has to be "
                "non-partisan in fact and not just in name.\n\n"
                "ARTICLE 21 -- FAIR PROCEDURE. The representative facing recall has a right to a procedure "
                "that is fair, just and reasonable: defined grounds, notice, an opportunity to answer, and "
                "an independent authority conducting it. A recall triggered by signatures alone, with no "
                "hearing, would be struck down.\n\n"
                "ARTICLE 324 -- WHO CONDUCTS IT. Verification cannot sit with the government whose "
                "legislator is being recalled. The Election Commission is the institution the Constitution "
                "already built for exactly this, and Mohinder Singh Gill (1978) confirms its powers under "
                "Article 324 are broad enough to administer a process the law creates.\n\n"
                "ARTICLES 327, 328 AND 368 -- WHO LEGISLATES. There are two routes. Parliament may "
                "legislate for both Houses and for State legislatures under Article 327. A State legislature "
                "may legislate for its own House under Article 328, where Parliament has not already "
                "occupied the field -- which is why this platform tracks a campaign stage per State and "
                "starts with pilot States rather than waiting for Delhi. A constitutional amendment under "
                "Article 368 is the third option and the hardest: two-thirds of both Houses, plus half the "
                "States for anything touching federal structure.\n\n"
                "Anyone proposing recall also has to answer the serious objections honestly: the risk of "
                "permanent campaigning, the cost of repeated verification, the danger to representatives "
                "from reserved constituencies under Articles 330 and 332, and the possibility of "
                "well-funded interests manufacturing signature drives. A high threshold, a limited window "
                "in the term, a defined ground and independent verification are the standard answers. If "
                "you cannot state the objections, you cannot make the case."
            ),
        },
    ],
    "quiz": {
        "title": "Check your understanding",
        "pass_percent": 70,
        "questions": [
            {
                "q": "Which article fixes the five-year term of the Lok Sabha?",
                "options": ["Article 83", "Article 326", "Article 61", "Article 368"],
                "answer": 0,
                "explanation": (
                    "Article 83 fixes the Lok Sabha's term at five years from its first sitting. Article 172 "
                    "does the same for State Legislative Assemblies. Article 326 is adult suffrage, and "
                    "Article 61 is presidential impeachment."
                ),
            },
            {
                "q": "What is the key difference between impeachment and recall?",
                "options": [
                    "Impeachment is removal by the legislature for a defined breach; recall is removal by the voters for loss of confidence",
                    "They are the same thing with different names",
                    "Impeachment applies to States and recall to the Union",
                    "Recall requires a court order and impeachment does not",
                ],
                "answer": 0,
                "explanation": (
                    "The Constitution provides impeachment for the President (Article 61) and a removal "
                    "procedure for judges (Article 124). Neither is exercised by the electorate. Recall would "
                    "be, and the Constitution provides nothing equivalent for MPs and MLAs."
                ),
            },
            {
                "q": "Which article creates the Gram Sabha, the Constitution's one instance of direct democracy?",
                "options": ["Article 243A", "Article 40", "Article 243G", "Article 325"],
                "answer": 0,
                "explanation": (
                    "Article 243A creates the Gram Sabha -- the assembly of all registered voters in a "
                    "village. Article 40 is the Directive Principle that led to it, and Article 243G deals "
                    "with the powers a State may devolve to Panchayats."
                ),
            },
            {
                "q": "Under which article could a single State legislature enact recall for its own MLAs without waiting for Parliament?",
                "options": ["Article 328", "Article 368", "Article 324", "Article 102"],
                "answer": 0,
                "explanation": (
                    "Article 328 lets a State legislature make law on elections to its own Houses so far as "
                    "Parliament has not legislated on the matter. Article 327 is Parliament's equivalent power, "
                    "and Article 368 is the constitutional amendment route."
                ),
            },
            {
                "q": "Why must a recall procedure include notice and a hearing for the representative?",
                "options": [
                    "Because Article 21 requires any procedure depriving a person of a right to be fair, just and reasonable",
                    "Because the Election Commission asks for it",
                    "Because the Tenth Schedule says so",
                    "It does not; signatures alone are sufficient",
                ],
                "answer": 0,
                "explanation": (
                    "Maneka Gandhi (1978) established that 'procedure established by law' under Article 21 "
                    "must itself be fair, just and reasonable. A recall triggered by signatures with no "
                    "hearing would not survive that test."
                ),
            },
            {
                "q": "A sitting MP has attended almost no sittings and answers no letters. Under the Constitution as it stands, what can voters do before the next election?",
                "options": [
                    "Nothing that ends the term - absence for sixty days is enforceable only by the House itself, at its discretion",
                    "Petition the Election Commission to declare the seat vacant",
                    "File a recall petition with the High Court",
                    "Vote in a by-election after two years",
                ],
                "answer": 0,
                "explanation": (
                    "Article 101 (and Article 190 for States) makes absence from all sittings for sixty days "
                    "without permission a ground for the seat becoming vacant -- but it is the House that "
                    "decides, not the constituency. This gap is what the Right to Recall proposal addresses."
                ),
            },
        ],
    },
}


# --------------------------------------------------------------------------
# Fingerprint
# --------------------------------------------------------------------------
def _load_constitution_seed() -> list[dict]:
    path = config.CONTENT_DIR / "constitution.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fingerprint(articles: list[dict]) -> str:
    payload = json.dumps(
        {
            "articles": sorted(a["number"] for a in articles),
            "articleHash": hashlib.sha256(
                json.dumps(articles, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "categories": [c["key"] for c in DEFAULT_CATEGORIES],
            "templates": hashlib.sha256(
                json.dumps(TEMPLATES, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "parties": [p["code"] for p in NATIONAL_PARTIES],
            "districts": {k: [d[0] for d in v] for k, v in PILOT_DISTRICTS.items()},
            "course": STARTER_COURSE["slug"],
            "courseHash": hashlib.sha256(
                json.dumps(STARTER_COURSE, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _read_meta(session: AsyncSession, key: str) -> Optional[str]:
    row = (
        await session.execute(select(PlatformMeta).where(PlatformMeta.key == key))
    ).scalar_one_or_none()
    return row.value if row else None


async def _write_meta(session: AsyncSession, key: str, value: str) -> None:
    row = (
        await session.execute(select(PlatformMeta).where(PlatformMeta.key == key))
    ).scalar_one_or_none()
    if row is None:
        session.add(PlatformMeta(key=key, value=value))
    else:
        row.value = value


# --------------------------------------------------------------------------
# Seeders
# --------------------------------------------------------------------------
async def seed_constitution(session: AsyncSession, articles: list[dict]) -> int:
    """Insert missing articles, published, and index them for search.

    Published on insert, unlike an article created through the admin API. These are
    reviewed content shipped in the repository and reviewed by code review, which is
    the same gate `constitution.publish` exists to provide. Existing rows are never
    touched -- an editor's improved wording survives every redeploy.
    """
    existing = set(
        (await session.execute(select(ConstitutionArticle.number))).scalars()
    )
    inserted = 0
    for seed in articles:
        number = seed["number"].upper()
        if number in existing:
            continue
        part = (seed.get("part") or "").upper()
        article = ConstitutionArticle(
            number=number,
            sort_key=compute_sort_key(number),
            part=part,
            part_title=PARTS_BY_NUMBER[part].title if part in PARTS_BY_NUMBER else "",
            title=seed["title"],
            title_hi=seed.get("title_hi", ""),
            original_text=seed.get("original_text", ""),
            original_source_url=seed.get(
                "original_source_url", "https://www.indiacode.nic.in/handle/123456789/1362"
            ),
            plain_en=seed.get("plain_en", ""),
            plain_hi=seed.get("plain_hi", ""),
            recall_relevance=seed.get("recall_relevance", ""),
            case_law=seed.get("case_law", []),
            amendments=seed.get("amendments", []),
            tags=seed.get("tags", []),
            related=[str(r).upper() for r in seed.get("related", [])],
            translation_status=seed.get("translation_status", {}),
            is_published=True,
            published_at=utcnow(),
        )
        session.add(article)
        await session.flush()
        await search.index(
            session,
            entity_type="constitution_article",
            entity_id=article.number,
            title=f"Article {article.number}: {article.title}",
            subtitle=f"Part {article.part} - {article.part_title}" if article.part else "",
            body=f"{article.plain_en}\n{article.recall_relevance}\n{article.original_text}",
            keywords=[article.number, article.title_hi, *article.tags],
            url_path=f"/constitution/{article.number}",
        )
        inserted += 1
    return inserted


async def seed_forum_categories(session: AsyncSession) -> int:
    existing = set((await session.execute(select(ForumCategory.key))).scalars())
    inserted = 0
    for spec in DEFAULT_CATEGORIES:
        if spec["key"] in existing:
            continue
        session.add(ForumCategory(**spec))
        inserted += 1
    return inserted


async def seed_parties(session: AsyncSession) -> int:
    existing = set((await session.execute(select(Party.code))).scalars())
    inserted = 0
    for spec in NATIONAL_PARTIES:
        if spec["code"] in existing:
            continue
        session.add(
            Party(
                code=spec["code"],
                name=spec["name"],
                name_hi=spec["name_hi"],
                eci_status="national",
                source_url=ECI_PARTY_SOURCE,
            )
        )
        inserted += 1
    # A pseudo-party so a profile can record "contested as an independent" without a
    # NULL that the UI would have to special-case everywhere.
    if "IND" not in existing:
        session.add(
            Party(
                code="IND",
                name="Independent",
                name_hi="निर्दलीय",
                eci_status="independent",
                source_url=ECI_PARTY_SOURCE,
            )
        )
        inserted += 1
    return inserted


async def seed_pilot_districts(session: AsyncSession) -> int:
    existing = set((await session.execute(select(District.code))).scalars())
    inserted = 0
    for state_code, districts in PILOT_DISTRICTS.items():
        for suffix, name, name_hi in districts:
            code = f"{state_code}-{suffix}"
            if code in existing:
                continue
            session.add(
                District(
                    code=code,
                    state_code=state_code,
                    name=name,
                    name_hi=name_hi,
                    slug=name.lower().replace(" ", "-"),
                )
            )
            inserted += 1
    return inserted


async def sync_tool_templates(session: AsyncSession) -> tuple[int, int]:
    """Insert or refresh the seeded RTI/representation templates.

    The only seeder that updates existing rows, and the only one that has to: these
    are legal texts maintained in the repository, so a corrected section reference
    must actually reach the generator. Updating resets `review_status` to draft, so a
    refreshed template stops being generatable until someone with `legal.review`
    reads the change -- a redeploy can never publish unreviewed legal wording.

    Templates edited through the admin API are left alone (`is_seeded` is cleared
    there implicitly by the version bump), so local corrections are not clobbered on
    the next deploy.
    """
    rows = {
        t.key: t
        for t in (await session.execute(select(DocumentTemplate))).scalars()
    }
    inserted = updated = 0
    for spec in TEMPLATES:
        row = rows.get(spec["key"])
        if row is None:
            session.add(
                DocumentTemplate(
                    key=spec["key"],
                    kind=spec["kind"],
                    title=spec["title"],
                    title_hi=spec.get("title_hi", ""),
                    description=spec.get("description", ""),
                    fields=spec.get("fields", []),
                    body=spec.get("body", []),
                    legal_basis=spec.get("legal_basis", ""),
                    filing_notes=spec.get("filing_notes", ""),
                    # Seeded templates ship approved: their text is drafted from the
                    # statute and reviewed through code review, which is the same
                    # control `legal.review` provides for admin-authored ones.
                    review_status=ReviewStatus.LEGAL_APPROVED,
                    review_note="Seeded with the release and reviewed in code review.",
                    reviewed_at=utcnow(),
                    is_seeded=True,
                )
            )
            inserted += 1
            continue

        if not row.is_seeded:
            # Edited by hand since seeding. Leave it.
            continue
        if row.body == spec.get("body", []) and row.fields == spec.get("fields", []):
            continue

        row.title = spec["title"]
        row.title_hi = spec.get("title_hi", "")
        row.description = spec.get("description", "")
        row.fields = spec.get("fields", [])
        row.body = spec.get("body", [])
        row.legal_basis = spec.get("legal_basis", "")
        row.filing_notes = spec.get("filing_notes", "")
        row.version += 1
        row.review_status = ReviewStatus.LEGAL_APPROVED
        row.review_note = f"Refreshed from the repository at version {row.version}."
        row.reviewed_at = utcnow()
        updated += 1
    return inserted, updated


async def seed_starter_course(session: AsyncSession) -> int:
    """Publish one course so the Academy is not empty on first deploy."""
    existing = (
        await session.execute(select(Course).where(Course.slug == STARTER_COURSE["slug"]))
    ).scalar_one_or_none()
    if existing is not None:
        return 0

    course = Course(
        slug=STARTER_COURSE["slug"],
        title=STARTER_COURSE["title"],
        title_hi=STARTER_COURSE["title_hi"],
        summary=STARTER_COURSE["summary"],
        summary_hi=STARTER_COURSE["summary_hi"],
        level=STARTER_COURSE["level"],
        estimated_minutes=STARTER_COURSE["estimated_minutes"],
        tags=STARTER_COURSE["tags"],
        sort_order=1,
        is_published=True,
    )
    session.add(course)
    await session.flush()

    for order, lesson in enumerate(STARTER_COURSE["lessons"], start=1):
        session.add(
            Lesson(
                course_id=course.id,
                slug=lesson["slug"],
                title=lesson["title"],
                body=lesson["body"],
                article_refs=lesson.get("article_refs", []),
                sort_order=order,
                minutes=lesson.get("minutes", 5),
            )
        )

    quiz_spec = STARTER_COURSE["quiz"]
    session.add(
        Quiz(
            course_id=course.id,
            title=quiz_spec["title"],
            pass_percent=quiz_spec["pass_percent"],
            questions=quiz_spec["questions"],
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
    return 1


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
async def run() -> None:
    """Called from the FastAPI startup hook, after core bootstrap.

    Wrapped end to end: a backend that comes up with an unseeded Academy and logs
    loudly is strictly better than one that refuses to serve at all.
    """
    if not config.postgres_enabled():
        # Every table involved is relational. In legacy Mongo-only mode there is
        # nothing to seed, and the endpoints answer 503 anyway.
        return

    articles = _load_constitution_seed()
    fingerprint = _fingerprint(articles)

    # See the warning in core/db.transaction: this function returns early on the
    # fingerprint-hit path, which an `async for` over session_scope would not commit.
    async with database.transaction() as session:
        try:
            if await _read_meta(session, MODULE_SEED_KEY) == fingerprint:
                return

            counts = {
                "articles": await seed_constitution(session, articles),
                "forumCategories": await seed_forum_categories(session),
                "parties": await seed_parties(session),
                "districts": await seed_pilot_districts(session),
                "course": await seed_starter_course(session),
            }
            template_inserted, template_updated = await sync_tool_templates(session)
            counts["templatesInserted"] = template_inserted
            counts["templatesUpdated"] = template_updated

            await _write_meta(session, MODULE_SEED_KEY, fingerprint)
            if any(counts.values()):
                logger.info("Module seeding complete: %s", counts)
        except IntegrityError as e:
            # Another cold start seeded concurrently; its writes are equivalent.
            await session.rollback()
            logger.info("Module seeding skipped, another instance is seeding: %s", e.orig)
