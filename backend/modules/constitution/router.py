"""The Constitution Library: articles in the original, in plain English and in Hindi.

The draft/publish split here is not ceremony. Constitutional text is legal
content: an unreviewed paraphrase of Article 21 published under this platform's
name is worse than no paraphrase at all. So `constitution.edit` writes drafts and
only `constitution.publish` makes one public, which is the same gate §6 gives the
Editor role and withholds from Content Writers.

Reads are locale-aware through core/i18n, which is also where the rule lives that
a machine-translated legal field is never served as the authoritative text.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, i18n, search
from backend.core.citations import STANDARD_DISCLAIMER
from backend.core.deps import get_session, require_permission
from backend.core.models import utcnow
from backend.core.rbac import Principal
from backend.modules.constitution import parts as parts_registry
from backend.modules.constitution.models import ConstitutionArticle, compute_sort_key

router = APIRouter(tags=["constitution"])

INDIA_CODE = "https://www.indiacode.nic.in/handle/123456789/1362"


class ArticleWrite(BaseModel):
    number: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=3, max_length=300)
    title_hi: str = ""
    part: str = ""
    original_text: str = ""
    original_source_url: str = ""
    plain_en: str = ""
    plain_hi: str = ""
    recall_relevance: str = ""
    case_law: list[dict] = Field(default_factory=list)
    amendments: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    translation_status: dict = Field(default_factory=dict)


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    title_hi: Optional[str] = None
    part: Optional[str] = None
    original_text: Optional[str] = None
    original_source_url: Optional[str] = None
    plain_en: Optional[str] = None
    plain_hi: Optional[str] = None
    recall_relevance: Optional[str] = None
    case_law: Optional[list[dict]] = None
    amendments: Optional[list[dict]] = None
    tags: Optional[list[str]] = None
    related: Optional[list[str]] = None
    translation_status: Optional[dict] = None


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------
def _summary(article: ConstitutionArticle, locale: str) -> dict:
    title = i18n.field_for(article, "title", locale)
    return {
        "number": article.number,
        "title": title["text"],
        "titleLocale": title["locale"],
        "part": article.part,
        "partTitle": article.part_title,
        "tags": article.tags,
        "hasPlainLanguage": bool(article.plain_en),
        "hasOriginalText": bool(article.original_text),
        "isPublished": article.is_published,
        "url": f"/constitution/{article.number}",
    }


def _detail(article: ConstitutionArticle, locale: str) -> dict:
    plain_field = "plain_en" if i18n.normalise(locale) == "en" else f"plain_{i18n.normalise(locale)}"
    plain = getattr(article, plain_field, "") or article.plain_en

    payload = _summary(article, locale)
    payload.update(
        {
            "originalText": article.original_text,
            # An article whose verbatim text has not been transcribed says so and
            # links to the authoritative source, instead of letting the plain
            # English read as the law.
            "originalTextPending": not article.original_text,
            "originalSourceUrl": article.original_source_url or INDIA_CODE,
            "plainLanguage": {
                "text": plain,
                "locale": i18n.normalise(locale) if plain != article.plain_en else "en",
                "isParaphrase": True,
                "notice": (
                    "This is the Right to Recall Movement's plain-language explanation, not the "
                    "text of the Constitution. Read the original text above for the exact wording."
                ),
            },
            "plainEnglish": article.plain_en,
            "plainHindi": article.plain_hi,
            "recallRelevance": article.recall_relevance,
            "caseLaw": article.case_law,
            "amendments": article.amendments,
            "related": article.related,
            "updatedAt": article.updated_at.isoformat() if article.updated_at else None,
            "publishedAt": article.published_at.isoformat() if article.published_at else None,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    )
    return payload


async def _index_article(session: AsyncSession, article: ConstitutionArticle) -> None:
    await search.index(
        session,
        entity_type="constitution_article",
        entity_id=article.number,
        title=f"Article {article.number}: {article.title}",
        subtitle=f"Part {article.part} - {article.part_title}" if article.part else "",
        body=f"{article.plain_en}\n{article.recall_relevance}\n{article.original_text}",
        keywords=[article.number, article.title_hi, *article.tags, *[str(r) for r in article.related]],
        locale="en",
        is_published=article.is_published,
        url_path=f"/constitution/{article.number}",
    )


# --------------------------------------------------------------------------
# Public reads
# --------------------------------------------------------------------------
@router.get("/constitution/parts")
async def list_parts():
    return parts_registry.as_dicts()


@router.get("/constitution/articles")
async def list_articles(
    part: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    locale: str = "en",
    limit: int = Query(default=100, ge=1, le=400),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ConstitutionArticle)
        .where(ConstitutionArticle.is_published.is_(True))
        .order_by(ConstitutionArticle.sort_key)
    )
    if part:
        stmt = stmt.where(ConstitutionArticle.part == part.upper())
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(ConstitutionArticle.title).like(needle),
                func.lower(ConstitutionArticle.plain_en).like(needle),
                ConstitutionArticle.number.like(f"{q}%"),
            )
        )

    rows = list((await session.execute(stmt)).scalars())
    # Tag filtering happens here rather than in SQL because `tags` is a portable
    # JSON column (SQLite in tests, Postgres in production) and a JSON containment
    # operator would only work on one of them. The list is a few hundred rows.
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]

    total = len(rows)
    window = rows[offset : offset + limit]
    return {
        "total": total,
        "items": [_summary(r, locale) for r in window],
    }


@router.get("/constitution/articles/{number}")
async def get_article(
    number: str, locale: str = "en", session: AsyncSession = Depends(get_session)
):
    article = (
        await session.execute(
            select(ConstitutionArticle).where(
                func.upper(ConstitutionArticle.number) == number.upper(),
                ConstitutionArticle.is_published.is_(True),
            )
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail=f"Article {number} is not in the library yet")
    return _detail(article, locale)


@router.get("/constitution/articles/{number}/history")
async def article_history(number: str, session: AsyncSession = Depends(get_session)):
    """Public edit history -- the Wikipedia-History pillar, per §7."""
    entries = await audit.history(session, entity_type="constitution_article", entity_id=number.upper())
    return [audit.to_dict(e, include_actor=False) for e in entries]


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/constitution/articles")
async def admin_list_articles(
    admin: Principal = Depends(require_permission("constitution.edit")),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(ConstitutionArticle).order_by(ConstitutionArticle.sort_key))
    ).scalars()
    return [
        {
            **_summary(r, "en"),
            "plainEnglishWords": len((r.plain_en or "").split()),
            "hasHindi": bool(r.plain_hi),
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.post("/admin/constitution/articles")
async def create_article(
    payload: ArticleWrite,
    request: Request,
    admin: Principal = Depends(require_permission("constitution.edit")),
    session: AsyncSession = Depends(get_session),
):
    number = payload.number.strip().upper()
    existing = (
        await session.execute(select(ConstitutionArticle).where(ConstitutionArticle.number == number))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Article {number} already exists")

    part = (payload.part or "").upper()
    article = ConstitutionArticle(
        number=number,
        sort_key=compute_sort_key(number),
        part=part,
        part_title=parts_registry.PARTS_BY_NUMBER[part].title if part in parts_registry.PARTS_BY_NUMBER else "",
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        original_text=payload.original_text,
        original_source_url=payload.original_source_url or INDIA_CODE,
        plain_en=payload.plain_en,
        plain_hi=payload.plain_hi,
        recall_relevance=payload.recall_relevance,
        case_law=payload.case_law,
        amendments=payload.amendments,
        tags=payload.tags,
        related=[str(r).upper() for r in payload.related],
        translation_status=payload.translation_status,
        # Created as a draft, always. Publishing is a separate permission.
        is_published=False,
        updated_by=admin.id,
    )
    session.add(article)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="constitution_article",
        entity_id=number,
        summary=f"Drafted Article {number}: {article.title}",
        changes=audit.diff(None, {"number": number, "title": article.title}),
        source_url=article.original_source_url,
        is_public=True,
        request=request,
    )
    await _index_article(session, article)
    return _detail(article, "en")


@router.put("/admin/constitution/articles/{number}")
async def update_article(
    number: str,
    payload: ArticleUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("constitution.edit")),
    session: AsyncSession = Depends(get_session),
):
    article = (
        await session.execute(
            select(ConstitutionArticle).where(ConstitutionArticle.number == number.upper())
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    updates = payload.model_dump(exclude_unset=True)
    before, after = {}, {}
    for field, value in updates.items():
        if value is None:
            continue
        if field == "part":
            value = value.upper()
            article.part_title = (
                parts_registry.PARTS_BY_NUMBER[value].title
                if value in parts_registry.PARTS_BY_NUMBER
                else ""
            )
        if field == "related":
            value = [str(r).upper() for r in value]
        current = getattr(article, field)
        if current != value:
            before[field] = current
            after[field] = value
            setattr(article, field, value)

    if not after:
        raise HTTPException(status_code=400, detail="No changes provided")

    article.updated_by = admin.id
    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type="constitution_article",
        entity_id=article.number,
        summary=f"Edited Article {article.number}",
        changes=audit.diff(before, after),
        source_url=article.original_source_url,
        is_public=True,
        request=request,
    )
    await _index_article(session, article)
    return _detail(article, "en")


@router.post("/admin/constitution/articles/{number}/publish")
async def publish_article(
    number: str,
    request: Request,
    publish: bool = True,
    admin: Principal = Depends(require_permission("constitution.publish")),
    session: AsyncSession = Depends(get_session),
):
    article = (
        await session.execute(
            select(ConstitutionArticle).where(ConstitutionArticle.number == number.upper())
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    if publish and not article.plain_en.strip():
        # Publishing an article with no plain-language text ships a page whose
        # only content is a link to India Code. The library's entire purpose is
        # the layer on top of that.
        raise HTTPException(
            status_code=400,
            detail="Add the plain-English explanation before publishing -- that is what the library is for.",
        )

    if article.is_published == publish:
        raise HTTPException(
            status_code=400, detail=f"Article {article.number} is already {'published' if publish else 'a draft'}"
        )

    article.is_published = publish
    article.published_at = utcnow() if publish else None

    await audit.record(
        session,
        actor=admin,
        action="publish" if publish else "unpublish",
        entity_type="constitution_article",
        entity_id=article.number,
        summary=f"{'Published' if publish else 'Unpublished'} Article {article.number}",
        changes={"is_published": {"before": not publish, "after": publish}},
        is_public=True,
        request=request,
    )
    await _index_article(session, article)
    return _detail(article, "en")
