"""The verifiability gate: no claim about a named person ships without a source.

§7 of IMPLEMENTATION_PLAN.md states the rule; this module is the one place it is
implemented, so that "sourced" means the same thing in the Representative
Database, the Promise Tracker, the Constitution Library and the Citizen Report
Cards rather than four slightly different things.

Three ideas, deliberately kept separate:

* `VerificationStatus` -- how much scrutiny a claim has had. The default is
  UNVERIFIED, never "fine unless someone objects", and the public serialiser
  refuses to present an unverified claim as plain fact.
* `Citation` -- where the claim came from. Validated, because a `source_url`
  field that accepts "told to me by a volunteer" is decoration.
* `OFFICIAL_SOURCES` -- the domains that count as a public official record. A
  citation outside this list is allowed (a news report of a court order is a
  real source) but is marked as secondary, which is a different editorial
  weight and is surfaced as such.

Nothing here talks to a database or to FastAPI on purpose: the same rules are
applied by module routers, by the fact-check queue and by the bulk importer, and
a rule that lives in a route handler is a rule the importer will forget.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import urlparse
import re


class VerificationStatus(str, Enum):
    """How much scrutiny a claim about a real person or body has had.

    Ordered by trust, and the order is used: `at_least()` below is how a public
    endpoint asks "may I render this as fact".
    """

    # Entered, sourced, not yet reviewed. Renders with a visible "pending
    # citation review" marker, never as an assertion.
    UNVERIFIED = "unverified"
    # A Fact Checker has followed the source and confirmed the claim matches it.
    FACT_CHECKED = "fact_checked"
    # Someone credibly contests it (usually via the corrections workflow). Stays
    # visible -- silently hiding a disputed claim is how a platform gets accused
    # of quietly editing history -- but is rendered as disputed, with the
    # dispute alongside it.
    DISPUTED = "disputed"
    # Reviewed and found wrong. Retained for the audit trail, excluded from
    # every public read.
    RETRACTED = "retracted"


_TRUST_ORDER = {
    VerificationStatus.RETRACTED: -1,
    VerificationStatus.UNVERIFIED: 0,
    VerificationStatus.DISPUTED: 1,
    VerificationStatus.FACT_CHECKED: 2,
}

# Statuses that may appear in a public read at all. RETRACTED is absent by
# design: a claim found to be false about a living person must stop being served.
PUBLICLY_VISIBLE = frozenset(
    {VerificationStatus.UNVERIFIED, VerificationStatus.FACT_CHECKED, VerificationStatus.DISPUTED}
)


def at_least(status: str, minimum: VerificationStatus) -> bool:
    try:
        return _TRUST_ORDER[VerificationStatus(status)] >= _TRUST_ORDER[minimum]
    except ValueError:
        return False


def is_publicly_visible(status: str) -> bool:
    try:
        return VerificationStatus(status) in PUBLICLY_VISIBLE
    except ValueError:
        # An unrecognised status is treated as the least trusted thing it could
        # be, not the most.
        return False


# --------------------------------------------------------------------------
# What counts as a source
# --------------------------------------------------------------------------
# Domains that publish primary public records. Suffix-matched, so
# `affidavit.eci.gov.in` matches `eci.gov.in`.
#
# This list is intentionally short and boring. It is not "sources we like" -- it
# is "sources whose documents are the record itself", which is what makes a
# claim about a living person defensible rather than merely attributed.
OFFICIAL_SOURCES: dict[str, str] = {
    "eci.gov.in": "Election Commission of India",
    "results.eci.gov.in": "ECI Results",
    "affidavit.eci.gov.in": "ECI Candidate Affidavits",
    "myneta.info": "ADR / MyNeta (ECI affidavit transcriptions)",
    "adrindia.org": "Association for Democratic Reforms",
    "prsindia.org": "PRS Legislative Research",
    "sansad.in": "Parliament of India",
    "loksabha.nic.in": "Lok Sabha",
    "rajyasabha.nic.in": "Rajya Sabha",
    "sci.gov.in": "Supreme Court of India",
    "ecourts.gov.in": "eCourts Services",
    "indiacode.nic.in": "India Code (Central legislation)",
    "egazette.gov.in": "Gazette of India",
    "data.gov.in": "Open Government Data Platform India",
    "pib.gov.in": "Press Information Bureau",
    "rti.gov.in": "RTI Online",
    "cic.gov.in": "Central Information Commission",
    "censusindia.gov.in": "Census of India",
    "niti.gov.in": "NITI Aayog",
}

# Any government or court domain is primary even if not enumerated above --
# there are hundreds of state portals and listing them all is not feasible.
_GOV_SUFFIXES = (".gov.in", ".nic.in", ".gov", ".court.gov.in")


class CitationError(ValueError):
    """A citation that does not meet the §7 bar. Callers map this to a 400."""


@dataclass(frozen=True)
class Citation:
    """A single piece of evidence behind one field.

    `source_date` is the date of the DOCUMENT, not the date it was entered --
    an affidavit filed in 2019 is 2019 evidence however recently someone typed
    it in, and conflating the two is how stale figures start looking current.
    """

    url: str
    title: str
    source_date: Optional[str] = None
    publisher: Optional[str] = None
    is_primary: bool = False

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "sourceDate": self.source_date,
            "publisher": self.publisher,
            # Surfaced so the UI can distinguish "ECI affidavit" from "news
            # report about an ECI affidavit". Both are citations; they are not
            # the same evidence.
            "isPrimary": self.is_primary,
        }


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def classify_source(url: str) -> tuple[bool, Optional[str]]:
    """(is_primary, publisher_name) for a citation URL.

    Matches the MOST SPECIFIC entry, not the first one that fits: without that,
    `affidavit.eci.gov.in` is attributed to "Election Commission of India" because
    `eci.gov.in` happens to come earlier in the dict, and the citation loses the
    detail that makes it checkable.
    """
    host = domain_of(url)
    if not host:
        return False, None

    best: Optional[tuple[int, str]] = None
    for domain, publisher in OFFICIAL_SOURCES.items():
        if host == domain or host.endswith(f".{domain}"):
            if best is None or len(domain) > best[0]:
                best = (len(domain), publisher)
    if best is not None:
        return True, best[1]

    if host.endswith(_GOV_SUFFIXES):
        return True, host
    return False, host or None


_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def parse_citation(
    payload: dict,
    *,
    require_primary: bool = False,
    field_name: str = "source",
) -> Citation:
    """Validate a citation submitted over the API.

    `require_primary=True` is used for the fields that carry real legal risk --
    criminal cases, declared assets, conviction status. For those, a news
    article is not enough: the platform's defence is "we are reporting what the
    public record says", and that defence needs the public record.
    """
    url = (payload.get("url") or payload.get("source_url") or "").strip()
    if not url:
        raise CitationError(f"A source URL is required for {field_name}")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise CitationError(
            f"The source for {field_name} must be a full public URL starting with https://"
        )

    title = (payload.get("title") or "").strip()
    if len(title) < 4:
        raise CitationError(
            f"Describe the source for {field_name} (e.g. 'ECI affidavit, 2024 general election')"
        )

    source_date = (payload.get("source_date") or payload.get("sourceDate") or "").strip() or None
    if source_date and not _DATE_RE.match(source_date):
        raise CitationError("Source date must be YYYY, YYYY-MM or YYYY-MM-DD")
    if source_date:
        # A document dated in the future is a typo, and a typo in an evidence
        # date is worth catching before it is published next to someone's name.
        try:
            parts = [int(p) for p in source_date.split("-")]
            as_date = date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
        except ValueError:
            raise CitationError("Source date is not a real date")
        if as_date > datetime.now(timezone.utc).date():
            raise CitationError("Source date is in the future")

    is_primary, publisher = classify_source(url)
    if require_primary and not is_primary:
        raise CitationError(
            f"{field_name} must cite a primary public record (ECI, a court, PRS, a Gazette "
            f"notification or a government portal). '{domain_of(url)}' is a secondary source -- "
            "cite the document it reports on."
        )

    return Citation(
        url=url,
        title=title,
        source_date=source_date,
        publisher=(payload.get("publisher") or "").strip() or publisher,
        is_primary=is_primary,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
# Wording is shared so the same status never gets two different explanations in
# two different parts of the site.
STATUS_LABELS: dict[str, str] = {
    VerificationStatus.UNVERIFIED: "Unverified - pending citation review",
    VerificationStatus.FACT_CHECKED: "Fact-checked against the cited source",
    VerificationStatus.DISPUTED: "Disputed - a correction is under review",
    VerificationStatus.RETRACTED: "Retracted",
}

# Platform-wide, per §7. Rendered on every representative profile and anywhere
# criminal-case data appears. Kept here rather than in the frontend so the API
# ships its own disclaimer and an embedder cannot drop it.
STANDARD_DISCLAIMER = (
    "Information is compiled from public records: Election Commission of India affidavits, "
    "court filings, PRS Legislative Research and Gazette notifications. Pending criminal "
    "cases are allegations, not convictions, and every person is presumed innocent until "
    "convicted by a court. The Right to Recall Movement does not independently investigate "
    "allegations and takes no position on the guilt of any individual. If you believe "
    "anything here is inaccurate, use 'Suggest a correction' on this page."
)


def claim_envelope(
    value,
    *,
    status: str,
    citation: Optional[dict] = None,
    updated_at=None,
) -> dict:
    """Wrap one sourced value in the shape the frontend renders.

    Every claim about a person crosses the wire in this envelope rather than as
    a bare value. That is the structural half of the §7 rule: a frontend cannot
    accidentally render an unverified criminal-case count as a plain number,
    because it never receives a plain number.
    """
    return {
        "value": value,
        "status": status,
        "statusLabel": STATUS_LABELS.get(status, status),
        "isFact": at_least(status, VerificationStatus.FACT_CHECKED),
        "citation": citation,
        "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
    }
