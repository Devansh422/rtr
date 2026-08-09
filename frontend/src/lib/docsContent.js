/*
 * Content for the /docs guide.
 *
 * Written for a citizen, a journalist or a new volunteer — NOT for a developer.
 * There is no API in here, no database, no "module". If a sentence needs a
 * technical word to make sense, the sentence is wrong.
 *
 * Kept as data rather than JSX so that the table of contents, the "who needs an
 * account" summary and the per-section counts are all derived from one list. Adding
 * a feature means adding an object here; nothing else has to be edited.
 *
 * Style rules for anyone editing this file:
 *
 * - `steps` describes what the PERSON does and what the site does back, in order.
 *   Not what the software does internally.
 * - `honest` is where a limitation goes. Every feature that is incomplete says so
 *   in its own entry rather than in a disclaimer at the bottom that nobody reads.
 * - `who` always answers "do I need an account?" because that is the first thing
 *   anyone wants to know.
 */

export const ACCESS = {
  ANYONE: "Anyone — no account needed",
  MEMBER: "Members — free, sign in with your access code",
  STAFF: "Team members with the right role",
};

export const STATUS = {
  LIVE: { key: "live", label: "Working now" },
  GROWING: { key: "growing", label: "Working, still filling with data" },
  SOON: { key: "soon", label: "Built, waiting on content" },
};

