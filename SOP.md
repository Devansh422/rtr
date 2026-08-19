# Standard Operating Procedure (SOP)
## Right to Recall Movement — Constitutional Civic-Tech Platform

| Field | Value |
| --- | --- |
| Document | Standard Operating Procedure, whole application |
| Applies to | `rtr` repository — React frontend + FastAPI backend, deployed as one Vercel project |
| Audience | Platform owners, admins, editors, research/fact-check team, legal team, moderators, volunteer managers, developers |
| Last updated | 2026-08-19 |
| Source of truth | This file for *procedure*. `IMPLEMENTATION_PLAN.md` for *architecture rationale*, `DEPLOY.md` for *deployment detail*, `memory/PRD.md` for *shipped history*. Where those disagree with this file, they are the technical authority and this file must be corrected. |

---

## 1. Purpose and scope

### 1.1 Purpose
This SOP defines how the Right to Recall platform is set up, operated, changed, moderated and audited. It exists so that any authorised person can perform a routine task the same way every time, and so that no step in the trust chain (citation → fact-check → publish → audit) is skipped by accident.

### 1.2 Scope
Covers the complete application:
- the public React SPA (`frontend/`),
- the FastAPI modular monolith (`backend/`) served through one Vercel Python function (`api/index.py`),
- MongoDB (CMS content, submissions, throttles) and Postgres/Neon (identity, RBAC, all relational modules, audit log),
- operational scripts (`backend/scripts/`), migrations, seeds, bulk imports and the demo dataset,
- editorial, moderation, legal-review and data-protection workflows.

### 1.3 Governing principles (non-negotiable — `IMPLEMENTATION_PLAN.md` §1)
1. **Non-partisan by construction.** No feature, content item or moderation decision may position the platform as favouring a party, religion, caste or community. Party affiliation is displayed as a neutral fact only.
2. **Every factual claim about a named person is sourced.** No claim about a living person is published without a link to a public official source. Unsourced or unreviewed claims stay visibly marked `unverified`; they are never rendered as plain fact.
3. **DPDP Act 2023 compliance is built in, not retrofitted.** Consent notice on every form, published privacy policy, working erasure endpoint, no PII sent to third-party AI.

Any procedure here that appears to conflict with these three is wrong; escalate to the platform owner rather than working around it.

---

## 2. System overview

### 2.1 Architecture at a glance

```
                     one Vercel project, one origin
   ┌──────────────────────────────────────────────────────────────┐
   │  /(.*)      → frontend/build (React SPA, CRA + craco)         │
   │  /api/(.*)  → api/index.py  → backend/server.py (FastAPI)     │
   └──────────────────────────────────────────────────────────────┘
                          │                    │
                MongoDB Atlas (M0)      Postgres (Neon)
                CMS content, form       identity, RBAC, geography,
                submissions, member     all feature modules,
                sign-in records,        append-only audit log
                rate-limit counters
```

Optional integrations, each degrading one feature rather than breaking the app:
- **Brevo** — transactional email. Unset → sends are logged no-ops; every flow that emails also shows the same information on screen.
- **Gemini** — Constitution Assistant prose answers. Unset → the assistant returns ranked cited sources only.
- **Meilisearch** — site search. Unset → search runs on Postgres.

`GET /api/health` reports what a running instance actually has.

### 2.2 Technology
| Layer | Technology |
| --- | --- |
| Frontend | React 19, CRA + craco, Tailwind, shadcn/ui + Radix, framer-motion, Lenis, react-router-dom v7, axios, TanStack Query |
| Backend | FastAPI 0.110, Starlette, Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Motor (MongoDB), Alembic, PyJWT, bcrypt, qrcode, httpx |
| Hosting | Vercel — static build plus one Python serverless function (`maxDuration` 30s) |
| Data | MongoDB Atlas free tier; Neon Postgres free tier (autosuspends after 5 min idle) |
| Tests | pytest with xdist (2 workers, `loadscope`), in-memory SQLite — no infrastructure required |

### 2.3 Repository layout
| Path | Contents |
| --- | --- |
| `api/index.py` | Vercel entrypoint; imports the app, never duplicates it |
| `backend/server.py` | App assembly only — lifespan, CORS, health, router mounting |
| `backend/core/` | Shared infrastructure: config, db, mongo, deps, rbac, permissions, audit, citations, moderation, search, certificates, documents, notify, limits, i18n, erasure, geography, membership, security, bootstrap |
| `backend/modules/<name>/` | One feature per folder: `router.py`, usually `models.py`, sometimes `service.py` |
| `backend/content/` | Seed content (CMS JSON, constitution, import seeds) plus `content/demo/` |
| `backend/migrations/versions/` | Alembic migrations (3 to date) |
| `backend/scripts/` | `migrate`, `load_demo`, `import_representatives`, `import_manifesto`, `import_research`, `harvest_gov_sources`, `import_datagovin` |
| `backend/tests/` | `backend_test`, `test_admin`, `test_core_rbac`, `test_platform_modules` |
| `frontend/src/` | `pages/`, `components/`, `lib/` (API clients `api.js`, `adminApi.js`, `memberApi.js`, `platformApi.js`), `context/` (admin + member auth, locale, join) |
| `frontend/build/` | Build output — **never commit or deploy a locally built copy** |
| `DEPLOY.md`, `IMPLEMENTATION_PLAN.md`, `memory/PRD.md`, `design_guidelines.json`, `test_result.md` | Deployment, architecture, history, design system, test protocol |

**Dependency rule (enforced at review):** modules import from `core`; `core` never imports from `modules`; modules never import each other. Cross-module needs go through a core seam (`search.index()`, the `erasure` registry, `certificates`, `notify`).

