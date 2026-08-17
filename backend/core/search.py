"""Cross-module search over the shared `search_docs` index.

Two things this solves at once.

**Dependency direction.** Search has to span constitution articles,
representatives, states, petitions, research documents and academy courses. If
the search module imported all of them, §4's one-way rule would be dead on
arrival. Instead each module calls `index()` when it publishes, and search only
ever reads one table.

**Free-tier reality.** §5 picks self-hosted Meilisearch, which needs a container
this project does not have. So the default engine is Postgres, and the honest
version of that decision is: for a few thousand short documents, a scan with
Python-side ranking is not a compromise, it is the correct amount of machinery.
`MEILISEARCH_URL` switches engines without touching a caller, for when the index
outgrows it -- the trigger is roughly "over ~50k docs, or query latency past
300ms on a warm database".

Ranking is computed in Python rather than SQL so the same code produces the same
order on SQLite (tests) and Postgres (production), and so the weights are
readable instead of buried in a CASE expression.
"""

from functools import lru_cache
from typing import Iterable, Optional
import logging
import re

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config
from backend.core.models import SearchDoc, utcnow

logger = logging.getLogger(__name__)

# Body text is truncated before storage. The index exists to FIND a page, not to
# be a second copy of it, and an unbounded body column on a 0.5 GB database
# would make the index the largest thing in it.
MAX_BODY_CHARS = 2000

# Weights for the Postgres path. Deliberately coarse: a title hit should beat a
# body hit decisively, and everything else is tie-breaking.
_W_TITLE_EXACT = 100
_W_TITLE_TOKEN = 30
_W_SUBTITLE_TOKEN = 12
_W_KEYWORD_TOKEN = 10
_W_BODY_TOKEN = 3

_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)

# Words too common in this corpus to narrow anything -- every second document
# mentions "article" or "constitution".
#
# Question words matter more here than in a typical stoplist, because most queries
# arrive as questions. Leaving "which" in was a real bug: "which zoning bylaw
# governs rooftop solar" matched dozens of articles on "which" alone, so the AI
# assistant believed it had found relevant sources and answered from them.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is",
        "are", "was", "were", "be", "been", "by", "with", "from", "as", "if",
        "not", "no", "any", "all", "about", "into", "than", "then",
        "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
        "can", "could", "should", "would", "will", "shall", "may", "might", "must",
        "does", "do", "did", "has", "have", "had",
        "i", "my", "me", "we", "our", "you", "your", "it", "its", "this", "that",
        "these", "those", "there", "here",
        "ka", "ki", "ke", "kaa", "hai", "hain", "kya", "kaise", "kab", "kahan",
        "kaun", "kyon", "mein", "me", "se", "ko", "par", "aur", "ya", "nahi",
    }
)

# A result has to clear this to count as a hit. Without a floor, one incidental
# body-word match (worth _W_BODY_TOKEN) returns a "relevant" document, which is how
# a search box looks broken and how the AI assistant ends up grounding an answer in
# a page that merely shares a word with the question.
MIN_SCORE = 10


def tokenise(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split((text or "").lower()) if t and t not in _STOPWORDS]


