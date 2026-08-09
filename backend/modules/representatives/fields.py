"""The registry of trackable facts about a representative.

Static Python for the same reason core/permissions.py is: a field key appears in
API paths and in the fact-check queue, and `requires_primary` is a legal control.
A field whose citation requirement could be edited from an admin screen is a
citation requirement that will be edited the first time a volunteer cannot find
the affidavit.

`requires_primary=True` means a news report is not enough. It is set for exactly
the fields where the platform's defence is "we are reporting what the public
record says" -- criminal cases, declared assets, attendance. For those, the
public record is the defence, and a secondary source is not a substitute for it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimField:
    key: str
    label: str
    category: str
    # "count" | "currency" | "percent" | "text" | "year"
    kind: str
    requires_primary: bool
    # Shown next to the figure. The most-misread numbers on a page like this are
    # the ones presented without saying what they mean.
    explanation: str
    # Whether a period (term, session, financial year) is expected. Attendance
    # without a session is meaningless; declared assets without a filing year is
    # worse than meaningless.
    period_required: bool = False


CLAIM_FIELDS: list[ClaimField] = [
    # ---- Criminal cases. The highest-risk surface on the platform. ----
    ClaimField(
        "criminal.pending_cases",
        "Pending criminal cases declared",
        "Criminal record",
        "count",
        True,
        "The number of criminal cases the candidate declared as pending in their own "
        "affidavit to the Election Commission. Pending cases are allegations that a court "
        "has not decided. They are not convictions and imply no guilt.",
        period_required=True,
    ),
    ClaimField(
        "criminal.serious_cases",
        "Of which are serious offences",
        "Criminal record",
        "count",
        True,
        "Cases carrying a maximum sentence of five years or more, or involving offences "
        "against the body, women, or the public exchequer, per the ADR classification. "
        "Still allegations, not findings.",
        period_required=True,
    ),
    ClaimField(
        "criminal.convictions",
        "Convictions recorded",
        "Criminal record",
        "count",
        True,
        "Convictions declared or recorded by a court. Unlike pending cases, a conviction is "
        "a judicial finding -- and under Section 8 of the Representation of the People Act "
        "certain convictions disqualify a legislator immediately.",
        period_required=True,
    ),
    # ---- Assets and liabilities ----
    ClaimField(
        "assets.total",
        "Total declared assets",
        "Assets and liabilities",
        "currency",
        True,
        "Self-declared value of movable and immovable assets in the affidavit filed with the "
        "nomination papers. Self-declared, valued as at the date of filing, and not audited "
        "by anyone -- including us.",
        period_required=True,
    ),
    ClaimField(
        "assets.movable",
        "Declared movable assets",
        "Assets and liabilities",
        "currency",
        True,
        "Cash, deposits, shares, vehicles, jewellery and similar, as declared.",
        period_required=True,
    ),
    ClaimField(
        "assets.immovable",
        "Declared immovable assets",
        "Assets and liabilities",
        "currency",
        True,
        "Land and buildings, as declared. Agricultural land is often declared at circle "
        "rates far below market value, so this figure is a floor rather than a valuation.",
        period_required=True,
    ),
    ClaimField(
        "liabilities.total",
        "Declared liabilities",
        "Assets and liabilities",
        "currency",
        True,
        "Loans and dues declared in the affidavit. Read alongside assets; neither number "
        "means much on its own.",
        period_required=True,
    ),
    # ---- Legislative work. The measures that speak to doing the job. ----
    ClaimField(
        "attendance.percent",
        "Attendance in the House",
        "Legislative work",
        "percent",
        True,
        "Sittings attended as a percentage of sittings held while the member held the seat. "
        "A high figure means presence, not participation; read it with debates and questions.",
        period_required=True,
    ),
    ClaimField(
        "performance.questions_asked",
        "Questions asked",
        "Legislative work",
        "count",
        True,
        "Starred and unstarred questions tabled. Compare against the House average for the "
        "same period rather than against another member in another House.",
        period_required=True,
    ),
    ClaimField(
        "performance.debates",
        "Debates participated in",
        "Legislative work",
        "count",
        True,
        "Debates the member spoke in. Ministers typically show low counts because they "
        "answer rather than participate, which is a limitation of the metric, not a finding "
        "about the minister.",
        period_required=True,
    ),
    ClaimField(
        "performance.private_member_bills",
        "Private member's Bills introduced",
        "Legislative work",
        "count",
        True,
        "Bills introduced by the member in their own right. Very few ever become law; the "
        "number indicates legislative initiative, not legislative success.",
        period_required=True,
    ),
    ClaimField(
        "funds.local_area_utilised_percent",
        "Constituency development funds utilised",
        "Funds",
        "percent",
        True,
        "Share of the member's local area development allocation actually spent, per the "
        "administering ministry's own dashboard. Low utilisation can reflect state-level "
        "administrative delays as well as the member's own initiative.",
        period_required=True,
    ),
    # ---- Background. Sourced, but low-risk. ----
    ClaimField(
        "background.education",
        "Highest education declared",
        "Background",
        "text",
        False,
        "As declared in the nomination affidavit. Educational qualification is not a "
        "constitutional requirement for office (see Article 84) and is published as "
        "context, not as a measure of fitness.",
    ),
    ClaimField(
        "background.profession",
        "Profession declared",
        "Background",
        "text",
        False,
        "As stated by the candidate in their nomination affidavit. Self-declared and "
        "unaudited, often broad ('agriculturist', 'social worker'), and it says nothing "
        "about current income or business interests -- those, where declared, appear "
        "under assets.",
    ),
    ClaimField(
        "background.age",
        "Age at last election",
        "Background",
        "count",
        False,
        "Age declared in the nomination affidavit at the time of that election, so it does "
        "not advance on this page. The constitutional minimum is 25 for the Lok Sabha and a "
        "State Assembly, and 30 for the Rajya Sabha (Articles 84 and 173).",
    ),
    ClaimField(
        "elections.margin_percent",
        "Winning margin",
        "Election result",
        "percent",
        True,
        "Margin over the runner-up as a percentage of valid votes polled, from the Election "
        "Commission's result.",
        period_required=True,
    ),
    ClaimField(
        "elections.vote_share_percent",
        "Vote share",
        "Election result",
        "percent",
        True,
        "Share of valid votes polled, from the Election Commission's result.",
        period_required=True,
    ),
    ClaimField(
        "elections.turnout_percent",
        "Constituency turnout",
        "Election result",
        "percent",
        True,
        "Turnout in the constituency at that election, from the Election Commission's result. "
        "A fact about the constituency rather than about the member.",
        period_required=True,
    ),
]

CLAIM_FIELDS_BY_KEY: dict[str, ClaimField] = {f.key: f for f in CLAIM_FIELDS}
CLAIM_FIELD_KEYS: frozenset[str] = frozenset(CLAIM_FIELDS_BY_KEY)

# Display order for the profile page, so the most consequential section is not
# buried and the criminal-record block always carries the disclaimer next to it.
CATEGORY_ORDER: tuple[str, ...] = (
    "Legislative work",
    "Election result",
    "Criminal record",
    "Assets and liabilities",
    "Funds",
    "Background",
)


def catalogue() -> list[dict]:
    """Served to the admin data-entry screen and the public field-explainer."""
    return [
        {
            "key": f.key,
            "label": f.label,
            "category": f.category,
            "kind": f.kind,
            "requiresPrimarySource": f.requires_primary,
            "explanation": f.explanation,
            "periodRequired": f.period_required,
        }
        for f in CLAIM_FIELDS
    ]