export const SECTIONS = [
  // ======================================================================
  {
    id: "learn",
    title: "Understand how the system works",
    lede:
      "Before you can hold anyone to account you have to know what they are actually required to do. Everything in this section is free, open to anyone, and written to be read by someone who has never opened a law book.",
    features: [
      {
        id: "constitution-library",
        name: "Constitution Library",
        path: "/constitution",
        status: STATUS.GROWING,
        who: ACCESS.ANYONE,
        oneLine:
          "The articles of the Constitution that matter for accountability, each explained in plain English and Hindi.",
        steps: [
          "Open the Library and either search (by article number, by subject, or by a phrase like 'voting age') or browse the six Parts we mark as the place to start.",
          "Open any article. The page shows you four things, in this order: the exact words of the Constitution; our plain-language explanation; why that article matters for the Right to Recall argument; and what the courts have actually held about it.",
          "The plain-language explanation is clearly labelled as ours, not as the law. Where our wording and the original differ, the original wins, and we say so on every page.",
          "Related articles are linked at the bottom, so you can follow the argument rather than reading in numerical order.",
          "If you think an explanation is wrong, use 'Suggest a correction' at the top of the page.",
        ],
        honest:
          "The Library has 61 articles, not all 395. We add them as researchers write and review each one. Where we have not transcribed the exact constitutional text yet, the page says so and links you to India Code, the government's own source, rather than letting our paraphrase stand in for the law.",
      },
      {
        id: "academy",
        name: "Learning Academy",
        path: "/academy",
        status: STATUS.GROWING,
        who: `${ACCESS.ANYONE} to read. ${ACCESS.MEMBER} to save progress and earn a certificate.`,
        oneLine:
          "Short courses that take you from 'what is recall' to being able to argue the case properly.",
        steps: [
          "Pick a course. The first one, 'The Right to Recall', takes about half an hour and covers the whole argument end to end.",
          "Read the lessons in order. Each one links to the constitutional articles it discusses, so you can check what we say against the actual provision.",
          "Mark each lesson as read as you go. If you are signed in, your place is saved and you can come back later.",
          "When you have read every lesson, take the quiz. You need 70% to pass, and there is no limit on attempts.",
          "Pass the quiz with all lessons read, and a certificate is issued to you automatically.",
        ],
        honest:
          "One course is published so far. The quiz explains why each answer is right or wrong after you submit — a quiz that only says 'wrong' teaches nothing.",
      },
      {
        id: "assistant",
        name: "Ask (the Constitution assistant)",
        path: "/ask",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Ask a question in plain language and get an answer built from this site's own library.",
        steps: [
          "Type a question — 'Can an MLA be recalled?', 'Explain Article 326 in simple words', 'What is the difference between recall and impeachment?'. Hindi and Hinglish work too.",
          "The assistant searches this platform's Constitution Library and Research Centre first, then answers using only what it found.",
          "Every answer shows the sources it used, as links. You can click through and check it.",
          "If the library has nothing relevant, it tells you so rather than inventing an answer. It will never make up an article number.",
          "If you ask about your own legal situation, it will decline and point you to free legal aid instead — because advice on your facts needs a lawyer who can see them.",
        ],
        honest:
          "It will not tell you who to vote for, or whether a particular politician is corrupt. That is not a technical limitation — this platform is non-partisan by policy and it applies to the assistant too. Do not put your phone number, email or ID numbers into a question.",
      },
      {
        id: "research",
        name: "Research Centre and Media Library",
        path: "/research",
        status: STATUS.SOON,
        who: ACCESS.ANYONE,
        oneLine:
          "The original documents — judgments, affidavits, reports, datasets — with a link to where each one really came from.",
        steps: [
          "Switch between the Research Centre (judgments, reports, RTI replies, datasets) and the Media Library (posters, infographics, video, handouts you can reuse).",
          "Filter by type, or search by title, author or subject.",
          "Every item shows who produced it, when, and the licence it is available under, so you know whether you can reuse it.",
          "Some documents we host a copy of; others we only link to. A Supreme Court judgment stays on the Court's own website — that link is the citation, and rehosting it would add nothing.",
        ],
        honest:
          "This fills up as research happens. If a claim on this site cites a document, that document should be findable here.",
      },
      {
        id: "knowledge-hub",
        name: "Knowledge Hub and Blog",
        path: "/knowledge",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Explainers, myth-busting, campaign news and how recall works in other countries.",
        steps: [
          "The Knowledge Hub answers the questions people actually ask first, including the common objections to recall.",
          "The Blog carries campaign news and longer pieces.",
          "Both are written for someone with no background in this, and both are searchable from the search box in the header.",
        ],
      },
    ],
  },

  // ======================================================================
  {
    id: "accountability",
    title: "Find out what your representatives have actually done",
    lede:
      "This is the part people mean when they say 'Election Commission meets Wikipedia'. Everything here is compiled from public records and linked back to them. Nothing is our opinion, and where something has not been checked yet, the page says so on the figure itself.",
    features: [
      {
        id: "who-represents-me",
        name: "Who represents me",
        path: "/my-representatives",
        status: STATUS.GROWING,
        who: ACCESS.ANYONE,
        oneLine: "Pick your state and constituency, and see the people who hold your seats.",
        steps: [
          "Choose your state. If you know your constituency, choose that too.",
          "You get your MPs and MLAs, grouped by which House they sit in.",
          "Each one is marked as directly elected by voters or not — which matters, because a recall right exercised by voters can only reach a seat that voters filled.",
          "Click through to any profile for their full record.",
        ],
        honest:
          "This page tells you how many profiles exist versus how many seats there are — for example '3 published of 48 seats'. That is deliberate. A page that quietly showed you three of forty-eight MPs would look complete and would be misleading.",
      },
      {
        id: "representative-database",
        name: "Representative Database",
        path: "/representatives",
        status: STATUS.GROWING,
        who: ACCESS.ANYONE,
        oneLine:
          "A profile for each MP and MLA: attendance, questions asked, debates, declared assets, declared criminal cases — each with a link to the record it came from.",
        steps: [
          "Browse or filter by state, House or party.",
          "Open a profile. Before you see any figure, you see how many of that profile's figures have been fact-checked and how many are still awaiting check.",
          "Every single number carries its own badge — 'Fact-checked against the cited source' or 'Unverified — pending citation review' — and its own link to the public record behind it.",
          "Every number also carries a short note explaining what it does NOT mean. Attendance measures presence, not participation. A minister's debate count is low because ministers answer rather than participate. Declared assets are self-declared and audited by nobody.",
          "At the bottom of each profile is the full change history: every edit, when it happened, and the source behind it.",
        ],
        honest:
          "Where a profile records pending criminal cases, those come from the person's own affidavit to the Election Commission. A pending case is an allegation a court has not decided. It is not a conviction, and publishing the number is not an accusation — it is the disclosure the Supreme Court held voters are entitled to in 2002. We do not investigate allegations and take no position on anyone's guilt.",
      },
      {
        id: "promise-tracker",
        name: "Promise Tracker",
        path: "/promises",
        status: STATUS.SOON,
        who: ACCESS.ANYONE,
        oneLine: "What was promised, by whom, and what became of it.",
        steps: [
          "Filter by state, party or status.",
          "Open any promise to see the commitment in its own words, when and where it was made, and what the current status is.",
          "Each promise carries two separate pieces of evidence: a link proving the promise was made, and a link showing what happened to it.",
          "Marking a promise 'not delivered' requires a primary official source — a scheme's own progress report, a budget document, an RTI reply. A news article saying a promise was broken is somebody else's assessment, not the record.",
        ],
        honest:
          "There are seven statuses, not two. Most real promises are partially delivered, stalled in a department, or genuinely too early to judge. A tracker with only 'kept' and 'broken' would force every ambiguous case into a verdict it cannot support.",
      },
      {
        id: "report-cards",
        name: "Citizen Report Cards",
        path: "/reports",
        status: STATUS.LIVE,
        who: `${ACCESS.ANYONE} to read. ${ACCESS.MEMBER} to file one.`,
        oneLine:
          "What public services actually look like where you live — the thing no official dataset records.",
        steps: [
          "Pick a state to see its service scorecard: water, roads, health centres, ration shops, pensions and so on.",
          "To file your own: sign in, choose the service and your locality, describe what is happening and since when, and rate how well the service is working.",
          "Your report goes to a moderator. Nothing publishes automatically. You will see its status in your dashboard, including the reason if it is not published.",
          "Once published, other people in the same area can confirm it — 'this is happening to me too'.",
          "If the department responds or fixes it, that response is recorded on the same page with the same prominence as your complaint.",
        ],
        honest:
          "Report about a service and a place, not about a person. Scores are only shown once enough people in an area have rated a service — below that the page shows the number of reports instead, because three ratings is not a constituency's water score. Never include phone numbers, email addresses or ID numbers; the form will refuse them.",
      },
      {
        id: "corrections",
        name: "Suggest a correction",
        path: "/representatives",
        status: STATUS.LIVE,
        who: `${ACCESS.ANYONE} — you do not need an account`,
        oneLine: "Tell us something is wrong, and see publicly what we did about it.",
        steps: [
          "Every page carrying a fact about a person, a state or the Constitution has a 'Suggest a correction' button.",
          "Say what is wrong. If you can, add a link to the public record that proves it — a court filing, an affidavit, an RTI reply, an official order.",
          "A reviewer checks it against that source.",
          "The outcome is published on the page either way: accepted with the record corrected, or not accepted with the reviewer's reason written out.",
          "While a correction is being reviewed, the page shows that a correction has been filed, without publishing its contents yet.",
        ],
        honest:
          "You do not need an account, deliberately: requiring one to report an error about a powerful person filters out exactly the people most likely to know about it. Corrections that cite a public record are resolved much faster, because a reviewer can act on them immediately.",
      },
      {
        id: "history",
        name: "Change history on every page",
        path: "/constitution",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Anyone can see every edit ever made to a record, and the evidence behind it.",
        steps: [
          "Representative profiles, constitution articles, promises and state campaign statuses all have a history tab.",
          "It lists every change: what the value was before, what it became, when, and the source that justified it.",
          "The record cannot be edited or deleted afterwards — including by us.",
          "The name of the volunteer who made the edit is not shown. You can see the change and the evidence; naming contributors would invite pressure on them and is not part of what transparency requires.",
        ],
      },
    ],
  },

  // ======================================================================
  {
    id: "campaign",
    title: "Follow and push the campaign",
    lede:
      "The Right to Recall does not need one national law to start. Any state legislature can act on its own MLAs. So the campaign is tracked state by state, and every claim about where a state stands has to be backed by a public record.",
    features: [
      {
        id: "campaign-dashboard",
        name: "Campaign dashboard and map",
        path: "/states",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "All 36 states and union territories, coloured by how far the campaign has got.",
        steps: [
          "The map shows every state and union territory as an equal tile, shaded by its stage.",
          "There are eight stages: no demand yet, awareness, petition submitted, bill introduced, committee stage, passed assembly, passed Parliament, act enforced.",
          "Click any tile for that state's page.",
          "Delhi and Maharashtra are marked as pilot states — they are being built end to end first, so the pattern is proven before it is copied to the rest of the country.",
        ],
        honest:
          "Equal-sized tiles rather than a geographic map, on purpose. Goa and Rajasthan get the same visual weight because every state legislature has the same power to act here, and a real map would make the big states look like the whole argument.",
      },
      {
        id: "state-pages",
        name: "State pages",
        path: "/states",
        status: STATUS.GROWING,
        who: ACCESS.ANYONE,
        oneLine: "One page per state: its stage, its representatives, its petitions, its events, its reports.",
        steps: [
          "See exactly where the state is on the eight-stage pipeline, with the evidence for that status and the full history of every stage change.",
          "See the representatives published for that state, and how many are still to be researched.",
          "See petitions, upcoming events and the citizen report scorecard for that state.",
          "Generate a letter to your representative in that state, straight from the page.",
        ],
        honest:
          "For a union territory without a legislative assembly, the page says so and explains that the case there has to run through Parliament instead — there is no House for a state bill to pass through.",
      },
      {
        id: "petitions",
        name: "Petitions",
        path: "/petitions",
        status: STATUS.LIVE,
        who: `${ACCESS.ANYONE} to read. ${ACCESS.MEMBER} to sign or start one.`,
        oneLine: "Petitions whose signature count can survive being handed to a Chief Minister.",
        steps: [
          "Browse open petitions, sorted by what is moving fastest rather than by what is oldest.",
          "To sign: sign in, optionally add a comment, and choose whether your name is listed publicly.",
          "To start one: write it, address it to a specific office, and submit. A moderator checks it against the content policy before it opens for signatures — usually within two working days.",
          "Milestones are marked as they are reached, starting at 50 signatures.",
          "When a petition is delivered or answered, that is recorded on the page with evidence.",
          "You can withdraw your signature at any time, and withdrawing really removes it.",
        ],
        honest:
          "Signing requires a free account, and that costs us signups. A petition with 50,000 signatures that anyone could inflate with a script is worth less than one with 500 that cannot, because the first one can be dismissed in a sentence. Your name is not published unless you tick the box — the count includes everyone, the public list only includes those who chose to appear.",
      },
      {
        id: "events",
        name: "Events",
        path: "/events",
        status: STATUS.SOON,
        who: `${ACCESS.ANYONE} to browse. ${ACCESS.MEMBER} to register.`,
        oneLine: "Workshops, training, public meetings and signature drives — with a real attendance record.",
        steps: [
          "Browse upcoming events, filtered by your state.",
          "Register, and you get a ticket with a QR code on it, plus an email confirmation.",
          "Show the QR code at the door. A volunteer scans it and you are marked present.",
          "After the event, everyone who actually attended is issued a participation certificate.",
        ],
        honest:
          "Each ticket has its own QR code rather than one code for the whole event, so a photograph of somebody else's code cannot mark you present. Certificates go only to people who actually attended — a certificate for an event you did not attend would devalue every other certificate we issue.",
      },
    ],
  },

  // ======================================================================
  {
    id: "act",
    title: "Use the rights you already have",
    lede:
      "You do not have to wait for the law to change to hold an office to account. These are the tools that already work, and they are free. Nothing you type into any of them is stored by us.",
    features: [
      {
        id: "rti",
        name: "RTI application generator",
        path: "/tools/rti-general",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine:
          "Produces a properly drafted Right to Information application, ready to print and post.",
        steps: [
          "Fill in the form: which office holds the record, what you want, and your address for the reply.",
          "The tool tells you as you go — for example, that you should ask for RECORDS ('provide a copy of the sanction order') rather than explanations ('why was this not done'), because the Act covers information held in material form.",
          "Preview it on screen, then download it as a Word file to edit, or print it straight to PDF.",
          "The page also tells you the fee, where to send it, and how long they have to reply: 30 days normally, 48 hours if life or liberty is involved.",
          "There is a separate generator for the first appeal (if they do not reply or refuse) and the second appeal to the Information Commission.",
        ],
        honest:
          "We never see or store what you write. The tool records only that an RTI was generated, for one state, at one time — nothing about you or your grievance. Download or print before you leave the page, because nothing is saved.",
      },
      {
        id: "representation",
        name: "Write to your MP or MLA",
        path: "/tools/representation-to-representative",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "A formal representation that creates a record, rather than a phone call that does not.",
        steps: [
          "Describe the issue, what you have already tried, and exactly what you want them to do.",
          "The tool produces a formal letter citing Article 350, which gives every person the right to submit a representation for redress of a grievance.",
          "Download or print it, and send it to both their constituency office and their House address. Keep the postal receipt.",
          "If there is no reply in three or four weeks, the standard next step is an RTI to the department asking what action was taken on your representation — and this site will draft that too.",
        ],
        honest:
          "One issue and one clear ask per letter. A letter listing nine grievances gets filed; a letter asking one question gets answered.",
      },
      {
        id: "recall-letter",
        name: "Right to Recall demand letter",
        path: "/tools/recall-demand",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine:
          "Asks your representative to state, on the record, whether they support a citizens' Right to Recall.",
        steps: [
          "Fill in who your representative is and, if you want, why this matters to you personally.",
          "The letter sets out the constitutional argument — that Article 326 rests democracy on your vote, that Articles 83 and 172 then fix a five-year term with no way for voters to end it, and that Article 328 already lets a state legislature act.",
          "It asks them to do three things: say publicly whether they support it, raise it in their House, and tell you what they did.",
          "Send it. Then publish their reply — or the absence of one — so it is on the record either way.",
        ],
        honest:
          "The letter states explicitly that it is not sent on behalf of any party and that the same letter is going to representatives of every party. That is true, and it is why the letter is hard to dismiss.",
      },
      {
        id: "pil",
        name: "PIL Resource Centre",
        path: "/tools",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "What a Public Interest Litigation actually involves — and why we will not draft one for you.",
        steps: [
          "Read what Article 32 (Supreme Court) and Article 226 (High Court) actually offer, and why the High Court is the right door for most people.",
          "Work through the checklist a lawyer will ask you about: have you raised it with the authority first, is there another remedy you have not used, are your facts documented, can a court actually order what you want.",
          "Use the list of free legal help. Free legal aid is a statutory entitlement for a great many people through NALSA, and every district has an office at the court complex.",
        ],
        honest:
          "We do not draft petitions and we will not. Filing in a High Court is the practice of law, a badly drafted PIL can be dismissed with costs, and a template cannot know your facts. What we do instead is help you build the documentary record — RTIs, representations, sourced research — that any petition would need.",
      },
      {
        id: "forum",
        name: "Discussion forum",
        path: "/forum",
        status: STATUS.LIVE,
        who: `${ACCESS.ANYONE} to read. ${ACCESS.MEMBER} to post.`,
        oneLine: "Somewhere to argue about conduct and policy — never about a community.",
        steps: [
          "Seven rooms: the Right to Recall itself, understanding the Constitution, your constituency, state campaigns, civic tools, research and data, and help.",
          "Read anything without an account. Sign in to post or reply.",
          "You post under a display name, not your real name, by default.",
          "There are upvotes but no downvotes. You can mark a post useful; you cannot bury someone.",
          "Posts that appear to campaign for a party, or to blame a community, are held for a moderator rather than deleted. You will see the reason and can rewrite.",
        ],
        honest:
          "Contribution points exist, but they gate only the things people abuse — posting links, or starting a thread about a named representative. Replying, posting and voting need no points at all. There is no leaderboard.",
      },
      {
        id: "volunteer-board",
        name: "Volunteer task board",
        path: "/volunteer-portal",
        status: STATUS.LIVE,
        who: ACCESS.MEMBER,
        oneLine: "Real work with a defined outcome, and hours somebody actually checks.",
        steps: [
          "Tell us what you can help with: translation, research, legal, design, social media, field organising, data entry, teaching, software, and more.",
          "Take a task from the board. Every task says what 'done' looks like before you start it.",
          "Do the work, then submit it with a note and the hours it took.",
          "A volunteer manager confirms the hours. They may confirm fewer than you claimed, with a reason — estimating your own hours is genuinely hard, and the number that ends up on a certificate has to be one we can stand behind.",
          "At 20 verified hours you can issue yourself a service certificate.",
          "You can give a task back at any time with no penalty.",
        ],
      },
    ],
  },

  // ======================================================================
  {
    id: "account",
    title: "Your account, your certificates, your data",
    lede:
      "Joining is free and takes a minute. There is no password to remember — you get an access code. Everything we hold about you is visible to you, and you can delete all of it yourself in one click.",
    features: [
      {
        id: "joining",
        name: "Joining the movement",
        path: "/join",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Name, email and state. You get a movement ID and an access code.",
        steps: [
          "Fill in the join form. Before you submit, a notice tells you exactly what will be collected, why, and how long it is kept. You have to tick a box saying you have read it — it is not pre-ticked.",
          "You get a movement ID and a one-time access code. The code is shown once and never again, because we only ever store a scrambled version of it. Save it.",
          "Use your email and that code to sign in at any time.",
          "You also get a shareable supporter certificate.",
        ],
        honest:
          "We never sell your data, never share it with any political party, and do not use advertising trackers. We do not ask for your Aadhaar, PAN, voter ID, date of birth, caste, religion or income, and the site actively refuses posts containing Aadhaar or PAN numbers.",
      },
      {
        id: "dashboard",
        name: "Your dashboard",
        path: "/dashboard",
        status: STATUS.LIVE,
        who: ACCESS.MEMBER,
        oneLine: "Everything you have done, everything we hold, and the button that deletes it.",
        steps: [
          "See your petitions signed and started, your reports and their status, your forum posts including any held for review, your volunteer tasks and hours, your event tickets, and your courses.",
          "See your consent history: what you agreed to, when, and under which version of the privacy notice.",
          "Withdraw consent for anything optional — email updates, for instance — and it stops immediately.",
          "Delete everything with one button. It runs straight away and really deletes.",
        ],
        honest:
          "Three things survive deletion, and we say so plainly rather than hiding it: the log of staff edits to platform records (which does not contain your submissions and cannot be rewritten by anyone including us); replies other people wrote to your posts, with your name detached; and petitions you started that other people have signed, with your authorship removed.",
      },
      {
        id: "certificates",
        name: "Certificates and verification",
        path: "/certificates",
        status: STATUS.LIVE,
        who: `${ACCESS.MEMBER} to earn. ${ACCESS.ANYONE} to verify.`,
        oneLine: "Certificates with a code anyone can check — including an employer.",
        steps: [
          "You can earn three kinds: volunteer service (20 verified hours), event participation (attended, not just registered), and course completion (lessons read and quiz passed).",
          "Each certificate carries a short code, like RTR-K7M2-9PQX.",
          "Anyone can type that code into the verification page and see who holds it, what it was for, when it was issued and whether it is still valid — and nothing else.",
          "Download it as a Word file, or print it to PDF.",
        ],
        honest:
          "The wording is deliberately modest. This is a record of civic volunteering, not an academic qualification. Overclaiming would make every certificate we issue worth less. Codes never contain the letters O or I, or the digits 0 or 1, so those are the characters to double-check if a code will not verify.",
      },
      {
        id: "language",
        name: "English and Hindi",
        path: "/constitution",
        status: STATUS.GROWING,
        who: ACCESS.ANYONE,
        oneLine: "Switch the whole site between English and Hindi from the header.",
        steps: [
          "Use the language button in the header. Your choice is remembered.",
          "The interface, and content written in both languages, switches over.",
          "The switcher also lists the languages we are working towards — Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali and others — greyed out until a volunteer has reviewed them.",
        ],
        honest:
          "We will not publish a machine translation of constitutional text as though it were the text. If a translation exists but has not been checked by a person, the page shows the reviewed English and tells you an unreviewed draft exists. Accuracy matters more than coverage here. Translating is one of the volunteer tasks on the board.",
      },
      {
        id: "search",
        name: "Search",
        path: "/search",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "One box across the Constitution, representatives, promises, petitions, research and courses.",
        steps: [
          "Use the search icon in the header, or go to the search page directly.",
          "Results are grouped by what they are, with the Constitution and representatives first.",
          "With an empty search box, the page shows you exactly how much of the site is searchable — how many articles, how many profiles, how many documents.",
        ],
        honest:
          "That coverage count is there so that finding nothing tells you something useful. If we have twelve representative profiles rather than four thousand, you should be able to see that, instead of concluding the search is broken.",
      },
    ],
  },
// ======================================================================
  {
    id: "movement",
    title: "The movement itself",
    lede:
      "The parts of the site that are about who we are and how to reach us, rather than about the data. All of it is open to anyone.",
    features: [
      {
        id: "about",
        name: "About the movement",
        path: "/about",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "What the Right to Recall Movement is, what it wants, and what it refuses to be.",
        steps: [
          "Read the case for a citizens' Right to Recall, laid out as a numbered argument rather than a slogan.",
          "See the timeline of how the demand has developed in India.",
          "Read the non-partisan commitment in full — including what it costs us to hold to it.",
        ],
      },
      {
        id: "campaigns",
        name: "Campaigns",
        path: "/campaigns",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "The specific pushes running right now, and how to join one.",
        steps: [
          "Browse the active campaigns.",
          "Open one to see what it is asking for, where it stands, and how many people have joined it.",
          "Join directly from the campaign page — your signup is attributed to that campaign so we can see what is actually working.",
        ],
      },
      {
        id: "volunteer-signup",
        name: "Volunteer signup",
        path: "/volunteer",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine:
          "Register as a volunteer. Different from the task board — this is the first step, that is where the work is.",
        steps: [
          "Fill in your details, your state, what you do, and why you want to help.",
          "Before you submit, a notice tells you exactly what will be collected and why. You have to tick it yourself.",
          "You get a volunteer ID and an access code. Save the code — it is shown once.",
          "Sign in with it, then set up your skills on the task board and start taking work.",
        ],
      },
      {
        id: "resources",
        name: "Toolkits and downloads",
        path: "/resources",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Ready-made material for organising: explainer sheets, toolkits, research summaries.",
        steps: [
          "Browse by type — document, toolkit or research.",
          "Download what you need and use it. Anything in the Media Library is licensed for reuse, and the licence is stated on each item.",
        ],
      },
      {
        id: "contact",
        name: "Contact",
        path: "/contact",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine: "Write to the team — including to contest a moderation decision.",
        steps: [
          "Send a message through the form.",
          "Use this if a moderator removed something of yours and you think that was wrong. Every removal is recorded, so there is always a record to check.",
          "Use it too if you think something on this site is inaccurate but there is no correction button on the page in question.",
        ],
      },
      {
        id: "policies",
        name: "Published policies",
        path: "/privacy",
        status: STATUS.LIVE,
        who: ACCESS.ANYONE,
        oneLine:
          "The privacy policy, the content policy and the sourcing disclaimer, all published in full.",
        steps: [
          "The privacy policy lists exactly what is collected on each form, why, and for how long — including the three things that survive account deletion and why.",
          "The content policy is the same set of rules the site actually applies to posts, published word for word. Publishing it is what lets us credibly claim to be non-partisan.",
          "The disclaimer explains where data about named people comes from, why a pending case is not a conviction, and why our plain-language explanations are not the law.",
        ],
        honest:
          "These are linked in the footer of every page rather than buried. A civic platform that hides its own policies is making a claim it has not earned.",
      },
    ],
  },
];

