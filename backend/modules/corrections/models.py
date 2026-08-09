"""The "Suggest a correction" workflow.

§7 lists this as both a legal safeguard and a genuine engagement feature, and it
is the closest thing this platform has to a Wikipedia talk page. It is a
deliberately generic object: `entity_type` + `entity_id` + optional `field_key`,
so a correction can point at a representative's asset figure, a constitution
article's plain-English text, a state's campaign stage or a research document,
without this module knowing anything about those modules.

That genericity is also why accepting a correction does NOT automatically rewrite
the thing it objects to. Reaching into another module's tables to mutate a claim
would be exactly the sideways coupling §4 forbids, and worse, it would let a
correction queue become an unreviewed edit channel. Instead: accepting a
correction records the finding and links to the claim it concerns, and the
reviewer -- who holds `corrections.review`, and in practice is Research Team or a
Fact Checker -- makes the actual edit through the owning module, where the
citation and audit rules apply. One extra click, and the verifiability gate stays
in one place.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class CorrectionStatus(str):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    NEEDS_INFO = "needs_more_info"


STATUS_LABELS: dict[str, str] = {
    CorrectionStatus.OPEN: "Received",
    CorrectionStatus.UNDER_REVIEW: "Under review",
    CorrectionStatus.ACCEPTED: "Accepted - record corrected",
    CorrectionStatus.REJECTED: "Reviewed - no change made",
    CorrectionStatus.DUPLICATE: "Duplicate of an earlier correction",
    CorrectionStatus.NEEDS_INFO: "More information needed",
}

# Statuses a reviewer has actually ruled on, and whose reasoning is therefore
# safe and useful to publish. `open` is excluded on purpose -- see the note in
# the router on why unreviewed submissions are not shown verbatim.
RESOLVED_STATUSES = frozenset(
    {CorrectionStatus.ACCEPTED, CorrectionStatus.REJECTED, CorrectionStatus.DUPLICATE}
)

# Entity types a correction may be filed against. An allow-list, so a typo in a
# client cannot create a queue of corrections about an entity nobody owns.
CORRECTABLE_ENTITIES: dict[str, str] = {
    "representative": "Representative profile",
    "promise": "Promise tracker entry",
    "constitution_article": "Constitution article",
    "state": "State campaign status",
    "research_document": "Research document",
    "report": "Citizen report card",
}


class Correction(Base):
    __tablename__ = "corrections"
    __table_args__ = (
        Index("ix_correction_entity", "entity_type", "entity_id"),
        Index("ix_correction_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    # Which specific field is contested, when the submitter can say. Optional,
    # because "the whole tone of this page is wrong" is a legitimate objection
    # even though it names no field.
    field_key: Mapped[str] = mapped_column(String(60), nullable=False, default="")

    # ---- What the submitter says ----
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_title: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    # ---- Who filed it ----
    # A Citizen id when signed in. Anonymous submission is allowed on purpose:
    # requiring an account to report an error about a powerful person filters out
    # exactly the people most likely to know about it. Anonymity costs the
    # submitter their reputation credit, not their right to be heard.
    citizen_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Optional, and only so the reviewer can come back with a question. Never
    # published, and erased along with everything else on a DPDP erasure request.
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CorrectionStatus.OPEN)
    # The reviewer's reasoning. Published for resolved corrections, because "we
    # looked and here is why we did or did not change it" is the entire
    # credibility payoff of running this workflow in the open.
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Claim/record id the correction led to, when it led to one. A pointer, not a
    # foreign key -- it can reference rows in several modules.
    resulted_in: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # Moderation verdict from core/moderation, stored so a reviewer sees why a
    # submission was held rather than having to re-run the check mentally.
    policy_flags: Mapped[str] = mapped_column(Text, nullable=False, default="")

    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
