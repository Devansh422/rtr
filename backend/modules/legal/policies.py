"""The published policies: privacy, content, disclaimer, cookies.

§1 makes DPDP Act 2023 compliance a Phase-0 requirement rather than a later
cleanup, and §11 records that the erasure endpoint shipped while "the notice next to
each submit button and the policy page it links to" did not. This module is that
missing half.

The policies live in Python rather than in the CMS deliberately. A privacy notice is
a legal commitment about what the software does; if it is editable content, it drifts
away from the code and the version a user consented to cannot be reconstructed.
Changing a policy here is a code review and a version bump, which is the correct
change process for a promise.

Every claim below is checked against what the code actually does. Where the honest
answer is unflattering -- the audit log is never deleted, uploads currently sit in
MongoDB, a machine translation may be unreviewed -- it says so.
"""

# Bump on any substantive change. `ConsentRecord.policy_version` stores this, so
# "what did this person agree to" always has an answer.
PRIVACY_POLICY_VERSION = "1.0"
PRIVACY_EFFECTIVE_DATE = "2026-08-09"

# Purposes a person can be asked to consent to. Each one names the data, the reason,
# and how long it is kept -- the three things the DPDP Act requires a notice to state
# in plain language.
CONSENT_PURPOSES: dict[str, dict] = {
    "membership": {
        "label": "Joining the movement",
        "data": ["Name", "Email address", "State", "City (optional)", "Mobile number (optional)"],
        "why": (
            "To record you as a supporter, issue your movement ID and access code, and let you sign in "
            "to your dashboard."
        ),
        "retention": "Until you ask us to delete it. You can do that yourself from your dashboard at any time.",
        "required": True,
    },
    "volunteering": {
        "label": "Volunteering",
        "data": ["Name", "Email address", "Phone number", "State", "Profession", "Skills", "City"],
        "why": (
            "To match you with volunteer tasks, contact you about work you have taken on, verify your "
            "hours and issue certificates."
        ),
        "retention": "Until you ask us to delete it, or two years after your last activity.",
        "required": False,
    },
    "newsletter": {
        "label": "Email updates",
        "data": ["Email address"],
        "why": "To send campaign updates and news about the Right to Recall movement.",
        "retention": "Until you unsubscribe.",
        "required": False,
    },
    "community": {
        "label": "Posting in the forum, on petitions and in reports",
        "data": ["Display name (a pseudonym by default)", "State", "What you write"],
        "why": (
            "To attribute your posts, count your petition signatures once each, and let moderators apply "
            "the content policy."
        ),
        "retention": (
            "Posts stay up while your account exists. If you delete your data, your posts are removed "
            "and replies to them are kept with your name detached."
        ),
        "required": False,
    },
    "events": {
        "label": "Registering for an event",
        "data": ["Name", "Email address", "Attendance record"],
        "why": "To issue your ticket, mark you present at the door, and issue a participation certificate.",
        "retention": "Attendance records are kept for three years so certificates stay verifiable.",
        "required": False,
    },
}


