"""The AI Constitution Assistant.

Retrieval-Augmented Generation, per §9, and the retrieval half is the part that
matters. The assistant is not allowed to answer from the model's own knowledge:
every answer is grounded in text pulled from this platform's own Constitution
Library and Research Centre, the sources are returned alongside the answer, and if
retrieval finds nothing relevant the assistant says so instead of composing
something plausible.

Retrieval goes through the shared search index (core/search), which is also why
this module does not import the constitution module -- §4's one-way rule holds, and
the index is exactly the seam that makes it hold.

Four hard rules, enforced in code rather than in the prompt alone, because a prompt
is a request and a code path is a guarantee:

1. **No sources, no answer.** `_refuse_no_sources` returns before any model call.
2. **No legal advice.** Questions phrased as "what should I do about my case" are
   answered with the PIL Resource Centre and free legal aid routes, not with advice.
3. **No PII leaves the platform.** The question is scrubbed of identifiers before it
   is sent anywhere, because §5 warns that free-tier prompts may be retained.
4. **Degrade, never fail.** With no API key, or when the quota is gone, the
   assistant returns the retrieved passages with a plain explanation. That is a
   genuinely useful answer -- it is what a good library index does -- and it costs
   nothing.
"""

from typing import Optional
import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config, limits, moderation, search
from backend.core.deps import get_session, require_permission
from backend.core.models import utcnow
from backend.core.rbac import Principal
from backend.modules.ai.models import AnswerCache, QuestionLog

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Types the assistant may ground an answer in. Citizen reports and forum posts are
# deliberately absent: they are unverified first-person accounts, and an assistant
# that quotes them is laundering them into fact.
GROUNDING_TYPES = ("constitution_article", "research_document", "promise", "state")
MIN_SOURCES = 1
TOP_K = 5


class AskIn(BaseModel):
    question: str = Field(..., min_length=8, max_length=500)
    locale: str = "en"


# Phrasings that make a question a request for advice on the asker's own matter.
# Answering these is both outside what a retrieval assistant can do honestly and,
# arguably, the unauthorised practice of law.
_ADVICE_PATTERNS = [
    r"\bmy case\b", r"\bmy matter\b", r"\bshould i (file|sue|appeal|go to court)\b",
    r"\bwill i win\b", r"\bcan i sue\b", r"\bam i entitled\b", r"\bmy fir\b",
    r"\bmy land\b", r"\bmy property (dispute|case)\b", r"\bmy divorce\b",
    r"\bmera case\b", r"\bmujhe kya karna\b", r"\bkya main.*kar sakta hoon\b",
    r"\bhow much compensation (will|can) i\b", r"\bmy bail\b",
]

# Questions that are not what this assistant is for at all.
_OUT_OF_SCOPE_PATTERNS = [
    r"\bwho should i vote for\b", r"\bwhich party is (better|best)\b",
    r"\bkis party ko vote\b", r"\bis .* corrupt\b",
    r"\bwrite (me )?a (poem|song|essay|story)\b", r"\btranslate this\b",
]


def _normalise(question: str) -> str:
    """Collapse a question to its cache key form."""
    text = re.sub(r"\s+", " ", (question or "").strip().lower())
    return re.sub(r"[?!.]+$", "", text)


def _hash(question: str) -> str:
    return hashlib.sha256(_normalise(question).encode("utf-8")).hexdigest()


def _classify(question: str) -> Optional[str]:
    """Return a refusal reason, or None if the question is answerable."""
    lowered = question.lower()
    if any(re.search(p, lowered) for p in _OUT_OF_SCOPE_PATTERNS):
        return "out_of_scope"
    if any(re.search(p, lowered) for p in _ADVICE_PATTERNS):
        return "legal_advice"
    return None


