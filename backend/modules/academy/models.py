"""Constitutional Learning Academy: courses, lessons, quizzes, completion certificates.

One thing to get right: **the correct answers live in a column the public
serialiser never touches.** Quiz questions and their answers are stored together
in `Quiz.questions` because they are authored and edited together, and the risk
that follows is obvious -- one careless `return quiz.questions` and every answer
is in the browser's network tab. The router therefore has exactly two functions
that read that column: `_public_questions` (strips answers) and the grader
(server-side only), and nothing else may touch it.

Lessons cross-reference the Constitution Library by ARTICLE NUMBER
(`article_refs`), not by database id. That keeps this module from importing the
constitution module (§4's one-way rule) and, more practically, means a lesson's
"read Article 326" link survives the article row being recreated.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow

LEVELS: dict[str, str] = {
    "beginner": "Start here",
    "intermediate": "Going deeper",
    "advanced": "For organisers and researchers",
}

# Correct answers needed to pass. Set at 70 rather than 100 because the quiz is a
# check on understanding, not an exam, and a certificate nobody can get is a
# certificate nobody attempts.
DEFAULT_PASS_PERCENT = 70


class Course(Base):
    __tablename__ = "academy_courses"
    __table_args__ = (Index("ix_course_slug", "slug", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    summary_hi: Mapped[str] = mapped_column(String(700), nullable=False, default="")
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    cover_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Lesson(Base):
    __tablename__ = "academy_lessons"
    __table_args__ = (
        UniqueConstraint("course_id", "slug", name="uq_lesson_slug"),
        Index("ix_lesson_course", "course_id", "sort_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("academy_courses.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Constitution article numbers this lesson explains, e.g. ["326", "83"]. See
    # the module docstring for why these are numbers rather than ids.
    article_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # YouTube ids. Video hosting is free there and embeds anywhere (§5).
    video_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class Quiz(Base):
    """One quiz per course.

    `questions` holds the answers. Read it only through the two functions named in
    the module docstring.
    """

    __tablename__ = "academy_quizzes"
    __table_args__ = (UniqueConstraint("course_id", name="uq_quiz_course"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("academy_courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False, default="Check your understanding")
    pass_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_PASS_PERCENT)
    # [{"q": ..., "q_hi": ..., "options": [...], "options_hi": [...],
    #   "answer": 0, "explanation": ...}]
    questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class Enrollment(Base):
    __tablename__ = "academy_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "citizen_id", name="uq_enrollment"),
        Index("ix_enrollment_citizen", "citizen_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("academy_courses.id", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    # Lesson ids the learner has marked done. A JSON list rather than a join table
    # because it is only ever read and written whole, for one learner at a time.
    completed_lessons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class QuizAttempt(Base):
    __tablename__ = "academy_quiz_attempts"
    __table_args__ = (Index("ix_attempt_citizen", "citizen_id", "quiz_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    quiz_id: Mapped[str] = mapped_column(
        ForeignKey("academy_quizzes.id", ondelete="CASCADE"), nullable=False
    )
    citizen_id: Mapped[str] = mapped_column(
        ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False
    )
    score_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Submitted answer indices, kept so a learner can review what they got wrong.
    answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