### 2.4 Module inventory (≈229 API routes)
| Module | Routes | Responsibility |
| --- | --- | --- |
| auth | 4 | Admin login, member login (access code), session/me |
| members | 4 | Member profile, consent, data erasure |
| staff | 8 | Staff accounts, role grant/revoke, permission listing |
| cms | 8 | Generic CRUD over 10 Mongo content types |
| states | 5 | 36 states/UTs, campaign pipeline stage, public history |
| submissions | 6 | Join/supporter, volunteer, contact, newsletter forms |
| uploads | 2 | Admin media upload/serve (6 MB cap) |
| analytics | 2 | Pageview tracking and admin report |
| audit | 2 | Internal audit view; public per-entity history |
| legal | 9 | Privacy, content policy, disclaimer, consent notices and records |
| constitution | 8 | 61 bilingual articles, parts, draft/publish, history |
| representatives | 26 | Profiles, constituencies, parties, claim store, fact-check queue |
| corrections | 6 | "Suggest a correction" on any entity, review queue |
| manifesto | 25 | Elections, manifestos, promises, RTI chain, replies, documents, assessments |
| search | 3 | Cross-module search, suggest, coverage |
| petitions | 15 | Directory, national petition, sign / sign-public, by-state, export |
| reports | 10 | Citizen Report Cards, corroboration, government response, scorecards |
| forum | 13 | 7 categories, threads, replies, upvotes, moderation |
| volunteers | 15 | Tasks, claims, verified hours, certificates |
| events | 12 | Events, registration, QR tickets, check-in, certificates |
| tools | 12 | RTI / appeal / representation / recall-letter generators, legal-review gate |
| academy | 14 | Courses, lessons, server-graded quizzes, certificates |
| research | 9 | Research Centre / Media Library, licence per item |
| certificates | 4 | Public verification, download, print |
| ai | 7 | Constitution Assistant, answer cache, coverage gaps |

### 2.5 Public route map (SPA)
`/` · `/about` · `/campaigns` · `/campaigns/:id` · `/blog` · `/blog/:id` · `/volunteer` · `/knowledge` · `/resources` · `/contact` · `/join` · `/constitution` · `/constitution/:number` · `/representatives` · `/representatives/:slug` · `/my-representatives` · `/promises` · `/manifesto` (+ `/promises`, `/rti`, `/replies`, `/documents`, `/dashboard`, `/promise/:code`) · `/states` · `/states/:slug` · `/petition` (national) · `/petitions` · `/petitions/:slug` · `/reports` · `/reports/:slug` · `/forum` · `/forum/:slug` · `/tools` · `/tools/:key` · `/academy` (+ course, lesson, quiz) · `/research` · `/volunteer-portal` · `/events` · `/events/:slug` · `/ask` · `/search` · `/certificates/:code` · `/docs` · `/privacy` · `/content-policy` · `/disclaimer` · `/login` · `/dashboard` · `/admin/login` · `/admin`

---

## 3. Roles, responsibilities and access

### 3.1 Role matrix (`backend/core/permissions.py` — 11 roles, 37 permissions)
| Role | Rank | Responsible for | Cannot do |
| --- | --- | --- | --- |
| Super Admin | 100 | Platform ownership, staff accounts, role grants, audit log, all publishing | — |
| State Admin | 60 | One state: campaign stage, volunteers, events, petitions, campaign/news content, submissions | Act outside its state scope |
| District Admin | 50 | One district: volunteers, events, submissions, scoped state edits | Act outside its district |
| Fact Checker | 45 | Verifying sourced claims; publishing representatives, promises, manifesto entries; verifying reports; reading audit | Verify a claim they entered themselves |
| Legal Team | 45 | Template legal review, disputed claims, defamation risk, corrections, resources, audit read | Publish representative data |
| Research Team | 40 | Entering representatives, promises, constitution drafts, manifesto entries, research documents; reviewing corrections | Publish any of it |
| Editor | 35 | Constitution edit/publish, media, academy, research | Touch representative claims |
| Moderator | 30 | Forum and citizen-report moderation, mutes | Publish factual claims |
| Volunteer Manager | 30 | Volunteer tasks, verified hours, events, certificates, notifications | Publish factual claims |
| Content Writer | 20 | Drafting CMS content | Publish |
| Analyst | 10 | Read-only analytics | Any write |

### 3.2 Structural guards (expect these; they are not bugs)
- **Escalation guard.** Nobody may grant a role ranked at or above their own, nor grant a permission they do not hold.
- **Last Super Admin protection.** The final Super Admin cannot be revoked; the bootstrap account cannot be deleted or deactivated from the UI (change `ADMIN_EMAIL` and redeploy instead).
- **Separation of duties on facts.** The person who entered a claim cannot verify it, and publishing a representative is blocked while any high-risk claim is unverified.
- **Legal gate on templates.** Editing an RTI/representation template resets it to `draft` until someone with `legal.review` approves it again.

### 3.3 Procedure — granting access
1. Confirm the requester's task and pick the **narrowest role** that covers it.
2. Super Admin creates the account: `POST /api/admin/users` (admin panel → Team).
3. Assign the role: `POST /api/admin/users/{user_id}/roles`, with state/district scope where the role is scoped.
4. Verify: the user signs in at `/admin/login` and sees only their screens.
5. The grant is written to the audit log automatically — no separate record needed.
6. **Off-boarding (same day access ends):** revoke roles (`DELETE /api/admin/users/{user_id}/roles/{role_key}`), then deactivate or delete the account (`DELETE /api/admin/users/{user_id}`).

---

## 4. Environments

| Environment | Purpose | Notes |
| --- | --- | --- |
| Local | Development and testing | Local Mongo + local/Neon Postgres; SQLite for the test suite |
| Vercel Preview | Branch and PR builds | **Shares production environment variables, therefore the production database**, unless given its own Vercel project and `DATABASE_URL`. Treat preview writes as real. |
| Production | Public site | Default branch auto-deploys on push |

**Rule:** never run `load_demo --load` or a bulk import against a `DATABASE_URL` used by any public deployment.

---

## 5. SOP — Local development setup

**Prerequisites:** Python 3.12 (3.10 is the floor), Node 18+, a reachable MongoDB, optionally Neon Postgres.

