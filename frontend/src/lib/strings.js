/*
 * Interface strings, English and Hindi.
 *
 * Only chrome: navigation, buttons, labels, empty states. Long-form content lives in
 * the database and comes back from the API already locale-aware, with provenance --
 * see backend/core/i18n.py for why a machine-translated constitutional passage is
 * never served as the authoritative text.
 *
 * Keys are dotted and grouped by surface. Hindi here is authored, not machine
 * translated, which is what §8 means by "all new content authored bilingually from
 * the start" for Phase 0-1.
 *
 * ADDING A LANGUAGE: add its code to LIVE_LOCALES and a block below. A locale
 * present in backend/core/i18n.py but absent here is listed in the switcher as
 * "coming soon" rather than being selectable, which is how a partially translated
 * interface is kept out of production.
 */

export const DEFAULT_LOCALE = "en";
export const LIVE_LOCALES = ["en", "hi"];

export const STRINGS = {
  en: {
    // ---- Navigation ----
    "nav.constitution": "Constitution",
    "nav.representatives": "Representatives",
    "nav.states": "States",
    "nav.petitions": "Petitions",
    "nav.reports": "Report cards",
    "nav.forum": "Discuss",
    "nav.tools": "Civic tools",
    "nav.academy": "Learn",
    "nav.research": "Research",
    "nav.assistant": "Ask",
    "nav.search": "Search",
    "nav.volunteer": "Volunteer",
    "nav.events": "Events",

    // ---- Shared ----
    "common.loading": "Loading...",
    "common.readMore": "Read more",
    "common.viewAll": "View all",
    "common.back": "Back",
    "common.share": "Share",
    "common.source": "Source",
    "common.sources": "Sources",
    "common.history": "Change history",
    "common.suggestCorrection": "Suggest a correction",
    "common.filters": "Filters",
    "common.clearFilters": "Clear filters",
    "common.searchPlaceholder": "Search articles, representatives, petitions...",
    "common.noResults": "Nothing found",
    "common.signInPrompt": "Sign in with your access code to take part.",
    "common.disclaimer": "Disclaimer",
    "common.updated": "Updated",
    "common.of": "of",

    // ---- Verification (§7) ----
    "verify.unverified": "Unverified - pending citation review",
    "verify.factChecked": "Fact-checked against the cited source",
    "verify.disputed": "Disputed - a correction is under review",
    "verify.primarySource": "Primary public record",
    "verify.secondarySource": "Secondary source",

    // ---- Constitution ----
    "constitution.title": "The Constitution, in plain language",
    "constitution.lede":
      "The original text, an explanation anyone can read, and why each article matters for holding representatives to account.",
    "constitution.originalText": "Original text",
    "constitution.plainEnglish": "In plain English",
    "constitution.plainHindi": "In Hindi",
    "constitution.recallRelevance": "Why this matters for Right to Recall",
    "constitution.caseLaw": "What the courts have held",
    "constitution.related": "Related articles",
    "constitution.paraphraseNotice":
      "This is our explanation, not the text of the Constitution. Read the original above for the exact wording.",
    "constitution.textPending":
      "The verbatim text of this article has not been transcribed yet. Read it on India Code.",

    // ---- Representatives ----
    "reps.title": "Who represents you, and what they have done",
    "reps.lede":
      "Every figure here is compiled from a public record and linked to it. Pending criminal cases are allegations, not convictions.",
    "reps.findMine": "Find my representatives",
    "reps.noProfiles": "No profiles are published for this filter yet.",
    "reps.helpBuild": "Help us research and publish this data",
    "reps.directlyElected": "Directly elected by voters",
    "reps.notDirectlyElected": "Not directly elected by voters",
    "reps.promises": "Promises tracked",
    "reps.claimsFactChecked": "fact-checked",
    "reps.claimsUnverified": "awaiting fact-check",

    // ---- States and campaign ----
    "states.title": "Where the campaign stands, state by state",
    "states.lede":
      "Eight stages, from no demand to an Act in force. Every change of stage is dated and sourced.",
    "states.pilot": "Pilot state",
    "states.noLegislature": "No legislative assembly",
    "states.stage": "Campaign stage",

    // ---- Manifesto accountability ----
    // The Hindi here matters more than on most surfaces: this module is about
    // Uttarakhand, the manifesto it tracks was published in Hindi, and the RTI
    // replies it quotes are written in Hindi. The promise text, questions,
    // answers and evidence statements come from the API in both languages and
    // are rendered from the record itself -- these keys are chrome only.
    "manifesto.title": "Uttarakhand Manifesto Accountability",
    "manifesto.chain": "Manifesto promise → RTI → government reply → evidence → public record",
    "manifesto.lede":
      "Every promise made in the Uttarakhand Assembly Election, tracked against the state government's own records obtained under the Right to Information Act.",
    "manifesto.explore": "Explore promises",
    "manifesto.viewRti": "View RTI records",
    "manifesto.viewRecord": "View complete record",
    "manifesto.nav.election": "Uttarakhand 2022",
    "manifesto.nav.promises": "All promises",
    "manifesto.nav.rti": "RTI records",
    "manifesto.nav.replies": "Government replies",
    "manifesto.nav.evidence": "Evidence",
    "manifesto.nav.dashboard": "Accountability dashboard",
    "manifesto.says": "What the manifesto says",
    "manifesto.recordsSay": "What the government's own records say",
    "manifesto.assessment": "Evidence-based assessment",
    "manifesto.whyThisStatus": "Why this status?",
    "manifesto.viewOriginal": "View the original",
    "manifesto.download": "Download the original",
    "manifesto.timeline": "Evidence timeline",
    "manifesto.recordHistory": "Record history",

    // ---- Petitions ----
    "petitions.title": "Petitions",
    "petitions.lede":
      "Every signature is tied to a verified member account and counted once. That is what makes the number on the cover worth handing to an office.",
    "petitions.sign": "Sign this petition",
    "petitions.signed": "You have signed this",
    "petitions.withdraw": "Withdraw my signature",
    "petitions.start": "Start a petition",
    "petitions.signatures": "signatures",
    "petitions.target": "target",

    // ---- The common cause (the national petition) ----
    "commonCause.nav": "Sign the petition",
    "commonCause.eyebrow": "The common cause",
    "commonCause.sign": "Sign the petition",
    "commonCause.stateEyebrow": "State by state",
    "commonCause.stateHeading": "Where the signatures are coming from",

    // ---- Reports ----
    "reports.title": "Citizen report cards",
    "reports.lede":
      "What public services actually look like where you live. Every report is read by a moderator before it is published.",
    "reports.file": "File a report",
    "reports.scorecard": "Service scorecard",
    "reports.confirm": "This is happening to me too",

    // ---- Forum ----
    "forum.title": "Discuss",
    "forum.lede":
      "Non-partisan by policy. Argue about conduct and policy, never about a community.",
    "forum.newThread": "Start a discussion",
    "forum.reply": "Reply",
    "forum.helpful": "Useful",
    "forum.readPolicy": "Read the content policy",

    // ---- Tools ----
    "tools.title": "Civic tools",
    "tools.lede":
      "Generate an RTI application, write to your representative, or understand what a PIL involves. Free, and nothing you type is stored.",
    "tools.generate": "Generate",
    "tools.downloadDocx": "Download as Word (.docx)",
    "tools.printPdf": "Print / Save as PDF",
    "tools.preview": "Preview",
    "tools.legalBasis": "Legal basis",
    "tools.filingNotes": "How to file it",
    "tools.nothingStored":
      "Nothing you type here is saved. Download or print before you leave the page.",

    // ---- Academy ----
    "academy.title": "Constitutional Learning Academy",
    "academy.lede": "Short courses on how the system works and where accountability stops.",
    "academy.startCourse": "Start this course",
    "academy.continue": "Continue",
    "academy.markDone": "Mark as read",
    "academy.takeQuiz": "Take the quiz",
    "academy.certificate": "Your certificate",

    // ---- Research ----
    "research.title": "Research Centre",
    "research.lede": "Judgments, affidavits, reports and datasets, each with its original source.",
    "research.media": "Media Library",
    "research.download": "Download",
    "research.hostedElsewhere": "Open the original source",
    "research.licence": "Licence",

    // ---- Assistant ----
    "assistant.title": "Ask about the Constitution",
    "assistant.lede":
      "Answers are drawn from this platform's own library and always show their sources. It will not advise on your own case.",
    "assistant.placeholder": "e.g. Can an MLA be recalled?",
    "assistant.ask": "Ask",
    "assistant.thinking": "Looking through the library...",
    "assistant.helpful": "This helped",
    "assistant.notHelpful": "This did not help",

    // ---- Volunteer ----
    "volunteer.title": "Volunteer task board",
    "volunteer.lede": "Real work, with defined outcomes and verified hours.",
    "volunteer.claim": "Take this task",
    "volunteer.submit": "Submit your work",
    "volunteer.verifiedHours": "verified hours",

    // ---- Events ----
    "events.title": "Events",
    "events.register": "Register",
    "events.ticket": "Your ticket",
    "events.showQr": "Show this QR at the door",

    // ---- Consent / DPDP ----
    "consent.title": "Before you submit",
    "consent.agree": "I have read this and agree",
    "consent.readPolicy": "Read the full privacy policy",
    "consent.deleteAnytime": "You can delete all of it yourself, any time, from your dashboard.",
  },

  hi: {
    // ---- Navigation ----
    "nav.constitution": "संविधान",
    "nav.representatives": "प्रतिनिधि",
    "nav.states": "राज्य",
    "nav.petitions": "याचिकाएँ",
    "nav.reports": "नागरिक रिपोर्ट",
    "nav.forum": "चर्चा",
    "nav.tools": "नागरिक साधन",
    "nav.academy": "सीखें",
    "nav.research": "शोध",
    "nav.assistant": "पूछें",
    "nav.search": "खोजें",
    "nav.volunteer": "स्वयंसेवा",
    "nav.events": "कार्यक्रम",

    // ---- Shared ----
    "common.loading": "लोड हो रहा है...",
    "common.readMore": "और पढ़ें",
    "common.viewAll": "सभी देखें",
    "common.back": "वापस",
    "common.share": "साझा करें",
    "common.source": "स्रोत",
    "common.sources": "स्रोत",
    "common.history": "परिवर्तन इतिहास",
    "common.suggestCorrection": "सुधार सुझाएँ",
    "common.filters": "छानबीन",
    "common.clearFilters": "छानबीन हटाएँ",
    "common.searchPlaceholder": "अनुच्छेद, प्रतिनिधि, याचिकाएँ खोजें...",
    "common.noResults": "कुछ नहीं मिला",
    "common.signInPrompt": "भाग लेने के लिए अपने एक्सेस कोड से साइन इन करें।",
    "common.disclaimer": "अस्वीकरण",
    "common.updated": "अद्यतन",
    "common.of": "में से",

    // ---- Verification ----
    "verify.unverified": "असत्यापित - स्रोत समीक्षा प्रतीक्षित",
    "verify.factChecked": "उद्धृत स्रोत के विरुद्ध तथ्य-जाँचित",
    "verify.disputed": "विवादित - सुधार समीक्षाधीन",
    "verify.primarySource": "प्राथमिक सार्वजनिक अभिलेख",
    "verify.secondarySource": "द्वितीयक स्रोत",

    // ---- Constitution ----
    "constitution.title": "संविधान, सरल भाषा में",
    "constitution.lede":
      "मूल पाठ, सबके लिए पठनीय व्याख्या, और यह कि प्रत्येक अनुच्छेद प्रतिनिधियों की जवाबदेही के लिए क्यों महत्वपूर्ण है।",
    "constitution.originalText": "मूल पाठ",
    "constitution.plainEnglish": "सरल अंग्रेज़ी में",
    "constitution.plainHindi": "हिंदी में",
    "constitution.recallRelevance": "राइट टू रिकॉल के लिए यह क्यों महत्वपूर्ण है",
    "constitution.caseLaw": "न्यायालयों ने क्या कहा है",
    "constitution.related": "संबंधित अनुच्छेद",
    "constitution.paraphraseNotice":
      "यह हमारी व्याख्या है, संविधान का पाठ नहीं। सटीक शब्दों के लिए ऊपर मूल पाठ पढ़ें।",
    "constitution.textPending":
      "इस अनुच्छेद का शब्दशः पाठ अभी लिप्यंतरित नहीं हुआ है। इसे India Code पर पढ़ें।",

    // ---- Representatives ----
    "reps.title": "आपका प्रतिनिधित्व कौन करता है, और उन्होंने क्या किया है",
    "reps.lede":
      "यहाँ प्रत्येक आँकड़ा सार्वजनिक अभिलेख से संकलित है और उससे जुड़ा है। लंबित आपराधिक मामले आरोप हैं, दोषसिद्धि नहीं।",
    "reps.findMine": "मेरे प्रतिनिधि खोजें",
    "reps.noProfiles": "इस छानबीन के लिए अभी कोई प्रोफ़ाइल प्रकाशित नहीं है।",
    "reps.helpBuild": "इस आँकड़े पर शोध और प्रकाशन में हमारी मदद करें",
    "reps.directlyElected": "मतदाताओं द्वारा प्रत्यक्ष निर्वाचित",
    "reps.notDirectlyElected": "मतदाताओं द्वारा प्रत्यक्ष निर्वाचित नहीं",
    "reps.promises": "ट्रैक किए गए वादे",
    "reps.claimsFactChecked": "तथ्य-जाँचित",
    "reps.claimsUnverified": "तथ्य-जाँच प्रतीक्षित",

    // ---- States ----
    "states.title": "अभियान की स्थिति, राज्य दर राज्य",
    "states.lede":
      "आठ चरण, माँग न होने से लेकर अधिनियम लागू होने तक। प्रत्येक चरण-परिवर्तन दिनांकित और स्रोत-सहित है।",
    "states.pilot": "पायलट राज्य",
    "states.noLegislature": "कोई विधान सभा नहीं",
    "states.stage": "अभियान चरण",

    // ---- Manifesto accountability ----
    "manifesto.title": "उत्तराखंड घोषणापत्र जवाबदेही",
    "manifesto.chain": "घोषणापत्र का वादा → आरटीआई → सरकारी उत्तर → साक्ष्य → सार्वजनिक अभिलेख",
    "manifesto.lede":
      "उत्तराखंड विधान सभा चुनाव में किए गए प्रत्येक वादे का, सूचना का अधिकार अधिनियम के अंतर्गत प्राप्त राज्य सरकार के अपने अभिलेखों के आधार पर अनुसरण।",
    "manifesto.explore": "वादे देखें",
    "manifesto.viewRti": "आरटीआई अभिलेख देखें",
    "manifesto.viewRecord": "पूरा अभिलेख देखें",
    "manifesto.nav.election": "उत्तराखंड 2022",
    "manifesto.nav.promises": "सभी वादे",
    "manifesto.nav.rti": "आरटीआई अभिलेख",
    "manifesto.nav.replies": "सरकारी उत्तर",
    "manifesto.nav.evidence": "साक्ष्य",
    "manifesto.nav.dashboard": "जवाबदेही डैशबोर्ड",
    "manifesto.says": "घोषणापत्र क्या कहता है",
    "manifesto.recordsSay": "सरकार के अपने अभिलेख क्या कहते हैं",
    "manifesto.assessment": "साक्ष्य-आधारित आकलन",
    "manifesto.whyThisStatus": "यह स्थिति क्यों?",
    "manifesto.viewOriginal": "मूल दस्तावेज़ देखें",
    "manifesto.download": "मूल दस्तावेज़ डाउनलोड करें",
    "manifesto.timeline": "साक्ष्य समयरेखा",
    "manifesto.recordHistory": "अभिलेख इतिहास",

    // ---- Petitions ----
    "petitions.title": "याचिकाएँ",
    "petitions.lede":
      "प्रत्येक हस्ताक्षर एक सत्यापित सदस्य खाते से जुड़ा है और एक बार गिना जाता है। इसीलिए वह संख्या किसी कार्यालय को सौंपने योग्य है।",
    "petitions.sign": "इस याचिका पर हस्ताक्षर करें",
    "petitions.signed": "आपने इस पर हस्ताक्षर किए हैं",
    "petitions.withdraw": "मेरा हस्ताक्षर वापस लें",
    "petitions.start": "याचिका शुरू करें",
    "petitions.signatures": "हस्ताक्षर",
    "petitions.target": "लक्ष्य",

    // ---- The common cause (the national petition) ----
    "commonCause.nav": "याचिका पर हस्ताक्षर करें",
    "commonCause.eyebrow": "साझा उद्देश्य",
    "commonCause.sign": "याचिका पर हस्ताक्षर करें",
    "commonCause.stateEyebrow": "राज्य दर राज्य",
    "commonCause.stateHeading": "हस्ताक्षर कहाँ से आ रहे हैं",

    // ---- Reports ----
    "reports.title": "नागरिक रिपोर्ट कार्ड",
    "reports.lede":
      "आपके क्षेत्र में सार्वजनिक सेवाएँ वास्तव में कैसी हैं। प्रकाशन से पूर्व प्रत्येक रिपोर्ट मॉडरेटर पढ़ता है।",
    "reports.file": "रिपोर्ट दर्ज करें",
    "reports.scorecard": "सेवा स्कोरकार्ड",
    "reports.confirm": "मेरे साथ भी यही हो रहा है",

    // ---- Forum ----
    "forum.title": "चर्चा",
    "forum.lede": "नीति से गैर-दलीय। आचरण और नीति पर बहस करें, कभी किसी समुदाय पर नहीं।",
    "forum.newThread": "चर्चा शुरू करें",
    "forum.reply": "उत्तर दें",
    "forum.helpful": "उपयोगी",
    "forum.readPolicy": "सामग्री नीति पढ़ें",

    // ---- Tools ----
    "tools.title": "नागरिक साधन",
    "tools.lede":
      "आरटीआई आवेदन बनाएँ, अपने प्रतिनिधि को लिखें, या समझें कि पीआईएल में क्या होता है। निःशुल्क, और आपका लिखा कुछ भी संग्रहीत नहीं होता।",
    "tools.generate": "तैयार करें",
    "tools.downloadDocx": "वर्ड (.docx) में डाउनलोड करें",
    "tools.printPdf": "प्रिंट / पीडीएफ सहेजें",
    "tools.preview": "पूर्वावलोकन",
    "tools.legalBasis": "विधिक आधार",
    "tools.filingNotes": "इसे कैसे दाखिल करें",
    "tools.nothingStored":
      "आपका यहाँ लिखा कुछ भी सहेजा नहीं जाता। पृष्ठ छोड़ने से पहले डाउनलोड या प्रिंट कर लें।",

    // ---- Academy ----
    "academy.title": "संवैधानिक शिक्षा अकादमी",
    "academy.lede": "लघु पाठ्यक्रम: व्यवस्था कैसे काम करती है और जवाबदेही कहाँ रुक जाती है।",
    "academy.startCourse": "यह पाठ्यक्रम शुरू करें",
    "academy.continue": "जारी रखें",
    "academy.markDone": "पढ़ा हुआ चिह्नित करें",
    "academy.takeQuiz": "प्रश्नोत्तरी दें",
    "academy.certificate": "आपका प्रमाणपत्र",

    // ---- Research ----
    "research.title": "शोध केंद्र",
    "research.lede": "निर्णय, शपथपत्र, रिपोर्ट और आँकड़े, प्रत्येक अपने मूल स्रोत के साथ।",
    "research.media": "मीडिया पुस्तकालय",
    "research.download": "डाउनलोड",
    "research.hostedElsewhere": "मूल स्रोत खोलें",
    "research.licence": "अनुज्ञप्ति",

    // ---- Assistant ----
    "assistant.title": "संविधान के बारे में पूछें",
    "assistant.lede":
      "उत्तर इस मंच के अपने पुस्तकालय से आते हैं और सदैव अपने स्रोत दिखाते हैं। यह आपके व्यक्तिगत मामले पर सलाह नहीं देगा।",
    "assistant.placeholder": "उदा. क्या किसी विधायक को वापस बुलाया जा सकता है?",
    "assistant.ask": "पूछें",
    "assistant.thinking": "पुस्तकालय में देख रहे हैं...",
    "assistant.helpful": "यह उपयोगी था",
    "assistant.notHelpful": "यह उपयोगी नहीं था",

    // ---- Volunteer ----
    "volunteer.title": "स्वयंसेवक कार्य बोर्ड",
    "volunteer.lede": "वास्तविक कार्य, निर्धारित परिणामों और सत्यापित घंटों के साथ।",
    "volunteer.claim": "यह कार्य लें",
    "volunteer.submit": "अपना कार्य जमा करें",
    "volunteer.verifiedHours": "सत्यापित घंटे",

    // ---- Events ----
    "events.title": "कार्यक्रम",
    "events.register": "पंजीकरण करें",
    "events.ticket": "आपका टिकट",
    "events.showQr": "प्रवेश पर यह क्यूआर दिखाएँ",

    // ---- Consent ----
    "consent.title": "जमा करने से पहले",
    "consent.agree": "मैंने यह पढ़ा है और सहमत हूँ",
    "consent.readPolicy": "पूरी गोपनीयता नीति पढ़ें",
    "consent.deleteAnytime": "आप यह सब कभी भी अपने डैशबोर्ड से स्वयं हटा सकते हैं।",
  },
};
