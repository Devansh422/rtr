# Right To Recall — Platform Implementation Plan

Scope: evolve the current campaign site into the described Constitutional Civic-Tech Platform (Wikipedia + Change.org + Election Commission + Reddit + GitHub + Wikipedia-History, for India, non-partisan) — built entirely on free-tier infrastructure. This document is the working plan; update it as decisions are made (mirrors how `memory/PRD.md` already tracks shipped work).

Last updated: 2026-08-09.

---

## 1. Non-negotiables (read before building anything)

The "sole purpose" section of the brief is the actual product spec — everything else is a feature to serve it. Three things follow directly from it and must be enforced structurally, not just by good intentions:

1. **Non-partisan by construction.** No feature may let the platform be read as favoring a party, religion, caste, or community. This means: the Forum, Citizen Reports, and Representative profiles need moderation gates *before* anything ships (see §7), not after abuse happens. Party affiliation is shown as a neutral fact (like an infobox), never as framing.
2. **Every factual claim about a named person must be sourced and citable.** "Criminal Cases," "Assets," "Promises," "Attendance" are defamation-risk surfaces. The rule (borrowed from Wikipedia's verifiability policy): no claim about a living person ships without a link to a public official source (ECI affidavit, PRS record, court record, Gazette notification). Anything without a source stays in "unverified — pending citation" state, visibly marked, never rendered as fact.
3. **DPDP Act 2023 compliance is a Phase-0 requirement, not a later cleanup.** The moment you collect mobile numbers, email, or volunteer PII (already happening today via `/api/volunteers`, `/api/supporters`), you need a consent notice, a privacy policy, a data retention policy, and a way to delete a user's data on request. Do this before scaling signups, not after.

---

## 2. Current state (audit)

What exists today, so the plan builds on it instead of restarting:

- **Frontend:** CRA (react-scripts) + craco, React 19, Tailwind + shadcn/ui, framer-motion, Lenis smooth scroll, react-router-dom v7. Fully client-rendered SPA (no SSR/SSG). ~20 pages, single design system ("Optimistic Civic Blueprint", documented in `design_guidelines.json`).
- **Backend:** One FastAPI file, `backend/server.py` (963 lines, flat `APIRouter`, no module boundaries). MongoDB via Motor. JSON files in `backend/content/*.json` seed Mongo collections on first boot; admin edits persist to Mongo.
- **Auth:** Single hardcoded admin (`ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars) + a separate lightweight "member" login for supporters. No RBAC, no OTP, no social login.
- **Hosting:** Single Vercel project — static frontend + FastAPI as one Python serverless function (`api/index.py`). MongoDB Atlas M0 (free).
- **Data:** Campaigns, blogs, FAQ, news, testimonials, resources, jurisdictions, myths, leaders — all hand-authored JSON, no real representative/legislative data yet.
- **What's genuinely reusable:** the join/pledge flow, certificate generation (`html-to-image`), share buttons (wa.me links, already free), the design system, the content-JSON-seeds-Mongo pattern for CMS-lite editing, and the admin shell.

This is a solid MVP shell for a "campaign site." Almost none of the Wikipedia/Election-Commission/GitHub-transparency/Reddit layers exist yet — that's the gap this plan closes.

---

## 3. The one architecture decision to make before Phase 0

**Should the public site move from CRA (client-only SPA) to a server-rendered framework (Next.js, App Router)?**

Recommendation: **yes, for the public/content side; keep the admin panel a plain SPA.**

Why this matters more than any other technical choice here: the entire vision is *content that needs to be found* — thousands of constitution articles, representative profiles, state/district pages, knowledge-centre entries, all in up to 22 languages. A pure client-rendered SPA:
- ships blank HTML to search engines and social-share crawlers (bad for "spread awareness" — the stated sole purpose),
- has no clean per-locale URL/SSR story for i18n at this scale,
- makes deep-linking to a specific article/representative slow (empty shell → fetch → render).

Next.js (or Remix — Next has the bigger ecosystem and free-tier fit with Vercel, which you already use) gives SSR/SSG for content pages, static generation for the ~thousands of constitution/representative/state pages (rebuilt on content change via ISR — still free on Vercel Hobby), and first-class i18n routing (`/hi/`, `/ta/`, …).

This is a real migration cost, so scope it honestly:
- The design system, Tailwind config, shadcn components, and most page components port over with light changes (routing hooks and data-fetching change; motion/visual code mostly doesn't).
- Do it **incrementally**: stand up Next.js as a new app, port the marketing pages first (Home, About, Join — the parts that don't yet need new data), keep the FastAPI backend and its `/api/*` contract untouched, and treat the admin panel as a separate CRA/Vite SPA indefinitely (it doesn't need SEO or i18n routing).
- If you decide the migration cost isn't worth it right now, everything else in this plan still works with CRA — you just accept worse SEO/i18n and should self-host a prerenderer (e.g. `react-snap`) as a stopgap. Flagging this as the one decision worth pausing on before Phase 0 starts (see the question at the end of this document).

---

## 4. Target architecture

**Pattern: modular monolith**, not microservices. A volunteer-run project cannot operate 20 independently deployed services on free tiers — one FastAPI app with clean internal module boundaries (own router, own service layer, own tables/collections per module) gets 90% of the benefit of microservices (separation of concerns, independent ownership by module) with none of the operational cost. Split into real services later only if a specific module (e.g. AI assistant, PDF generation) needs independent scaling.

```
frontend/            Next.js (public, SSR/SSG, i18n)   — new
admin/               Vite/CRA SPA (internal tool)        — evolves from current admin
backend/
  core/              auth, rbac, db sessions, config
  modules/
    cms/             pages, blogs, articles, media, FAQ (Mongo — flexible schema)
    constitution/    articles, plain-English/Hindi text, case law links (Postgres)
    representatives/ MLA/MP/Minister profiles, promises, attendance (Postgres)
    states/          state & district pages, campaign-status pipeline (Postgres)
    petitions/       internal petition system, signatures (Postgres)
    reports/         citizen report cards (Postgres)
    forum/           discussion forum, reputation (Postgres)
    volunteers/      volunteer portal, skills, task assignment (Postgres)
    events/          event mgmt, QR attendance, certificates (Postgres)
    academy/         courses, quizzes, certificates (Postgres)
    research/        document repository (Postgres metadata + object storage)
    tools/           RTI generator, representation generator, PIL centre (stateless + Postgres log)
    ai/              constitution assistant (RAG over constitution+case law)
    notifications/   email, push, WhatsApp-share helpers
    analytics/       event tracking, dashboards
    audit/           immutable change log (the "GitHub transparency" layer)
  search/            Meilisearch client wrapper
api/index.py         unchanged Vercel entrypoint, mounts all module routers
```

### Database: keep Mongo, add Postgres — deliberately, not by accident

MongoDB Atlas M0 stays for what it's good at: loosely structured CMS content (blog posts, FAQ, media metadata) where schema flexibility beats relational integrity.

Everything described in the brief that is fundamentally **relational and needs joins/aggregation/reporting** — representatives ↔ constituencies ↔ promises ↔ attendance ↔ parties; petitions ↔ signatures ↔ states; users ↔ roles ↔ permissions; forum threads ↔ replies ↔ reputation; citizen reports ↔ verification status ↔ government responses — will fight MongoDB's document model constantly (duplicated data, no real foreign keys, painful "state-wise dashboard" aggregations). Use **Postgres** for these modules from day one.

Free Postgres host: **Neon** (100 compute-hours/month, 0.5GB storage, autosuspends after 5 min idle — fine for a serverless FastAPI backend that's also cold-starting between requests) is the pragmatic default. If you want bundled Auth/Storage/Row-Level-Security instead of building RBAC by hand, **Supabase** (500MB DB, 500MB storage, pauses after 7 days of *zero* traffic — a daily cron ping avoids this) is the alternative; pick one, don't run both. This plan assumes **Neon + hand-rolled RBAC in FastAPI**, because RLS-per-role in Supabase is powerful but adds a second permissions system to reason about on top of the app-level RBAC you need anyway for the CMS/admin panel.

Two databases is genuine complexity — the trade-off is accepted deliberately because the relational modules are the majority of the platform's real substance (Representative DB, Promise Tracker, Campaign Dashboard, Petitions, Forum, Citizen Reports are the features that make this "Election Commission + Change.org + Reddit," not the CMS pages).

---

## 5. Free-resource matrix

Everything below is a genuinely free tier as of mid-2026 (verified before writing this plan — free tiers drift, re-check before committing budget-sensitive decisions).

| Need | Free choice | Limit / gotcha | Upgrade trigger |
|---|---|---|---|
| Frontend hosting | Vercel Hobby (Next.js) | 100GB bandwidth/mo, 10s function timeout (300s with Fluid Compute). **ToS restricts Hobby to non-commercial use** — if Donations module goes live, move to Pro (~$20/mo) | Donations live, or bandwidth exceeded |
| Backend hosting | Vercel serverless (current setup) | Same 10s/300s ceiling — long AI/PDF jobs need offloading | AI assistant / bulk PDF generation at scale |
| Backend overflow worker | Render.com free web service | 512MB RAM, spins down after 15 min idle (30–60s cold start) | Real-time or latency-sensitive jobs |
| Relational DB | Neon free tier | 0.5GB storage, 100 compute-hrs/mo, autosuspend 5 min idle | DB > 0.5GB or compute-hours exhausted |
| CMS DB | MongoDB Atlas M0 (existing) | 512MB hard cap, shared vCPU | Cap approaching |
| Interactive India map | Leaflet + OpenStreetMap tiles, or `react-simple-maps` + a free India TopoJSON | No API key, no quota | N/A — stays free indefinitely |
| Search | Meilisearch, **self-hosted** (not Meilisearch Cloud — its free tier is ~10K docs/mo, too small) | Needs its own small VM/container; Meilisearch Cloud is a 14-day trial only | Self-host RAM insufficient for full index |
| Object storage (media library, RTI PDFs) | Cloudflare R2 | 10GB storage, **zero egress fee always** — better than Atlas/S3 for a public media library | 10GB exceeded |
| CAPTCHA | Cloudflare Turnstile | Free, unlimited requests, but 20 widgets/10 hostnames cap | N/A |
| Email | Brevo | 300 emails/day free (~9K/mo) | Sustained >300/day |
| Push notifications | Firebase Cloud Messaging | Genuinely free, unlimited | N/A |
| WhatsApp sharing | `wa.me` deep links (already implemented) | No API, no cost, no message-sending capability (share-only) | Need to *send* WhatsApp messages → Meta Cloud API (has a paid tier) |
| Social login | Google/GitHub OAuth (direct, or via Supabase Auth if adopted) | Free | N/A |
| OTP login | Email OTP (via Brevo) as the free default | **SMS OTP is not free anywhere** — Supabase/Firebase Auth is free but SMS delivery is billed per-message via Twilio/MSG91/etc. | Budget available for SMS, or switch to WhatsApp OTP via Meta Cloud API's free conversation tier |
| Analytics | Umami, self-hosted (MIT license, no vendor lock-in) | Needs a small free container (Render free tier works) | Traffic outgrows free container |
| AI assistant | Google Gemini API free tier (Flash-Lite/Flash) | ~1,000 req/day (Flash-Lite) shared 250K TPM. **Free-tier prompts may be used for training/review — never send user PII** | Usage exceeds daily free quota |
| Vector store (for AI RAG) | `pgvector` extension on the same Neon Postgres | No extra service | Index size stresses the 0.5GB DB cap |
| Machine-translation draft assist | LibreTranslate, self-hosted | Needs ~8GB RAM for all languages (fine to self-host just the target subset); quality is a *draft*, not a substitute for human review | N/A — always pair with volunteer review |
| PDF/DOCX generation (RTI, representations) | WeasyPrint / ReportLab (PDF) + `python-docx` (DOCX) | Pure Python, no service, no cost | N/A |
| QR attendance | `qrcode` (Python, generate) + `html5-qrcode` (JS, scan) | Free, client-side | N/A |
| Video hosting | YouTube (unlisted/public as needed) | Free, unlimited, embeds anywhere | N/A |
| Backups | `mongodump`/`pg_dump` via scheduled GitHub Actions (public repo = unlimited free minutes; private = 2,000 min/mo) → encrypted upload to Backblaze B2 | B2 free: 10GB storage, egress capped at 3x average stored volume/month | Backup size or restore-frequency exceeds cap |
| Data sourcing (representatives) | MyNeta/ADR affidavit data, PRS Legislative Research, Sansad (Lok Sabha/Rajya Sabha) open data, ECI, data.gov.in | Free to read/cite; **check each source's reuse/attribution terms before bulk scraping** — prefer official open-data downloads over scraping | Needs a paid data-licensing arrangement only if a source explicitly requires it |

---

## 6. Roles & permissions (RBAC)

| Role | Scope | Can do |
|---|---|---|
| Super Admin | Platform-wide | Everything, incl. role assignment, audit log access |
| State Admin | One state | Manage state page, local campaign status, state volunteers/events |
| District Admin | One district | Same, scoped to district (Phase 5+, once district pages exist) |
| Research Team | Platform-wide, read/propose | Add/edit representative data, promises, research repository — goes to review queue |
| Legal Team | Platform-wide | Review PIL centre content, RTI/representation templates, moderate defamation-risk content |
| Fact Checkers | Platform-wide | Approve/reject Research Team submissions before publish (the "verifiability gate") |
| Editors | CMS scope | Publish blogs, news, constitution plain-English text (post fact-check for legal claims) |
| Content Writers | CMS scope, draft-only | Create drafts; cannot publish directly |
| Moderators | Forum + Citizen Reports | Hide/remove posts, resolve reports, apply the non-partisan content policy |
| Volunteer Managers | Volunteer module | Assign tasks, verify hours, issue certificates |

Implementation: a single `roles` + `permissions` + `user_roles` (scoped by `state_id`/`district_id` nullable) table set in Postgres, enforced via a FastAPI dependency (`require_permission("representatives:publish")`), reused by every module router. Build this once in Phase 0 — retrofitting RBAC after 10 modules exist is much more expensive.

---

## 7. The trust layer (this is what makes it "Election Commission," not just another NGO site)

- **Citation-required fields.** Any field like "criminal cases," "assets," "attendance %" is stored with a `source_url`, `source_date`, and `verification_status` (`unverified` / `fact_checked` / `disputed`). Unverified data is visually marked, never asserted as plain fact.
- **Edit history per entity** (the "Wikipedia History" pillar). Every change to a representative profile, constitution article, or promise status is an append-only audit row: who, when, before/after, source. Expose a public "history" tab per page — this is also your GitHub-style transparency layer, and it's cheap to build (one `audit_log` table + a diff view) but does more for credibility than almost anything else on this list.
- **Correction/dispute workflow.** A "Suggest a correction" button on every representative/article page, routed to Research Team → Fact Checker review. This is both a legal safeguard and a genuine engagement feature (mirrors Wikipedia talk pages).
- **Standard disclaimer**, platform-wide: information is sourced from public records (ECI affidavits, court filings, PRS data); charges are not convictions; RTR Movement does not independently investigate allegations. Put this in the footer and on every representative profile.
- **Content policy for Forum/Citizen Reports**, enforced by Moderators: no party-political campaigning, no religious/caste/communal framing, no unverified personal attacks. Publish this policy publicly — it's what lets you credibly claim "non-partisan."

---

## 8. Multilingual strategy

Don't attempt all 22 scheduled languages at once — sequence it:

1. **Phase 0–1:** English + Hindi, `i18next` + Next.js i18n routing (`/hi/...`). All new content authored bilingually from the start (UI strings + constitution plain-English text).
2. **Phase 3–4:** add Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali (largest speaker populations after Hindi) — UI strings via community-contributed translation files (a Volunteer Portal task: "Translation" skill category, already in the brief), long-form content (constitution articles, knowledge-centre entries) via LibreTranslate draft + mandatory human review before publish (never publish raw machine translation as legal/constitutional content — accuracy matters more than coverage here).
3. **Phase 5+:** remaining scheduled languages, same pipeline, prioritized by volunteer translator availability rather than a fixed order.

---

## 9. AI Constitution Assistant (design sketch)

- Retrieval-Augmented Generation, not a raw chatbot: embed constitution articles + summarized case law into `pgvector` on the Neon Postgres instance; retrieve top-k relevant chunks per question; pass to Gemini Flash with a system prompt that (a) requires citing the specific Article/case retrieved, (b) refuses to give "legal advice" and instead points to the PIL Resource Centre / a lawyer, (c) never fabricates an article number — if retrieval finds nothing relevant, say so.
- Supports the brief's example queries directly: "Can an MLA be recalled?" → retrieves Right-to-Recall knowledge-centre entries + relevant state provisions; "Explain Article 326" → retrieves that article's plain-English + case law; "Generate RTI" / "Generate Representation" → these are deterministic template-fill flows (§ tools module), not LLM generation — more reliable and zero AI cost.
- Free-tier discipline: cache repeated questions (same question asked by many users — e.g. "difference between recall and impeachment" — should hit a cache/FAQ, not the LLM, both for cost and consistency of the answer).

---

## 10. Phased roadmap

Pilot-first, not nationwide-first: brief explicitly uses Delhi and Maharashtra as examples — build the State/Representative/Campaign-Dashboard modules against those two states end-to-end before templating to all 28+8.

| Phase | Duration (est.) | Ships |
|---|---|---|
| **0 — Foundations** | 3–4 weeks | RBAC + audit log in Postgres; modularize `backend/server.py` into the module structure in §4; decide + start Next.js migration for public pages; i18n scaffolding (EN/HI); privacy policy + consent flows (DPDP compliance); Umami analytics self-hosted |
| **1 — Answer the landing-page questions** | 4–6 weeks | New hero/landing per brief (4 CTAs: Learn More / Join / Read the Constitution / Volunteer); Interactive India map (Leaflet/react-simple-maps) linking to 2 pilot state pages (Delhi, Maharashtra) showing current MLAs/MPs/state govt (seeded manually for these two states first); Constitution Library MVP — 30–50 core articles with plain English/Hindi/original text, searchable (Meilisearch self-hosted); Campaign Status Dashboard (the 8-stage pipeline) for the 2 pilot states |
| **2 — Representative accountability core** | 6–8 weeks | Representative Database for pilot states (sourced per §5, citation-gated per §7); Promise Tracker MVP; Petition system (internal, signatures + comments + share); Volunteer Portal (skills, task board) |
| **3 — Civic tools** | 6–8 weeks | RTI Generator, Representation Generator (PDF/DOCX via WeasyPrint/python-docx); PIL Resource Centre; Citizen Report Cards (with verification workflow); Discussion Forum MVP (moderated, reputation-lite) |
| **4 — Knowledge scale-out** | 8–10 weeks | Right to Recall Knowledge Centre expanded to 100+ interconnected articles; Constitutional Learning Academy (courses + quizzes + certificates); Research Centre (searchable document repository); Media Library; Event Management + QR attendance |
| **5 — Scale & AI** | ongoing | AI Constitution Assistant live; expand Representative DB + state pages beyond the 2 pilots to all states; begin district pages; multilingual expansion (Tamil/Telugu/Kannada/Malayalam/Marathi/Bengali); Analytics Dashboard (state-wise visitors, campaign progress, most-searched articles) |
| **6 — Hardening** | ongoing, parallel to 4–5 | Security review (auth, RBAC, upload handling, injection), accessibility audit, load testing against free-tier ceilings, legal review of disclaimers/content policy, backup/restore drill |

Do not start Phase 2+ modules before Phase 0's RBAC + audit log exist — every later module depends on both, and retrofitting them is the most expensive mistake available here.

---

## 10b. Phase 0 progress (backend complete, 2026-07-28)

Shipped:

- **Modular monolith backend.** `backend/server.py` went from 963 lines of everything to ~100 lines of app assembly. Routes now live in `backend/modules/{auth,members,staff,cms,states,submissions,uploads,analytics,audit}/`, cross-cutting infrastructure in `backend/core/`. The one-way dependency rule (modules → core, never sideways) is stated in both package docstrings.
- **Postgres relational layer** (`core/models.py`, 9 tables): users, roles, permissions, role_permissions, user_roles, states, districts, audit_log, platform_meta. SQLAlchemy 2.0 async, portable types so tests run on SQLite.
- **RBAC** (`core/permissions.py`, `core/rbac.py`, `core/deps.py`): 33 permissions, 11 roles, geographic scoping (state/district), rank-based privilege-escalation guard, last-Super-Admin protection. The registry is static Python and self-validates at import.
- **Audit log** (`core/audit.py`): append-only, field-level diffs with secret redaction, internal vs public views (public omits the contributor's identity).
- **Geography** (`core/geography.py`): all 28 states + 8 UTs with ISO codes, `has_legislature` flag, Delhi/Maharashtra flagged as pilots, plus the 8-stage campaign pipeline.
- **Alembic migrations** + `python -m backend.scripts.migrate`; DDL never runs from the serverless function.
- **DPDP groundwork:** `DELETE /api/me/data` (real erasure across all member collections, in one place so later modules must extend it), IP addresses hashed rather than stored in the audit log.
- **A working vertical slice** proving the stack: `PUT /api/admin/states/{code}/campaign` enforces permission → geographic scope → mandatory citation → domain rule (no state bill in a UT without an assembly) → audited change → public history.

Verified: 47 routes (28 pre-existing, byte-identical contract; 19 new), 38 new unit tests passing, migration schema matches the models exactly (9/9 tables, all columns), Vercel entrypoint imports clean.

Not yet done in Phase 0: Next.js migration, i18n scaffolding, self-hosted Umami, and the public-facing privacy policy / consent UI.

## 10c. Phases 1-5 progress (all feature modules shipped, 2026-08-09)

Every module in the §4 architecture now exists, is wired, tested and has a public UI.

**Backend — 14 new modules, 180 API routes (up from 47), 43 tables (up from 9).**

| Module | What shipped |
|---|---|
| `constitution/` | Articles with verbatim text, plain English + Hindi, case law, "why this matters for recall", parts index, draft/publish gate, public history. 47 articles seeded bilingually. |
| `representatives/` | Profiles, constituencies, parties, and the **citation-gated claim store** — one row per (representative, field, period), each carrying its own source and verification status. 17 tracked fields, 8 requiring a primary public record. Fact-check queue. Promise Tracker with two independent citations per promise. |
| `corrections/` | Generic "Suggest a correction" against any entity, with the unresolved/resolved disclosure split described below. |
| `petitions/` | Petitions, signatures (one per verified member, enforced by constraint), milestones, delivery evidence, aggregate export. |
| `reports/` | Citizen Report Cards, moderation-before-publication, corroboration, government response as a first-class field, per-place scorecard with a sample-size floor. |
| `forum/` | 7 categories, threads, one-level replies, upvotes only, reputation gates, moderator queue, time-boxed mutes. |
| `volunteers/` | Skills, task board with acceptance criteria, claimed/submitted/verified pipeline, hours claimed vs verified kept separate, service certificates. |
| `events/` | Events, registration, **per-ticket** QR check-in (not per-event), attendance sheet, participation certificates. |
| `academy/` | Courses, lessons cross-linked to articles, quizzes graded server-side, completion certificates. One starter course seeded. |
| `research/` | Research Centre and Media Library in one repository, licence recorded per item, host-or-link decision explicit. |
| `tools/` | RTI application / first appeal / second appeal, representation, department letter, recall demand letter. Legal-review gate on every template. Nothing a citizen types is stored. |
| `ai/` | Constitution Assistant: retrieval-grounded, four hard refusal rules in code, answer cache that staff can correct and pin, coverage-gap report. |
| `legal/` | Privacy policy, content policy, disclaimer and consent records, all served from the API. |
| `search/` + `certificates/` | Site-wide search over the shared index; public certificate verification. |

**Core additions** (`backend/core/`): `citations.py` (the verifiability gate),
`moderation.py` (the non-partisan content policy as code), `search.py` (shared index
— the seam that keeps §4's one-way rule intact), `certificates.py`, `documents.py`
(DOCX via stdlib zip + browser print-to-PDF; see its docstring for why not
WeasyPrint), `notify.py`, `limits.py`, `i18n.py`, `erasure.py`.

**Frontend**: 26 new pages, i18n scaffolding (EN/HI authored, not machine
translated), an India tile-grid map, the campaign dashboard, shared primitives that
make it structurally hard to render an unverified claim as fact, and the DPDP consent
notice wired into all three signup forms.

**Verified**: 156 unit/API tests passing (38 Phase-0 + 118 new), migration applies
and rolls back cleanly with schema matching the models exactly (43/43 tables, no
column drift), frontend builds clean.

### Decisions taken during this phase, and why

1. **Search runs on Postgres, not Meilisearch.** §5 picks self-hosted Meilisearch,
   which needs a container this project does not have. For a few thousand short
   documents a scan with Python-side ranking is the correct amount of machinery. The
   Meilisearch path is implemented behind the same interface and switches on with an
   env var. Trigger: ~50k docs or >300ms warm queries.
2. **DOCX + browser print, not server-rendered PDF.** These documents must work in
   Devanagari. WeasyPrint needs native libraries that do not fit a Vercel function,
   and ReportLab mangles conjuncts without a shaping engine. DOCX is a zip of XML
   (stdlib, full Unicode) and the browser's print dialog shapes Devanagari correctly
   for free.
3. **No representative data seeded.** Publishing claims about named living people is
   exactly what the citation and fact-check gates exist to govern; shipping a seed
   file of people would bypass them. Constituencies likewise come from ECI
   delimitation orders via the bulk importer, not from memory.
4. **A tile-grid map, not a choropleth.** India's borders are politically contested
   and a boundary file has to be chosen deliberately, not picked up incidentally.
   Equal tiles also give every state the same visual weight, which is the correct
   rhetoric for "any state legislature can act on this under Article 328".
5. **The erasure registry.** One function that knows thirteen schemas is a function
   that will miss the fourteenth, and the submissions module cannot import the forum
   without breaking §4. Core now owns the order and each module registers its own
   step; a test asserts every table holding a `citizen_id` is covered.

## 11. Immediate next steps (concrete, for the next work session)

1. ~~Confirm the Next.js migration and Neon-Postgres decisions~~ — done, see "Decisions confirmed" below.
2. ~~Stand up Postgres + Alembic; create roles/permissions/user_roles/audit_log~~ — done, §10b.
3. ~~Split `backend/server.py` into the `backend/modules/...` structure~~ — done, §10b.
4. **Create a real Neon project and run the migration against it.** Everything is verified against SQLite and an in-process ASGI harness; it has not yet touched a real Postgres. Then add `DATABASE_URL` to Vercel and confirm `GET /api/health` reports `"postgres": true`.
5. ~~Build the feature modules in §4~~ — done, §10c.
6. **Scaffold the Next.js app.** Still outstanding and now the largest single gap: 26 new pages ship blank HTML to crawlers, which directly undercuts the "spread awareness" purpose. The API contract is stable and locale-aware, so the migration is a frontend-only project.
7. **Add the admin UI for the new modules.** All 70 admin endpoints exist and are covered by tests; the admin SPA still only exposes the pre-Phase-0 CMS screens. Priority order by how much a volunteer needs them: fact-check queue → corrections queue → representative data entry → moderation queues → volunteer submissions.
8. **Import the pilot states' constituencies** from the ECI delimitation orders via `POST /api/admin/constituencies/bulk`, then enter and fact-check the first representative profiles end to end. This is what proves the citation gate against real data.
9. ~~Write the privacy policy and consent UI~~ — done: `/privacy`, `/content-policy`, `/disclaimer`, and the consent notice on all three signup forms.
10. **Self-host Umami** for analytics, still outstanding from Phase 0.

---

## Decisions confirmed (2026-07-28)

1. **Next.js migration:** confirmed — proceed now, per §3.
2. **Database strategy:** confirmed — Postgres (Neon) added alongside MongoDB for relational modules, per §4.

Both are now locked assumptions for Phase 0 (§10–11), not open questions.