_REFUSALS: dict[str, dict] = {
    "legal_advice": {
        "answer": (
            "This looks like a question about your own legal situation, and I am not able to advise on "
            "that -- not as a limitation of this tool, but because advice on your facts needs a lawyer "
            "who can see them.\n\n"
            "What is available to you right now, free of cost:\n"
            "- Free legal aid is a statutory entitlement for many people under the Legal Services "
            "Authorities Act, 1987. Every district has a District Legal Services Authority at the court "
            "complex, and NALSA lists them.\n"
            "- If your grievance is with a public authority, an RTI application is often the strongest "
            "first step, and this platform will draft one for you.\n"
            "- The PIL Resource Centre explains when a matter belongs in a High Court under Article 226 "
            "and what a court will expect you to have tried first.\n\n"
            "Ask me instead about what a provision of the Constitution says, or how a procedure works in "
            "general, and I can help with that."
        ),
        "links": [
            {"label": "PIL Resource Centre", "url": "/tools/pil"},
            {"label": "Generate an RTI application", "url": "/tools/rti"},
            {"label": "NALSA - free legal aid", "url": "https://nalsa.gov.in/"},
        ],
    },
    "out_of_scope": {
        "answer": (
            "I only answer questions about the Constitution, electoral law and how accountability "
            "mechanisms work. I do not evaluate parties or candidates, and this platform is non-partisan "
            "by policy -- it holds every party to the same standard and takes no position on how anyone "
            "should vote.\n\n"
            "If you want to judge a representative's record, the Representative Database publishes their "
            "attendance, questions, declared assets and criminal cases, each with a link to the public "
            "record it came from. Read the sources and decide for yourself."
        ),
        "links": [
            {"label": "Representative Database", "url": "/representatives"},
            {"label": "Content policy", "url": "/content-policy"},
        ],
    },
    "no_sources": {
        "answer": (
            "I could not find anything in this platform's Constitution Library or Research Centre that "
            "answers this, so I am not going to guess. Making up an Article number would be worse than "
            "saying nothing.\n\n"
            "The library currently covers the core articles on fundamental rights, elections, the "
            "legislature and amendment. If your question is about a provision that is not in it yet, the "
            "full text is on India Code, and you can ask a researcher to add it through the forum."
        ),
        "links": [
            {"label": "Browse the Constitution Library", "url": "/constitution"},
            {"label": "India Code - full text", "url": "https://www.indiacode.nic.in/handle/123456789/1362"},
            {"label": "Ask in the Research forum", "url": "/forum?category=research"},
        ],
    },
}

SYSTEM_PROMPT = """\
You are the Constitution Assistant for the Right to Recall Movement, a non-partisan Indian civic \
platform. You explain Indian constitutional and electoral law in plain language.

ABSOLUTE RULES:
1. Answer ONLY from the numbered sources given below. If they do not contain the answer, say plainly \
that the platform's library does not cover it. Never fill a gap from memory.
2. Cite the specific Article number or document title you are relying on, inline, e.g. "under Article 326".
3. NEVER state an Article number that does not appear in the sources. If you are unsure of a number, \
describe the provision without numbering it.
4. Do not give legal advice about anyone's particular case. Point to the PIL Resource Centre and free \
legal aid instead.
5. Be strictly non-partisan. Never praise or criticise a party, a government or a named politician. \
Discuss institutions and provisions.
6. Distinguish clearly between what the Constitution SAYS and what courts have HELD.
7. Be brief: 120-220 words, plain sentences, no preamble, no bullet-point padding.
8. If the question is in Hindi or Hinglish, answer in the same language.
"""


def _build_prompt(question: str, sources: list[dict]) -> str:
    numbered = "\n\n".join(
        f"[{i + 1}] {s['title']}\n{s.get('snippet') or s.get('subtitle') or ''}"
        for i, s in enumerate(sources)
    )
    return f"{SYSTEM_PROMPT}\n\nSOURCES:\n{numbered}\n\nQUESTION: {question}\n\nANSWER:"


async def _call_gemini(prompt: str) -> Optional[str]:
    """One generation call. None on any failure, so the caller falls back."""
    if not config.GEMINI_API_KEY:
        return None
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return None

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"{GEMINI_URL}/{config.GEMINI_MODEL}:generateContent",
                params={"key": config.GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        # Low temperature: this is an explainer, and creative
                        # variation in a constitutional answer is a defect.
                        "temperature": 0.2,
                        "maxOutputTokens": 500,
                        "topP": 0.9,
                    },
                },
            )
        if response.status_code == 429:
            logger.info("Gemini free-tier quota exhausted; serving retrieval-only answers")
            return None
        if response.status_code >= 400:
            logger.warning("Gemini error %s: %s", response.status_code, response.text[:300])
            return None
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        return text or None
    except Exception as e:
        logger.warning("Gemini call failed: %s", e)
        return None


