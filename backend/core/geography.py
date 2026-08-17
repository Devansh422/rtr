"""States and union territories -- the fixed spine the platform is organised on.

Static Python, not CMS data: these codes appear in URLs (`/state/maharashtra`),
in RBAC scope columns, in the campaign pipeline and in every state-wise
aggregate. A set of identifiers that half the routing depends on should not be
editable from an admin screen.

`code` is the ISO 3166-2:IN subdivision code. Note that ISO still uses the
pre-rename codes for three states (CT Chhattisgarh, OR Odisha, UT Uttarakhand)
where common Indian usage is CG/OD/UK. ISO is used here because it is a stable
published standard; the human-facing identifier in URLs is `slug`, so this
choice is invisible to visitors.

SEAT COUNTS ARE SEED DEFAULTS, NOT VERIFIED CLAIMS. They are here so a state
page has structure before its data is collected. Per §7, no number sourced this
way may be presented to the public as fact until a Fact Checker has confirmed
it against the Election Commission and attached a source -- and the delimitation
exercise will change Lok Sabha and assembly figures. Treat them as scaffolding.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StateSeed:
    code: str
    name: str
    name_hi: str
    slug: str
    is_union_territory: bool = False
    has_legislature: bool = True
    lok_sabha_seats: int = 0
    rajya_sabha_seats: int = 0
    assembly_seats: int = 0
    is_pilot: bool = False


# Pilot states, built end-to-end before the pattern is templated nationwide
# (§10). Every other state renders a "help us build this page" state rather
# than an empty page implying the data is simply missing.
PILOT_STATE_CODES = {"DL", "MH"}


STATES: list[StateSeed] = [
    # ---- States ----
    StateSeed("AP", "Andhra Pradesh", "आंध्र प्रदेश", "andhra-pradesh", lok_sabha_seats=25, rajya_sabha_seats=11, assembly_seats=175),
    StateSeed("AR", "Arunachal Pradesh", "अरुणाचल प्रदेश", "arunachal-pradesh", lok_sabha_seats=2, rajya_sabha_seats=1, assembly_seats=60),
    StateSeed("AS", "Assam", "असम", "assam", lok_sabha_seats=14, rajya_sabha_seats=7, assembly_seats=126),
    StateSeed("BR", "Bihar", "बिहार", "bihar", lok_sabha_seats=40, rajya_sabha_seats=16, assembly_seats=243),
    StateSeed("CT", "Chhattisgarh", "छत्तीसगढ़", "chhattisgarh", lok_sabha_seats=11, rajya_sabha_seats=5, assembly_seats=90),
    StateSeed("GA", "Goa", "गोवा", "goa", lok_sabha_seats=2, rajya_sabha_seats=1, assembly_seats=40),
    StateSeed("GJ", "Gujarat", "गुजरात", "gujarat", lok_sabha_seats=26, rajya_sabha_seats=11, assembly_seats=182),
    StateSeed("HR", "Haryana", "हरियाणा", "haryana", lok_sabha_seats=10, rajya_sabha_seats=5, assembly_seats=90),
    StateSeed("HP", "Himachal Pradesh", "हिमाचल प्रदेश", "himachal-pradesh", lok_sabha_seats=4, rajya_sabha_seats=3, assembly_seats=68),
    StateSeed("JH", "Jharkhand", "झारखंड", "jharkhand", lok_sabha_seats=14, rajya_sabha_seats=6, assembly_seats=81),
    StateSeed("KA", "Karnataka", "कर्नाटक", "karnataka", lok_sabha_seats=28, rajya_sabha_seats=12, assembly_seats=224),
    StateSeed("KL", "Kerala", "केरल", "kerala", lok_sabha_seats=20, rajya_sabha_seats=9, assembly_seats=140),
    StateSeed("MP", "Madhya Pradesh", "मध्य प्रदेश", "madhya-pradesh", lok_sabha_seats=29, rajya_sabha_seats=11, assembly_seats=230),
    StateSeed("MH", "Maharashtra", "महाराष्ट्र", "maharashtra", lok_sabha_seats=48, rajya_sabha_seats=19, assembly_seats=288, is_pilot=True),
    StateSeed("MN", "Manipur", "मणिपुर", "manipur", lok_sabha_seats=2, rajya_sabha_seats=1, assembly_seats=60),
    StateSeed("ML", "Meghalaya", "मेघालय", "meghalaya", lok_sabha_seats=2, rajya_sabha_seats=1, assembly_seats=60),
    StateSeed("MZ", "Mizoram", "मिज़ोरम", "mizoram", lok_sabha_seats=1, rajya_sabha_seats=1, assembly_seats=40),
    StateSeed("NL", "Nagaland", "नागालैंड", "nagaland", lok_sabha_seats=1, rajya_sabha_seats=1, assembly_seats=60),
    StateSeed("OR", "Odisha", "ओडिशा", "odisha", lok_sabha_seats=21, rajya_sabha_seats=10, assembly_seats=147),
    StateSeed("PB", "Punjab", "पंजाब", "punjab", lok_sabha_seats=13, rajya_sabha_seats=7, assembly_seats=117),
    StateSeed("RJ", "Rajasthan", "राजस्थान", "rajasthan", lok_sabha_seats=25, rajya_sabha_seats=10, assembly_seats=200),
    StateSeed("SK", "Sikkim", "सिक्किम", "sikkim", lok_sabha_seats=1, rajya_sabha_seats=1, assembly_seats=32),
    StateSeed("TN", "Tamil Nadu", "तमिल नाडु", "tamil-nadu", lok_sabha_seats=39, rajya_sabha_seats=18, assembly_seats=234),
    StateSeed("TG", "Telangana", "तेलंगाना", "telangana", lok_sabha_seats=17, rajya_sabha_seats=7, assembly_seats=119),
    StateSeed("TR", "Tripura", "त्रिपुरा", "tripura", lok_sabha_seats=2, rajya_sabha_seats=1, assembly_seats=60),
    StateSeed("UP", "Uttar Pradesh", "उत्तर प्रदेश", "uttar-pradesh", lok_sabha_seats=80, rajya_sabha_seats=31, assembly_seats=403),
    StateSeed("UT", "Uttarakhand", "उत्तराखंड", "uttarakhand", lok_sabha_seats=5, rajya_sabha_seats=3, assembly_seats=70),
    StateSeed("WB", "West Bengal", "पश्चिम बंगाल", "west-bengal", lok_sabha_seats=42, rajya_sabha_seats=16, assembly_seats=294),
    # ---- Union territories ----
    # has_legislature matters editorially, not just structurally: a UT without an
    # assembly has no MLAs to profile and no house through which a state Right to
    # Recall bill could pass, so its page argues a different case entirely.
    StateSeed("AN", "Andaman and Nicobar Islands", "अंडमान और निकोबार द्वीपसमूह", "andaman-and-nicobar-islands", is_union_territory=True, has_legislature=False, lok_sabha_seats=1),
    StateSeed("CH", "Chandigarh", "चंडीगढ़", "chandigarh", is_union_territory=True, has_legislature=False, lok_sabha_seats=1),
    StateSeed("DH", "Dadra and Nagar Haveli and Daman and Diu", "दादरा और नगर हवेली तथा दमन और दीव", "dadra-and-nagar-haveli-and-daman-and-diu", is_union_territory=True, has_legislature=False, lok_sabha_seats=2),
    StateSeed("DL", "Delhi", "दिल्ली", "delhi", is_union_territory=True, has_legislature=True, lok_sabha_seats=7, rajya_sabha_seats=3, assembly_seats=70, is_pilot=True),
    StateSeed("JK", "Jammu and Kashmir", "जम्मू और कश्मीर", "jammu-and-kashmir", is_union_territory=True, has_legislature=True, lok_sabha_seats=5, rajya_sabha_seats=4, assembly_seats=90),
    StateSeed("LA", "Ladakh", "लद्दाख", "ladakh", is_union_territory=True, has_legislature=False, lok_sabha_seats=1),
    StateSeed("LD", "Lakshadweep", "लक्षद्वीप", "lakshadweep", is_union_territory=True, has_legislature=False, lok_sabha_seats=1),
    StateSeed("PY", "Puducherry", "पुडुचेरी", "puducherry", is_union_territory=True, has_legislature=True, lok_sabha_seats=1, rajya_sabha_seats=1, assembly_seats=30),
]

STATES_BY_CODE: dict[str, StateSeed] = {s.code: s for s in STATES}
STATES_BY_SLUG: dict[str, StateSeed] = {s.slug: s for s in STATES}
VALID_STATE_CODES: frozenset[str] = frozenset(STATES_BY_CODE)


# --------------------------------------------------------------------------
# Zones
# --------------------------------------------------------------------------
# Thirty-six rows is too many to read as one list, so anything that presents
# every state at once (the petition's state-wise sections, state-wise aggregates)
# groups them. The grouping is the STATUTORY one -- the five Zonal Councils
# constituted under Part III of the States Reorganisation Act 1956, plus the
# North Eastern Council constituted under the North Eastern Council Act 1971 --
# and not a set of regions invented here.
#
# That choice is a §1 matter, not a cosmetic one. Any home-made grouping of
# Indian states ("the Hindi belt", "the south") carries an argument inside it,
# and this platform cannot afford to make one incidentally while laying out a
# page. A grouping fixed by statute carries none: it is a citable fact about how
# the Union already organises inter-state consultation.
#
# Membership below follows the councils' own membership, which is why Andaman
# and Nicobar Islands and Lakshadweep sit in the Southern zone and Sikkim in the
# North Eastern one -- geography would put them elsewhere, the statute does not.


@dataclass(frozen=True)
class Zone:
    key: str
    label: str
    label_hi: str
    codes: tuple[str, ...]


ZONE_SOURCE_URL = "https://www.mha.gov.in/en/divisionofmha/inter-state-council-division"

ZONES: list[Zone] = [
    Zone("northern", "Northern", "उत्तरी", ("CH", "DL", "HR", "HP", "JK", "LA", "PB", "RJ")),
    Zone("central", "Central", "मध्य", ("CT", "MP", "UP", "UT")),
    Zone("eastern", "Eastern", "पूर्वी", ("BR", "JH", "OR", "WB")),
    Zone("western", "Western", "पश्चिमी", ("DH", "GA", "GJ", "MH")),
    Zone("southern", "Southern", "दक्षिणी", ("AN", "AP", "KA", "KL", "LD", "PY", "TG", "TN")),
    Zone("north_eastern", "North Eastern", "पूर्वोत्तर", ("AR", "AS", "MN", "ML", "MZ", "NL", "SK", "TR")),
]

ZONE_BY_CODE: dict[str, str] = {code: zone.key for zone in ZONES for code in zone.codes}
ZONES_BY_KEY: dict[str, Zone] = {z.key: z for z in ZONES}


def zone_of(code: str) -> str:
    """The zonal council a state or UT belongs to. Empty string if unknown."""
    return ZONE_BY_CODE.get((code or "").upper(), "")


# --------------------------------------------------------------------------
# Campaign pipeline
# --------------------------------------------------------------------------
# The eight stages a state moves through, in order. Stored as an integer index
# so "further along than" is a comparison rather than a lookup table, and so
# inserting a stage later does not require rewriting stored values.
CAMPAIGN_STAGES: list[tuple[str, str]] = [
    ("no_demand", "No Demand Yet"),
    ("awareness", "Awareness Stage"),
    ("petition_submitted", "Petition Submitted"),
    ("bill_introduced", "Bill Introduced"),
    ("committee_stage", "Committee Stage"),
    ("passed_assembly", "Passed Assembly"),
    ("passed_parliament", "Passed Parliament"),
    ("act_enforced", "Act Enforced"),
]

CAMPAIGN_STAGE_KEYS: list[str] = [k for k, _ in CAMPAIGN_STAGES]
CAMPAIGN_STAGE_LABELS: dict[str, str] = dict(CAMPAIGN_STAGES)


def stage_index(key: str) -> int:
    try:
        return CAMPAIGN_STAGE_KEYS.index(key)
    except ValueError:
        return 0
