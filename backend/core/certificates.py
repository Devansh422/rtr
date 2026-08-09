"""Issuing and rendering certificates.

Shared by the Volunteer Portal, Events and the Academy. The interesting design
choice is that a certificate is a database row first and a document second: the
row is what makes the code on it verifiable, and the printable output is generated
on demand from the row rather than stored. Nothing is kept that could drift out of
sync with the record.

Rendering reuses core/documents, so a certificate is a DOCX or a print-to-PDF page
through exactly the same path as an RTI application -- and gets correct Devanagari
for the same reason.
"""

from typing import Optional
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.documents import Block, DocumentDraft
from backend.core.models import Certificate, utcnow

# Same alphabet as the member access code: no 0/O or 1/I, because these get read
# off a screen and typed into a verification box by someone who is not the holder.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

KINDS: dict[str, str] = {
    "volunteer_hours": "Certificate of Volunteer Service",
    "event_attendance": "Certificate of Participation",
    "course_completion": "Certificate of Completion",
    "supporter": "Certificate of Support",
}


def new_code(prefix: str = "RTR") -> str:
    """A short, transcribable verification code, e.g. RTR-K7M2-9PQX."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"{prefix}-{raw[:4]}-{raw[4:]}"


async def issue(
    session: AsyncSession,
    *,
    kind: str,
    holder_name: str,
    title: str,
    detail: Optional[dict] = None,
    citizen_id: Optional[str] = None,
    holder_email: str = "",
    issued_by: Optional[str] = None,
) -> Certificate:
    """Create one certificate. Part of the caller's transaction.

    Codes are retried on collision rather than assumed unique: 32^8 is a large
    space, but "assumed unique" is how you get a duplicate that breaks
    verification for two people at once.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown certificate kind: {kind}")

    for _ in range(5):
        code = new_code()
        exists = (
            await session.execute(select(Certificate).where(Certificate.code == code))
        ).scalar_one_or_none()
        if exists is None:
            break
    else:  # pragma: no cover - five collisions in a 32^8 space
        raise RuntimeError("Could not allocate a unique certificate code")

    certificate = Certificate(
        code=code,
        kind=kind,
        citizen_id=citizen_id,
        holder_email=(holder_email or "").lower(),
        holder_name=holder_name.strip(),
        title=title.strip(),
        detail=detail or {},
        issued_by=issued_by,
    )
    session.add(certificate)
    await session.flush()
    return certificate


def to_dict(certificate: Certificate, *, public: bool = True) -> dict:
    payload = {
        "code": certificate.code,
        "kind": certificate.kind,
        "kindLabel": KINDS.get(certificate.kind, certificate.kind),
        "holderName": certificate.holder_name,
        "title": certificate.title,
        "detail": certificate.detail,
        "issuedAt": certificate.issued_at.isoformat() if certificate.issued_at else None,
        "valid": not certificate.revoked,
        "revokedReason": certificate.revoked_reason or None,
        "verifyUrl": f"/certificates/{certificate.code}",
    }
    if not public:
        payload["holderEmail"] = certificate.holder_email
        payload["issuedBy"] = certificate.issued_by
    return payload


def render(certificate: Certificate, *, site_url: str = "https://righttorecall.in") -> DocumentDraft:
    """The printable certificate.

    Wording is deliberately modest. This is a civic volunteering record, not an
    academic award, and overclaiming ("Certified Constitutional Expert") would make
    every certificate the platform issues worth less.
    """
    detail_lines = [
        Block(f"{key}: {value}", kind="para", align="center")
        for key, value in (certificate.detail or {}).items()
        if value not in (None, "", [])
    ]

    return DocumentDraft(
        title=f"{KINDS.get(certificate.kind, 'Certificate')} - {certificate.holder_name}",
        filename=f"{certificate.code}.docx",
        blocks=[
            Block("RIGHT TO RECALL MOVEMENT", kind="para", align="center", bold=True),
            Block("A non-partisan civic platform", kind="para", align="center", italic=True),
            Block("", kind="spacer"),
            Block(KINDS.get(certificate.kind, "Certificate"), kind="heading", align="center"),
            Block("", kind="spacer"),
            Block("This is to certify that", kind="para", align="center"),
            Block(certificate.holder_name, kind="subheading", align="center"),
            Block(certificate.title, kind="para", align="center"),
            *detail_lines,
            Block("", kind="spacer"),
            Block(
                f"Issued on {certificate.issued_at.date().isoformat() if certificate.issued_at else utcnow().date().isoformat()}",
                kind="para",
                align="center",
            ),
            Block("", kind="spacer"),
            Block(f"Certificate code: {certificate.code}", kind="para", align="center", bold=True),
            Block(
                f"Verify this certificate at {site_url}/certificates/{certificate.code}",
                kind="para",
                align="center",
            ),
        ],
        hint=(
            "Use your browser's Print dialog and choose 'Save as PDF'. Anyone can confirm this "
            "certificate is genuine using the code at the bottom."
        ),
    )
