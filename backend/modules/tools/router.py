"""RTI generator, Representation generator and the PIL Resource Centre.

The generator is a pure function of (template, inputs) -> document. Nothing the
citizen types is written to a database; see the note on GenerationLog for why that
matters more here than anywhere else on the platform.

Output comes in three shapes from one builder: a JSON preview for the screen, a
DOCX for editing, and a print-optimised HTML page whose "Save as PDF" uses the
browser's own text engine -- which is how a Devanagari RTI application comes out
correctly shaped without a native font stack on the server (see core/documents).
"""

from typing import Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, limits
from backend.core.documents import DOCX_MEDIA_TYPE, Block, DocumentDraft
from backend.core.deps import get_session, require_permission
from backend.core.models import utcnow
from backend.core.rbac import Principal
from backend.modules.tools.models import (
    TOOL_KINDS,
    DocumentTemplate,
    GenerationLog,
    ReviewStatus,
)
from backend.modules.tools.seed_templates import PIL_GUIDE, RTI_GUIDE

router = APIRouter(tags=["tools"])

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class GenerateIn(BaseModel):
    template_key: str
    values: dict = Field(default_factory=dict)
    state_code: Optional[str] = None


class TemplateIn(BaseModel):
    key: str = Field(..., min_length=3, max_length=60)
    kind: str
    title: str = Field(..., min_length=6, max_length=240)
    title_hi: str = ""
    description: str = ""
    state_code: Optional[str] = None
    fields: list[dict] = Field(default_factory=list)
    body: list[dict] = Field(..., min_length=1)
    legal_basis: str = ""
    filing_notes: str = ""


class ReviewIn(BaseModel):
    status: str
    note: str = ""


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _template_dict(template: DocumentTemplate, *, include_body: bool = False) -> dict:
    payload = {
        "key": template.key,
        "kind": template.kind,
        "kindLabel": TOOL_KINDS.get(template.kind, template.kind),
        "title": template.title,
        "titleHi": template.title_hi,
        "description": template.description,
        "state": template.state_code,
        "fields": template.fields,
        "legalBasis": template.legal_basis,
        "filingNotes": template.filing_notes,
        "reviewStatus": template.review_status,
        "isLegallyApproved": template.review_status == ReviewStatus.LEGAL_APPROVED,
        "version": template.version,
    }
    if include_body:
        payload["body"] = template.body
    return payload


def _derived_clauses(template: DocumentTemplate, values: dict) -> dict:
    """Fill the conditional fragments the templates reference.

    Templates use `{{period_clause}}` rather than an if/else in the body because
    the alternative is a template language, and a template language in a legal
    document generator is a bug factory. A handful of named optional fragments,
    computed here, covers every case the seeded set needs.
    """
    clauses = {}

    period = (values.get("period") or "").strip()
    clauses["period_clause"] = f" for the period {period}" if period else ""

    contact = (values.get("applicant_contact") or "").strip()
    clauses["contact_clause"] = f"Contact: {contact}" if contact else ""

    if (values.get("is_bpl") or "").lower() == "yes":
        clauses["fee_clause"] = (
            "I hold a Below Poverty Line card and am therefore exempt from the application fee "
            "under Section 7(5) of the Right to Information Act, 2005. A copy of the card is enclosed."
        )
        clauses["bpl_enclosure"] = " and a copy of the BPL card"
    else:
        mode = (values.get("fee_mode") or "Indian Postal Order").strip()
        clauses["fee_clause"] = (
            f"The prescribed application fee is enclosed by way of {mode}."
        )
        clauses["bpl_enclosure"] = ""

    steps = (values.get("steps_taken") or "").strip()
    clauses["steps_clause"] = (
        f"I have already taken the following steps in this matter: {steps}" if steps else ""
    )

    reason = (values.get("personal_reason") or "").strip()
    clauses["reason_clause"] = reason if reason else ""

    since = (values.get("since") or "").strip()
    clauses["since_clause"] = f"\nThe situation has continued since {since}." if since else ""

    reference = (values.get("rti_reference") or "").strip()
    clauses["reference_clause"] = f" (your reference {reference})" if reference else ""

    officer = (values.get("officer") or "").strip()
    clauses["officer_line"] = f"{officer},\n" if officer else ""

    return clauses