PRIVACY_POLICY: dict = {
    "version": PRIVACY_POLICY_VERSION,
    "effective": PRIVACY_EFFECTIVE_DATE,
    "statute": "Digital Personal Data Protection Act, 2023",
    "summary": (
        "We collect as little as we can, we tell you why before you give it, we never sell it, and you can "
        "delete it yourself in one click. This page explains exactly what that means, including the parts "
        "that are less convenient for us to admit."
    ),
    "sections": [
        {
            "heading": "Who we are",
            "body": (
                "The Right to Recall Movement is a non-partisan civic platform campaigning for a citizens' "
                "Right to Recall elected representatives in India. For the purposes of the Digital Personal "
                "Data Protection Act, 2023 we are the Data Fiduciary for the personal data described below. "
                "You can reach us through the contact form on this site."
            ),
        },
        {
            "heading": "What we collect, and why",
            "body": (
                "We ask for data only at the point where it is needed for something you have chosen to do. "
                "The list below is complete; there is no additional collection happening in the background."
            ),
            "purposes": True,
        },
        {
            "heading": "What we do NOT collect",
            "body": (
                "We do not ask for your Aadhaar, PAN, voter ID number, date of birth, caste, religion, "
                "income or political affiliation, and the platform actively refuses posts containing "
                "Aadhaar or PAN numbers. We do not use third-party advertising or analytics trackers, and "
                "there are no advertising cookies on this site. We do not buy data about you from anyone."
            ),
        },
        {
            "heading": "How your consent works",
            "body": (
                "Each form tells you what it collects and why, next to the button -- not in a link you are "
                "expected not to read. Consent is per purpose: agreeing to join the movement does not sign "
                "you up for volunteering. You can withdraw consent for any optional purpose at any time "
                "from your dashboard, and withdrawing it stops that use immediately. We record which "
                "version of this policy you agreed to and when."
            ),
        },
        {
            "heading": "Your rights, and how to use them",
            "body": (
                "Under the DPDP Act you have the right to know what we hold, to have it corrected, to have "
                "it erased, and to nominate someone to exercise these rights if you are unable to."
            ),
            "rights": [
                {
                    "right": "Access",
                    "how": "Your dashboard shows everything we hold about you. There is no request to file.",
                },
                {
                    "right": "Correction",
                    "how": "Edit your profile from the dashboard, or use the contact form for anything not editable there.",
                },
                {
                    "right": "Erasure",
                    "how": (
                        "'Delete my data' in your dashboard. It runs immediately and really deletes -- "
                        "your supporter record, volunteer record, contact messages, newsletter "
                        "subscription, forum posts, reports, petition signatures and certificates."
                    ),
                },
                {
                    "right": "Grievance redressal",
                    "how": (
                        "Use the contact form. If we do not resolve it, you may complain to the Data "
                        "Protection Board of India."
                    ),
                },
            ],
        },
        {
            "heading": "What survives deletion, and why",
            "body": (
                "Being straightforward about this is more useful than a reassuring sentence that is not "
                "quite true. Three things are not erased:\n\n"
                "1. THE AUDIT LOG. Every change to platform data is recorded in an append-only log: who "
                "changed what, when, and on what source. This is the transparency mechanism that lets "
                "anyone check the history of a claim about a named person, and it cannot be rewritten -- "
                "including by us. It records staff actions on the platform's own records. It does not "
                "contain your form submissions, and IP addresses in it are stored only as a one-way hash.\n\n"
                "2. REPLIES OTHER PEOPLE WROTE. If you delete your account, your posts go. Replies that "
                "other people wrote to them are their words, not yours, and they stay -- with your name "
                "detached from the thread.\n\n"
                "3. AGGREGATE COUNTS. A petition's signature total drops by one when you withdraw. "
                "Historical counts already published elsewhere (in a document handed to an office, for "
                "instance) cannot be retrieved."
            ),
        },
        {
            "heading": "Who else sees your data",
            "body": (
                "We use a small number of service providers, and no one else:\n\n"
                "- MongoDB Atlas and Neon (Postgres) store the data.\n"
                "- Vercel hosts the site and the API.\n"
                "- Brevo sends transactional email, and receives only your email address and the message.\n"
                "- Cloudflare Turnstile protects forms from bots where enabled, and receives no personal data.\n"
                "- Google Gemini powers the Constitution Assistant. Your question is stripped of phone "
                "numbers, email addresses and identity numbers before it is sent, because free-tier "
                "prompts may be retained by the provider. Do not put personal details in a question to "
                "the assistant.\n\n"
                "We do not sell, rent or trade personal data, and we do not share it with any political "
                "party. We disclose data only where the law requires it."
            ),
        },
        {
            "heading": "Where your data is stored",
            "body": (
                "On servers operated by the providers above, which may be outside India. The DPDP Act "
                "permits transfer outside India except to countries the Central Government restricts, and "
                "we will move providers if a restriction applies to one of ours."
            ),
        },
        {
            "heading": "Security, honestly stated",
            "body": (
                "Passwords and access codes are stored only as bcrypt hashes -- we cannot read them and "
                "cannot recover one for you. Traffic is encrypted in transit. Staff access is controlled by "
                "role-based permissions, and every staff action on platform records is logged. Files "
                "uploaded through the admin panel are currently stored inside the database rather than in "
                "dedicated object storage; that is a known limitation being moved to Cloudflare R2. No "
                "platform can promise it will never be breached; if we are, we will notify affected users "
                "and the Data Protection Board as the Act requires."
            ),
        },
        {
            "heading": "Children",
            "body": (
                "The platform is intended for people aged 18 and over, since it concerns voting and "
                "elections. We do not knowingly collect data about children, and we do not do behavioural "
                "tracking or targeted advertising to anyone, which is what the Act specifically prohibits "
                "in respect of children."
            ),
        },
        {
            "heading": "Cookies",
            "body": (
                "One session token, stored in your browser so you stay signed in, and one anonymous "
                "identifier used to count page views without identifying you. No advertising cookies, no "
                "third-party trackers, no cross-site profiling. Clearing your browser storage signs you out "
                "and resets the counter."
            ),
        },
        {
            "heading": "Changes to this policy",
            "body": (
                f"This is version {PRIVACY_POLICY_VERSION}, effective {PRIVACY_EFFECTIVE_DATE}. If we change "
                "it substantively we will bump the version and ask for consent again where the change "
                "affects what we do with data you have already given."
            ),
        },
    ],
}