def _stem(token: str) -> str:
    """Strip regular English inflections, conservatively.

    WHY THIS EXISTS. Matching is substring-based, so a query token has to be a
    substring of the document. That works in one direction only: searching
    "recall" finds "recalled", and searching "recalled" finds nothing at all.
    The AI assistant listed "Can an MLA be recalled?" among its own example
    questions and then refused it for want of sources -- the corpus says
    "recall" throughout -- which is the clearest possible demonstration of the
    problem.

    NOT A REAL STEMMER, and deliberately not. Porter would fold "election" and
    "elect" together and pull in a great deal this corpus does not mean; these
    four rules cover the inflections that actually appear in questions
    (recalled, recalling, elections, powers) and leave everything else alone.
    The length floors stop it mangling short words -- "led" must not become "l".
    """
    if len(token) >= 7 and token.endswith("ing"):
        return token[:-3]
    if len(token) >= 6 and token.endswith("ed"):
        return token[:-2]
    # "authorities" -> "authority", "bodies" -> "body".
    if len(token) >= 5 and token.endswith("ies"):
        return token[:-3] + "y"
    # Only strip a whole "es" after a sibilant, where the "e" is part of the
    # plural: "matches" -> "match", "boxes" -> "box". Applying it generally turned
    # "states" into "stat", which then matched "statute", "statement" and
    # "status" -- worse than not stemming at all.
    if len(token) >= 5 and token.endswith("es") and token[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return token[:-2]
    if len(token) >= 5 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


@lru_cache(maxsize=4096)
def _stem_set(text: str) -> frozenset[str]:
    """The stems of every word in a field, for whole-word comparison.

    Cached because the same handful of documents are re-scored across a burst of
    keystrokes, and the bodies are already truncated to MAX_BODY_CHARS.
    """
    return frozenset(_stem(t) for t in tokenise(text))


def _matches(token: str, text: str, stems: frozenset[str]) -> bool:
    """Does `token` match this field?

    TWO PATHS, AND THE SECOND ONE IS NARROW ON PURPOSE.

    1. Substring, as before: "consti" finds "constitution", which is what makes
       the search box feel responsive while somebody is still typing.
    2. Stem equality as a WHOLE WORD: query "recalled" and document "recall"
       both stem to "recall", so they match.

    Path 2 compares stems rather than doing a second substring test, and that
    distinction is the whole design. Stemming only the query and then matching it
    as a substring turns "governs" into "govern", which is inside "government",
    "governance" and "governor" -- so a question about zoning bylaws suddenly
    found constitutional articles to ground itself in, and the assistant answered
    a question it should have declined. Comparing stem to stem, bounded to whole
    words, cannot do that: "government" stems to "government", never to "govern".
    """
    if token in text:
        return True
    stem = _stem(token)
    return stem != token and stem in stems


def meilisearch_enabled() -> bool:
    return config.meilisearch_enabled()


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------
async def index(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    title: str,
    url_path: str,
    subtitle: str = "",
    body: str = "",
    keywords: Iterable[str] = (),
    state_code: Optional[str] = None,
    locale: str = "en",
    is_published: bool = True,
) -> None:
    """Upsert one document. Idempotent, and safe to call on every save.

    Part of the caller's transaction, like the audit log and for the same
    reason: an index entry for a row that rolled back is a search result that
    404s.
    """
    row = (
        await session.execute(
            select(SearchDoc).where(
                SearchDoc.entity_type == entity_type,
                SearchDoc.entity_id == str(entity_id),
                SearchDoc.locale == locale,
            )
        )
    ).scalar_one_or_none()

    values = {
        "title": (title or "")[:300],
        "subtitle": (subtitle or "")[:400],
        "body": (body or "")[:MAX_BODY_CHARS],
        "keywords": " ".join(keywords)[:1000],
        "url_path": url_path[:300],
        "state_code": state_code,
        "is_published": is_published,
    }

    if row is None:
        session.add(
            SearchDoc(
                entity_type=entity_type,
                entity_id=str(entity_id),
                locale=locale,
                **values,
            )
        )
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = utcnow()


async def unindex(session: AsyncSession, *, entity_type: str, entity_id: str) -> None:
    """Remove every locale of one entity, e.g. after a hard delete."""
    await session.execute(
        delete(SearchDoc).where(
            SearchDoc.entity_type == entity_type, SearchDoc.entity_id == str(entity_id)
        )
    )


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _score(doc: SearchDoc, tokens: list[str], raw_query: str) -> int:
    title = (doc.title or "").lower()
    subtitle = (doc.subtitle or "").lower()
    keywords = (doc.keywords or "").lower()
    body = (doc.body or "").lower()

    score = 0
    if raw_query and raw_query in title:
        score += _W_TITLE_EXACT
    for token in tokens:
        # Once per field, whether it matched as written or through its stem.
        # Scoring both paths would quietly double the weight of every inflected
        # word and reorder results for no defensible reason.
        if _matches(token, title, _stem_set(title)):
            score += _W_TITLE_TOKEN
        if _matches(token, subtitle, _stem_set(subtitle)):
            score += _W_SUBTITLE_TOKEN
        if _matches(token, keywords, _stem_set(keywords)):
            score += _W_KEYWORD_TOKEN
        if _matches(token, body, _stem_set(body)):
            score += _W_BODY_TOKEN
    return score


def _snippet(doc: SearchDoc, tokens: list[str], width: int = 180) -> str:
    body = doc.body or doc.subtitle or ""
    lowered = body.lower()
    # Stems too, or a result matched on "recalled" shows the opening of the
    # article instead of the sentence the reader searched for. A loose substring
    # is fine here: this only picks where to cut the excerpt, and has no bearing
    # on whether the document was considered relevant.
    for token in (v for t in tokens for v in dict.fromkeys((t, _stem(t)))):
        idx = lowered.find(token)
        if idx >= 0:
            start = max(0, idx - width // 3)
            end = min(len(body), start + width)
            return ("..." if start else "") + body[start:end].strip() + ("..." if end < len(body) else "")
    return body[:width]


async def query(
    session: AsyncSession,
    q: str,
    *,
    types: Optional[Iterable[str]] = None,
    state_code: Optional[str] = None,
    locale: Optional[str] = None,
    limit: int = 20,
    include_unpublished: bool = False,
    min_score: int = MIN_SCORE,
) -> list[dict]:
    """Ranked results. Empty query returns nothing rather than everything."""
    raw = (q or "").strip().lower()
    tokens = tokenise(raw)
    if not tokens:
        return []

    if meilisearch_enabled():
        results = await _meili_query(raw, types=types, limit=limit)
        if results is not None:
            return results
        # Fall through to Postgres on any Meilisearch failure. A search box that
        # degrades is better than one that 500s because a sidecar is restarting.

    stmt = select(SearchDoc)
    if not include_unpublished:
        stmt = stmt.where(SearchDoc.is_published.is_(True))
    if types:
        stmt = stmt.where(SearchDoc.entity_type.in_(list(types)))
    if state_code:
        stmt = stmt.where(SearchDoc.state_code == state_code)
    if locale:
        stmt = stmt.where(SearchDoc.locale == locale)

    # Narrow in SQL to candidates matching ANY token, then rank in Python. Two
    # reasons: the ranking stays portable across SQLite and Postgres, and the
    # candidate set is what makes this cheap -- without it the scan is the whole
    # table on every keystroke.
    # Candidates are narrowed on the STEM, which is the shorter string and so the
    # looser pattern: "%recall%" catches "recall" and "recalled" alike. `_score`
    # then does the precise work, so widening here costs a few more rows to rank
    # and no accuracy.
    conditions = []
    for token in tokens[:6]:
        pattern = f"%{_stem(token)}%"
        conditions.extend(
            [
                func.lower(SearchDoc.title).like(pattern),
                func.lower(SearchDoc.subtitle).like(pattern),
                func.lower(SearchDoc.keywords).like(pattern),
                func.lower(SearchDoc.body).like(pattern),
            ]
        )
    stmt = stmt.where(or_(*conditions)).limit(400)

    docs = list((await session.execute(stmt)).scalars())
    scored = sorted(
        ((_score(d, tokens, raw), d) for d in docs), key=lambda pair: (-pair[0], pair[1].title)
    )

    return [
        {
            "entityType": doc.entity_type,
            "entityId": doc.entity_id,
            "title": doc.title,
            "subtitle": doc.subtitle,
            "snippet": _snippet(doc, tokens),
            "url": doc.url_path,
            "state": doc.state_code,
            "locale": doc.locale,
            "score": score,
        }
        for score, doc in scored[:limit]
        if score >= min_score
    ]


async def _meili_query(
    q: str, *, types: Optional[Iterable[str]], limit: int
) -> Optional[list[dict]]:
    """Search a self-hosted Meilisearch instance. None on any failure.

    Returning None rather than raising is what makes the fallback in `query()`
    work: the caller cannot tell which engine answered, which is the point of
    keeping both behind one function.
    """
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx ships with the FastAPI stack
        return None

    filters = f"entity_type IN [{', '.join(types)}]" if types else None
    headers = (
        {"Authorization": f"Bearer {config.MEILISEARCH_KEY}"} if config.MEILISEARCH_KEY else {}
    )
    payload = {"q": q, "limit": limit}
    if filters:
        payload["filter"] = filters

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{config.MEILISEARCH_URL}/indexes/{config.MEILISEARCH_INDEX}/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            hits = response.json().get("hits", [])
    except Exception as e:
        logger.warning("Meilisearch query failed, falling back to Postgres: %s", e)
        return None

    return [
        {
            "entityType": hit.get("entity_type"),
            "entityId": hit.get("entity_id"),
            "title": hit.get("title", ""),
            "subtitle": hit.get("subtitle", ""),
            "snippet": (hit.get("body") or "")[:180],
            "url": hit.get("url_path", ""),
            "state": hit.get("state_code"),
            "locale": hit.get("locale", "en"),
            "score": 0,
        }
        for hit in hits
    ]


async def suggest(session: AsyncSession, prefix: str, limit: int = 8) -> list[dict]:
    """Titles beginning with `prefix` -- backs the type-ahead box."""
    prefix = (prefix or "").strip().lower()
    if len(prefix) < 2:
        return []
    rows = (
        await session.execute(
            select(SearchDoc)
            .where(SearchDoc.is_published.is_(True), func.lower(SearchDoc.title).like(f"{prefix}%"))
            .order_by(SearchDoc.title)
            .limit(limit)
        )
    ).scalars()
    return [
        {"title": r.title, "url": r.url_path, "entityType": r.entity_type} for r in rows
    ]