// ======================================================================
// How the platform stays trustworthy. Separate from the feature list because it
// is the thing that makes the feature list worth anything.
// ======================================================================
export const TRUST = [
  {
    id: "verification",
    title: "Every figure tells you how much it has been checked",
    body:
      "Numbers on this site are not presented as plain facts. Each one carries a badge. 'Fact-checked against the cited source' means a second person opened the source and confirmed it. 'Unverified — pending citation review' means a researcher entered it with a source but nobody has confirmed it yet. 'Disputed' means somebody has credibly contested it and the objection is published alongside. A claim we found to be wrong stops being shown at all.",
  },
  {
    id: "sourcing",
    title: "No claim about a person without a public record behind it",
    body:
      "It is not possible to record a criminal case count, an asset figure or an attendance percentage on this site without also recording where it came from — they are stored as one thing, so a number cannot exist without its source. For the highest-risk figures, a news article is not accepted: the source has to be the public record itself, from the Election Commission, a court, Parliament's own data, a Gazette notification or a government portal.",
  },
  {
    id: "two-people",
    title: "The person who enters a figure cannot be the person who approves it",
    body:
      "Research and fact-checking are separate jobs held by separate people. A profile will not publish while any of its high-risk figures are still unverified, and the system refuses to let you approve a claim you entered yourself. This is not a matter of remembering — the site will not do it.",
  },
  {
    id: "non-partisan",
    title: "The same standard for every party",
    body:
      "Party affiliation appears on a profile the way a date of birth does: as a neutral fact. There is no rating, no score and no description of any party anywhere on this site — there is nowhere to record one. The same fields, the same sourcing rule and the same review gate apply to every representative regardless of who they belong to. Campaigning for or against a party is not permitted anywhere on the platform, including in the forum, on petitions and in the assistant's answers.",
  },
  {
    id: "moderation",
    title: "Moderation is human, explained and appealable",
    body:
      "Automated checks only decide whether something waits for a person to read it. People make removal decisions. If your post is held you are told which rule it hit and can rewrite it — it is not deleted silently. Every moderation action is recorded. A time-out from posting is always dated and always carries a reason, and it lifts itself; nobody is ever banned from reading.",
  },
  {
    id: "history",
    title: "The record cannot be quietly changed",
    body:
      "Every edit to every record is written to a log that nothing can rewrite or delete, including us. That log is what the public history tab on each page is built from. It also means that if this platform ever got something wrong and corrected it, you can see that that is what happened.",
  },
];