```sh
# 1. Python environment
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r backend/requirements-dev.txt

# 2. Backend configuration
cp backend/.env.example backend/.env
#    fill MONGO_URL, DB_NAME, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL

# 3. Schema + reference data (when DATABASE_URL is set)
.venv/bin/python -m backend.scripts.migrate

# 4. Run the API on port 3001 (matches frontend/.env)
.venv/bin/uvicorn backend.server:app --reload --port 3001

# 5. Frontend
cd frontend && npm install --legacy-peer-deps && npm start   # http://localhost:3000
```

Notes:
- `--legacy-peer-deps` is required: `react-day-picker@8` declares a peer range excluding React 19.
- `frontend/.env` sets `REACT_APP_BACKEND_URL=http://localhost:3001` because the dev server and API are different origins. This file must never influence a deployed build.
- `AUTO_CREATE_TABLES=1` builds tables from the models for local work only. **Never set it in a deployed environment** — it diverges the live schema from migration history.
- Verify with `curl localhost:3001/api/health`.

---

## 6. SOP — Initial deployment (go-live)

Perform in order.

1. **MongoDB Atlas.** Create an M0 cluster. Add a DB user with read/write on any database (avoid `@ : / ?` in the password or percent-encode it). Network Access → `0.0.0.0/0`, because serverless functions have no fixed egress IP. Copy the connection string **without** the database name (`DB_NAME` is passed separately).
2. **Neon Postgres.** Create a project. Copy the connection string **verbatim**, including `?sslmode=require`. Do not hand-edit it: the app adds the async driver prefix and translates the parameters itself.
3. **Apply the schema from your machine, before the first deploy:**
   ```sh
   DATABASE_URL='postgresql://...' MONGO_URL='mongodb+srv://...' DB_NAME=rtr_movement \
     JWT_SECRET=... ADMIN_EMAIL=... ADMIN_PASSWORD=... \
     .venv/bin/python -m backend.scripts.migrate
   ```
   This runs `alembic upgrade head`, reconciles the role/permission registry, seeds all 36 states and UTs, and creates the Super Admin.
4. **Generate a real `JWT_SECRET`** (`openssl rand -hex 32`). It signs admin *and* member tokens and salts the audit log's IP hashes.
5. **Rotate `ADMIN_PASSWORD`** before the site is public — see §13.2.
6. **Set `CORS_ORIGINS`** to your own domain(s). The default `*` lets any site call the API with a member's browser.
7. **Vercel project.** Add New → Project → import the repo.
   - Root Directory = repo root (**not** `frontend/`) — the function needs `backend/**` beside it.
   - Framework Preset = **Other**. `vercel.json` sets `"framework": null` deliberately; auto-detection makes the Python function serve the site and the static build stops being served.
   - Leave Build & Development Settings **empty** — dashboard fields override `vercel.json`.
   - Add every environment variable (Appendix A) **before** the first deploy, or every `/api/*` request 500s until you add them and redeploy.
8. **Deploy**, then verify:
   ```sh
   curl https://YOUR-DOMAIN/api/health      # want "postgres": true AND "schema": true
   ```
9. Sign in at `/admin/login`; confirm the new password works and the old one does not.
10. Hard-refresh a deep link (e.g. `/campaigns`) to confirm the SPA fallback rewrite is intact.

**Never deploy a locally built `frontend/build`.** A local `.env` bakes `localhost:3001` into the bundle; let Vercel build it, where the API base correctly resolves to the relative `/api`.

---

## 7. SOP — Routine release

1. Work on a branch and open a PR. Review must confirm: the dependency rule holds, new admin routes declare a permission, citation/moderation gates are not bypassed, tests are added.
2. Run checks locally:
   ```sh
   .venv/bin/python -m pytest backend/tests      # config-pinned: -n 2 --dist loadscope
   cd frontend && npm run verify                 # lint + prettier check + build
   ```
3. **Check the diff for new files under `backend/migrations/versions/`.**
   - **If present:** run `python -m backend.scripts.migrate` against the target database **first**, then push. Migrations here are additive, so deployed code keeps working against the new schema. Pushing first leaves a window where affected endpoints 500.
   - If absent: push.
4. Merge to the default branch; Vercel deploys automatically.
5. Verify: `curl https://YOUR-DOMAIN/api/health`, then spot-check one page per area the release touched.
6. If `requirements.txt` changed, confirm `api/requirements.txt` stays byte-identical (a test enforces this) and `httpx` stays pinned — the Gemini, Brevo and Meilisearch clients import it defensively and degrade **silently** without it.

### 7.1 Rollback
Vercel → Deployments → promote the previous production deployment. Because migrations are additive, a code rollback is safe without a schema rollback. Do not downgrade the schema unless the migration author documented a safe path.

---

## 8. SOP — Database and migrations

| Task | Command / action |
| --- | --- |
| Apply schema + reconcile registry and seeds | `python -m backend.scripts.migrate` |
| Apply schema only | `cd backend && alembic upgrade head` |
| Author a migration | Add under `backend/migrations/versions/`; verify column-for-column against the models |
| Verify a deployment's schema | `GET /api/health` → `"schema": true` |

Rules:
- The serverless function **never** migrates. A function racing to migrate on cold start is how a database ends up half-migrated.
- `postgres: true, schema: false` means "connected, tables missing" — run the migration.
- Mongo collections are seeded from `backend/content/*.json` **only when empty**, so editors' changes are never overwritten by a redeploy.
- Postgres seeding is idempotent and race-tolerant, fingerprinted in `platform_meta` so later cold starts skip it in one query.

### 8.1 Seeded on first boot
| Seeded | Count | Source |
| --- | --- | --- |
| Permissions / roles | 37 / 11 | `core/permissions.py` |
| States and UTs | 36 | `core/geography.py` |
| Districts (pilot states) | 47 — Delhi 11, Maharashtra 36 | `seed_modules.py` |
| ECI-recognised national parties + Independent | 6 + 1 | `seed_modules.py` |
| Constitution articles | 61, bilingual, published | `content/constitution.json` |
| Forum categories | 7 | `modules/forum/models.py` |
| RTI / representation templates | 6, legal-approved | `modules/tools/seed_templates.py` |
| Starter course | 1 (4 lessons, 6-question quiz) | `seed_modules.py` |
| National petition | 1, bilingual, opens on first boot, never overwritten | `seed_modules.NATIONAL_PETITION` |

