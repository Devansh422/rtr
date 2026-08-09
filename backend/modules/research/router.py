"""Research Centre and Media Library endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, search
from backend.core.citations import CitationError, parse_citation
from backend.core.deps import get_session, require_permission
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.research.models import (
    DOCUMENT_KINDS,
    LICENCES,
    MEDIA_KINDS,
    ResearchDocument,
)

router = APIRouter(tags=["research"])


class DocumentIn(BaseModel):
    title: str = Field(..., min_length=6, max_length=300)
    kind: str
    source_url: str
    title_hi: str = ""
    summary: str = ""
    summary_hi: str = ""
    authors: str = ""
    publisher: str = ""
    published_on: Optional[date] = None
    file_url: str = ""
    file_type: str = ""
    file_size_kb: Optional[int] = None
    page_count: Optional[int] = None
    licence: str = "linked_only"
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    state_code: Optional[str] = None
    article_refs: list[str] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    title_hi: Optional[str] = None
    summary: Optional[str] = None
    summary_hi: Optional[str] = None
    kind: Optional[str] = None
    authors: Optional[str] = None
    publisher: Optional[str] = None
    published_on: Optional[date] = None
    source_url: Optional[str] = None
    file_url: Optional[str] = None
    licence: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[list[str]] = None
    state_code: Optional[str] = None
    article_refs: Optional[list[str]] = None


def _serialise(document: ResearchDocument) -> dict:
    return {
        "id": document.id,
        "slug": document.slug,
        "title": document.title,
        "titleHi": document.title_hi,
        "summary": document.summary,
        "summaryHi": document.summary_hi,
        "kind": document.kind,
        "kindLabel": DOCUMENT_KINDS.get(document.kind, document.kind),
        "collection": "media" if document.kind in MEDIA_KINDS else "research",
        "authors": document.authors or None,
        "publisher": document.publisher or None,
        "publishedOn": document.published_on.isoformat() if document.published_on else None,
        # The citation. Always present, always the original.
        "sourceUrl": document.source_url,
        # Absent when the platform does not host a copy -- the reader is sent to
        # the source instead, which is the correct behaviour for a judgment or a
        # government report.
        "fileUrl": document.file_url or None,
        "isHostedHere": bool(document.file_url),
        "fileType": document.file_type or None,
        "fileSizeKb": document.file_size_kb,
        "pageCount": document.page_count,
        "licence": document.licence,
        "licenceLabel": LICENCES.get(document.licence, document.licence),
        "language": document.language,
        "tags": document.tags,
        "state": document.state_code,
        "articleRefs": document.article_refs,
        "downloadCount": document.download_count,
        "isPublished": document.is_published,
        "url": f"/research/{document.slug}",
    }


async def _index(session: AsyncSession, document: ResearchDocument) -> None:
    await search.index(
        session,
        entity_type="research_document",
        entity_id=document.slug,
        title=document.title,
        subtitle=f"{DOCUMENT_KINDS.get(document.kind, document.kind)}"
        + (f" - {document.publisher}" if document.publisher else ""),
        body=document.summary,
        keywords=[document.kind, document.authors, *document.tags, *document.article_refs],
        state_code=document.state_code,
        is_published=document.is_published,
        url_path=f"/research/{document.slug}",
    )


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/research/kinds")
async def list_kinds():
    return {
        "kinds": [
            {
                "key": key,
                "label": label,
                "collection": "media" if key in MEDIA_KINDS else "research",
            }
            for key, label in DOCUMENT_KINDS.items()
        ],
        "licences": [{"key": key, "label": label} for key, label in LICENCES.items()],
    }


@router.get("/research/documents")
async def list_documents(
    collection: Optional[str] = Query(default=None, pattern="^(research|media)$"),
    kind: Optional[str] = None,
    state: Optional[str] = None,
    tag: Optional[str] = None,
    article: Optional[str] = None,
    q: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ResearchDocument).where(ResearchDocument.is_published.is_(True))
    if kind:
        stmt = stmt.where(ResearchDocument.kind == kind)
    elif collection == "media":
        stmt = stmt.where(ResearchDocument.kind.in_(list(MEDIA_KINDS)))
    elif collection == "research":
        stmt = stmt.where(ResearchDocument.kind.notin_(list(MEDIA_KINDS)))
    if state:
        stmt = stmt.where(ResearchDocument.state_code == state.upper())
    if language:
        stmt = stmt.where(ResearchDocument.language == language)
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(ResearchDocument.title).like(needle),
                func.lower(ResearchDocument.summary).like(needle),
                func.lower(ResearchDocument.authors).like(needle),
            )
        )

    rows = list((await session.execute(stmt.order_by(ResearchDocument.created_at.desc()))).scalars())
    # JSON-column filters are applied in Python so the same code works on SQLite
    # and Postgres -- the same reason the constitution module filters tags this way.
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]
    if article:
        rows = [r for r in rows if article.upper() in (r.article_refs or [])]

    return {
        "total": len(rows),
        "items": [_serialise(r) for r in rows[offset : offset + limit]],
    }


@router.get("/research/documents/{slug}")
async def get_document(slug: str, session: AsyncSession = Depends(get_session)):
    document = (
        await session.execute(
            select(ResearchDocument).where(
                ResearchDocument.slug == slug, ResearchDocument.is_published.is_(True)
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialise(document)


@router.post("/research/documents/{slug}/download")
async def register_download(slug: str, session: AsyncSession = Depends(get_session)):
    """Count a download and hand back the URL to fetch.

    A counter rather than a redirect proxy: proxying every PDF through a serverless
    function would burn the function's execution time and Vercel's bandwidth on
    bytes that Cloudflare R2 serves for free with no egress charge (§5).
    """
    document = (
        await session.execute(
            select(ResearchDocument).where(
                ResearchDocument.slug == slug, ResearchDocument.is_published.is_(True)
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document.download_count += 1
    return {
        "url": document.file_url or document.source_url,
        "isHostedHere": bool(document.file_url),
        "licence": LICENCES.get(document.licence, document.licence),
        "attribution": (
            f"{document.authors or document.publisher or 'Source'}"
            f"{f', {document.published_on.year}' if document.published_on else ''}. "
            f"Retrieved from {document.source_url}"
        ),
    }


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/research/documents")
async def admin_list_documents(
    published: Optional[bool] = None,
    admin: Principal = Depends(require_permission("research.manage")),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ResearchDocument).order_by(ResearchDocument.created_at.desc()).limit(400)
    if published is not None:
        stmt = stmt.where(ResearchDocument.is_published.is_(published))
    return [_serialise(r) for r in (await session.execute(stmt)).scalars()]


@router.post("/admin/research/documents")
async def create_document(
    payload: DocumentIn,
    request: Request,
    admin: Principal = Depends(require_permission("research.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.kind not in DOCUMENT_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(DOCUMENT_KINDS)}")
    if payload.licence not in LICENCES:
        raise HTTPException(status_code=400, detail=f"licence must be one of {list(LICENCES)}")

    # The source URL is a citation, so it goes through the same validator the
    # representative claims use rather than a looser check here.
    try:
        citation = parse_citation(
            {"url": payload.source_url, "title": payload.title}, field_name="the source"
        )
    except CitationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.file_url and payload.licence == "linked_only":
        raise HTTPException(
            status_code=400,
            detail="You are hosting a copy, so choose the licence that actually permits that.",
        )

    slug = slugify(payload.title)
    if (await session.execute(select(ResearchDocument).where(ResearchDocument.slug == slug))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A document with that title already exists")

    document = ResearchDocument(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        summary_hi=payload.summary_hi.strip(),
        kind=payload.kind,
        authors=payload.authors.strip(),
        publisher=payload.publisher.strip() or (citation.publisher or ""),
        published_on=payload.published_on,
        source_url=citation.url,
        file_url=payload.file_url.strip(),
        file_type=payload.file_type.strip(),
        file_size_kb=payload.file_size_kb,
        page_count=payload.page_count,
        licence=payload.licence,
        language=payload.language,
        tags=payload.tags,
        state_code=payload.state_code.upper() if payload.state_code else None,
        article_refs=[str(a).upper() for a in payload.article_refs],
        uploaded_by=admin.id,
    )
    session.add(document)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="research_document",
        entity_id=slug,
        summary=f"Added to the repository: {document.title}",
        source_url=citation.url,
        is_public=False,
        request=request,
    )
    return _serialise(document)


@router.put("/admin/research/documents/{document_id}")
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    request: Request,
    admin: Principal = Depends(require_permission("research.manage")),
    session: AsyncSession = Depends(get_session),
):
    document = (
        await session.execute(select(ResearchDocument).where(ResearchDocument.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    updates = payload.model_dump(exclude_unset=True)
    before, after = {}, {}
    for field, value in updates.items():
        if value is None:
            continue
        if field == "kind" and value not in DOCUMENT_KINDS:
            raise HTTPException(status_code=400, detail=f"kind must be one of {list(DOCUMENT_KINDS)}")
        if field == "licence" and value not in LICENCES:
            raise HTTPException(status_code=400, detail=f"licence must be one of {list(LICENCES)}")
        if field == "article_refs":
            value = [str(a).upper() for a in value]
        if field == "state_code":
            value = value.upper()
        current = getattr(document, field)
        if current != value:
            before[field] = current.isoformat() if hasattr(current, "isoformat") else current
            after[field] = value.isoformat() if hasattr(value, "isoformat") else value
            setattr(document, field, value)

    if not after:
        raise HTTPException(status_code=400, detail="No changes provided")

    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type="research_document",
        entity_id=document.slug,
        summary=f"Updated {document.title}",
        changes=audit.diff(before, after),
        is_public=False,
        request=request,
    )
    await _index(session, document)
    return _serialise(document)


@router.post("/admin/research/documents/{document_id}/publish")
async def publish_document(
    document_id: str,
    request: Request,
    publish: bool = True,
    admin: Principal = Depends(require_permission("research.manage")),
    session: AsyncSession = Depends(get_session),
):
    document = (
        await session.execute(select(ResearchDocument).where(ResearchDocument.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document.is_published = publish
    await audit.record(
        session,
        actor=admin,
        action="publish" if publish else "unpublish",
        entity_type="research_document",
        entity_id=document.slug,
        summary=f"{'Published' if publish else 'Unpublished'} {document.title}",
        is_public=False,
        request=request,
    )
    await _index(session, document)
    return _serialise(document)


@router.delete("/admin/research/documents/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("research.manage")),
    session: AsyncSession = Depends(get_session),
):
    document = (
        await session.execute(select(ResearchDocument).where(ResearchDocument.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    title, slug = document.title, document.slug
    await search.unindex(session, entity_type="research_document", entity_id=slug)
    await session.delete(document)
    await audit.record(
        session,
        actor=admin,
        action="delete",
        entity_type="research_document",
        entity_id=slug,
        summary=f"Removed from the repository: {title}",
        is_public=False,
        request=request,
    )
    return {"ok": True}