def _retrieval_answer(sources: list[dict]) -> str:
    """The no-model answer: what the library has, and why it is relevant.

    Worth reading rather than a placeholder. A ranked list of the right articles
    with their opening lines is what a good index gives you, and most questions are
    resolved by being pointed at the right provision.
    """
    lines = [
        "Here is what this platform's library holds on that. I have not generated an explanation -- "
        "these are the sources themselves, in order of relevance:",
        "",
    ]
    for source in sources:
        snippet = (source.get("snippet") or source.get("subtitle") or "").strip()
        lines.append(f"- {source['title']}" + (f" - {snippet}" if snippet else ""))
    lines.extend(
        [
            "",
            "Open any of them for the original text, the plain-language explanation and the relevant "
            "case law.",
        ]
    )
    return "\n".join(lines)


def _answer_payload(
    *,
    question: str,
    answer: str,
    sources: list[dict],
    engine: str,
    cached: bool,
    reviewed: bool = False,
    links: Optional[list[dict]] = None,
    refusal: Optional[str] = None,
) -> dict:
    return {
        "question": question,
        "answer": answer,
        # Always present, always the platform's own pages, so any claim in the
        # prose can be checked against the provision it came from.
        "sources": [
            {
                "title": s["title"],
                "url": s["url"],
                "type": s["entityType"],
                "snippet": s.get("snippet"),
            }
            for s in sources
        ],
        "links": links or [],
        "engine": engine,
        "cached": cached,
        "humanReviewed": reviewed,
        "refusal": refusal,
        "disclaimer": (
            "This is a general explanation grounded in the sources listed above. It is not legal advice, "
            "and it is not a substitute for reading the provision itself. Where the answer and a source "
            "disagree, the source is right."
        ),
    }


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/assistant/status")
async def assistant_status(session: AsyncSession = Depends(get_session)):
    """What the assistant can currently do, so the UI can be honest about it."""
    indexed = (
        await session.execute(
            select(func.count())
            .select_from(search.SearchDoc)
            .where(
                search.SearchDoc.entity_type.in_(list(GROUNDING_TYPES)),
                search.SearchDoc.is_published.is_(True),
            )
        )
    ).scalar_one()
    return {
        "available": True,
        "engine": config.assistant_engine(),
        "indexedSources": indexed,
        "note": (
            "Answers are generated from this platform's own library and always show their sources."
            if config.GEMINI_API_KEY
            else "No generation model is configured, so the assistant returns the relevant sources from "
            "the library rather than a written answer."
        ),
        "examples": [
            "Can an MLA be recalled?",
            "Explain Article 326 in simple words",
            "What is the difference between recall and impeachment?",
            "How long is a Lok Sabha member's term, and can it end early?",
            "Who can be disqualified from being an MP?",
        ],
    }