**Deliberately never seeded:** representative profiles and constituencies. Shipping either bypasses the exact gates the platform exists to demonstrate. Constituencies are imported from ECI delimitation orders via `POST /api/admin/constituencies/bulk` with a source URL on every row.

---

## 9. SOP — Content operations

### 9.1 CMS content (campaigns, blogs, news, FAQ, testimonials, resources, leaders, jurisdictions, myths, opportunities)
1. Sign in at `/admin/login` → Content Manager.
2. Create or edit the item (`POST`/`PUT /api/admin/content/{ctype}`); Content Writers draft, Editors publish.
3. Changes are stored in MongoDB and are permanent — JSON files only seed empty collections.
4. Tone check before publishing: hopeful, non-partisan, fact-based, action-oriented; no invented numbers; no party framing.

### 9.2 Constitution articles
1. Research Team edits an article (`PUT /api/admin/constitution/articles/{number}`) with verbatim text, plain-English and Hindi renderings, case law and the "why this matters for Right to Recall" note.
2. Editor publishes (`POST /api/admin/constitution/articles/{number}/publish`).
3. Every change is audited; the public sees it at `/constitution/:number` with a history view that shows the change and its citation but never names the contributor.
4. Editing a seeded article through the panel is permanent — reseeding only inserts missing rows.

### 9.3 Representative profiles — the fact-check chain (highest-risk workflow)
This is the workflow the platform's credibility rests on. It cannot be shortened.

1. **Enter** — Research Team creates the profile as a **draft** (`POST /api/admin/representatives`) and adds claims (`PUT /api/admin/representatives/{rep_id}/claims`). One row per (representative, field, period), each carrying its own `source_url`, `source_date` and verification status. 17 tracked fields; 8 are high-risk (criminal cases, assets, liabilities, attendance, and similar) and **require a primary public record** — an ECI affidavit, court record, PRS record or Gazette notification. A news report *about* an affidavit is not the affidavit.
2. **Queue** — every new claim lands `UNVERIFIED` and renders behind a "pending citation review" marker. There is no flag that skips this.
3. **Verify** — a Fact Checker works `GET /api/admin/factcheck/queue`, opens each cited source, and records the outcome (`POST /api/admin/factcheck/claims/{claim_id}`): accepted, disputed or retracted, with reasoning. **The person who entered a claim cannot verify it.**
4. **Publish** — `POST /api/admin/representatives/{rep_id}/publish`. If it refuses, the response lists the claims still unverified: that is the gate working, not a bug. Either a Fact Checker confirms each against its source, or the claim is removed.
5. **Disclose** — the profile carries the standing disclaimer: information is sourced from public records; charges are not convictions; the Movement does not independently investigate allegations.
6. **Audit** — the whole chain is in the append-only log: who, when, field-by-field before/after, and the source URL. Public history is exposed per entity without naming contributors.

### 9.4 Promises and the manifesto/RTI chain
- A promise entry requires **two independent citations**: that the promise was made, and what became of it. Adverse statuses need a primary source.
- Seven statuses exist, not two. A status or assessment is the platform's own conclusion about a government and lives in a separate table — **no bulk process can write one**. Imported promises read "status not established from available records" until a human publishes an assessment against the records.
- The RTI chain is modelled end to end: application → questions → responses → replies → attached records. A reply-due date is computed at 30 days from filing (s.7(1), RTI Act) when a source file omits it.
- Publishing an assessment: `POST /api/admin/manifesto/promises/{promise_id}/assessment`, by someone holding `manifesto.publish` (Fact Checker or Super Admin).

### 9.5 Corrections and disputes
1. Anyone — including anonymous visitors — may submit a correction on any entity (`POST /api/corrections`), rate-limited to 10 per 3 hours.
2. Unresolved submissions are **disclosed as a fact without their text**, so the existence of an objection is public but an unreviewed allegation is not.
3. Research Team or Legal Team reviews from `GET /api/admin/corrections` and resolves (`POST /api/admin/corrections/{correction_id}`).
4. On resolution, both the objection and the reviewer's reasoning are published.
5. Target: triage within 7 days; anything alleging defamation goes to Legal Team the same day.

### 9.6 Forum moderation
- 7 categories; **upvotes only** (downvotes become pile-ons). Reputation gates abuse-prone actions and nothing else.
- `core/moderation.py` triages every submission: publish, hold for a Moderator, or refuse outright. Almost everything flagged lands in the middle bucket, because a keyword cannot distinguish criticism of a government from an attack on a community.
- Held posts remain visible to their author **with the reason**.
- Moderator procedure: work `GET /api/admin/forum/queue`; act with `POST /api/admin/forum/threads/{id}/moderate` or `.../replies/{id}/moderate`; persistent abuse → `POST /api/admin/citizens/{citizen_id}/mute` (reversible via `DELETE`).
- Moderate against the published content policy (`/content-policy`): no party-political campaigning, no religious/caste/communal framing, no unverified personal attacks.

### 9.7 Citizen Report Cards
- Nothing auto-publishes. Reports carry corroboration counts, and a per-place scorecard is withheld below a sample-size floor.
- Government response is a first-class field: record it via `POST /api/admin/reports/{report_id}/response`.
- Verification: `POST /api/admin/reports/{report_id}/verify` (`reports.verify`, held by Fact Checker/Super Admin).

