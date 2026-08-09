"""The seeded template set, plus the RTI and PIL guidance.

These ship as `legal_approved` because they are drafted from the statute and use
its own wording. Any EDIT to a seeded template drops it back to `draft` (see the
router), so a well-meaning change cannot quietly put unreviewed legal text in front
of the public.

Everything here is procedural: which form, which section, which office, how long to
wait. None of it is advice about the merits of anyone's case, which is the line the
PIL guidance below states explicitly and refuses to cross.
"""

# --------------------------------------------------------------------------
# Shared field definitions
# --------------------------------------------------------------------------
_APPLICANT_FIELDS = [
    {"name": "applicant_name", "label": "Your full name", "type": "text", "required": True, "maxLength": 120},
    {
        "name": "applicant_address",
        "label": "Your full postal address",
        "type": "textarea",
        "required": True,
        "maxLength": 400,
        "help": "The reply is posted to this address, so include the PIN code.",
    },
    {
        "name": "applicant_contact",
        "label": "Phone or email (optional)",
        "type": "text",
        "required": False,
        "maxLength": 120,
        "help": "Not required by law. Give it only if you want the office to be able to call you.",
    },
    {"name": "place", "label": "Place", "type": "text", "required": True, "maxLength": 80},
    {"name": "letter_date", "label": "Date", "type": "date", "required": True},
]

_CITIZENSHIP_FIELD = {
    "name": "is_bpl",
    "label": "Do you hold a Below Poverty Line (BPL) card?",
    "type": "select",
    "required": True,
    "options": ["No", "Yes"],
    "help": "BPL cardholders pay no fee under Section 7(5) of the RTI Act. Attach a copy of the card.",
}


