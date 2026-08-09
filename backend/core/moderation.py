"""The non-partisan content policy, as code.

§1 of IMPLEMENTATION_PLAN.md says non-partisanship must be enforced
structurally, not by good intentions, and §7 says the Forum and Citizen Reports
need moderation gates *before* they ship. This module is that gate.

What it is and is not:

* It is a TRIAGE aid. It decides whether a submission publishes immediately,
  waits for a Moderator, or is refused outright. Almost everything it flags
  lands in the middle bucket, because a keyword cannot tell criticism of a
  policy from an attack on a community, and pretending otherwise would either
  censor legitimate civic speech or wave through the thing the policy exists to
  stop.
* It is NOT a banned-word list. Naming a party, a religion or a caste is often
  exactly what an accurate civic report has to do -- "the sitting MLA's party"
  is a neutral fact, and a report about discriminatory delivery of a scheme
  cannot be written without naming who was discriminated against. So identity
  terms alone never trigger anything; they only matter when they co-occur with
  hostility or campaigning markers in the same passage.
* It is explainable. Every decision returns the rule that fired and the text
  that fired it, because a moderator overturning a machine's call needs to see
  its reasoning, and a citizen whose post was held deserves to be told why.

The lexicons are deliberately small, English/Hindi/Hinglish, and will miss
things. That is expected: the design assumption is a human Moderator queue with
machine assistance, not machine moderation with human appeal.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional
import re


class Decision(str, Enum):
    ALLOW = "allow"
    # Stored, not published. Appears in the Moderator queue.
    HOLD = "hold_for_review"
    # Refused at the API boundary; nothing is stored. Reserved for content that
    # is unlawful or unsafe to hold at all (personal identifiers, doxxing).
    REJECT = "reject"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class PolicyFlag:
    code: str
    severity: Severity
    # Written to be shown to the person who submitted the content, so it
    # explains the policy rather than merely announcing a verdict.
    explanation: str
    excerpt: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "explanation": self.explanation,
            "excerpt": self.excerpt,
        }


@dataclass
class Verdict:
    decision: Decision
    flags: list[PolicyFlag] = field(default_factory=list)

    @property
    def publishes(self) -> bool:
        return self.decision is Decision.ALLOW

    def as_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "flags": [f.as_dict() for f in self.flags],
        }


# --------------------------------------------------------------------------
# Lexicons
# --------------------------------------------------------------------------
# Identity terms. On their own these are neutral and NEVER flag anything -- see
# the module docstring. They are one half of a co-occurrence rule.
_IDENTITY_TERMS = {
    # religion
    "hindu", "hindus", "muslim", "muslims", "musalman", "sikh", "sikhs", "christian",
    "christians", "jain", "buddhist", "parsi", "isai", "hinduon", "musalmano",
    # caste / community
    "dalit", "dalits", "brahmin", "brahmins", "thakur", "yadav", "jaat", "jat",
    "maratha", "patidar", "obc", "adivasi", "tribal", "harijan", "bania",
    "caste", "jaati", "jati", "savarna", "bahujan",
    # region-as-identity
    "bihari", "madrasi", "bhaiya", "outsider", "bangladeshi", "rohingya",
}

# Hostility markers: calls to exclusion, violence, or collective blame.
#
# Inflections are listed explicitly rather than stemmed. A stemmer would catch
# "driven" from "drive" but would also collapse words that matter differently, and
# this list has to be auditable by a moderator reading it -- so the cost is a longer
# list and the benefit is that what fires is exactly what is written here.
_HOSTILITY_TERMS = {
    "kill", "kills", "killed", "killing", "beat", "beaten", "thrash", "lynch",
    "lynched", "burn", "burnt", "destroy", "destroyed",
    "drive out", "driven out", "drove out", "throw out", "thrown out", "threw out",
    "kick out", "kicked out", "push out", "pushed out",
    "deport", "deported", "cleanse", "cleansed", "wipe out", "wiped out",
    "traitor", "traitors", "anti-national", "antinational", "desh drohi",
    "gaddar", "maro", "maar do", "bhaga do", "nikal do", "khatam",
    "parasite", "parasites", "vermin", "infiltrator", "infiltrators", "termite",
    "termites", "encroacher", "encroachers",
    "should not be allowed", "should be removed", "have no right", "do not belong",
    "get out of", "go back to",
}

# Party-political campaigning markers. Not party NAMES -- the ask.
_CAMPAIGNING_TERMS = {
    "vote for", "vote karo", "vote de", "vote dena", "support the party",
    "join our party", "elect", "re-elect", "reelect", "defeat the",
    "harao", "jitao", "zindabad", "murdabad", "hai hai",
    "our party", "party ko vote", "booth", "campaign for",
    "chunav me vote", "mp banao", "mla banao", "cm banao", "pm banao",
}

# Unverified personal accusation markers. Fine on a policy, defamatory on a
# named person without a citation -- the Citizen Report and Forum flows both
# require a source when one of these appears with a named individual.
_ACCUSATION_TERMS = {
    "corrupt", "bribe", "bribes", "took money", "paisa khaya", "ghotala",
    "scam", "scamster", "thief", "chor", "criminal", "murderer", "rapist",
    "launder", "black money", "commission khaya", "daaru bata",
    "fraud", "fraudster", "embezzle", "kickback",
}

# Slur-shaped abuse aimed at a person. Kept generic on purpose: an exhaustive
# profanity list is both unmaintainable and unnecessary, because the queue
# exists. These are the terms whose only use is abuse.
_ABUSE_TERMS = {
    "bastard", "idiot", "moron", "stupid fool", "shut up", "kutta", "kutte",
    "suar", "harami", "kamina", "nalayak", "bewakoof", "gaddha",
}


def _terms_present(haystack: str, terms: Iterable[str]) -> list[str]:
    """Whole-word/phrase matches, so 'scam' does not fire on 'scamper'."""
    found = []
    for term in terms:
        pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, haystack):
            found.append(term)
    return found


# --------------------------------------------------------------------------
# Personal identifiers -- the only hard rejections
# --------------------------------------------------------------------------
# Holding someone's Aadhaar or PAN in a public forum post is a DPDP problem and
# a safety problem regardless of intent, so this is refused rather than queued:
# the platform must not store it even briefly in a moderation queue.
_AADHAAR_RE = re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_PHONE_RE = re.compile(r"(?:\+91[\s-]?|\b0)?[6-9]\d{9}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
_URL_RE = re.compile(r"https?://\S+")


def _excerpt(text: str, needle: str, width: int = 60) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    return ("..." if start else "") + text[start : idx + len(needle) + width // 2].strip() + "..."


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------
def review(
    text: str,
    *,
    names_a_person: bool = False,
    has_citation: bool = False,
    allow_contact_details: bool = False,
) -> Verdict:
    """Apply the content policy to one submission.

    `names_a_person` is set by the caller when the submission is attached to a
    named representative (a Citizen Report about an MLA, a forum thread on a
    profile). It is what turns "corrupt" from a political adjective into an
    accusation about an identifiable individual, which §7 says needs a source.

    `allow_contact_details` is for the flows where an email or phone number is
    the point (an event organiser's contact line), so the identifier rule does
    not have to be duplicated with an exception in each caller.
    """
    flags: list[PolicyFlag] = []
    body = (text or "").strip()
    if not body:
        return Verdict(Decision.ALLOW)

    lowered = body.lower()

    # ---- Hard rejections: things we must not store ----
    if _AADHAAR_RE.search(body):
        flags.append(
            PolicyFlag(
                "personal_identifier",
                Severity.BLOCK,
                "This looks like an Aadhaar number. Never post government identity numbers "
                "publicly -- remove it and describe the issue without it.",
            )
        )
    if _PAN_RE.search(body):
        flags.append(
            PolicyFlag(
                "personal_identifier",
                Severity.BLOCK,
                "This looks like a PAN. Remove it before posting.",
            )
        )
    if not allow_contact_details:
        if _PHONE_RE.search(body):
            flags.append(
                PolicyFlag(
                    "contact_details",
                    Severity.BLOCK,
                    "Phone numbers cannot be posted publicly, including your own -- it exposes "
                    "you, and posting someone else's is harassment. Use the contact form instead.",
                )
            )
        if _EMAIL_RE.search(body):
            flags.append(
                PolicyFlag(
                    "contact_details",
                    Severity.BLOCK,
                    "Email addresses cannot be posted publicly. Use the contact form instead.",
                )
            )

    if any(f.severity is Severity.BLOCK for f in flags):
        return Verdict(Decision.REJECT, flags)

    # ---- Communal / caste framing: identity + hostility in the same passage ----
    identity_hits = _terms_present(lowered, _IDENTITY_TERMS)
    hostility_hits = _terms_present(lowered, _HOSTILITY_TERMS)
    if identity_hits and hostility_hits:
        flags.append(
            PolicyFlag(
                "communal_framing",
                Severity.WARN,
                "This appears to blame or target a religion, caste or community. The movement is "
                "non-partisan and non-communal by policy: argue about the conduct of an office "
                "holder or an institution, never about a community. A moderator will review this.",
                _excerpt(body, hostility_hits[0]),
            )
        )
    elif hostility_hits:
        flags.append(
            PolicyFlag(
                "hostile_language",
                Severity.WARN,
                "This contains language calling for harm or exclusion. A moderator will review it.",
                _excerpt(body, hostility_hits[0]),
            )
        )

    # ---- Party-political campaigning ----
    campaigning_hits = _terms_present(lowered, _CAMPAIGNING_TERMS)
    if campaigning_hits:
        flags.append(
            PolicyFlag(
                "party_campaigning",
                Severity.WARN,
                "This reads as campaigning for or against a party or candidate. The platform "
                "holds every party to the same standard and cannot host electoral campaigning "
                "-- rewrite it as a factual point about conduct or policy.",
                _excerpt(body, campaigning_hits[0]),
            )
        )

    # ---- Unsourced accusation against a named person ----
    accusation_hits = _terms_present(lowered, _ACCUSATION_TERMS)
    if accusation_hits and names_a_person and not has_citation:
        flags.append(
            PolicyFlag(
                "unsourced_accusation",
                Severity.WARN,
                "This makes a serious allegation about a named person without citing a public "
                "record. Add a link to the court filing, ECI affidavit, RTI reply or official "
                "order it rests on. Pending cases are allegations, not convictions.",
                _excerpt(body, accusation_hits[0]),
            )
        )

    # ---- Personal abuse ----
    abuse_hits = _terms_present(lowered, _ABUSE_TERMS)
    if abuse_hits:
        flags.append(
            PolicyFlag(
                "personal_abuse",
                Severity.WARN,
                "Personal insults are removed regardless of who they target. Criticise the "
                "decision, not the person.",
                _excerpt(body, abuse_hits[0]),
            )
        )

    # ---- Spam heuristics ----
    links = _URL_RE.findall(body)
    if len(links) > 4:
        flags.append(
            PolicyFlag(
                "possible_spam",
                Severity.WARN,
                f"{len(links)} links in one post. Keep to the sources that matter.",
            )
        )
    letters = [c for c in body if c.isalpha()]
    if len(letters) > 40 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        flags.append(
            PolicyFlag(
                "shouting",
                Severity.INFO,
                "Mostly capital letters reads as shouting; it is not a policy breach but it "
                "will be edited.",
            )
        )

    if any(f.severity is Severity.WARN for f in flags):
        return Verdict(Decision.HOLD, flags)
    return Verdict(Decision.ALLOW, flags)


def scrub_identifiers(text: str) -> str:
    """Redact identifiers from text the platform has already accepted.

    Used on legacy or imported content that predates the gate, and as a second
    line under it -- `review()` refuses new submissions containing these, but a
    document ingested by the research importer never went through review.
    """
    text = _AADHAAR_RE.sub("[Aadhaar redacted]", text or "")
    text = _PAN_RE.sub("[PAN redacted]", text)
    text = _PHONE_RE.sub("[phone redacted]", text)
    return text


# Published verbatim at /api/legal/content-policy, and the Moderator queue links
# to it. §7: "Publish this policy publicly -- it's what lets you credibly claim
# non-partisan."
CONTENT_POLICY = {
    "version": "1.0",
    "effective": "2026-08-09",
    "principles": [
        {
            "title": "Non-partisan, always",
            "body": (
                "This platform exists to establish the Right to Recall, not to help or harm any "
                "party. Every party, in government or opposition, is held to exactly the same "
                "standard. Party affiliation is published as a neutral fact, the way a date of "
                "birth is. Campaigning for or against a party or candidate is not permitted "
                "anywhere on the platform."
            ),
        },
        {
            "title": "No communal, caste or religious framing",
            "body": (
                "Criticise what an office holder or an institution did. Never argue that a "
                "religion, caste, region or community is the problem. Reports and posts that "
                "target a community are removed; naming a community as the subject of "
                "discrimination is not the same thing and is permitted."
            ),
        },
        {
            "title": "Serious claims need public records",
            "body": (
                "Any allegation about a named person must cite a public official source: a court "
                "filing, an ECI affidavit, an RTI reply, a Gazette notification or an official "
                "order. Pending criminal cases are allegations, not convictions. Claims without a "
                "source are held and marked unverified, never published as fact."
            ),
        },
        {
            "title": "No personal data, no personal abuse",
            "body": (
                "Do not post Aadhaar or PAN numbers, phone numbers or email addresses -- yours or "
                "anyone else's. Do not insult people. Both are removed on sight."
            ),
        },
        {
            "title": "Moderation is human and appealable",
            "body": (
                "Automated checks only decide whether a submission waits for a person. Moderators "
                "make removal decisions, every removal is recorded in the audit log, and you can "
                "contest one through 'Suggest a correction' or the contact form."
            ),
        },
    ],
}