### 9.8 Petitions
- `/petition` is the flagship national petition, resolved through `GET /api/petitions/national` from one constant (`NATIONAL_PETITION_SLUG`) — `national` also works as a slug alias on every `/petitions/{slug}/*` route.
- **One-step signing** (`POST /petitions/{slug}/sign-public`) creates a member account through `core/membership.ensure_supporter` and signs in one request, returning a session so the signer can withdraw without hunting for an access code. Uniqueness is a database constraint on (petition, citizen).
- The endpoint **refuses an address that already has an account** and redirects to login — the returned session would otherwise hand over somebody else's dashboard and their erasure rights.
- Signatures are a count of **accounts, not verified people** (no email confirmation exists yet). The page states this; do not remove that wording or quote the number as verified individuals.
- State-wise breakdown groups states by the **statutory zonal councils** (States Reorganisation Act 1956; North Eastern Council Act 1971), never a home-made grouping. Percentages are of signatures that carry a state, with "not stated" shown alongside.
- Exports are **aggregate only** (`GET /api/admin/petitions/{petition_id}/export`). Never export signer identities.

### 9.9 Volunteers, events, academy
- Volunteer hours are claimed by the volunteer (`POST /me/volunteer/assignments/{id}/submit`) and **verified** by a Volunteer Manager (`POST /api/admin/volunteer/submissions/{assignment_id}/verify`) before they count.
- Events issue per-ticket QR codes; check-in via `POST /api/admin/events/{event_id}/checkin`. The ticket code is always shown as text, so check-in works even if QR rendering is unavailable.
- Academy quizzes are **server-graded**; certificates issue automatically on pass.
- All three issue certificates with publicly verifiable codes at `/certificates/:code`. A certificate is a database row first and a document second — the printable output is generated on demand, so nothing can drift. Revoke with `POST /api/admin/certificates/{code}/revoke`.

### 9.10 Research Centre / Media Library
- Every item needs a `source_url` — a catalogue entry with no link to the original is an unverifiable assertion, and this library is what the AI assistant grounds its answers in.
- `licence` decides whether a copy may be hosted or only linked; it defaults to `linked_only`, and a row supplying `file_url` **without** a stated licence is refused rather than guessed.
- Publish with `POST /api/admin/research/documents/{document_id}/publish` (`research.manage`).

### 9.11 Document tools (RTI, appeals, representation, recall demand)
- 6 legal templates, each behind a **legal-review gate**. Editing one (`PUT /api/admin/tools/templates/{key}`) resets it to `draft`; a `409 "awaiting legal review"` on the public side means exactly that. Someone with `legal.review` approves via `POST /api/admin/tools/templates/{key}/review`.
- Changing `seed_templates.py` in the repo **does** reach the deployed template and resets it to draft, so a redeploy can never put unreviewed legal wording in front of the public.
- Output is DOCX (stdlib zip) plus browser print-to-PDF — chosen because PDF libraries either mangle Devanagari or need native libraries that do not fit a Vercel function.
- **Nothing a citizen types into a generator is stored.**

### 9.12 Constitution Assistant (AI)
- Retrieval-grounded over the published library, with four refusal rules enforced in code: no sources → no answer; no legal advice; no PII leaves the platform; degrade rather than fail.
- The backend strips phone numbers, email addresses and ID numbers from a question before it leaves the platform. Free-tier prompts may be retained by the provider, and the privacy policy says so. **Do not weaken this.**
- Without `GEMINI_API_KEY`, or when the free quota is exhausted, the assistant returns the ranked cited sources instead of prose. Both are expected operating conditions.
- Answers are cached and **correctable**: review at `GET /api/admin/assistant/cache`, edit with `PUT`, delete with `DELETE`. Coverage gaps (questions the library cannot answer) are reported at `GET /api/admin/assistant/gaps` — work that list into the research backlog monthly.

---

## 10. SOP — Bulk imports

All importers share one shape: file in, `--dry-run` first, unpublished unless `--publish` is typed, safe to re-run.

| Script | Fills | Refuses |
| --- | --- | --- |
| `import_representatives` | Representative profiles and sourced claims | High-risk claims from a secondary source; overwriting a fact-checked value |
| `import_manifesto` | Promises, RTI applications, questions, answers, replies, records | Any status or assessment; a record with no provenance |
| `import_research` | Research Centre / Knowledge Hub library | A row with no `source_url`; hosting a copy with no stated licence |
| `harvest_gov_sources` | Discovers documents on official sites, writes an import CSV | Any URL `robots.txt` disallows; any site that 403s an honestly-identified agent |
| `import_datagovin` | Catalogues data.gov.in datasets via the official API | Nothing, but upstream 502s are reported, never silently dropped |

### 10.1 Standard procedure
1. Obtain the source file from a **published, downloadable** dataset. These are importers, not scrapers: parsing a published file is stable and attributable; parsing someone's HTML is neither and needs a licence review first.
2. `--list-sources` / `--template` to see the expected shape.
3. **Always `--dry-run` first.** Nothing is written and you see exactly what would change.
4. Run for real. Review the conflict report — a fact-checked value that disagrees with the file is reported for a human, never overwritten.
5. Route everything imported through §9.3 or §9.4 before publishing.

Examples:
```sh
.venv/bin/python -m backend.scripts.import_representatives --list-sources
.venv/bin/python -m backend.scripts.import_representatives \
    --source myneta_affidavits --file uttarakhand-2022.csv \
    --source-url https://myneta.info/uttarakhand2022/ --dry-run

.venv/bin/python -m backend.scripts.import_manifesto --template
.venv/bin/python -m backend.scripts.import_manifesto --election uttarakhand-2022 \
    --promises promises.csv --rti rti.csv --questions questions.csv \
    --documents documents.csv --dry-run

.venv/bin/python -m backend.scripts.import_research --file judgments.csv --dry-run
```

### 10.2 Harvesting from government sites
```sh
.venv/bin/python -m backend.scripts.harvest_gov_sources --list
.venv/bin/python -m backend.scripts.harvest_gov_sources --source cic_annual_reports --out cic.csv
.venv/bin/python -m backend.scripts.import_research --file cic.csv --dry-run
```
- The harvester **never writes to the database**: a parser that misreads a page must not be able to make a public claim without a person seeing it first.
- It checks `robots.txt` before every request, waits 1.5s between calls to a host, and HEAD-checks every link so a dead citation never enters the catalogue.
- **It identifies itself honestly and never spoofs a browser.** Sites that serve only a fake desktop User-Agent (e.g. `indiacode.nic.in`) are not harvested — cite and link to those documents instead. `--list` prints what is excluded and why. **Do not "fix" this by adding a browser User-Agent.**
- data.gov.in is `Disallow: /` for all agents, so it is reached through its API with your own key:
  ```sh
  export DATA_GOV_IN_API_KEY=<your 32-character key>
  .venv/bin/python -m backend.scripts.import_datagovin --resource <uuid> --dry-run
  ```
  Generate a key at data.gov.in → My Account → Generate Your New API KEY. Do not use the `579b464db66ec23bdd000001…` documentation key — its quota is shared and it rate-limits.

