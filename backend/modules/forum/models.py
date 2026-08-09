"""Discussion forum: threads, replies, corroborative upvotes, moderation state.

Two decisions that differ from how a general-purpose forum would be built, both
following from §1's non-partisan requirement.

**There are no downvotes.** A downvote button on civic content about
representatives becomes a way for whichever group is more organised to bury the
other's posts, and the resulting front page looks like an editorial position the
platform did not take. Upvotes only, read as "this is useful", and ranking mixes
them with recency so a popular thread cannot sit at the top forever.

**Reputation gates actions, it does not rank people.** There is no leaderboard and
no visible score comparison. Reputation exists to raise the cost of abuse -- a
brand-new account cannot post links or start ten threads in an hour -- and
nothing else. A platform that scores its citizens against each other has built a
game, and people play games differently from how they do civics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class PostStatus(str):
    PUBLISHED = "published"
    # Caught by the content policy gate; visible to its author and to moderators
    # only. Deliberately not silently discarded -- a member whose post vanished
    # with no explanation concludes the platform is censoring them.
    HELD = "held"
    REMOVED = "removed"


# What a member must have earned before they can do each thing. Zero for the
# things civic participation requires; non-zero only where the action is a known
# abuse vector.
REPUTATION_GATES: dict[str, int] = {
    "reply": 0,
    "thread": 0,
    "upvote": 0,
    # Link-spam is the cheapest attack on a new forum, and 10 points is roughly
    # "one accepted correction, or one published report, or a few useful replies".
    "post_links": 10,
    # Starting a thread on a named representative's profile is the highest-risk
    # post type on the platform.
    "thread_on_representative": 20,
}


class ForumCategory(Base):
    """Fixed set of rooms, seeded from a static list.

    Not user-creatable: an open category list on a non-partisan platform becomes
    a set of party fan clubs within a week, and moderating that is a different
    and much larger job than moderating posts.
    """

    __tablename__ = "forum_categories"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ForumThread(Base):
    __tablename__ = "forum_threads"
    __table_args__ = (
        Index("ix_thread_slug", "slug", unique=True),
        Index("ix_thread_category", "category_key", "last_activity_at"),
        Index("ix_thread_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    category_key: Mapped[str] = mapped_column(
        ForeignKey("forum_categories.key", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Optional link to the record being discussed, e.g. representative/<slug>.
    # A plain string rather than a foreign key because it may point into any
    # module, and this module must not depend on them (§4).
    subject_ref: Mapped[str] = mapped_column(String(140), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PostStatus.PUBLISHED)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Bumped by replies, so an active discussion surfaces without needing a
    # subquery on every list read.
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    policy_flags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    moderation_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    moderated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ForumReply(Base):
    __tablename__ = "forum_replies"
    __table_args__ = (
        Index("ix_reply_thread", "thread_id", "created_at"),
        Index("ix_reply_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("forum_threads.id", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    # One level of nesting only. Deeper trees turn a civic discussion into an
    # argument tree that nobody reads to the bottom of.
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PostStatus.PUBLISHED)
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    policy_flags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    moderation_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    moderated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ForumVote(Base):
    """One upvote. No value column, because there is only one kind."""

    __tablename__ = "forum_votes"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "citizen_id", name="uq_forum_vote"),
        Index("ix_vote_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "thread" | "reply"
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# Seeded on boot. Chosen to give every legitimate conversation somewhere to go
# that is not "general", because an unfocused general room is where moderation
# problems accumulate.
DEFAULT_CATEGORIES: list[dict] = [
    {
        "key": "right-to-recall",
        "name": "The Right to Recall",
        "name_hi": "राइट टू रिकॉल",
        "description": "The case for recall, how it would work, and objections to it.",
        "sort_order": 10,
    },
    {
        "key": "constitution",
        "name": "Understanding the Constitution",
        "name_hi": "संविधान को समझना",
        "description": "Questions about articles, judgments and how the system is meant to work.",
        "sort_order": 20,
    },
    {
        "key": "my-constituency",
        "name": "My constituency",
        "name_hi": "मेरा निर्वाचन क्षेत्र",
        "description": "Local issues, service delivery and what your representative is doing.",
        "sort_order": 30,
    },
    {
        "key": "state-campaigns",
        "name": "State campaigns",
        "name_hi": "राज्य अभियान",
        "description": "Organising in a particular state, and where each state's campaign stands.",
        "sort_order": 40,
    },
    {
        "key": "civic-tools",
        "name": "RTI, PIL and representations",
        "name_hi": "आरटीआई, पीआईएल और अभ्यावेदन",
        "description": "Using the tools: filing an RTI, writing to an office, going to court.",
        "sort_order": 50,
    },
    {
        "key": "research",
        "name": "Research and data",
        "name_hi": "शोध और आंकड़े",
        "description": "Sources, datasets, and help verifying claims for the representative database.",
        "sort_order": 60,
    },
    {
        "key": "help",
        "name": "Help and feedback",
        "name_hi": "सहायता और प्रतिक्रिया",
        "description": "Problems with the platform, and suggestions for it.",
        "sort_order": 70,
    },
]
