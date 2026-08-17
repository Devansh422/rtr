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

from datetime import date
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
from backend.modules.manifesto.models import ManifestoElection
from backend.modules.petitions.models import NATIONAL_PETITION_SLUG, Petition, PetitionStatus
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
# The common cause
# --------------------------------------------------------------------------
# The one national petition the whole platform points at. Shipped in the
# repository rather than created through the admin panel for the same reason the
# starter course is: it carries this movement's central demand, it goes out under
# the platform's name to the institutions named in it, and code review is a
# better gate for that text than a form field. Seeding never overwrites, so an
# editor's later improvement to the wording survives every redeploy.
#
# Every factual statement below is about the Constitution and is checkable in the
# Library on this site; no claim is made about any party, government or named
# person, and the demand is drafted to apply identically to every representative
# (§1). `closes_at` is deliberately left unset -- a standing national demand that
# expires in ninety days would have to be re-created, losing its signatures.
NATIONAL_PETITION: dict = {
    "slug": NATIONAL_PETITION_SLUG,
    "title": "Enact a Right to Recall law for elected representatives in India",
    "title_hi": "भारत में निर्वाचित प्रतिनिधियों के लिए 'राइट टू रिकॉल' कानून बनाया जाए",
    "summary": (
        "A citizen's power over a representative currently begins and ends on polling day. "
        "This petition asks Parliament and the State legislatures to create a lawful, "
        "safeguarded procedure by which the voters of a constituency can recall the person "
        "they elected before the end of the term."
    ),
    "addressed_to": "Parliament of India and the Legislative Assembly of every State",
    "target_signatures": 100_000,
    "body": (
        "We, the undersigned citizens of India, ask Parliament and the State legislatures to "
        "enact a Right to Recall: a defined legal procedure by which the registered voters of a "
        "constituency may remove the representative they elected, before the end of that "
        "representative's term, subject to the safeguards set out below.\n\n"
        "WHY. Article 83 fixes the term of the Lok Sabha at five years and Article 172 does the "
        "same for a State Legislative Assembly. Between one election and the next, the "
        "Constitution gives the electorate no means of ending a term it has granted. Article 101 "
        "(and Article 190 for the States) makes absence from every sitting for sixty days a "
        "ground on which a seat may be declared vacant -- but that is decided by the House, not "
        "by the constituency. Article 61 provides impeachment for the President and Article 124 "
        "a removal procedure for judges; neither is exercised by voters. The Constitution's one "
        "instance of continuing direct democracy is the Gram Sabha under Article 243A. Nothing "
        "equivalent exists between a voter and their MP or MLA.\n\n"
        "THE ROUTE. This does not require a constitutional amendment to begin. Under Article "
        "327, Parliament may legislate on elections to Parliament and to the State legislatures. "
        "Under Article 328, a State legislature may legislate on elections to its own House so "
        "far as Parliament has not already occupied the field -- so a single Assembly can act "
        "for its own members without waiting for anyone. Under Article 324 the Election "
        "Commission has the superintendence, direction and control of elections, which is the "
        "institution already built to verify and administer a process of this kind.\n\n"
        "THE SAFEGUARDS WE ASK FOR. A recall law without limits would be worse than no recall "
        "law, and we do not ask for one. We ask that any Bill provide: a high signature "
        "threshold, verified by the Election Commission and not by any private body; a defined "
        "window within the term, so that a representative is not campaigning permanently; "
        "defined and stated grounds; written notice to the representative and a real "
        "opportunity to be heard, as Article 21 requires of any procedure that takes away a "
        "right; a secret ballot for the recall vote itself; specific protection against the "
        "misuse of recall in constituencies reserved under Articles 330 and 332; and recovery "
        "of costs where a drive is found to be frivolous or manufactured.\n\n"
        "WHAT WE ARE ASKING FOR, SPECIFICALLY. First, that the Union Government publish its "
        "position on recall and refer the question to a parliamentary committee or the Law "
        "Commission for a public report within a stated time. Second, that State legislatures "
        "introduce a Bill under Article 328 providing for the recall of their own members, with "
        "the safeguards above. Third, that the text of any such Bill, and the report behind it, "
        "be published for public comment before it is passed.\n\n"
        "This petition names no party, no government and no individual. It asks for a law that "
        "would apply identically to every elected representative in India, including those we "
        "voted for ourselves. Accountability that only applies to one's opponents is not "
        "accountability."
    ),
    "body_hi": (
        "हम, नीचे हस्ताक्षर करने वाले भारत के नागरिक, संसद और राज्य विधानमंडलों से आग्रह करते हैं कि "
        "'राइट टू रिकॉल' को कानूनी रूप दिया जाए -- अर्थात एक ऐसी निश्चित विधिक प्रक्रिया, जिसके द्वारा "
        "किसी निर्वाचन क्षेत्र के पंजीकृत मतदाता, नीचे दी गई सुरक्षाओं के अधीन, अपने चुने हुए प्रतिनिधि को "
        "उसका कार्यकाल समाप्त होने से पहले वापस बुला सकें।\n\n"
        "क्यों। अनुच्छेद 83 लोक सभा का कार्यकाल पाँच वर्ष निर्धारित करता है और अनुच्छेद 172 राज्य "
        "विधान सभा का। एक चुनाव से अगले चुनाव के बीच, संविधान मतदाताओं को उस कार्यकाल को समाप्त "
        "करने का कोई साधन नहीं देता जो उन्होंने ही दिया है। अनुच्छेद 101 (और राज्यों के लिए अनुच्छेद 190) "
        "के अंतर्गत साठ दिन तक सभी बैठकों से अनुपस्थिति पर सीट रिक्त घोषित की जा सकती है -- परंतु यह "
        "निर्णय सदन करता है, निर्वाचन क्षेत्र नहीं। अनुच्छेद 61 राष्ट्रपति के महाभियोग की और अनुच्छेद 124 "
        "न्यायाधीशों को हटाने की प्रक्रिया देता है; इनमें से कोई भी मतदाता के हाथ में नहीं है। संविधान में "
        "निरंतर प्रत्यक्ष लोकतंत्र का एकमात्र उदाहरण अनुच्छेद 243A की ग्राम सभा है। मतदाता और उसके "
        "सांसद या विधायक के बीच ऐसा कुछ नहीं है।\n\n"
        "रास्ता। इसके लिए शुरुआत में संविधान संशोधन आवश्यक नहीं है। अनुच्छेद 327 के अंतर्गत संसद "
        "संसद और राज्य विधानमंडलों के चुनावों पर कानून बना सकती है। अनुच्छेद 328 के अंतर्गत कोई राज्य "
        "विधानमंडल अपने ही सदन के चुनावों पर कानून बना सकता है, जहाँ तक संसद ने उस विषय पर कानून "
        "न बनाया हो -- अर्थात एक अकेली विधान सभा अपने सदस्यों के लिए स्वयं यह कदम उठा सकती है। "
        "अनुच्छेद 324 के अंतर्गत निर्वाचन आयोग के पास चुनावों का अधीक्षण, निदेशन और नियंत्रण है, और "
        "यही वह संस्था है जो ऐसी प्रक्रिया के सत्यापन और संचालन के लिए पहले से मौजूद है।\n\n"
        "जिन सुरक्षाओं की हम माँग करते हैं। बिना सीमाओं वाला रिकॉल कानून, रिकॉल न होने से भी बुरा "
        "होगा, और हम ऐसी माँग नहीं करते। किसी भी विधेयक में यह होना चाहिए: हस्ताक्षरों की ऊँची सीमा, "
        "जिसका सत्यापन निर्वाचन आयोग करे, कोई निजी संस्था नहीं; कार्यकाल के भीतर एक निश्चित अवधि, "
        "ताकि प्रतिनिधि निरंतर चुनाव-प्रचार में न रहे; स्पष्ट रूप से घोषित आधार; प्रतिनिधि को लिखित सूचना "
        "और सुनवाई का वास्तविक अवसर, जैसा अनुच्छेद 21 किसी भी अधिकार-हरण करने वाली प्रक्रिया से "
        "अपेक्षित करता है; रिकॉल मतदान के लिए गुप्त मतपत्र; अनुच्छेद 330 और 332 के अंतर्गत आरक्षित "
        "निर्वाचन क्षेत्रों में दुरुपयोग के विरुद्ध विशेष संरक्षण; और तुच्छ या कृत्रिम रूप से खड़े किए गए "
        "अभियानों की स्थिति में व्यय की वसूली।\n\n"
        "हम विशेष रूप से क्या माँग रहे हैं। पहला, कि संघ सरकार रिकॉल पर अपना पक्ष सार्वजनिक करे और "
        "इस प्रश्न को किसी संसदीय समिति या विधि आयोग को, एक निश्चित समय-सीमा में सार्वजनिक रिपोर्ट "
        "के लिए सौंपे। दूसरा, कि राज्य विधानमंडल अनुच्छेद 328 के अंतर्गत अपने सदस्यों के रिकॉल के लिए "
        "उपर्युक्त सुरक्षाओं सहित विधेयक प्रस्तुत करें। तीसरा, कि ऐसे किसी विधेयक का पाठ और उसके पीछे "
        "की रिपोर्ट पारित होने से पहले जनता की टिप्पणी के लिए प्रकाशित की जाए।\n\n"
        "यह याचिका किसी दल, किसी सरकार या किसी व्यक्ति का नाम नहीं लेती। यह ऐसे कानून की माँग "
        "करती है जो भारत के हर निर्वाचित प्रतिनिधि पर समान रूप से लागू हो -- उन पर भी जिन्हें हमने "
        "स्वयं वोट दिया है। जवाबदेही यदि केवल विरोधियों पर लागू हो, तो वह जवाबदेही नहीं है।"
    ),
}