def build(template: DocumentTemplate, values: dict) -> DocumentDraft:
    """Substitute values into the template's blocks.

    Missing required fields are reported all at once rather than one per attempt:
    a citizen filling in an RTI form should not have to submit nine times to
    discover nine gaps.
    """
    missing = [
        field.get("label", field["name"])
        for field in template.fields
        if field.get("required") and not str(values.get(field["name"], "")).strip()
    ]
    if missing:
        raise HTTPException(status_code=400, detail={"message": "Some required details are missing", "missing": missing})

    # Only declared field names are substitutable, so a caller cannot inject a
    # placeholder the template author never intended.
    allowed = {field["name"]: str(values.get(field["name"], "")).strip() for field in template.fields}
    allowed.update(_derived_clauses(template, values))

    blocks: list[Block] = []
    for raw in template.body:
        text = raw.get("text", "")
        text = _PLACEHOLDER_RE.sub(lambda m: allowed.get(m.group(1), ""), text)
        # A block whose entire content was an empty optional clause is dropped
        # rather than rendered as a blank paragraph in the middle of a letter.
        if raw.get("kind") in (None, "para", "bullet") and not text.strip():
            continue
        blocks.append(
            Block(
                text=text.strip("\n"),
                kind=raw.get("kind", "para"),
                bold=bool(raw.get("bold")),
                italic=bool(raw.get("italic")),
                align=raw.get("align", "left"),
            )
        )

    return DocumentDraft(
        title=template.title,
        filename=f"{template.key}.docx",
        blocks=blocks,
        hint=(
            "Read this through and edit anything that does not match your situation before sending it. "
            + (template.filing_notes.split("\n\n")[0] if template.filing_notes else "")
        ),
    )


