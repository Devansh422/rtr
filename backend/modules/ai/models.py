"""Answer cache and question log for the Constitution Assistant.

The cache is not a performance optimisation, or not mainly. Three reasons it is the
first thing in this module:

1. **Free-tier arithmetic.** §5 budgets roughly 1,000 requests a day. "What is the
   difference between recall and impeachment?" will be asked hundreds of times, and
   every cache hit is a question someone else gets to ask.
2. **Consistency.** Two citizens asking the same constitutional question and getting
   differently-worded answers is a credibility problem for a platform whose entire
   claim is accuracy. A cached answer is the same answer.
3. **Reviewability.** Cached answers can be read by a human, corrected, and pinned.
   A model that answers freshly every time cannot be audited at all -- and §9's
   requirement that the assistant never fabricate an Article number is only
   enforceable if someone can look at what it actually said.

The question log stores questions, never questioners. See the note on the table.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class AnswerCache(Base):
    __tablename__ = "ai_answer_cache"
    __table_args__ = (Index("ix_ai_cache_key", "question_hash", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # sha256 of the normalised question. Normalisation is in the router, so
    # "Can an MLA be recalled?" and "can an mla be recalled" share an entry.
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # Article numbers and document slugs the answer was grounded in. Returned with
    # every answer so a reader can check the source rather than trust the prose.
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "gemini" | "retrieval_only". Recorded because the two are genuinely
    # different products and a reader deserves to know which one answered.
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="retrieval_only")

    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # A staff member has read this answer and vouched for it. Pinned answers are
    # never regenerated, which is how a wrong answer gets permanently fixed.
    is_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class QuestionLog(Base):
    """What people ask. Never who asked it.

    No citizen id, no IP, no session. What this table is for is finding the
    questions the Constitution Library should answer directly -- if two hundred
    people a week ask how to check their voter registration, that is a page to
    write, not a query to keep serving through a language model.

    Questions are scrubbed of identifiers before they get here, because a free-tier
    model provider may retain prompts (§5) and because a log of citizens' legal
    worries is not something this platform should hold.
    """

    __tablename__ = "ai_question_log"
    __table_args__ = (Index("ix_ai_log_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    was_cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # False when retrieval found nothing relevant -- the most useful signal in the
    # table, because it is a list of things the library does not cover.
    was_answered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    refusal_reason: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="retrieval_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
