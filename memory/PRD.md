# PRD, #RightToRecall Movement Website

## Problem Statement
A vibrant, Gen-Z, mobile-first movement website for the #RightToRecall Movement, a NON-PARTISAN civic movement. Educates visitors in under 3 minutes and converts them into supporters, volunteers, and digital ambassadors. Primary conversion: "Join the RightToRecall Movement."

## Tech / Architecture
- Frontend: React 19 + Tailwind + shadcn/ui, framer-motion (scroll reveals, masked hero, parallax), lenis (smooth scroll), react-fast-marquee.
- Backend: FastAPI + MongoDB. Content served from JSON files at `/app/backend/content/*.json` via `/api/content/*`. Form submissions persisted to MongoDB.
- Design system: "Optimistic Civic Blueprint", Volt Yellow (#D4FF00) + Cobalt Blue, Clash Display + Satoshi fonts, rounded-3xl cards, pill buttons, light + dark mode.

## Personas
- First-time / young voter wanting to understand recall quickly.
- Would-be volunteer / ambassador ready to act.
- Journalist / partner exploring the movement.

## Core Requirements (static)
- Pages: Home, About, Campaigns, Blog/News, Volunteer, Resources, Contact.
- Features: dark/light mode, JSON-powered content, blog search + category filter, FAQ accordion, newsletter signup, share buttons, scroll progress bar, sticky navbar, back-to-top, floating Join CTA, SEO/OG/Twitter meta, robots.txt, sitemap.xml.
- Tone: hopeful, non-partisan, fact-based, action-oriented.

## Implemented (2026-07-27)
- Full 7-page site with kinetic masked hero, parallax hero image, editorial marquee, numbered manifesto chapters, animated timeline.
- Backend content endpoints (campaigns, blogs, faq, news, testimonials, resources) + stats.
- Working forms: Join (dialog), Volunteer, Contact, Newsletter, Supporters, all persist to MongoDB.
- Dark/light theme (next-themes), scroll widgets, share buttons.
- SEO meta, OG/Twitter cards, robots.txt, sitemap.xml.
- Tested end-to-end: backend 100% (13 pytest), frontend 100%.
- Fixed: scroll-reveal stagger animation (cards were stuck at opacity 0), refactored to self-triggering whileInView with index delay.

## Content editing (no code)
Edit JSON files in `/app/backend/content/` (campaigns.json, blogs.json, faq.json, news.json, testimonials.json, resources.json). Changes appear on refresh, no rebuild needed.

## Backlog / Next
- P1: Newsletter/volunteer email delivery via Resend or SendGrid.
- P1: Individual blog article detail page (backend endpoint exists).
- P2: Admin dashboard to view volunteer/contact submissions.
- P2: Real downloadable PDF assets for Resources.
- P2: Multi-language (Hindi + regional) support.

## Update (2026-07-27), Campaign Flow + Knowledge Hub
- Campaign Flow (/join): 4 steps, 30s animated explainer -> pledge -> details (name/state/city/email/mobile optional) -> thank-you. Generates Movement ID (RTR-YYYY-XXXXXX), downloadable digital certificate (html-to-image), verified badge, auto-newsletter subscribe, WhatsApp/X/Facebook/Instagram share. All "Join" CTAs now route to /join.
- Knowledge Hub (/knowledge): What is RTR, recall across jurisdictions, Myth vs Fact, FAQ, research articles, downloads.
- New backend: POST /api/supporters (movement_id + city/mobile/pledge + auto-newsletter), GET /api/content/jurisdictions, GET /api/content/myths.
- Removed all fabricated numbers (hero stats, campaign progress bars, invented news/blog counts).
- Logo => "RightToRecall / MOVEMENT" top-left. Real socials + email socialservant@gmail.com.
- Tested: backend 100% (16 pytest), frontend 100% (iteration_2).

## Update (2026-07-28), Phase 0 platform foundations
Scope shifted from "campaign website" to the Constitutional Civic-Tech Platform described in `IMPLEMENTATION_PLAN.md` (Wikipedia + Change.org + Election Commission + Reddit + GitHub transparency). Backend rebuilt as a modular monolith.

- Architecture: `backend/server.py` 963 -> ~100 lines (app assembly only). Routes moved to `backend/modules/{auth,members,staff,cms,states,submissions,uploads,analytics,audit}/`; shared infra in `backend/core/`. Rule: modules import from core, never from each other.
- Second database added: Postgres (Neon free tier) for relational modules, MongoDB retained for CMS content + form submissions. SQLAlchemy 2.0 async, NullPool + `statement_cache_size=0` for serverless/pgbouncer.
- RBAC: 33 permissions, 11 roles, state/district scoping, rank-based escalation guard, last-Super-Admin protection. Registry is static Python (`core/permissions.py`) and self-validates at import.
- Audit log: append-only, field-level diffs with secret redaction, internal view (names actor) vs public history view (does not).
- Geography: 28 states + 8 UTs seeded with ISO codes and `has_legislature`; Delhi + Maharashtra flagged as pilots. 8-stage campaign pipeline.
- Alembic migrations (`python -m backend.scripts.migrate`). DDL never runs from the serverless function.
- DPDP: `DELETE /api/me/data` does real erasure across all member collections; audit log hashes IPs instead of storing them.
- API contract unchanged: all 28 pre-existing routes preserved exactly, 19 added.
- Local Python floor is now 3.10 (pinned deps); dev venv uses 3.12 to match Vercel.
- Tests: 38 new unit tests (`backend/tests/test_core_rbac.py`) running on in-memory SQLite, no infrastructure needed. Migration verified column-for-column against the models.
- NOT yet done: real Neon project, Next.js migration, i18n, admin UI for roles, privacy policy page.

## Backlog / Next (updated 2026-07-28)
- P0: create real Neon project, run migration, set `DATABASE_URL` in Vercel, verify `/api/health`.
- P0: privacy policy page + consent notice on every form (DPDP).
- P1: Next.js app in `frontend-next/`, port design system then Home.
- P1: admin UI for the role endpoints (they exist and are unused).
- P1: seed Delhi + Maharashtra representative data by hand before building importers.

## Update (2026-08-09), Phases 1-5: every feature module

The platform described in `IMPLEMENTATION_PLAN.md` §4 is now built end to end. 180 API
routes (from 47), 43 tables (from 9), 26 new frontend pages.

### Modules
- **constitution**: 47 articles seeded bilingually with verbatim text, plain English + Hindi, case law, "why this matters for Right to Recall", draft/publish gate, public history.
- **representatives**: profiles + constituencies + parties, and a citation-gated claim store — one row per (representative, field, period), each carrying its own source and verification status. 17 tracked fields, 8 requiring a primary public record. Fact-check queue; publish is blocked while any high-risk claim is unverified, and nobody can verify a claim they entered.
- **promises**: two independent citations per entry (that it was made; what became of it). Adverse statuses need a primary source. Seven statuses, not two.
- **corrections**: generic "Suggest a correction" on any entity, open to anonymous submission. Unresolved submissions are disclosed as a fact without their text; resolved ones publish the objection and the reviewer's reasoning.
- **petitions**: signatures tied to verified member accounts, uniqueness enforced by constraint, milestones from 50 upward, aggregate-only export.
- **reports**: Citizen Report Cards, nothing auto-publishes, corroboration counts, government response as a first-class field, per-place scorecard withheld below a sample-size floor.
- **forum**: 7 categories, upvotes only (no downvotes — they become pile-ons), reputation gates abuse-prone actions and nothing else, held posts stay visible to their author with the reason.
- **volunteers / events / academy**: task board with verified hours, per-ticket QR check-in, courses with server-graded quizzes. All three issue certificates with publicly verifiable codes.
- **research**: Research Centre and Media Library in one repository, licence recorded per item.
- **tools**: RTI application / first appeal / second appeal, representation, department letter, recall demand letter. Legal-review gate per template; nothing a citizen types is stored.
- **ai**: Constitution Assistant, retrieval-grounded, four refusal rules enforced in code (no sources → no answer; no legal advice; no PII leaves the platform; degrade rather than fail), correctable answer cache, coverage-gap report.
- **legal**: privacy policy, content policy, disclaimer, consent records — all served from the API so the notice on a form and the published policy cannot drift.

### Plain-language guide at `/docs`
A non-technical guide to every feature: what it is, what happens step by step when
you use it, whether you need an account, and what it cannot do. 32 features across 6
areas, plus how the trust rules work, who does what, and an honest list of what is
not finished. Content lives in `frontend/src/lib/docsContent.js` as data, so the
contents list and the feature list cannot disagree — adding a feature means adding one
object. Linked from the navbar ("How this site works") and every page footer.

### Core additions
`citations.py` (verifiability gate), `moderation.py` (non-partisan content policy as
code), `search.py` (shared index — the seam that keeps modules from importing each
other), `certificates.py`, `documents.py`, `notify.py`, `limits.py`, `i18n.py`,
`erasure.py`.

### Decisions worth remembering
- Search runs on Postgres; Meilisearch is implemented behind the same interface and switches on with an env var. Trigger: ~50k docs or >300ms warm queries.
- Documents are DOCX (stdlib zip) + browser print-to-PDF, not WeasyPrint/ReportLab — both mangle Devanagari or need native libraries that do not fit a Vercel function.
- No representative or constituency data is seeded. Those go through the citation and fact-check gates, or the gates are theatre.
- India is drawn as a tile grid, not a choropleth: contested borders need a deliberately chosen boundary file, and equal tiles give every state equal weight.
- Erasure is a registry, not one function. Core owns the order; each module registers its own step; a test asserts every table holding a `citizen_id` is covered.

### Verified
156 unit/API tests (38 Phase-0 + 118 new) on in-memory SQLite, no infrastructure.
Migration applies and rolls back cleanly; schema matches the models exactly (43/43
tables, no column drift). Frontend builds clean.

### NOT done
- Next.js migration. Now the largest gap: 26 new pages ship blank HTML to crawlers, which undercuts the "spread awareness" purpose directly. API is stable and locale-aware, so it is a frontend-only project.
- Admin UI for the new modules. All 70 admin endpoints exist and are tested; the SPA still only exposes the pre-Phase-0 CMS screens.
- Real Neon project (still verified only against SQLite), self-hosted Umami.

## Backlog / Next (updated 2026-08-09)
- P0: real Neon project, run `python -m backend.scripts.migrate`, set `DATABASE_URL` in Vercel, verify `/api/health` reports `"postgres": true`.
- P0: admin UI for the fact-check queue and the corrections queue — the two screens a volunteer team cannot operate without.
- P1: Next.js migration for the public pages.
- P1: import pilot-state constituencies from ECI delimitation orders, then enter and fact-check the first real representative profiles.
- P2: self-hosted Umami; self-hosted Meilisearch once the index justifies it.