# Shown wherever information about a named person appears. Kept in step with
# core/citations.STANDARD_DISCLAIMER, which is the version the API attaches to
# representative and promise responses.
SITE_DISCLAIMER: dict = {
    "version": "1.0",
    "short": (
        "Information about named individuals is compiled from public records. Pending criminal cases are "
        "allegations, not convictions."
    ),
    "full": [
        {
            "heading": "Sources",
            "body": (
                "Data about representatives comes from public records: Election Commission of India "
                "affidavits and results, court filings, PRS Legislative Research, parliamentary and "
                "assembly records, and Gazette notifications. Every figure on a profile carries a link to "
                "the record it came from, and the date of that record."
            ),
        },
        {
            "heading": "Charges are not convictions",
            "body": (
                "Where a profile records pending criminal cases, those are allegations that a court has not "
                "decided. Article 20 and the presumption of innocence apply fully. We do not investigate "
                "allegations, we do not assess their merit, and we take no position on the guilt of any "
                "individual."
            ),
        },
        {
            "heading": "Self-declared figures",
            "body": (
                "Assets and liabilities are as declared by the candidate in their own nomination affidavit, "
                "valued at the date of filing and audited by nobody. They are a record of what was "
                "declared, not a valuation."
            ),
        },
        {
            "heading": "Unverified data is marked",
            "body": (
                "Every claim carries a verification status. 'Unverified - pending citation review' means a "
                "researcher has entered it with a source but a fact-checker has not yet confirmed it "
                "against that source. Such data is visibly marked and is never presented as established "
                "fact."
            ),
        },
        {
            "heading": "Plain-language explanations are ours, not the law",
            "body": (
                "Explanations of constitutional articles are written by this platform to be readable. They "
                "are paraphrases. The original text, and the link to it, is on every article page, and "
                "where the two differ the original governs."
            ),
        },
        {
            "heading": "Non-partisanship",
            "body": (
                "This platform campaigns for a mechanism, not for or against any party. Party affiliation "
                "is published as a neutral fact. The same data fields, the same sourcing standard and the "
                "same content policy apply to every representative regardless of party, and campaigning for "
                "or against a party is not permitted anywhere on the platform."
            ),
        },
        {
            "heading": "Corrections",
            "body": (
                "Every page carrying information about a named person has a 'Suggest a correction' option. "
                "Corrections citing a public record are acted on, and the outcome is published with the "
                "reasoning either way."
            ),
        },
        {
            "heading": "Not legal advice",
            "body": (
                "Nothing on this platform is legal advice. The RTI and representation generators produce "
                "templates for you to review and edit. The PIL Resource Centre explains a procedure and "
                "does not draft petitions. For advice on your own matter, consult a lawyer -- free legal "
                "aid is a statutory entitlement for many people through NALSA."
            ),
        },
    ],
}