// ======================================================================
export const ROLES = [
  {
    name: "Anyone visiting",
    can: "Read everything, use the RTI and letter generators, ask the assistant, verify a certificate, and file a correction — all without an account.",
  },
  {
    name: "Members",
    can: "Sign petitions, file report cards, post in the forum, take volunteer tasks, register for events, take courses and earn certificates.",
  },
  {
    name: "Research team",
    can: "Add representative data, promises and research documents. Cannot publish any of it — everything goes for fact-check.",
  },
  {
    name: "Fact checkers",
    can: "Confirm a sourced claim against its source, or mark it disputed. This is the gate that lets a profile go public.",
  },
  {
    name: "Legal team",
    can: "Approve the RTI and letter templates, and review anything with defamation risk. A template cannot be used by the public until they have signed off on its current wording.",
  },
  {
    name: "Moderators",
    can: "Apply the content policy to the forum, petitions and citizen reports.",
  },
  {
    name: "Editors and content writers",
    can: "Write and publish explainers, news and the plain-language constitution text. Writers draft; editors publish.",
  },
  {
    name: "State and district admins",
    can: "Everything above, but only for their own state or district. They cannot touch another state's data.",
  },
  {
    name: "Volunteer managers",
    can: "Post tasks, verify hours and issue certificates.",
  },
];

// ======================================================================
export const NOT_FINISHED = [
  {
    title: "Most representative profiles do not exist yet",
    body:
      "Every figure has to be found in a public record, entered with its citation and confirmed by a second person before a profile goes live. That is slow by design. Delhi and Maharashtra are being built first. Researching a constituency is a real task on the volunteer board.",
  },
  {
    title: "The Constitution Library has 61 articles, not 395",
    body:
      "Each one is written, reviewed and translated by a person. Where an article is missing, the search page and the assistant both say so and send you to India Code rather than guessing.",
  },
  {
    title: "Search engines cannot read most of these pages yet",
    body:
      "Because of how the site is currently built, Google sees an empty page for the Constitution Library, representative profiles and state pages. That is a real problem for a platform whose purpose is spreading awareness, it is a known limitation, and rebuilding the public pages to fix it is the next major piece of work.",
  },
  {
    title: "Languages beyond English and Hindi",
    body:
      "Tamil, Telugu, Kannada, Malayalam, Marathi and Bengali are next, in that rough order, and depend entirely on volunteer translators. We would rather have two languages that are accurate than eight that are machine-translated.",
  },
];
