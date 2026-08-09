"""The Constitution Library's relational schema.

Postgres rather than Mongo, per §4: articles are queried by part, by tag, by
relationship to other articles and by publication state, and the "related
articles" graph is the feature that makes the library a library rather than a
list. That is relational work.

Two design points worth stating because they are easy to get wrong later:

* **The verbatim text and the explanation are different fields with different
  rules.** `original_text` is law and is never edited for clarity; `plain_en` /
  `plain_hi` are the platform's own writing and are edited freely. Storing them
  in one field would make it impossible to tell a reader which one they are
  reading, and the whole value of a plain-language layer is that the reader
  knows it is a paraphrase.
* **`recall_relevance` is a first-class column.** The site exists for one
  purpose (§1); an article's connection to accountability and recall is the
  reason it is in this library rather than in a general constitutional
  encyclopedia. Keeping it in a named field rather than buried in prose means
  the "Why this matters for Right to Recall" section either exists or visibly
  does not.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.models import Base, new_id, utcnow


class ConstitutionArticle(Base):
    __tablename__ = "constitution_articles"
    __table_args__ = (
        Index("ix_constitution_number", "number", unique=True),
        Index("ix_constitution_part", "part"),
        Index("ix_constitution_published", "is_published"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    # "21", "21A", "243G", "368". A string because article numbers are not
    # integers -- inserted articles carry letters, and 21A sorts after 21 and
    # before 22, which no numeric type will do for you.
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    # Integer ordering key derived from `number` at write time, so the library
    # can be paged in constitutional order without sorting "10" before "9".
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    part: Mapped[str] = mapped_column(String(20), nullable=False, default="")  # Roman numeral, e.g. "III"
    part_title: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(400), nullable=False, default="")

    # Verbatim constitutional text. Empty is a legitimate state: an article whose
    # text has not yet been transcribed from India Code shows the citation and a
    # link rather than a paraphrase pretending to be the text. Never edited for
    # readability -- that is what the plain-language fields are for.
    original_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    plain_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plain_hi: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Why this article matters to the Right to Recall argument. See the module
    # docstring for why this is a column and not a paragraph inside plain_en.
    recall_relevance: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # [{"case": "...", "citation": "...", "year": 1978, "url": "...", "held": "..."}]
    # JSON rather than a table: case law is read as a block with its article,
    # never queried across articles, and a judgments table with no queries
    # against it is a join for its own sake.
    case_law: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    amendments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Article numbers, not ids: the graph must survive a row being recreated, and
    # "see also Article 32" is how a reader thinks about it.
    related: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # {"hi": "human_reviewed"} -- see core/i18n.Provenance. A machine draft of
    # constitutional text is never served as the text (§8).
    translation_status: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


def compute_sort_key(number: str) -> int:
    """Constitutional order as a sortable integer.

    Multiply the numeric part by 100 and add the letter suffix's position, so
    21 -> 2100, 21A -> 2101, 22 -> 2200. Handles the inserted-article convention
    (243A..243ZG) up to two suffix letters, which covers the Constitution as it
    stands.
    """
    digits = "".join(c for c in number if c.isdigit())
    letters = "".join(c for c in number if c.isalpha()).upper()
    base = int(digits) * 100 if digits else 0
    suffix = 0
    for i, char in enumerate(reversed(letters[:2])):
        suffix += (ord(char) - 64) * (26**i)
    return base + min(suffix, 99)
