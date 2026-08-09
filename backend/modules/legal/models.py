"""Consent records.

The DPDP Act requires that consent be informed, specific, and demonstrable. The
first two are the frontend's job (a notice next to the button, one purpose per
checkbox); the third is this table's. Without it, "did this person agree, to what,
and under which version of the notice" has no answer, and an unanswerable compliance
question is a failed one.

Append-only in spirit: withdrawing consent writes a new row with
`granted=False` rather than updating the old one. The history is the evidence, and
an audit trail you can overwrite is not an audit trail.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_consent_subject", "subject_email", "purpose"),
        Index("ix_consent_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    # Email rather than a foreign key to citizens: consent is given at the moment a
    # form is submitted, which is often BEFORE any account row exists, and the
    # record has to survive the account being deleted -- proving that consent was
    # obtained is exactly what an erased user might later dispute.
    subject_email: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Which version of the notice was on screen. Without this, a policy change
    # retroactively rewrites what everyone consented to.
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    # The exact notice text shown, so the record is self-contained even if the
    # policy file changes. Storage cost is trivial next to the value of not having
    # to reconstruct it.
    notice_shown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Which form or page it was given on.
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    # Hashed, never raw -- same reasoning as the audit log's ip_hash.
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