TEMPLATES: list[dict] = [
    # ----------------------------------------------------------------------
    {
        "key": "rti-general",
        "kind": "rti",
        "title": "RTI application (general)",
        "title_hi": "आरटीआई आवेदन (सामान्य)",
        "description": (
            "A request for information from any public authority under Section 6(1) of the Right to "
            "Information Act, 2005. Use this for records, file notings, expenditure details, copies of "
            "orders, or the status of a decision."
        ),
        "legal_basis": (
            "Section 6(1), Right to Information Act, 2005. Under Section 6(2) you do not have to give "
            "any reason for wanting the information, and you cannot be asked for one."
        ),
        "filing_notes": (
            "FEE: Rs 10 for a central public authority, by Indian Postal Order, demand draft, banker's "
            "cheque or court fee stamp payable to the Accounts Officer. State authorities set their own "
            "fee -- check your State's RTI Rules. BPL cardholders pay nothing (Section 7(5)).\n\n"
            "WHERE: The Public Information Officer of the authority that HOLDS the record. If you send it "
            "to the wrong office, Section 6(3) requires them to transfer it within five days.\n\n"
            "TIME: 30 days for a reply. 48 hours if the information concerns the life or liberty of a "
            "person. 35 days if you filed through an Assistant PIO. If they miss the deadline, Section "
            "7(6) entitles you to the information free of any further fee.\n\n"
            "KEEP: A photocopy of the application and the postal receipt. You need the date of despatch "
            "to calculate your appeal deadline."
        ),
        "fields": [
            {
                "name": "pio_office",
                "label": "Public Information Officer, office name and address",
                "type": "textarea",
                "required": True,
                "maxLength": 400,
                "help": "Name the office that holds the record, not the department's head office.",
            },
            {
                "name": "subject",
                "label": "Subject of your request (one line)",
                "type": "text",
                "required": True,
                "maxLength": 200,
            },
            {
                "name": "period",
                "label": "Period the information relates to",
                "type": "text",
                "required": False,
                "maxLength": 120,
                "help": "For example: 1 April 2024 to 31 March 2025. A narrower period gets a faster reply.",
            },
            {
                "name": "questions",
                "label": "The information you want, as numbered points",
                "type": "textarea",
                "required": True,
                "maxLength": 3000,
                "help": (
                    "Ask for RECORDS, not opinions -- the Act covers information held in material form. "
                    "'Provide a copy of the sanction order' works; 'Why was this not done?' does not. "
                    "Put each item on its own line."
                ),
            },
            _CITIZENSHIP_FIELD,
            {
                "name": "fee_mode",
                "label": "How are you paying the fee?",
                "type": "select",
                "required": True,
                "options": [
                    "Indian Postal Order",
                    "Demand draft",
                    "Banker's cheque",
                    "Court fee stamp",
                    "Cash (paid at the office counter)",
                    "Not applicable - BPL cardholder",
                ],
            },
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "To,\n{{pio_office}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {
                "kind": "para",
                "text": "Subject: Request for information under the Right to Information Act, 2005 - {{subject}}",
                "bold": True,
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Respected Sir/Madam,"},
            {
                "kind": "para",
                "text": (
                    "Under Section 6(1) of the Right to Information Act, 2005, I request the following "
                    "information relating to {{subject}}{{period_clause}}:"
                ),
            },
            {"kind": "para", "text": "{{questions}}"},
            {
                "kind": "para",
                "text": (
                    "I would be grateful if the information is provided in the form of certified copies of "
                    "the relevant records. If any part of this request is held by another public authority, "
                    "I request that it be transferred under Section 6(3) of the Act within five days and "
                    "that I be informed of the transfer."
                ),
            },
            {
                "kind": "para",
                "text": (
                    "If you consider any part of the information exempt, I request that you specify the "
                    "clause of Section 8 or 9 relied upon, and that the remainder be provided under "
                    "Section 10 of the Act."
                ),
            },
            {"kind": "para", "text": "{{fee_clause}}"},
            {
                "kind": "para",
                "text": (
                    "Please also inform me of the name and designation of the First Appellate Authority "
                    "for your office."
                ),
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Yours faithfully,"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "{{applicant_address}}"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Enclosure: Fee receipt / Indian Postal Order{{bpl_enclosure}}", "italic": True},
        ],
    },
    # ----------------------------------------------------------------------
    {
        "key": "rti-first-appeal",
        "kind": "rti_first_appeal",
        "title": "RTI first appeal",
        "title_hi": "आरटीआई प्रथम अपील",
        "description": (
            "Use this when the Public Information Officer has refused your request, given an incomplete or "
            "misleading reply, or said nothing at all within the time limit."
        ),
        "legal_basis": (
            "Section 19(1), Right to Information Act, 2005. The appeal must be filed within 30 days of the "
            "PIO's decision, or within 30 days of the date the reply was due if no reply came. A delay can "
            "be condoned if you show sufficient cause."
        ),
        "filing_notes": (
            "FEE: None. A first appeal carries no fee under the Act.\n\n"
            "WHERE: The First Appellate Authority of the SAME public authority -- an officer senior to the "
            "PIO. If the PIO did not tell you who that is, address it to 'The First Appellate Authority' at "
            "the same office.\n\n"
            "TIME: The FAA must decide within 30 days, extendable to 45 days with reasons recorded.\n\n"
            "ATTACH: A copy of your original application, proof of despatch, and the PIO's reply if you got one."
        ),
        "fields": [
            {
                "name": "faa_office",
                "label": "First Appellate Authority, office name and address",
                "type": "textarea",
                "required": True,
                "maxLength": 400,
            },
            {"name": "rti_date", "label": "Date of your original RTI application", "type": "date", "required": True},
            {
                "name": "rti_reference",
                "label": "PIO's reference or diary number (if you have one)",
                "type": "text",
                "required": False,
                "maxLength": 120,
            },
            {
                "name": "ground",
                "label": "What went wrong",
                "type": "select",
                "required": True,
                "options": [
                    "No reply was received within the time limit",
                    "The reply was incomplete",
                    "The request was refused",
                    "The information given was misleading or false",
                    "An excessive fee was demanded",
                ],
            },
            {
                "name": "grounds_detail",
                "label": "Explain, point by point, what is missing or wrong",
                "type": "textarea",
                "required": True,
                "maxLength": 3000,
                "help": "Match your points to the numbered items in the original application.",
            },
            {
                "name": "relief",
                "label": "What you want the Appellate Authority to order",
                "type": "textarea",
                "required": True,
                "maxLength": 800,
            },
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "To,\n{{faa_office}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {
                "kind": "para",
                "text": "Subject: First appeal under Section 19(1) of the Right to Information Act, 2005",
                "bold": True,
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Respected Sir/Madam,"},
            {
                "kind": "para",
                "text": (
                    "I filed an application under the Right to Information Act, 2005 on {{rti_date}}"
                    "{{reference_clause}}. I am aggrieved for the following reason: {{ground}}."
                ),
            },
            {"kind": "para", "text": "The specific deficiencies are as follows:"},
            {"kind": "para", "text": "{{grounds_detail}}"},
            {
                "kind": "para",
                "text": (
                    "This appeal is filed within the period allowed by Section 19(1) of the Act. I request "
                    "that you be pleased to:"
                ),
            },
            {"kind": "para", "text": "{{relief}}"},
            {
                "kind": "para",
                "text": (
                    "I further submit that, the statutory period having elapsed, the information ought to be "
                    "furnished free of further fee under Section 7(6) of the Act."
                ),
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Yours faithfully,"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "{{applicant_address}}"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
            {"kind": "spacer"},
            {
                "kind": "para",
                "text": (
                    "Enclosures: 1. Copy of the RTI application dated {{rti_date}}  "
                    "2. Proof of despatch  3. Copy of the PIO's reply, if received"
                ),
                "italic": True,
            },
        ],
    },
    # ----------------------------------------------------------------------
    {
        "key": "rti-second-appeal",
        "kind": "rti_second_appeal",
        "title": "RTI second appeal to the Information Commission",
        "title_hi": "सूचना आयोग को द्वितीय अपील",
        "description": (
            "Use this when the First Appellate Authority has decided against you, or has not decided within "
            "the time allowed."
        ),
        "legal_basis": (
            "Section 19(3), Right to Information Act, 2005. File within 90 days of the FAA's decision, or of "
            "the date it was due. Goes to the Central Information Commission for central authorities and to "
            "the State Information Commission for state authorities."
        ),
        "filing_notes": (
            "FEE: None.\n\nWHERE: The Central Information Commission (cic.gov.in) for central public "
            "authorities; your State Information Commission for state ones. Most Commissions accept online "
            "filing.\n\nATTACH: The original application, the first appeal, both proofs of despatch, and any "
            "replies received. A second appeal without these is usually returned."
        ),
        "fields": [
            {
                "name": "commission",
                "label": "Information Commission you are appealing to",
                "type": "text",
                "required": True,
                "maxLength": 200,
                "help": "For example: Central Information Commission, New Delhi.",
            },
            {"name": "public_authority", "label": "Public authority concerned", "type": "text", "required": True, "maxLength": 240},
            {"name": "rti_date", "label": "Date of the original RTI application", "type": "date", "required": True},
            {"name": "appeal_date", "label": "Date of your first appeal", "type": "date", "required": True},
            {
                "name": "faa_outcome",
                "label": "What the First Appellate Authority did",
                "type": "select",
                "required": True,
                "options": [
                    "Did not decide within the time allowed",
                    "Rejected the appeal",
                    "Ordered disclosure, which the PIO has not complied with",
                    "Decided only part of the appeal",
                ],
            },
            {"name": "grounds_detail", "label": "Grounds of appeal", "type": "textarea", "required": True, "maxLength": 4000},
            {"name": "relief", "label": "Relief sought", "type": "textarea", "required": True, "maxLength": 1000},
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "Before the {{commission}}"},
            {"kind": "spacer"},
            {
                "kind": "para",
                "text": "Second appeal under Section 19(3) of the Right to Information Act, 2005",
                "bold": True,
                "align": "center",
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Appellant: {{applicant_name}}, {{applicant_address}}"},
            {"kind": "para", "text": "Respondent: Public Information Officer, {{public_authority}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Respectfully submitted:"},
            {
                "kind": "para",
                "text": (
                    "1. The appellant filed an application under the Right to Information Act, 2005 with the "
                    "Public Information Officer, {{public_authority}}, on {{rti_date}}."
                ),
            },
            {
                "kind": "para",
                "text": "2. A first appeal under Section 19(1) was filed on {{appeal_date}}. {{faa_outcome}}.",
            },
            {"kind": "para", "text": "3. The appellant is aggrieved on the following grounds:"},
            {"kind": "para", "text": "{{grounds_detail}}"},
            {"kind": "para", "text": "4. The appellant accordingly prays that this Commission be pleased to:"},
            {"kind": "para", "text": "{{relief}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "Appellant"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
        ],
    },
    # ----------------------------------------------------------------------
    {
        "key": "representation-to-representative",
        "kind": "representation",
        "title": "Representation to your MP or MLA",
        "title_hi": "अपने सांसद या विधायक को अभ्यावेदन",
        "description": (
            "A formal letter to your elected representative asking them to act on an issue, take it up in the "
            "House, or state their position. Every representative maintains an office for exactly this, and a "
            "written representation on the record is treated differently from a phone call."
        ),
        "legal_basis": (
            "Article 350 of the Constitution entitles every person to submit a representation for the redress "
            "of a grievance to any officer or authority of the Union or a State in any language used in the "
            "Union or that State. There is no prescribed form and no fee."
        ),
        "filing_notes": (
            "SEND IT TWICE: to the constituency office and to the House address (Lok Sabha / Rajya Sabha "
            "Secretariat, or the State Assembly). Keep the postal receipt.\n\n"
            "FOLLOW UP: If there is no response in three to four weeks, an RTI to the concerned department "
            "asking what action was taken on your representation, quoting its date, is the standard next step "
            "-- and it creates a record.\n\n"
            "BE SPECIFIC: One issue, a clear ask, and a date. A letter listing nine grievances gets filed; a "
            "letter asking one question gets answered."
        ),
        "fields": [
            {
                "name": "representative_name",
                "label": "Name and designation of the representative",
                "type": "text",
                "required": True,
                "maxLength": 200,
                "help": "For example: Shri/Smt. A. B., Member of Parliament (Lok Sabha), <constituency>.",
            },
            {"name": "office_address", "label": "Their office address", "type": "textarea", "required": True, "maxLength": 400},
            {"name": "constituency", "label": "Your constituency", "type": "text", "required": True, "maxLength": 160},
            {"name": "subject", "label": "Subject (one line)", "type": "text", "required": True, "maxLength": 200},
            {
                "name": "issue",
                "label": "The issue, in your own words",
                "type": "textarea",
                "required": True,
                "maxLength": 3000,
                "help": "Say what is happening, where, since when, and who it affects. Facts, not adjectives.",
            },
            {
                "name": "steps_taken",
                "label": "What you have already tried (optional)",
                "type": "textarea",
                "required": False,
                "maxLength": 1000,
                "help": "Complaint numbers, dates, offices visited. This is what makes the letter hard to deflect.",
            },
            {
                "name": "ask",
                "label": "What exactly you are asking them to do",
                "type": "textarea",
                "required": True,
                "maxLength": 800,
                "help": "One clear ask. 'Raise a question in the House on X' or 'Write to the District Collector'.",
            },
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "To,\n{{representative_name}}\n{{office_address}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Subject: {{subject}}", "bold": True},
            {"kind": "spacer"},
            {"kind": "para", "text": "Respected Sir/Madam,"},
            {
                "kind": "para",
                "text": (
                    "I am a resident and registered voter of {{constituency}}, which you represent. I am "
                    "writing to bring the following matter to your attention and to request your intervention."
                ),
            },
            {"kind": "para", "text": "{{issue}}"},
            {"kind": "para", "text": "{{steps_clause}}"},
            {"kind": "para", "text": "I therefore request that you be pleased to:"},
            {"kind": "para", "text": "{{ask}}"},
            {
                "kind": "para",
                "text": (
                    "This representation is submitted in exercise of the right recognised by Article 350 of "
                    "the Constitution of India. I would be grateful for an acknowledgement and for information "
                    "on the action taken."
                ),
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Yours sincerely,"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "{{applicant_address}}"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
        ],
    },
    # ----------------------------------------------------------------------
    {
        "key": "recall-demand",
        "kind": "recall_demand",
        "title": "Right to Recall demand letter",
        "title_hi": "राइट टू रिकॉल मांग पत्र",
        "description": (
            "A letter to your MP or MLA asking them to state their position on legislating a Right to Recall, "
            "and to support it. Non-partisan by construction: the same letter goes to every representative "
            "regardless of party, and it asks for a position rather than assuming one."
        ),
        "legal_basis": (
            "Article 350 (right to submit a representation). The substantive ask rests on Article 328, which "
            "lets a State legislature make law on elections to its own House, and Article 327, under which "
            "Parliament may do so for both Houses and for State legislatures."
        ),
        "filing_notes": (
            "Send it to the constituency office and the House address. Publish the reply -- or the absence of "
            "one -- on this platform, so the record is public either way. A representative who supports the "
            "measure deserves that on the record just as much as one who does not."
        ),
        "fields": [
            {"name": "representative_name", "label": "Name and designation of the representative", "type": "text", "required": True, "maxLength": 200},
            {"name": "office_address", "label": "Their office address", "type": "textarea", "required": True, "maxLength": 400},
            {"name": "constituency", "label": "Your constituency", "type": "text", "required": True, "maxLength": 160},
            {
                "name": "house",
                "label": "Which House do they sit in?",
                "type": "select",
                "required": True,
                "options": ["Lok Sabha", "State Legislative Assembly", "Rajya Sabha", "State Legislative Council"],
            },
            {
                "name": "personal_reason",
                "label": "Why this matters to you (optional but effective)",
                "type": "textarea",
                "required": False,
                "maxLength": 1200,
                "help": "A specific local experience does more than a general argument.",
            },
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "To,\n{{representative_name}}\n{{office_address}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {
                "kind": "para",
                "text": "Subject: Request to state your position on legislating a citizens' Right to Recall",
                "bold": True,
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Respected Sir/Madam,"},
            {
                "kind": "para",
                "text": (
                    "I am a registered voter of {{constituency}}. I am writing about a gap in our electoral "
                    "law that I believe you are in a position to help close."
                ),
            },
            {
                "kind": "para",
                "text": (
                    "Article 326 of the Constitution rests our democracy on the adult citizen's vote. Once "
                    "that vote is cast, however, Articles 83 and 172 fix a five-year term, and the "
                    "Constitution provides no means by which the voters who elected a representative may end "
                    "that term. Removal is available for the President under Article 61 and for judges under "
                    "Article 124; the electorate has no equivalent power over its own representatives. At the "
                    "same time, the Constitution already accepts direct citizen decision-making at the "
                    "village level under Article 243A, and several States have legislated the recall of "
                    "panchayat and municipal representatives."
                ),
            },
            {"kind": "para", "text": "{{reason_clause}}"},
            {
                "kind": "para",
                "text": (
                    "Under Article 328, a State legislature may legislate on elections to its own House, and "
                    "under Article 327 Parliament may do so for Parliament and for State legislatures. A "
                    "Right to Recall with proper safeguards -- a high signature threshold, verification by "
                    "the Election Commission, a defined ground, and a fair hearing for the representative -- "
                    "is therefore achievable without waiting for a constitutional amendment."
                ),
            },
            {"kind": "para", "text": "I request that you be pleased to:"},
            {
                "kind": "bullet",
                "text": "State publicly whether you support the enactment of a citizens' Right to Recall;",
            },
            {
                "kind": "bullet",
                "text": (
                    "Raise the question in the {{house}}, by way of a question, a private member's Bill or a "
                    "submission to the relevant committee; and"
                ),
            },
            {
                "kind": "bullet",
                "text": "Inform me of the action you take, so that it can be recorded publicly.",
            },
            {
                "kind": "para",
                "text": (
                    "This request is not made on behalf of any political party and is being sent to "
                    "representatives of every party alike. I would be grateful for your reply either way."
                ),
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Yours sincerely,"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "{{applicant_address}}"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
        ],
    },
    # ----------------------------------------------------------------------
    {
        "key": "department-letter",
        "kind": "department_letter",
        "title": "Letter to a government department",
        "title_hi": "सरकारी विभाग को पत्र",
        "description": (
            "A formal complaint or request to a department, municipality or public office, structured so that "
            "it creates a record you can follow up with an RTI."
        ),
        "legal_basis": "Article 350 of the Constitution. No prescribed form and no fee.",
        "filing_notes": (
            "Ask for an acknowledgement with a diary number, and keep it. The diary number is what makes a "
            "later RTI -- 'what action was taken on complaint no. X dated Y' -- impossible to ignore."
        ),
        "fields": [
            {"name": "office", "label": "Office name and address", "type": "textarea", "required": True, "maxLength": 400},
            {"name": "officer", "label": "Officer's designation (if known)", "type": "text", "required": False, "maxLength": 160},
            {"name": "subject", "label": "Subject (one line)", "type": "text", "required": True, "maxLength": 200},
            {"name": "issue", "label": "What the problem is", "type": "textarea", "required": True, "maxLength": 3000},
            {"name": "location", "label": "Exact location affected", "type": "text", "required": True, "maxLength": 240},
            {"name": "since", "label": "Since when", "type": "text", "required": False, "maxLength": 120},
            {"name": "steps_taken", "label": "Earlier complaints, with numbers and dates", "type": "textarea", "required": False, "maxLength": 1000},
            {"name": "ask", "label": "What you want done", "type": "textarea", "required": True, "maxLength": 800},
            *_APPLICANT_FIELDS,
        ],
        "body": [
            {"kind": "para", "text": "To,\n{{officer_line}}{{office}}"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Date: {{letter_date}}", "align": "right"},
            {"kind": "spacer"},
            {"kind": "para", "text": "Subject: {{subject}}", "bold": True},
            {"kind": "spacer"},
            {"kind": "para", "text": "Respected Sir/Madam,"},
            {"kind": "para", "text": "I wish to bring the following matter to your notice."},
            {"kind": "para", "text": "Location: {{location}}{{since_clause}}"},
            {"kind": "para", "text": "{{issue}}"},
            {"kind": "para", "text": "{{steps_clause}}"},
            {"kind": "para", "text": "I request that you be pleased to:"},
            {"kind": "para", "text": "{{ask}}"},
            {
                "kind": "para",
                "text": (
                    "I request an acknowledgement of this letter with a diary number, and information on the "
                    "action taken and the officer responsible."
                ),
            },
            {"kind": "spacer"},
            {"kind": "para", "text": "Yours faithfully,"},
            {"kind": "spacer"},
            {"kind": "para", "text": "{{applicant_name}}"},
            {"kind": "para", "text": "{{applicant_address}}"},
            {"kind": "para", "text": "{{contact_clause}}"},
            {"kind": "para", "text": "Place: {{place}}"},
        ],
    },
]


# --------------------------------------------------------------------------
# Guidance
# --------------------------------------------------------------------------
RTI_GUIDE: dict = {
    "title": "How the RTI Act actually works",
    "statute": "Right to Information Act, 2005",
    "statuteUrl": "https://rti.gov.in/",
    "steps": [
        {
            "step": 1,
            "title": "Identify who holds the record",
            "body": (
                "The Act gives you information held by a public authority in material form. Address the "
                "application to the Public Information Officer of the office that actually holds the file -- "
                "not the ministry above it. If you get it wrong, Section 6(3) requires them to transfer it "
                "within five days."
            ),
        },
        {
            "step": 2,
            "title": "Ask for records, not explanations",
            "body": (
                "'Provide a copy of the tender evaluation report' is a valid request. 'Explain why the road "
                "was not repaired' is not, and gives the office an easy refusal. Ask for the document that "
                "would contain the answer."
            ),
        },
        {
            "step": 3,
            "title": "Pay the fee and keep the proof",
            "body": (
                "Rs 10 for central authorities; states set their own. BPL cardholders pay nothing under "
                "Section 7(5). You never have to say why you want the information -- Section 6(2) forbids "
                "asking. Keep a photocopy and the postal receipt: the despatch date starts every clock that "
                "follows."
            ),
        },
        {
            "step": 4,
            "title": "Wait 30 days",
            "body": (
                "30 days for a reply, 48 hours where life or liberty is involved, 35 days if filed through an "
                "Assistant PIO. If they miss the deadline, Section 7(6) means the information must be given "
                "free of any further fee."
            ),
        },
        {
            "step": 5,
            "title": "First appeal, within 30 days, no fee",
            "body": (
                "To the First Appellate Authority in the same office -- an officer senior to the PIO. They "
                "must decide within 30 days, or 45 with reasons recorded. Attach the original application and "
                "proof of despatch."
            ),
        },
        {
            "step": 6,
            "title": "Second appeal, within 90 days, no fee",
            "body": (
                "To the Central Information Commission for central authorities, or your State Information "
                "Commission. The Commission can order disclosure and impose a penalty on a PIO who refused "
                "without reasonable cause."
            ),
        },
    ],
    "exemptions": {
        "note": (
            "Section 8 lists what can be withheld -- national security, foreign relations, cabinet papers "
            "before a decision, information held in a fiduciary capacity, personal information with no public "
            "interest, and a few more. Two things are commonly misunderstood:"
        ),
        "points": [
            "A refusal must name the specific clause relied on. 'Exempt under Section 8' with no clause is not a lawful refusal.",
            "Section 10 requires partial disclosure: if part of a record is exempt, the rest must still be given.",
            "Section 8(2) allows disclosure even of exempt information where the public interest in disclosure outweighs the harm.",
            "Section 4 requires authorities to publish a great deal proactively. Sometimes what you want is already meant to be on their website.",
        ],
    },
    "disclaimer": (
        "This is procedural guidance about how to use a statute, not legal advice about your particular "
        "matter. If your case involves a deadline you have missed, a penalty, or litigation, consult a lawyer."
    ),
}


PIL_GUIDE: dict = {
    "title": "Public Interest Litigation: what it is, and what this platform will not do",
    "openingNote": (
        "We do not draft petitions. Filing in a High Court or the Supreme Court is the practice of law, a "
        "badly drafted PIL can be dismissed with costs, and a template cannot know your facts. What follows is "
        "an explanation of the route and a checklist for the conversation you should have with a lawyer -- "
        "including how to find one for free."
    ),
    "basis": [
        {
            "article": "32",
            "title": "Petition to the Supreme Court",
            "body": (
                "For the enforcement of a Fundamental Right. Dr Ambedkar called Article 32 the heart and soul "
                "of the Constitution. The right to move the Court under it is itself a Fundamental Right."
            ),
        },
        {
            "article": "226",
            "title": "Petition to a High Court",
            "body": (
                "Wider than Article 32, because it is not limited to Fundamental Rights, and usually faster "
                "and far cheaper. For most citizens this, not the Supreme Court, is the right door."
            ),
        },
    ],
    "whoCanFile": (
        "Indian courts have relaxed the requirement that you be personally affected. Any member of the public "
        "acting in good faith may move the court on behalf of people unable to approach it themselves. That "
        "relaxation is also why courts scrutinise motive: a PIL used for a private dispute, publicity or a "
        "political purpose attracts costs."
    ),
    "checklist": [
        "Has the grievance been raised with the authority first? Courts ask, and an unanswered representation or RTI reply is powerful evidence.",
        "Is there an alternative remedy -- a tribunal, an ombudsman, a statutory appeal? An unexhausted remedy is the most common reason a petition is turned away.",
        "Are the facts documented? Orders, RTI replies, photographs with dates, official correspondence. A PIL rests on records, not on accounts.",
        "Is the relief you want something a court can actually order?",
        "Is the respondent correctly identified -- the right authority, properly described?",
        "Is anyone personally interested in the outcome in a way that must be disclosed?",
        "Are you prepared for it to take years, and for costs if the court finds the petition frivolous?",
    ],
    "freeLegalHelp": [
        {
            "name": "National Legal Services Authority (NALSA) and State Legal Services Authorities",
            "detail": (
                "Free legal aid is a statutory entitlement under the Legal Services Authorities Act, 1987 for "
                "women, children, Scheduled Caste and Scheduled Tribe members, industrial workmen, people with "
                "disabilities, victims of trafficking or mass disaster, people in custody, and anyone below the "
                "prescribed income limit. Every district has a District Legal Services Authority at the court "
                "complex."
            ),
            "url": "https://nalsa.gov.in/",
        },
        {
            "name": "Supreme Court Legal Services Committee",
            "detail": "For matters already before the Supreme Court.",
            "url": "https://sclsc.gov.in/",
        },
        {
            "name": "Lok Adalat",
            "detail": (
                "For disputes capable of settlement. No court fee, and an award has the force of a civil court "
                "decree. Held periodically at every district court."
            ),
            "url": "https://nalsa.gov.in/lok-adalat",
        },
    ],
    "whatWeDoInstead": [
        "The RTI generator, to build the documentary record a petition would need.",
        "The Representation generator, to exhaust the administrative route first -- which courts expect.",
        "The Research Centre, where judgments and reports relevant to accountability are collected with citations.",
        "The Constitution Library, so you understand the provision you would be relying on before you pay anyone to explain it.",
    ],
    "disclaimer": (
        "Nothing on this platform is legal advice, no lawyer-client relationship arises from reading it, and no "
        "part of it should be used as a substitute for advice on your own facts."
    ),
}