---

## 11. SOP — Demo dataset (staging and demonstrations only)

**Never loaded automatically. Never load it on a site carrying real data.**

Contents: 6 representatives with 45 sourced claims, 9 promises, 5 petitions with signatures, 12 citizen reports, 6 forum discussions, 5 events, 8 volunteer tasks, 12 research documents, an extra course, 14 members.

Safety markers, deliberately unmistakable: names start with `[DEMO]`; parties and constituencies are fictional; every citation is titled **"DEMO RECORD - not a real source"**; member emails end in `@demo.rtr.invalid` (RFC 2606 reserved).

```sh
export DATABASE_URL='postgresql://...' MONGO_URL='mongodb+srv://...' DB_NAME=rtr_movement
export JWT_SECRET=... ADMIN_EMAIL=... ADMIN_PASSWORD=...

.venv/bin/python -m backend.scripts.migrate            # schema must exist first
.venv/bin/python -m backend.scripts.load_demo --status # safe any time
.venv/bin/python -m backend.scripts.load_demo --load   # asks you to type 'load demo data'
.venv/bin/python -m backend.scripts.load_demo --purge  # removes it, restores campaign stages
```
- Nothing needs redeploying; the frontend reads it on the next page load.
- Demo members sign in at `/login` with access code **`DEMO-USER`** (`citizen1@demo-rtr.example.com` … `citizen14`); `citizen1` has the richest activity.
- Member sign-in records are the only part needing MongoDB — if Mongo was unreachable, re-run `--load` later.
- Purge identifies only its own records by the markers above, so it cannot touch real data.
- **If `[DEMO]` profiles ever appear on a live site: purge immediately, then investigate which `DATABASE_URL` was used.**

---

## 12. SOP — Member and citizen support

### 12.1 Joining and access codes
- A visitor joins at `/join` or signs the national petition at `/petition`. Both paths mint the supporter record through the single `core/membership.ensure_supporter` path, producing a Movement ID and an access code.
- Members sign in at `/login` with email + access code (`POST /api/auth/member-login`); member tokens last 30 days.
- **Lost access code:** there is no self-service reset. Verify identity out of band, then reissue through the member record. Never read an access code aloud or send it over an unverified channel.

### 12.2 Consent (DPDP)
- Every form shows a consent notice served from the API (`GET /api/legal/consent-notices`), so the notice on a form and the published policy cannot drift.
- Consent records: `POST /api/legal/consent`; member view `GET /me/consent`; withdrawal `POST /me/consent/withdraw`.
- Aggregate view for compliance reporting: `GET /api/admin/legal/consent-summary`.

### 12.3 Erasure request (DPDP right to erasure)
1. Confirm the requester controls the account (they must be signed in; the endpoint is member-authenticated).
2. The member calls `DELETE /api/me/data` from their dashboard. This performs **real erasure** across every module that stores member data.
3. Erasure is a registry, not one function: core owns the order and the guarantees; each module registers its own step, and a test asserts every table holding a `citizen_id` is covered. **Any new module that stores member data must register its erasure step in the same PR.**
4. Confirm completion to the requester in writing. Target: within 7 days of a verified request.
5. Note that the audit log stores **hashed** IPs, not addresses, and never names contributors publicly.

---

## 13. SOP — Security and compliance

### 13.1 Secrets
- The five required variables (`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`) are read at import time; a missing one makes every `/api/*` request 500 with a clear `RuntimeError` naming the variable.
- Secrets live only in the Vercel dashboard and in a gitignored local `backend/.env`. Never in `vercel.json`, never in the repo, never in a test file.
- Rotating `JWT_SECRET` invalidates all sessions and makes previously stored audit IP hashes uncomparable (harmless, but expected).

### 13.2 Rotating the admin password (mandatory before first public deploy)
The pair `socialservant@gmail.com` / `RightToRecall@2026` was once hardcoded in `backend/tests/test_admin.py` and is therefore in this repository's git history. The literals are gone from HEAD, but **deleting them does not un-leak them** — every existing clone and fork keeps a copy. Rotation is the only fix.
1. Generate a new password (`openssl rand -base64 24`) and set `ADMIN_PASSWORD` in Vercel.
2. Redeploy. The next cold start rewrites the stored hash.
3. Confirm the old password fails at `/admin/login`.
4. Change that password anywhere else it was reused.
5. Consider moving the admin account to an address that is not the public contact address, so the login is not guessable from the site footer.

### 13.3 Authentication controls
| Control | Value |
| --- | --- |
| Admin token TTL | 12 hours |
| Member token TTL | 30 days |
| Failed logins before lockout | 10 per email |
| Lockout duration | 15 minutes |
| Password hashing | bcrypt |
| Upload cap | 6 MB |

### 13.4 Rate limits (`core/limits.py`, fixed window, stored in Mongo)
| Action | Limit |
| --- | --- |
| New forum discussions | 5 / hour |
| Forum replies | 30 / hour |
| Forum votes | 200 / hour |
| Citizen reports | 5 / 3 hours |
| Petition creation | 3 / day |
| Petition signatures | 40 / hour |
| Public one-step signatures | 12 / hour **per IP** |
| Correction suggestions | 10 / 3 hours |
| Assistant questions | 20 / hour |
| Document generation | 20 / hour |
| Event registrations | 15 / day |
| Quiz attempts | 30 / day |

Raising a limit is a deliberate decision by the platform owner, recorded in the PR, not an operational tweak.

