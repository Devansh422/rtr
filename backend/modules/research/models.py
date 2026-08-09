"""Research Centre and Media Library: one repository, two audiences.

The brief lists these separately and they are modelled together, on purpose. A
research paper and a campaign poster are the same object as far as this platform is
concerned -- a titled, tagged, attributed file with a source and a licence -- and
they differ only in `kind`. Two tables would mean two search paths, two upload
screens and two places to fix a licence bug, in exchange for a distinction that
exists in the sidebar rather than in the data.

Storage is by reference. `file_url` may point at Cloudflare R2 (§5: 10 GB free and,
unusually, zero egress, which is the property that matters for a public library), at
the existing `/api/uploads/{id}` route, or at a third-party source that should not
be rehosted -- a Supreme Court judgment stays on the Court's own site, both because
rehosting adds nothing and because the canonical link is the citation.

`licence` is required, and that is not bureaucracy. A civic platform that
republishes material without recording whether it is allowed to is one takedown
notice away from a credibility problem, and the person who uploaded the file three
years ago will not remember.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow

DOCUMENT_KINDS: dict[str, str] = {
    # Research Centre
    "research_paper": "Research paper",
    "report": "Report or study",
    "judgment": "Court judgment",
    "legislation": "Bill, Act or rules",
    "rti_reply": "RTI reply",
    "affidavit": "Election affidavit",
    "dataset": "Dataset",
    "committee_report": "Parliamentary or committee report",
    "manifesto": "Party manifesto",
    # Media Library
    "poster": "Poster",
    "infographic": "Infographic",
    "photo": "Photograph",
    "video": "Video",
    "presentation": "Presentation or deck",
    "template": "Template or handout",
}

# Kinds that belong in the Media Library view rather than the Research Centre.
# A display grouping, not a schema boundary -- see the module docstring.
MEDIA_KINDS = frozenset(
    {"poster", "infographic", "photo", "video", "presentation", "template"}
)

LICENCES: dict[str, str] = {
    "cc_by": "Creative Commons Attribution 4.0",
    "cc_by_sa": "Creative Commons Attribution-ShareAlike 4.0",
    "cc0": "Public domain dedication (CC0)",
    "gov_open": "Government Open Data Licence - India",
    "public_record": "Public record, reproduced for reporting and comment",
    "own_work": "Created by the Right to Recall Movement",
    "linked_only": "Not hosted here - linked to the original source",
    "permission": "Reproduced with the rights holder's permission",
}


class ResearchDocument(Base):
    __tablename__ = "research_documents"
    __table_args__ = (
        Index("ix_document_slug", "slug", unique=True),
        Index("ix_document_kind", "kind"),
        Index("ix_document_state", "state_code"),
        Index("ix_document_published", "is_published"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(240), nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(360), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # Free text: "Association for Democratic Reforms", "Supreme Court of India",
    # "Standing Committee on Law and Justice". Not a foreign key, because the set
    # of possible authors is the world.
    authors: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    publisher: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    published_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Where the document ORIGINALLY appeared -- the citation. Required.
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Where a reader gets the file from us, when we host it at all.
    file_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    file_size_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    licence: Mapped[str] = mapped_column(String(30), nullable=False, default="linked_only")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Constitution article numbers this document is about, for cross-linking
    # without importing the constitution module.
    article_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Counted because it is the only signal of which sources are actually used,
    # and therefore which are worth spending volunteer time summarising.
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploaded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