@router.post("/assistant/ask")
async def ask(
    payload: AskIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    question = payload.question.strip()

    # Rule 3, first: identifiers are removed before the text goes anywhere,
    # including into this platform's own log.
    question = moderation.scrub_identifiers(question)

    refusal = _classify(question)
    if refusal:
        session.add(
            QuestionLog(question=question, was_answered=False, refusal_reason=refusal)
        )
        canned = _REFUSALS[refusal]
        return _answer_payload(
            question=question,
            answer=canned["answer"],
            sources=[],
            engine="rules",
            cached=False,
            links=canned["links"],
            refusal=refusal,
        )

    await limits.check("ai.ask", limits.identity_for(request))

    key = _hash(question)
    cached = (
        await session.execute(select(AnswerCache).where(AnswerCache.question_hash == key))
    ).scalar_one_or_none()
    if cached is not None:
        cached.hit_count += 1
        session.add(QuestionLog(question=question, was_cached=True, engine=cached.engine))
        return _answer_payload(
            question=question,
            answer=cached.answer,
            sources=cached.citations,
            engine=cached.engine,
            cached=True,
            reviewed=cached.is_reviewed,
        )

    sources = await search.query(
        session, question, types=GROUNDING_TYPES, limit=TOP_K
    )
    if len(sources) < MIN_SOURCES:
        # Rule 1. No model call happens at all on this path.
        session.add(
            QuestionLog(question=question, was_answered=False, refusal_reason="no_sources")
        )
        canned = _REFUSALS["no_sources"]
        return _answer_payload(
            question=question,
            answer=canned["answer"],
            sources=[],
            engine="rules",
            cached=False,
            links=canned["links"],
            refusal="no_sources",
        )

    generated = await _call_gemini(_build_prompt(question, sources))
    engine = "gemini" if generated else "retrieval_only"
    answer = generated or _retrieval_answer(sources)

    session.add(
        AnswerCache(
            question_hash=key,
            question=question,
            answer=answer,
            citations=[
                {
                    "title": s["title"],
                    "url": s["url"],
                    "entityType": s["entityType"],
                    "snippet": s.get("snippet"),
                }
                for s in sources
            ],
            engine=engine,
            hit_count=0,
        )
    )
    session.add(QuestionLog(question=question, engine=engine))

    return _answer_payload(
        question=question, answer=answer, sources=sources, engine=engine, cached=False
    )


@router.post("/assistant/feedback")
async def feedback(
    request: Request,
    question: str = Query(..., max_length=500),
    helpful: bool = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Flag an answer as unhelpful so a human can look at it.

    An unhelpful cached answer is a bug with a permanent blast radius -- every
    future asker gets the same wrong thing -- so this un-reviews it and puts it in
    front of staff rather than silently regenerating.
    """
    cached = (
        await session.execute(select(AnswerCache).where(AnswerCache.question_hash == _hash(question)))
    ).scalar_one_or_none()
    if cached is None:
        return {"ok": True, "note": "No cached answer to flag."}

    if not helpful:
        cached.is_reviewed = False
        cached.review_note = "Flagged as unhelpful by a reader"
    return {"ok": True}


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/assistant/cache")
async def list_cache(
    unreviewed_only: bool = False,
    limit: int = Query(default=100, ge=1, le=300),
    admin: Principal = Depends(require_permission("ai.manage")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AnswerCache).order_by(AnswerCache.hit_count.desc()).limit(limit)
    if unreviewed_only:
        stmt = stmt.where(AnswerCache.is_reviewed.is_(False))
    rows = (await session.execute(stmt)).scalars()
    return [
        {
            "id": row.id,
            "question": row.question,
            "answer": row.answer,
            "citations": row.citations,
            "engine": row.engine,
            "hitCount": row.hit_count,
            "isReviewed": row.is_reviewed,
            "isPinned": row.is_pinned,
            "reviewNote": row.review_note or None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.put("/admin/assistant/cache/{cache_id}")
async def edit_cached_answer(
    cache_id: str,
    answer: str = Query(..., min_length=20),
    pin: bool = True,
    admin: Principal = Depends(require_permission("ai.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Rewrite a cached answer by hand and pin it.

    The correction mechanism for the assistant. A pinned answer is served verbatim
    and never regenerated, so a wrong answer to a frequently asked question is
    fixed once, permanently, by a person.
    """
    cached = (
        await session.execute(select(AnswerCache).where(AnswerCache.id == cache_id))
    ).scalar_one_or_none()
    if cached is None:
        raise HTTPException(status_code=404, detail="Cached answer not found")

    cached.answer = answer.strip()
    cached.is_reviewed = True
    cached.is_pinned = pin
    cached.reviewed_by = admin.id
    cached.review_note = "Edited and approved by staff"
    cached.updated_at = utcnow()
    return {"ok": True, "isPinned": cached.is_pinned}


@router.delete("/admin/assistant/cache/{cache_id}")
async def delete_cached_answer(
    cache_id: str,
    admin: Principal = Depends(require_permission("ai.manage")),
    session: AsyncSession = Depends(get_session),
):
    cached = (
        await session.execute(select(AnswerCache).where(AnswerCache.id == cache_id))
    ).scalar_one_or_none()
    if cached is None:
        raise HTTPException(status_code=404, detail="Cached answer not found")
    await session.delete(cached)
    return {"ok": True}


@router.get("/admin/assistant/gaps")
async def coverage_gaps(
    limit: int = Query(default=50, ge=1, le=200),
    admin: Principal = Depends(require_permission("ai.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Questions the library could not answer, most frequent first.

    The most actionable screen in this module: it is a list of pages the
    Constitution Library and Knowledge Centre should have, written by the people who
    wanted them.
    """
    rows = (
        await session.execute(
            select(QuestionLog.question, func.count())
            .where(QuestionLog.was_answered.is_(False), QuestionLog.refusal_reason == "no_sources")
            .group_by(QuestionLog.question)
            .order_by(func.count().desc())
            .limit(limit)
        )
    ).all()
    totals = dict(
        (
            await session.execute(
                select(QuestionLog.refusal_reason, func.count()).group_by(QuestionLog.refusal_reason)
            )
        ).all()
    )
    return {
        "unanswered": [{"question": question, "count": count} for question, count in rows],
        "refusalTotals": [
            {"reason": reason or "answered", "count": count} for reason, count in totals.items()
        ],
    }