### 13.5 Audit log
- Append-only: the only operations are append and read. Nothing updates or deletes.
- Records who, when, field-by-field before/after with secret redaction, and the source URL backing the change.
- Internal view `GET /api/admin/audit` (`audit.view`); public per-entity history `GET /api/history/{entity_type}/{entity_id}`, which shows the change and its citation but never names the contributor.
- It cannot be backfilled, which is why it runs from the first edit. **Never disable it to "clean up" a record** — correct the record instead, which itself audits.

### 13.6 Standing disclosures
Keep these live and unweakened: the platform-wide disclaimer (public records; charges are not convictions; the Movement does not independently investigate), the published content policy, the privacy policy, and the statement that petition signatures count accounts rather than verified people.

---

## 14. SOP — Monitoring, health and incident response

### 14.1 Routine checks
| Frequency | Check |
| --- | --- |
| After every deploy | `GET /api/health` → `status ok`, `postgres true`, `schema true`, expected `features` |
| Daily | Moderation queue, corrections queue, fact-check queue |
| Weekly | `GET /api/admin/analytics/pageviews`; Vercel function logs for repeated errors |
| Monthly | Assistant coverage gaps; audit-log spot check; access review of staff accounts |
| Per release | Test suite plus `npm run verify` |

### 14.2 Health response shape
```json
{
  "status": "ok",
  "mongo": true,
  "postgres": true,
  "schema": true,
  "hint": null,
  "features": { "search": "postgres", "assistant": "retrieval_only", "email": false }
}
```
`postgres` = "`DATABASE_URL` is configured". `schema` = "migrations have been applied". They fail independently and look identical from outside, which is why both are reported.

### 14.3 Troubleshooting runbook
| Symptom | Cause | Action |
| --- | --- | --- |
| All `/api/*` return 500 | Missing env var (`KeyError: 'MONGO_URL'` in function logs) | Add it in Vercel, redeploy |
| Timeouts / `ServerSelectionTimeoutError` | Atlas refusing connections | Confirm Network Access `0.0.0.0/0` and the percent-encoded credentials in `MONGO_URL` |
| Requests 404 at `undefined/api/...` | Stale `REACT_APP_BACKEND_URL` in Vercel | Remove it and redeploy |
| Build fails `ERESOLVE` | Install command lost `--legacy-peer-deps` | Restore it in `vercel.json` |
| Build fails "warnings as errors" | `CI=false` missing from build command | Restore it |
| 404 on deep link after refresh | SPA fallback rewrite missing or reordered | `/(.*)` → `/index.html` must stay **last** in `vercel.json` |
| Python response or 404 instead of the React app | Vercel framework auto-detection took over | Framework Preset → **Other**, Root Directory → repo root, redeploy |
| `vercel.json` changes appear to do nothing | Dashboard Build settings override it | Clear the Install/Build/Output fields in Project Settings |
| Missing-table / missing-column 500s after a deploy | Release added a migration that was not applied | `python -m backend.scripts.migrate` against the same `DATABASE_URL` |
| A preview deployment wrote to production data | Previews inherit production env vars | Expected; give previews their own database if it matters |
| Admin login rejects correct credentials | Admin was seeded under a previous `ADMIN_EMAIL` | Log in with the old email, or delete the `users` document and redeploy |
| `/api/constitution/articles` empty | Module seeding did not run, or Mongo-only mode | Check logs for "Module seeding failed"; confirm `DATABASE_URL`; re-run `migrate` |
| A representative refuses to publish | Fact-check gate | Fact Checker verifies each listed claim, or the claim is removed |
| Template returns `409 awaiting legal review` | Someone edited it; status reset by design | `legal.review` holder approves via `POST /api/admin/tools/templates/{key}/review` |
| QR codes 503 | `qrcode` missing from the deployed function | Confirm the build installed the root `requirements.txt`; check-in still works by typing the code |
| Assistant only lists sources | No `GEMINI_API_KEY`, or free quota exhausted | Expected fallback; check `/api/health` |
| `TypeError: connect() got an unexpected keyword argument 'sslmode'` | Old build | Deploy current code, which translates the parameter |
| `ConfigurationError: A DNS label is empty` | `MONGO_URL` still contains the literal `...` from an example | Put the real Atlas string in the env var |
| Demo load fails "DATABASE_URL is not set" | Dataset is entirely relational | Export the same `DATABASE_URL` the deployment uses |
| `[DEMO]` profiles on a live site | Demo loaded against production | `load_demo --purge`, then audit which URL was used |

### 14.4 Incident severity and escalation
| Severity | Example | Response |
| --- | --- | --- |
| **S1** | Unsourced or wrong claim about a named person is publicly visible; PII exposure; admin credential compromise | Unpublish or purge immediately, then investigate. Notify the platform owner and Legal Team the same hour. Record the timeline. |
| **S2** | Site down, all `/api` 500s, database unreachable | Apply the runbook; roll back the deployment if a release caused it |
| **S3** | One feature degraded (email, assistant prose, search backend) | Confirm via `/api/health`; fix at the next convenient point — the platform is designed to run without them |
| **S4** | Cosmetic or single-page bug | Normal release cycle |

For any S1 involving a person's data or a published claim, the correction path is: unpublish → record the correction with reasoning (which is itself audited and publicly visible) → tell the affected party what was changed. Never silently delete.

---

## 15. SOP — Testing and quality

```sh
.venv/bin/python -m pytest backend/tests      # do NOT change addopts; serial runs use -n 0
cd frontend && npm run verify                 # eslint + prettier check + CI=false build
```
- Suites: `backend_test.py` (public API), `test_admin.py` (admin flows, reads credentials from the environment — never hardcode them again), `test_core_rbac.py` (permissions, scoping, escalation guard), `test_platform_modules.py` (feature modules end to end).
- Everything runs on in-memory SQLite: **no infrastructure required**, so there is no excuse to skip the suite before a release.
- `pytest.ini` pins `-n 2 --dist loadscope` deliberately; do not modify it.
- Two invariants have dedicated tests and must keep passing: `requirements.txt` ≡ `api/requirements.txt`, and every table holding a `citizen_id` is covered by the erasure registry.
- `test_result.md` carries the main-agent/testing-agent protocol block — preserve that block when editing the file.

