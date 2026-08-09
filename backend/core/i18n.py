"""Locales, and the rule that a machine translation is never published as fact.

§8 of IMPLEMENTATION_PLAN.md sequences the languages rather than attempting all
22 at once, and the sequencing is encoded here (`Tier`) so that "is Tamil live?"
has one answer the API and the frontend both read.

The important rule is the second one. Constitutional text and claims about named
people are legal content; a LibreTranslate draft of "cognizable offence" is not
a translation, it is a liability. So a localised field carries the provenance of
its text -- original, human-reviewed, or machine draft -- and the public
serialiser refuses to serve a machine draft of a legal field without saying so.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class Tier(int, Enum):
    """Which phase a language ships in. Lower ships sooner."""

    LIVE = 1  # Phase 0-1: authored bilingually from the start
    PLANNED = 2  # Phase 3-4: largest speaker populations after Hindi
    FUTURE = 3  # Phase 5+: remaining scheduled languages, volunteer-led


@dataclass(frozen=True)
class Locale:
    code: str
    english_name: str
    native_name: str
    tier: Tier
    # ISO 15924 script, used by the frontend to pick a font stack -- Devanagari,
    # Tamil and Bengali need different fallbacks and guessing from the language
    # code is how you get boxes instead of letters.
    script: str


LOCALES: list[Locale] = [
    Locale("en", "English", "English", Tier.LIVE, "Latn"),
    Locale("hi", "Hindi", "हिन्दी", Tier.LIVE, "Deva"),
    Locale("ta", "Tamil", "தமிழ்", Tier.PLANNED, "Taml"),
    Locale("te", "Telugu", "తెలుగు", Tier.PLANNED, "Telu"),
    Locale("kn", "Kannada", "ಕನ್ನಡ", Tier.PLANNED, "Knda"),
    Locale("ml", "Malayalam", "മലയാളം", Tier.PLANNED, "Mlym"),
    Locale("mr", "Marathi", "मराठी", Tier.PLANNED, "Deva"),
    Locale("bn", "Bengali", "বাংলা", Tier.PLANNED, "Beng"),
    Locale("gu", "Gujarati", "ગુજરાતી", Tier.FUTURE, "Gujr"),
    Locale("pa", "Punjabi", "ਪੰਜਾਬੀ", Tier.FUTURE, "Guru"),
    Locale("or", "Odia", "ଓଡ଼ିଆ", Tier.FUTURE, "Orya"),
    Locale("as", "Assamese", "অসমীয়া", Tier.FUTURE, "Beng"),
    Locale("ur", "Urdu", "اردو", Tier.FUTURE, "Arab"),
]

LOCALES_BY_CODE: dict[str, Locale] = {loc.code: loc for loc in LOCALES}
DEFAULT_LOCALE = "en"
# Content is authored in both of these; anything else falls back until a
# volunteer translator has reviewed it.
LIVE_LOCALES: frozenset[str] = frozenset(loc.code for loc in LOCALES if loc.tier is Tier.LIVE)
RTL_LOCALES: frozenset[str] = frozenset({"ur"})


def normalise(locale: Optional[str]) -> str:
    """Accept `hi`, `hi-IN`, `HI` and unknown values; always return a real code."""
    if not locale:
        return DEFAULT_LOCALE
    code = locale.strip().lower().replace("_", "-").split("-")[0]
    return code if code in LOCALES_BY_CODE else DEFAULT_LOCALE


class Provenance(str, Enum):
    """Where a piece of localised text came from."""

    ORIGINAL = "original"  # authored in this language
    HUMAN = "human_reviewed"  # translated and reviewed by a volunteer
    MACHINE = "machine_draft"  # LibreTranslate output, NOT reviewed
    MISSING = "missing"  # no text in this language; caller fell back


# Fields whose meaning is legal or constitutional. A machine draft of one of
# these is never served as the primary text -- §8: "never publish raw machine
# translation as legal/constitutional content".
LEGAL_FIELDS = frozenset(
    {"original_text", "plain_text", "case_law", "disclaimer", "policy", "promise_text"}
)


def field_for(
    row: Any,
    base: str,
    locale: str,
    *,
    is_legal: bool = False,
) -> dict:
    """Read `base` in `locale` from an ORM row using the `<base>_<locale>` convention.

    Returns an envelope rather than a string, for the same reason
    citations.claim_envelope does: a frontend that receives a bare string cannot
    tell it is looking at an unreviewed machine draft, so it will render it as if
    it were the real text.
    """
    locale = normalise(locale)
    localised = getattr(row, f"{base}_{locale}", None) if locale != DEFAULT_LOCALE else None
    fallback = getattr(row, base, None) or getattr(row, f"{base}_en", None) or ""

    status_map = getattr(row, "translation_status", None) or {}
    provenance = status_map.get(locale, Provenance.MACHINE.value if localised else Provenance.MISSING.value)
    if locale == DEFAULT_LOCALE:
        provenance = Provenance.ORIGINAL.value

    text = localised or ""
    used_fallback = not text
    if used_fallback:
        text = fallback
    elif is_legal and provenance == Provenance.MACHINE.value:
        # Show the reviewed English alongside rather than instead: hiding the
        # draft entirely denies a Hindi reader any help, while presenting it as
        # the text would misrepresent constitutional language.
        return {
            "text": fallback,
            "locale": DEFAULT_LOCALE,
            "provenance": Provenance.MACHINE.value,
            "unreviewedDraft": text,
            "notice": (
                "A machine-assisted draft in this language exists but has not been reviewed by a "
                "volunteer yet. The English text is authoritative until it has been."
            ),
        }

    return {
        "text": text,
        "locale": DEFAULT_LOCALE if used_fallback else locale,
        "provenance": Provenance.MISSING.value if used_fallback else provenance,
        "notice": (
            "Not yet available in this language. Showing English."
            if used_fallback and locale != DEFAULT_LOCALE
            else None
        ),
    }


def locale_catalogue() -> list[dict]:
    """Served at `/api/locales` so the language switcher is built from one list."""
    return [
        {
            "code": loc.code,
            "englishName": loc.english_name,
            "nativeName": loc.native_name,
            "script": loc.script,
            "direction": "rtl" if loc.code in RTL_LOCALES else "ltr",
            "tier": loc.tier.value,
            # The switcher shows planned languages greyed out rather than hiding
            # them: "Tamil is coming, help translate it" recruits translators,
            # an absent entry does not.
            "available": loc.code in LIVE_LOCALES,
        }
        for loc in LOCALES
    ]