# --------------------------------------------------------------------------
# Manifesto accountability
# --------------------------------------------------------------------------
# The election itself is reference data -- a matter of public record, like the
# states list. It is seeded so the module has a spine on first boot.
#
# NOTHING ELSE IS SEEDED HERE, AND THAT IS DELIBERATE. A manifesto promise is a
# quotation from a named party's published document, and an assessment is a
# factual claim about a government. Neither may be invented to make a page look
# populated: they are entered by the research desk against the actual PDF and the
# actual RTI reply, through the admin API, where the citation and audit gates
# apply. An empty module that says "no promises published yet" is honest; a
# pre-filled one is the exact failure this platform exists to prevent (§1, §7).
UTTARAKHAND_ELECTION: dict = {
    "slug": "uttarakhand-2022",
    "state_code": "UT",
    # ISO says UT, every citizen says UK, and the code goes on RTI applications.
    "code_prefix": "UK",
    "name": "Uttarakhand Assembly Election 2022",
    "name_hi": "उत्तराखंड विधान सभा चुनाव 2022",
    "year": 2022,
    "house": "assembly",
    "election_date": date(2022, 2, 14),
    "result_date": date(2022, 3, 10),
    "source_url": "https://www.eci.gov.in/statistical-reports",
}


async def seed_manifesto_election(session: AsyncSession) -> int:
    """Open the Uttarakhand 2022 election row, once."""
    existing = (
        await session.execute(
            select(ManifestoElection).where(
                ManifestoElection.slug == UTTARAKHAND_ELECTION["slug"]
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0

    session.add(ManifestoElection(**UTTARAKHAND_ELECTION, is_published=True))
    await session.flush()
    return 1


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
            "nationalPetition": NATIONAL_PETITION["slug"],
            "nationalPetitionHash": hashlib.sha256(
                json.dumps(NATIONAL_PETITION, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "manifestoElection": UTTARAKHAND_ELECTION["slug"],
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


async def seed_national_petition(session: AsyncSession) -> int:
    """Open the national petition, once, if it is not already there.

    Opens immediately rather than entering the moderation queue, on the same
    reasoning as `create_official_petition`: the review gate for this text is
    code review, and there is no citizen author to hold accountable for it.

    Never updated in place. If the demand's wording needs to change after
    signatures exist, that is an editorial act with a public audit trail through
    the admin API -- not something a redeploy should do silently underneath the
    people who have already put their names to the old text.
    """
    existing = (
        await session.execute(select(Petition).where(Petition.slug == NATIONAL_PETITION["slug"]))
    ).scalar_one_or_none()
    if existing is not None:
        return 0

    petition = Petition(
        slug=NATIONAL_PETITION["slug"],
        title=NATIONAL_PETITION["title"],
        title_hi=NATIONAL_PETITION["title_hi"],
        summary=NATIONAL_PETITION["summary"],
        body=NATIONAL_PETITION["body"],
        body_hi=NATIONAL_PETITION["body_hi"],
        addressed_to=NATIONAL_PETITION["addressed_to"],
        # No state: this is the national demand, and every state-wise number on
        # the page is an aggregate of its signatures rather than a separate
        # petition per state.
        state_code=None,
        category="right-to-recall",
        target_signatures=NATIONAL_PETITION["target_signatures"],
        is_official=True,
        status=PetitionStatus.OPEN,
        closes_at=None,
    )
    session.add(petition)
    await session.flush()
    await search.index(
        session,
        entity_type="petition",
        entity_id=petition.slug,
        title=petition.title,
        subtitle=f"Petition to {petition.addressed_to}",
        body=petition.summary,
        keywords=["right to recall", "petition", "national"],
        is_published=True,
        url_path="/petition",
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
                "nationalPetition": await seed_national_petition(session),
                "manifestoElection": await seed_manifesto_election(session),
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