### 15.1 Definition of done for a feature PR
1. Tests added and passing; `npm run verify` clean.
2. Dependency rule respected (no module→module imports).
3. New admin routes declare a permission from the static registry.
4. Anything storing member data registers an erasure step.
5. Anything publishing a claim about a person goes through `core/citations`.
6. Anything accepting public text goes through `core/moderation` and a rate limit.
7. Anything new that publishes content calls `search.index()`.
8. Docs updated: `DEPLOY.md` for operational change, `memory/PRD.md` for shipped scope, this SOP for changed procedure.

---

## 16. Known gaps (carry into planning; do not present as finished)
- **No SSR.** The public site is a client-rendered SPA, so new pages ship blank HTML to crawlers — this directly undercuts the "spread awareness" purpose. A Next.js migration for the public pages is the largest open item; the API is stable and locale-aware, so it is a frontend-only project.
- **Admin UI lags the API.** All admin endpoints exist and are tested, but the SPA still exposes mainly the pre-Phase-0 CMS screens. The fact-check queue and corrections queue are the two screens a volunteer team cannot operate without.
- **Signatures are unconfirmed accounts.** No email confirmation exists; fixing it means adding confirmation in `core/membership`, where both entry points gain it at once.
- **No representative or constituency data is seeded** — by design. Real data enters through the importers and the fact-check gate.
- Self-hosted Umami and Meilisearch remain deferred; search stays on Postgres until roughly 50k documents or warm queries above 300ms.

---

## Appendix A — Environment variables

| Variable | Required | Purpose / default |
| --- | --- | --- |
| `MONGO_URL` | yes | Atlas connection string (no database name in the URI) |
| `DB_NAME` | yes | e.g. `rtr_movement` |
| `JWT_SECRET` | yes | Signs admin and member tokens; salts audit IP hashes. `openssl rand -hex 32` |
| `ADMIN_EMAIL` | yes | Bootstrap Super Admin login |
| `ADMIN_PASSWORD` | yes | Bootstrap Super Admin password; changing it and redeploying resets the stored hash |
| `DATABASE_URL` | strongly | Neon Postgres. Unset → Mongo-only fallback: roles, scoping, states API and audit log unavailable, those endpoints answer 503 |
| `CORS_ORIGINS` | no | Comma-separated. Defaults to `*` — **set it for production** |
| `SITE_URL` | no | Public origin for absolute links in emails and certificates. Default `https://righttorecall.in` |
| `BREVO_API_KEY` | no | Transactional email (300/day free). Unset → logged no-op |
| `BREVO_SENDER_EMAIL` / `BREVO_SENDER_NAME` | no | From address. Defaults `no-reply@righttorecall.in` / `Right to Recall Movement` |
| `GEMINI_API_KEY` | no | Assistant prose answers. Unset → retrieval-only |
| `GEMINI_MODEL` | no | Default `gemini-2.5-flash-lite` |
| `MEILISEARCH_URL` / `MEILISEARCH_KEY` / `MEILISEARCH_INDEX` | no | Self-hosted search. Unset → Postgres search |
| `DATA_GOV_IN_API_KEY` | no | Local only, for `import_datagovin` |
| `AUTO_CREATE_TABLES` | no | **Local/test only.** Never set in a deployed environment |
| `REACT_APP_BACKEND_URL` | no | **Leave unset in production.** Only for a backend on another origin |

## Appendix B — Command reference

| Purpose | Command |
| --- | --- |
| Run API locally | `uvicorn backend.server:app --reload --port 3001` |
| Run frontend locally | `cd frontend && npm start` |
| Migrate + seed | `python -m backend.scripts.migrate` |
| Migrate only | `cd backend && alembic upgrade head` |
| Backend tests | `python -m pytest backend/tests` |
| Frontend checks | `cd frontend && npm run verify` |
| Demo status / load / purge | `python -m backend.scripts.load_demo --status` / `--load` / `--purge` |
| Import representatives | `python -m backend.scripts.import_representatives --source <s> --file <f> --source-url <u> --dry-run` |
| Import manifesto chain | `python -m backend.scripts.import_manifesto --election <slug> --promises <f> --dry-run` |
| Import research library | `python -m backend.scripts.import_research --file <f> --dry-run` |
| Harvest official sources | `python -m backend.scripts.harvest_gov_sources --source <key> --out <f>` |
| Catalogue data.gov.in | `python -m backend.scripts.import_datagovin --resource <uuid> --dry-run` |
| Health check | `curl https://YOUR-DOMAIN/api/health` |

## Appendix C — Glossary

| Term | Meaning |
| --- | --- |
| **Claim** | One sourced statement about a representative, stored per (representative, field, period) with its own citation and verification status |
| **High-risk field** | A defamation-risk field (criminal cases, assets, liabilities, attendance and similar) that requires a **primary public record** |
| **Primary public record** | ECI affidavit, court record, PRS record, Gazette notification — not a news report about one |
| **Verification status** | `unverified` (default) / `fact_checked` / `disputed` / `retracted` |
| **Fact-check gate** | Publishing is blocked while any high-risk claim is unverified; the entering user cannot self-verify |
| **Legal-review gate** | Editing a legal template resets it to draft until `legal.review` approves |
| **Assessment** | The platform's own conclusion about a promise; human-only, never written by an import |
| **Correction** | A public objection on any entity; disclosed as existing while open, published with reasoning when resolved |
| **Access code** | A member's sign-in secret, minted once by `core/membership.ensure_supporter` |
| **Movement ID** | Public supporter identifier of the form `RTR-YYYY-XXXXXX` |
| **Erasure registry** | Core-owned ordering with per-module steps implementing `DELETE /api/me/data` |
| **Zonal grouping** | Statutory zones (States Reorganisation Act 1956; North Eastern Council Act 1971) used for state-wise aggregates |