async def _load_approved(session: AsyncSession, key: str) -> DocumentTemplate:
    template = (
        await session.execute(select(DocumentTemplate).where(DocumentTemplate.key == key))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.review_status != ReviewStatus.LEGAL_APPROVED:
        # A generator that emits unreviewed legal text is how a civic platform
        # starts giving bad legal advice at scale.
        raise HTTPException(
            status_code=409,
            detail="This template is awaiting legal review and cannot be generated yet.",
        )
    return template


async def _log(
    session: AsyncSession, template: DocumentTemplate, *, output_format: str, state_code: Optional[str]
) -> None:
    session.add(
        GenerationLog(
            template_key=template.key,
            kind=template.kind,
            state_code=(state_code or template.state_code),
            output_format=output_format,
        )
    )


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/tools")
async def list_tools(session: AsyncSession = Depends(get_session)):
    """The tools index: what is available, grouped by kind."""
    rows = list(
        (
            await session.execute(
                select(DocumentTemplate)
                .where(DocumentTemplate.review_status == ReviewStatus.LEGAL_APPROVED)
                .order_by(DocumentTemplate.kind, DocumentTemplate.title)
            )
        ).scalars()
    )
    grouped: dict[str, list[dict]] = {}
    for template in rows:
        grouped.setdefault(template.kind, []).append(
            {
                "key": template.key,
                "title": template.title,
                "titleHi": template.title_hi,
                "description": template.description,
                "state": template.state_code,
            }
        )
    return {
        "kinds": [
            {"key": key, "label": label, "templates": grouped.get(key, [])}
            for key, label in TOOL_KINDS.items()
        ],
        "guides": [
            {"key": "rti", "title": RTI_GUIDE["title"], "url": "/api/tools/guides/rti"},
            {"key": "pil", "title": PIL_GUIDE["title"], "url": "/api/tools/guides/pil"},
        ],
    }


@router.get("/tools/guides/rti")
async def rti_guide():
    return RTI_GUIDE


@router.get("/tools/guides/pil")
async def pil_guide():
    """The PIL Resource Centre.

    Explains the route and refuses to draft the petition. See the opening note in
    seed_templates.PIL_GUIDE for why that refusal is the responsible position
    rather than a missing feature.
    """
    return PIL_GUIDE


@router.get("/tools/templates/{key}")
async def get_template(key: str, session: AsyncSession = Depends(get_session)):
    template = await _load_approved(session, key)
    return _template_dict(template)


@router.post("/tools/generate")
async def generate_preview(
    payload: GenerateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Assemble the document and return it as text for on-screen review.

    Deliberately unauthenticated: someone filing an RTI about a public authority
    should not have to create an account with a civic platform first, and requiring
    one would mean we hold a record of who asked about what. Rate-limited by IP
    instead.
    """
    template = await _load_approved(session, payload.template_key)
    await limits.check("tools.generate", limits.identity_for(request))

    draft = build(template, payload.values)
    await _log(session, template, output_format="preview", state_code=payload.state_code)

    return {
        "title": draft.title,
        "text": draft.plain_text(),
        "blocks": [
            {"kind": b.kind, "text": b.text, "bold": b.bold, "italic": b.italic, "align": b.align}
            for b in draft.blocks
        ],
        "legalBasis": template.legal_basis,
        "filingNotes": template.filing_notes,
        "downloads": {
            "docx": "/api/tools/generate.docx",
            "print": "/api/tools/generate.html",
        },
        "disclaimer": (
            "This is a template filled in with what you typed. It is not legal advice. Read it, correct "
            "anything that does not match your situation, and keep a copy of what you send."
        ),
    }


@router.post("/tools/generate.docx")
async def generate_docx(
    payload: GenerateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    template = await _load_approved(session, payload.template_key)
    await limits.check("tools.generate", limits.identity_for(request))
    draft = build(template, payload.values)
    await _log(session, template, output_format="docx", state_code=payload.state_code)
    return Response(
        content=draft.docx(),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{draft.filename}"'},
    )


@router.post("/tools/generate.html")
async def generate_print_view(
    payload: GenerateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Print-optimised page. The PDF route -- see core/documents."""
    template = await _load_approved(session, payload.template_key)
    await limits.check("tools.generate", limits.identity_for(request))
    draft = build(template, payload.values)
    await _log(session, template, output_format="print", state_code=payload.state_code)
    return Response(content=draft.html(), media_type="text/html; charset=utf-8")


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/tools/templates")
async def admin_list_templates(
    admin: Principal = Depends(require_permission("tools.manage")),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(DocumentTemplate).order_by(DocumentTemplate.kind, DocumentTemplate.key))
    ).scalars()
    return [_template_dict(t, include_body=True) for t in rows]


@router.post("/admin/tools/templates")
async def create_template(
    payload: TemplateIn,
    request: Request,
    admin: Principal = Depends(require_permission("tools.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.kind not in TOOL_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(TOOL_KINDS)}")
    if (
        await session.execute(select(DocumentTemplate).where(DocumentTemplate.key == payload.key))
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A template with that key already exists")

    declared = {f.get("name") for f in payload.fields}
    _assert_placeholders_declared(payload.body, declared)

    template = DocumentTemplate(
        key=payload.key,
        kind=payload.kind,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        description=payload.description.strip(),
        state_code=payload.state_code.upper() if payload.state_code else None,
        fields=payload.fields,
        body=payload.body,
        legal_basis=payload.legal_basis.strip(),
        filing_notes=payload.filing_notes.strip(),
        # Always draft, even when created by the Legal Team. Approval is a
        # deliberate second action with its own audit entry.
        review_status=ReviewStatus.DRAFT,
    )
    session.add(template)
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="tool_template",
        entity_id=payload.key,
        summary=f"Drafted template: {payload.title}",
        is_public=False,
        request=request,
    )
    return _template_dict(template, include_body=True)


@router.put("/admin/tools/templates/{key}")
async def update_template(
    key: str,
    payload: TemplateIn,
    request: Request,
    admin: Principal = Depends(require_permission("tools.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Edit a template. ALWAYS drops it back to draft.

    Including for a seeded template, and including when the editor holds
    `legal.review` themselves. The approval attaches to a specific version of the
    text; letting an edit inherit it would make the review meaningless.
    """
    template = (
        await session.execute(select(DocumentTemplate).where(DocumentTemplate.key == key))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    declared = {f.get("name") for f in payload.fields}
    _assert_placeholders_declared(payload.body, declared)

    before_status = template.review_status
    template.title = payload.title.strip()
    template.title_hi = payload.title_hi.strip()
    template.description = payload.description.strip()
    template.fields = payload.fields
    template.body = payload.body
    template.legal_basis = payload.legal_basis.strip()
    template.filing_notes = payload.filing_notes.strip()
    template.state_code = payload.state_code.upper() if payload.state_code else None
    template.review_status = ReviewStatus.DRAFT
    template.reviewed_by = None
    template.reviewed_at = None
    template.version += 1

    await audit.record(
        session,
        actor=admin,
        action="update",
        entity_type="tool_template",
        entity_id=key,
        summary=f"Edited template {key} (now version {template.version}, review reset)",
        changes={"review_status": {"before": before_status, "after": ReviewStatus.DRAFT}},
        is_public=False,
        request=request,
    )
    return _template_dict(template, include_body=True)


@router.post("/admin/tools/templates/{key}/review")
async def review_template(
    key: str,
    payload: ReviewIn,
    request: Request,
    admin: Principal = Depends(require_permission("legal.review")),
    session: AsyncSession = Depends(get_session),
):
    """Approve or retire a template. Requires `legal.review`, not `tools.manage`.

    Two different permissions on purpose: whoever writes the template is not
    whoever signs off that it states the law correctly.
    """
    valid = {ReviewStatus.LEGAL_APPROVED, ReviewStatus.DRAFT, ReviewStatus.RETIRED}
    if payload.status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(valid)}")

    template = (
        await session.execute(select(DocumentTemplate).where(DocumentTemplate.key == key))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    before = template.review_status
    template.review_status = payload.status
    template.review_note = payload.note.strip()
    template.reviewed_by = admin.id
    template.reviewed_at = utcnow()

    await audit.record(
        session,
        actor=admin,
        action="legal_review",
        entity_type="tool_template",
        entity_id=key,
        summary=f"{key} v{template.version}: {before} -> {payload.status}",
        changes={"review_status": {"before": before, "after": payload.status}},
        is_public=False,
        request=request,
    )
    return _template_dict(template)


@router.get("/admin/tools/usage")
async def usage_stats(
    admin: Principal = Depends(require_permission("tools.manage")),
    session: AsyncSession = Depends(get_session),
):
    """How often each tool is used, by template and by state.

    Counts only. There is nothing else to report, because nothing else is stored --
    see the note on GenerationLog.
    """
    by_template = (
        await session.execute(
            select(GenerationLog.template_key, func.count()).group_by(GenerationLog.template_key)
        )
    ).all()
    by_state = (
        await session.execute(
            select(GenerationLog.state_code, func.count()).group_by(GenerationLog.state_code)
        )
    ).all()
    return {
        "byTemplate": [{"template": key, "count": count} for key, count in by_template],
        "byState": [{"state": state or "unspecified", "count": count} for state, count in by_state],
        "note": "Only counts are recorded. No applicant details or document contents are stored.",
    }


def _assert_placeholders_declared(body: list[dict], declared: set) -> None:
    """Fail fast on a placeholder no field supplies.

    Without this, a typo in a template body silently renders as an empty gap in the
    middle of a citizen's RTI application -- and nobody notices until an office
    rejects it.
    """
    known = declared | set(
        [
            "period_clause",
            "contact_clause",
            "fee_clause",
            "bpl_enclosure",
            "steps_clause",
            "reason_clause",
            "since_clause",
            "reference_clause",
            "officer_line",
        ]
    )
    used = {m for raw in body for m in _PLACEHOLDER_RE.findall(raw.get("text", ""))}
    unknown = sorted(used - known)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The template body uses placeholders that no field provides: {unknown}. "
                "Add a matching field, or remove the placeholder."
            ),
        )
