"""Templates for the RTI and Representation generators.

§9 is explicit that these are deterministic template-fill flows, not LLM
generation, and the reason is worth restating: an RTI application with a wrong
section reference gets rejected, and a representation that misstates the law
embarrasses the citizen who sent it. A template reviewed once by the Legal Team
and filled in mechanically is more reliable than a model that is right most of the
time, and it costs nothing to run.

Two consequences in this schema:

* `review_status` gates use. A template is `draft` until someone with
  `legal.review` approves it, and the generator refuses to render a draft for a
  member of the public. A generator that emits unreviewed legal text is the
  fastest way for this platform to give bad legal advice at scale.
* **Nothing a citizen types is stored.** `GenerationLog` records that an RTI was
  generated from template X in state Y at time T, and nothing else. RTI
  applications routinely contain the applicant's address and the details of their
  grievance; keeping those would create a database of citizens' complaints against
  the government, which is both a DPDP liability and a target. The generated
  document exists in the response body and nowhere else.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow

TOOL_KINDS: dict[str, str] = {
    "rti": "RTI application",
    "rti_first_appeal": "RTI first appeal",
    "rti_second_appeal": "RTI second appeal",
    "representation": "Representation to a representative",
    "department_letter": "Letter to a government department",
    "grievance_followup": "Grievance follow-up",
    "recall_demand": "Right to Recall demand letter",
}


class ReviewStatus(str):
    DRAFT = "draft"
    LEGAL_APPROVED = "legal_approved"
    RETIRED = "retired"


class DocumentTemplate(Base):
    __tablename__ = "tool_templates"
    __table_args__ = (
        Index("ix_template_key", "key", unique=True),
        Index("ix_template_kind", "kind", "review_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(60), nullable=False)

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # None = usable anywhere. Set when a template encodes state-specific rules
    # (RTI fees and the appellate authority differ by state).
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # [{"name": "pio_office", "label": "...", "type": "text|textarea|date|select",
    #   "required": true, "help": "...", "options": [...], "maxLength": 500}]
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{"kind": "para", "text": "To,\n{{pio_office}}", "align": "left", "bold": false}]
    # Blocks rather than one string, so the output maps straight onto
    # core/documents.Block and renders identically as DOCX and as print HTML.
    body: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # The provision the template relies on, shown to the user. "Section 6(1) of
    # the RTI Act, 2005" is what turns a form into something the citizen
    # understands they are exercising a right through.
    legal_basis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Practical notes: fee, where to send it, how long to wait.
    filing_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReviewStatus.DRAFT)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class GenerationLog(Base):
    """That a document was generated. Never what it said.

    See the module docstring. This exists so the platform can answer "is the RTI
    generator actually used, and for which states" without holding a single line of
    anyone's application.
    """

    __tablename__ = "tool_generation_log"
    __table_args__ = (Index("ix_generation_template", "template_key", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    template_key: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False, default="preview")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
