"""Public certificate verification.

Three modules issue certificates (volunteers, events, academy) through
core/certificates. This one only reads them, and exists so that verification has a
single public URL that does not belong to any of the three -- someone checking a
certificate on a CV should not have to know which part of the platform issued it.

Verification is unauthenticated. That is the entire point: the person checking is an
employer or a university, not a member.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, certificates, notify
from backend.core.deps import get_session, require_permission
from backend.core.documents import DOCX_MEDIA_TYPE
from backend.core.models import Certificate
from backend.core.rbac import Principal

router = APIRouter(tags=["certificates"])


class RevokeIn(BaseModel):
    reason: str = Field(..., min_length=10)


@router.get("/certificates/{code}")
async def verify_certificate(code: str, session: AsyncSession = Depends(get_session)):
    """Confirm a certificate is genuine.

    Returns the holder's name, what it was for, when it was issued and whether it is
    still valid -- and nothing else. No email address, no member id, no other
    certificates the same person holds. Whoever is verifying needs to know the
    document is real, not who else this person is.

    A revoked certificate returns 200 with `valid: false` rather than 404. "Not
    found" and "revoked" are different facts, and collapsing them would let a
    revoked certificate be passed off as a typo.
    """
    certificate = (
        await session.execute(select(Certificate).where(Certificate.code == code.strip().upper()))
    ).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No certificate with that code was issued by the Right to Recall Movement. Check the "
                "code for transcription errors -- our codes never contain the letters O or I, or the "
                "digits 0 or 1."
            ),
        )
    return {
        **certificates.to_dict(certificate),
        "issuer": "Right to Recall Movement",
        "verifiedAt": None,
    }


@router.get("/certificates/{code}/print", response_class=Response)
async def print_certificate(code: str, session: AsyncSession = Depends(get_session)):
    """Printable certificate page. Save-as-PDF from the browser (see core/documents)."""
    certificate = (
        await session.execute(select(Certificate).where(Certificate.code == code.strip().upper()))
    ).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.revoked:
        raise HTTPException(status_code=410, detail="This certificate has been revoked")

    draft = certificates.render(certificate, site_url=notify.SITE_URL)
    return Response(content=draft.html(), media_type="text/html; charset=utf-8")


@router.get("/certificates/{code}/download")
async def download_certificate(code: str, session: AsyncSession = Depends(get_session)):
    certificate = (
        await session.execute(select(Certificate).where(Certificate.code == code.strip().upper()))
    ).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.revoked:
        raise HTTPException(status_code=410, detail="This certificate has been revoked")

    draft = certificates.render(certificate, site_url=notify.SITE_URL)
    return Response(
        content=draft.docx(),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{draft.filename}"'},
    )


@router.post("/admin/certificates/{code}/revoke")
async def revoke_certificate(
    code: str,
    payload: RevokeIn,
    request: Request,
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Revoke a certificate issued in error.

    Not deleted. A certificate someone has already put on a CV must keep resolving,
    with `valid: false` and the reason -- deleting the row would make a real
    verification attempt look like a transcription error.
    """
    certificate = (
        await session.execute(select(Certificate).where(Certificate.code == code.strip().upper()))
    ).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")

    certificate.revoked = True
    certificate.revoked_reason = payload.reason.strip()
    await audit.record(
        session,
        actor=admin,
        action="revoke",
        entity_type="certificate",
        entity_id=certificate.code,
        summary=f"Revoked certificate {certificate.code}: {payload.reason.strip()[:80]}",
        is_public=False,
        request=request,
    )
    return certificates.to_dict(certificate, public=False)
