# Deploying to Vercel

One Vercel project serves both halves of this app:

- the React (CRA + craco) frontend, built from `frontend/` into `frontend/build`
  and served as static files;
- the FastAPI backend, served as a single Python serverless function from
  `api/index.py`, which imports the app from `backend/server.py`.

Because both are on the same origin, the frontend talks to the API through the
relative path `/api` and needs no backend URL configured.

## Go-live checklist

The full walkthrough is below. This is the short list of things that are wrong by
default and must be dealt with before the site is public — each links to the
section that explains it.

| # | Do this | Why it bites |
| --- | --- | --- |
| 1 | **Rotate the admin password.** The old one is in this repo's git history. | Anyone with a clone has a Super Admin login. See "Rotating a leaked admin password". |
| 2 | **Generate a real `JWT_SECRET`** (`openssl rand -hex 32`). | It signs admin and member tokens *and* salts the audit log's IP hashes. A guessable secret means forgeable sessions. |
| 3 | **Run the migrations before the deploy goes live** (`python -m backend.scripts.migrate`). | Pushing code does not touch the schema. Code expecting a missing table 500s on every affected endpoint. |
| 4 | **Set `CORS_ORIGINS` to your domain.** | It defaults to `*`, which lets any site call the API with a member's browser. |
| 5 | **Do not load the demo dataset.** | It is fabricated data about invented people on an accountability site. See step 5b. |
| 6 | **Never deploy a locally-built `frontend/build`.** | A local `.env` bakes `REACT_APP_BACKEND_URL=http://localhost:3001` into the bundle. Let Vercel build it, where that file does not exist and the API base correctly resolves to the relative `/api`. |
| 7 | **Check `/api/health` after deploying.** | It reports which databases and integrations the running instance actually has. |

Two things that are already handled, listed so nobody "fixes" them:

- `httpx` is pinned in `requirements.txt` and must stay pinned. The Gemini,
  Brevo and Meilisearch clients import it defensively and degrade to a silent
  no-op without it — a deployment with a valid API key that answers nothing and
  logs nothing.
- `requirements.txt` and `api/requirements.txt` must stay byte-identical. A test
  enforces both of these.

## Prerequisites

- A Vercel account.
- **A GitHub repository** connected to it. Vercel then builds and deploys on every
  push, which is the path this guide assumes. (The `vercel` CLI works too —
  `npm i -g vercel` then `vercel --prod` — but nothing here requires it.)
- A MongoDB database reachable from the public internet (Atlas free tier is
  fine). The bundled JSON files in `backend/content/` are seeded into it
  automatically on first boot.
- A Postgres database (Neon free tier is fine). Holds staff identity, roles and
  permissions, the states table and the audit log. See step 1b.
- **Python 3.12 on your own machine.** Not optional: migrations are never run by
  the deployed function, so you run them from here against the same database.
  (Python 3.10 is the floor — several pinned dependencies require it — and 3.12
  matches what Vercel runs.) Node 18+ if you want to build the frontend locally.

### The one thing that is not automatic

Pushing to GitHub deploys the **code**. It does not touch the **database schema**.
Migrations are applied by you, from your machine, with
`python -m backend.scripts.migrate` — see step 1b, and "Releases that add a
migration" in step 3 for the ordering. A deploy that ships code expecting a table
that does not exist yet will 500 on every affected endpoint until you run it.

## 1. MongoDB Atlas setup

1. Create a free **M0** cluster at <https://cloud.mongodb.com>.
2. **Database Access** -> add a database user with a password, role
   "Read and write to any database". Avoid `@ : / ?` in the password, or
   percent-encode it in the URI.
3. **Network Access** -> Add IP Address -> `0.0.0.0/0` (allow from anywhere).
   Serverless functions have no fixed egress IP, so an allow-list of specific
   addresses will not work.
4. **Connect** -> "Drivers" -> copy the connection string, e.g.
   `mongodb+srv://USER:PASSWORD@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority`.
   Keep the database name out of the URI; it is passed separately as `DB_NAME`.

## 1b. Postgres (Neon) setup

Two databases, on purpose: Mongo keeps loosely structured CMS content, Postgres
keeps everything relational (staff accounts, roles, geographic scoping, the
campaign pipeline, the audit log). See §4 of `IMPLEMENTATION_PLAN.md` for why.

1. Create a free project at <https://neon.com>.
2. Copy the connection string from the dashboard **verbatim**, including
   `?sslmode=require` and any `&channel_binding=require`. You do not need to edit
   it: the app swaps in the async driver prefix, strips the parameters that belong
   to `psql` rather than to the async driver, and turns `sslmode` into the SSL
   setting the driver actually wants.

   (Editing it is what causes trouble. If you drop `sslmode=require` by hand, Neon
   refuses the connection; if you leave it in on a version of this app that does
   not translate it, you get
   `TypeError: connect() got an unexpected keyword argument 'sslmode'`.)
3. Apply the schema **before** the first deploy, from your machine:

   ```sh
   python3.12 -m venv .venv
   .venv/bin/pip install -r requirements.txt -r backend/requirements-dev.txt
   DATABASE_URL='postgresql://...' MONGO_URL='mongodb+srv://...' DB_NAME=rtr_movement \
     JWT_SECRET=x ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=your-password \
     .venv/bin/python -m backend.scripts.migrate
   ```

   That runs `alembic upgrade head`, reconciles the role/permission registry,
   seeds all 36 states and UTs, and creates the Super Admin account.

Migrations are never run by the serverless function itself — a function racing
to migrate its own schema on a cold start is how you end up half-migrated. Run
the command above (or `cd backend && alembic upgrade head`) whenever a release
adds a migration.

Neon's free tier autosuspends after 5 minutes idle, so the first request after a
quiet period pays a cold start on top of Vercel's. That is expected.

## 2. Environment variables

Set these in the Vercel dashboard under **Settings -> Environment Variables**
(apply them to Production, Preview and Development). They are read by the Python
function; do not put them in `vercel.json`.

| Variable         | Required | Example / notes                                        |
| ---------------- | -------- | ------------------------------------------------------ |
| `MONGO_URL`      | yes      | the Atlas connection string from step 1                |
| `DB_NAME`        | yes      | `rtr_movement`                                         |
| `JWT_SECRET`     | yes      | long random string, e.g. `openssl rand -hex 32`        |
| `ADMIN_EMAIL`    | yes      | login for the admin panel                              |
| `ADMIN_PASSWORD` | yes      | admin password (see "Resetting the admin password")     |
| `DATABASE_URL`   | strongly | the Neon connection string from step 1b                |
| `CORS_ORIGINS`   | no       | defaults to `*`; only needed for cross-origin callers   |
| `SITE_URL`       | no       | public origin, used for absolute links in emails and certificates |

### Optional integrations

Each of these turns on one feature. **Every one of them is optional**, and with none
of them set the platform runs fully — the affected feature degrades to something
useful rather than breaking, and `GET /api/health` reports which mode each is in.

| Variable | Turns on | Without it |
| --- | --- | --- |
| `BREVO_API_KEY` | Transactional email (300/day free at <https://brevo.com>) | Sends are logged and skipped. Every flow that emails also shows the same information on screen. |
| `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME` | The From address on those emails | Defaults to `no-reply@righttorecall.in` |
| `GEMINI_API_KEY` | Written answers from the Constitution Assistant (Google AI Studio free tier) | The assistant returns the ranked source passages from the library instead of prose. Still useful, still cites everything. |
| `GEMINI_MODEL` | Which model | `gemini-2.5-flash-lite` |
| `MEILISEARCH_URL`, `MEILISEARCH_KEY` | Self-hosted Meilisearch for site search | Search runs on Postgres, which is adequate at this corpus size. See `backend/core/search.py` for the switch-over trigger. |

`GET /api/health` reports all of it:

```json
{
  "status": "ok",
  "mongo": true,
  "postgres": true,
  "features": { "search": "postgres", "assistant": "retrieval_only", "email": false }
}
```

**Never send user PII to the assistant.** Free-tier prompts may be retained by the
provider, which is why the backend strips phone numbers, email addresses and ID
numbers from a question before it leaves the platform. The privacy policy says so
explicitly; do not weaken that.

The five required variables are read at import time, so a missing one makes every
`/api/*` request fail with a 500 (a clear `RuntimeError` naming the variable, in
the function logs).

`DATABASE_URL` is marked "strongly" rather than "yes" because the app
deliberately still boots without it, falling back to the pre-Phase-0 Mongo-only
auth path so that deploying the modular backend cannot break a site that has not
been given a Postgres instance yet. In that mode roles, geographic scoping, the
states API and the audit log are all unavailable and their endpoints answer 503.
Treat it as required for any real deployment. `GET /api/health` reports which
mode an instance is running in:

```json
{ "status": "ok", "mongo": true, "postgres": true, "schema": true }
```

`schema` is separate from `postgres` on purpose: the first means "DATABASE_URL is
configured", the second means "the migrations have been applied". They fail
independently and look identical from outside, so both are reported.

Do **not** set `REACT_APP_BACKEND_URL`. Leaving it unset is what makes the
frontend use the same-origin `/api` path. Only set it if you deliberately point
the site at a backend hosted elsewhere. See `frontend/.env.example` and
`backend/.env.example` for local development templates.

## 3. Deploy from GitHub

1. In Vercel: **Add New -> Project -> Import Git Repository**, and pick the repo.
2. Leave **Root Directory** as the repo root. Do **not** set it to `frontend/` —
   the Python function lives at `api/index.py` and needs `backend/**` alongside it.
3. Leave the **Framework Preset** as **Other**. `vercel.json` sets
   `"framework": null` deliberately: letting Vercel auto-detect turns the Python
   function into the thing that serves the site, and the static build stops being
   served at all.
4. Do not fill in Build & Development Settings. `vercel.json` already supplies them
   and the dashboard fields would override it:
   - install: `cd frontend && npm install --legacy-peer-deps`
     (the `--legacy-peer-deps` flag is required: `react-day-picker@8` declares a
     peer range that excludes React 19)
   - build: `cd frontend && CI=false npm run build` (`CI=false` keeps CRA lint
     warnings from failing the build)
   - output: `frontend/build`
5. Add the environment variables from step 2 **before** you deploy. If the first
   build runs without them, every `/api/*` request 500s until you add them and
   redeploy.
6. Deploy. Vercel builds the static frontend and, separately, installs the root
   `requirements.txt` and bundles `api/index.py` as a Python function.
7. Verify with `curl https://YOUR-DOMAIN/api/health`. You want **both**
   `"postgres": true` and `"schema": true`.

   `postgres: true, schema: false` is the common fresh-deployment state: the
   connection works and the tables do not exist yet, because pushing to git
   deploys code and not schema. The response says so in its `hint` field. Run
   step 1b's `migrate` command and the same URL will report `schema: true`.

Routing comes from the `rewrites` in `vercel.json`: `/api/*` goes to the Python
function, and anything that is not an existing static file falls through to
`/index.html` so React Router handles client-side routes on refresh/deep links.

### After the first deploy

Every push to your default branch deploys to production automatically. Pushes to
other branches, and pull requests, get their own preview URL.

**Preview deployments share your environment variables**, which means they share
your database. A preview built from a branch is not a sandbox: signing up on a
preview URL writes a real supporter record, and running the demo loader against
that `DATABASE_URL` puts `[DEMO]` profiles on production. If you want a genuinely
separate environment, create a second Neon database and a second Vercel project
pointed at the same repo, and give that project its own `DATABASE_URL`.

### Releases that add a migration

Code deploys on push; the schema does not. When a release adds a migration, the
order that avoids downtime is:

1. Run `python -m backend.scripts.migrate` from your machine **first**. Every
   migration in this repo is additive — new tables and columns — so the currently
   deployed code keeps working against the new schema.
2. Then push. The new code arrives to a database that already has what it needs.

Doing it the other way round leaves a window where the deployed code queries
tables that do not exist yet, and every affected endpoint 500s until you catch up.

To check whether a release needs it, look for new files under
`backend/migrations/versions/` in the diff.

## 4. Admin panel

- Go to `https://YOUR-DOMAIN/admin/login` and sign in with `ADMIN_EMAIL` /
  `ADMIN_PASSWORD`. On success you land on `/admin`.
- The admin user is created on the first cold start after deploy. Sessions are
  JWTs valid for 12 hours; after 10 failed logins for an email, that email is
  locked out for 15 minutes.
- Content edits made in the panel are stored in MongoDB. The JSON files under
  `backend/content/` are only used to seed collections that are still empty, so
  your edits are never overwritten by a redeploy.

### Roles and permissions

The `ADMIN_EMAIL` account is a **Super Admin** and holds every permission. Give
everyone else the narrowest role that lets them do their job — the full matrix
is defined in `backend/core/permissions.py` and documented in §6 of
`IMPLEMENTATION_PLAN.md`:

| Role | For |
| --- | --- |
| Super Admin | Platform owners. Can assign roles and read the audit log. |
| State Admin / District Admin | Scoped to one state or district. |
| Research Team | Adds representative and promise data; cannot publish it. |
| Fact Checker | Approves sourced claims about named people before they go live. |
| Legal Team | Reviews templates, disputed claims, defamation risk. |
| Editor / Content Writer | Publishes / drafts CMS content. |
| Moderator | Forum and citizen reports. |
| Volunteer Manager | Volunteer tasks, hours, certificates. |
| Analyst | Read-only analytics. |

Two guards are worth knowing about because they will look like bugs otherwise:

- **You cannot grant a role that ranks at or above your own**, and you cannot
  grant a permission you do not hold. This is what stops anyone with
  `users.manage` from quietly promoting themselves to Super Admin.
- **The last Super Admin cannot be revoked**, and the bootstrap account cannot
  be deleted or deactivated from the UI. Change `ADMIN_EMAIL` and redeploy
  instead.

### The audit log

Every staff change is appended to an immutable log — who, when, what changed
field by field, and the source URL backing it. Internal view:
`GET /api/admin/audit` (needs `audit.view`). Public per-entity history:
`GET /api/history/{entity_type}/{entity_id}`, which shows the change and its
citation but never names the contributor. This is the transparency mechanism
described in §7 of the plan; it cannot be backfilled, which is why it is on from
the first edit.

### Resetting the admin password

Change `ADMIN_PASSWORD` in the Vercel dashboard and redeploy. On the next cold
start the stored hash is rewritten to match the environment variable.

### Rotating a leaked admin password

**Do this before the first public deploy.** The pair
`socialservant@gmail.com` / `RightToRecall@2026` was hardcoded in
`backend/tests/test_admin.py` and is therefore in this repository's git history.
Anyone who has ever cloned it has a working Super Admin login.

The literals have been removed from the file — the suite now reads `ADMIN_EMAIL`
and `ADMIN_PASSWORD` from the environment — but **deleting them from HEAD does
not un-leak them.** The history still contains the password, and rewriting
history does not help either: every existing clone and fork keeps its copy.

The only fix is rotation:

1. Set a new `ADMIN_PASSWORD` in the Vercel dashboard (generate it, do not invent
   it: `openssl rand -base64 24`).
2. Redeploy. The next cold start rewrites the stored hash.
3. Confirm the old password no longer works at `/admin/login`.
4. If that address is also used for anything else, change it there too — a
   password published in a git repository should be assumed compromised
   everywhere it was reused.

Consider moving the admin account to an address that is not the public contact
address, so the login is not guessable from the site's own footer.

## 5. What gets seeded on first boot

The first cold start after a deploy populates the platform's reference data. All of
it is idempotent, none of it overwrites an editor's work, and a fingerprint in
`platform_meta` means later cold starts skip it in one query.

| Seeded | Count | Source |
| --- | --- | --- |
| Permissions and roles | 37 permissions, 11 roles | `backend/core/permissions.py` |
| States and union territories | 36 | `backend/core/geography.py` |
| Districts of the pilot states | 47 (Delhi 11, Maharashtra 36) | `backend/seed_modules.py` |
| ECI-recognised national parties | 6, plus "Independent" | `backend/seed_modules.py` |
| Constitution articles | 61, published, bilingual | `backend/content/constitution.json` |
| Forum categories | 7 | `backend/modules/forum/models.py` |
| RTI / representation templates | 6, legal-approved | `backend/modules/tools/seed_templates.py` |
| Starter course | 1, with 4 lessons and a 6-question quiz | `backend/seed_modules.py` |

Two things are deliberately NOT seeded:

- **Representative profiles.** Publishing claims about named living people requires a
  citation per figure and a fact-check per figure (§7). Shipping a seed file of
  people would bypass exactly the gate the platform exists to demonstrate. Profiles
  are entered through the admin panel, sourced, and published only after review.
- **Constituencies.** Seat lists come from Election Commission delimitation orders and
  should be imported from that source, not typed from memory. Use
  `POST /api/admin/constituencies/bulk` with a source URL on each row.

## 5b. Loading the demo dataset (optional)

Sample content so that every page and every feature has something to show: 6
representatives with 45 sourced claims, 9 promises, 5 petitions with signatures, 12
citizen reports, 6 forum discussions, 5 events, 8 volunteer tasks, 12 research
documents, an extra course, and 14 members you can sign in as.

**It is never loaded automatically.** Nothing in the boot or deploy path touches it.

### Before you run it anywhere public

This platform publishes claims about named people, and fabricated data on a live
accountability site is precisely the failure its citation and fact-check gates exist
to prevent. The dataset is built so it cannot be mistaken for real:

- every person's name starts with `[DEMO]`, which appears in the profile heading,
  every listing, every search result and every screenshot;
- parties ("Demo Progressive Party") and constituencies ("Demo North Delhi") are
  fictional, so no real party or office holder is implicated by any figure;
- every citation is titled **"DEMO RECORD - not a real source"**, which renders next
  to each figure on the profile;
- member emails end in `@demo.rtr.invalid` (RFC 2606 reserved, never routable).

Load it on staging, on a local machine, or on a fresh site you are demonstrating.
Purge it before the site carries real data.

### Steps

Run from your machine, against the same `DATABASE_URL` the deployment uses. It talks
to the database directly, so there is nothing to deploy and no downtime.

```sh
# 1. Same environment variables as the migration in step 1b.
export DATABASE_URL='postgresql://...'
export MONGO_URL='mongodb+srv://...' DB_NAME=rtr_movement
export JWT_SECRET=x ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=your-password

# 2. Schema and reference data must already be in place.
.venv/bin/python -m backend.scripts.migrate

# 3. See what is currently loaded (safe to run any time).
.venv/bin/python -m backend.scripts.load_demo --status

# 4. Load it. Prints a warning and asks you to type 'load demo data' to confirm.
.venv/bin/python -m backend.scripts.load_demo --load
#    Add --yes to skip the prompt in a script.
```

Nothing needs redeploying — the frontend reads it on the next page load.

### Checking it worked

```sh
curl https://YOUR-DOMAIN/api/representatives | head       # 5 published profiles
curl https://YOUR-DOMAIN/api/petitions | head             # 5 petitions
curl "https://YOUR-DOMAIN/api/search?q=recall" | head     # ~20 results
```

Then in a browser: `/states` should have a coloured map, `/representatives` should
list five `[DEMO]` profiles, and `/representatives/demo-suresh-kolhe` should show a
**disputed** claim with the reviewer's note — which is the trust layer working.

### Signing in as a demo member

Every demo member signs in at `/login` with the access code **`DEMO-USER`**:

```
citizen1@demo-rtr.example.com  ...  citizen14@demo-rtr.example.com
```

`citizen1` has the most activity — signed petitions, filed reports, forum posts, 23
verified volunteer hours, event tickets and a course certificate — so it is the best
account for walking through the member experience.

Member sign-in is the only part that needs MongoDB. If Mongo is unreachable when you
load, the loader says so and everything else still loads; re-run `--load` later to add
the sign-in records.

### Removing it

```sh
.venv/bin/python -m backend.scripts.load_demo --purge
.venv/bin/python -m backend.scripts.load_demo --status   # confirm it is 0
```

Purge removes every record the loader created and restores the campaign stage of each
state it changed. It identifies its own records only by the markers above, so it
cannot touch real data sitting alongside it. Both `--load` and `--purge` are safe to
re-run: a second load adds nothing.

## Bulk import

Three importers fill the research-heavy modules from files, so a state can be
opened without typing every record through the admin API. All three share the
same shape: CSV or JSON in, `--dry-run` to see what would change, unpublished
unless `--publish` is typed, and safe to re-run.

| Script | Fills | Refuses |
| --- | --- | --- |
| `import_representatives` | Representative profiles and sourced claims | Claims on high-risk fields from a secondary source; overwriting a fact-checked value |
| `import_manifesto` | Promises, RTI applications, questions, answers, replies, records | Any status or assessment; a record with no provenance |
| `import_research` | Research Centre / Knowledge Hub library | A row with no `source_url`; hosting a copy with no stated licence |
| `harvest_gov_sources` | Discovers documents on official sites, writes an import CSV | Any URL robots.txt disallows; any site that 403s an honestly-identified agent |
| `import_datagovin` | Catalogues data.gov.in datasets via the official API | Nothing — but the upstream 502s often, and failures are reported, never silently dropped |

### Getting data off official government sites

Two tools, because the two routes have different rules.

```sh
.venv/bin/python -m backend.scripts.harvest_gov_sources --list
.venv/bin/python -m backend.scripts.harvest_gov_sources --source cic_annual_reports --out cic.csv
.venv/bin/python -m backend.scripts.import_research --file cic.csv --dry-run
```

`harvest_gov_sources` reads official index pages and writes the CSV `import_research`
takes. It never writes to the database itself: a parser that mis-reads a page
should not be able to make a public claim about what a government published
without a person seeing it first. It checks `robots.txt` before every request,
waits 1.5s between calls to the same host, and HEAD-checks every link so a dead
citation never enters the catalogue.

**It identifies itself honestly and never spoofs a browser.** Some government
sites serve only a fake desktop User-Agent and 403 an honest one —
`indiacode.nic.in` does exactly that. Those sites are not harvested. Getting past
a filter that exists to exclude automated clients is circumventing a stated
preference, and this project cannot both demand that institutions honour what
they publish and sneak past their front door. Cite and link to those documents
instead; that is what a citation is.

`--list` prints what is harvestable **and what is deliberately excluded, with the
reason**, so nobody re-derives it later.

For data.gov.in the portal is `Disallow: /` for every agent, so it is reached
through its API instead:

```sh
export DATA_GOV_IN_API_KEY=<your 32-character key>
.venv/bin/python -m backend.scripts.import_datagovin --resource <uuid> --dry-run
```

Get a key at data.gov.in → log in → My Account → **Generate Your New API KEY**.
Do not use the `579b464db66ec23bdd000001…` key from their documentation: it works,
but its quota is shared with every tutorial that copied it, so it rate limits and
returns 502 under load. The script warns if it sees that prefix.

The API has no catalogue endpoint, so resource IDs come from browsing the portal
in a browser — `robots.txt` governs automated agents, not people. Collect the
UUIDs you want and pass them with `--resource` or a `--resources` file.

### Manifesto promises, RTIs and replies

```sh
.venv/bin/python -m backend.scripts.import_manifesto --template   # the expected shape

.venv/bin/python -m backend.scripts.import_manifesto \
    --election uttarakhand-2022 \
    --promises promises.csv --rti rti.csv \
    --questions questions.csv --documents documents.csv --dry-run
```

Four files joined by code — one per stage of the chain, which is how research
arrives — or one nested JSON file passed to `--promises`. Any subset works: a run
with only `--documents` attaches records to promises that already exist.

**It cannot set a promise's status or write an assessment, and there is no flag
for it.** Those are the platform's own conclusions about a government, and §14
keeps them in a separate table precisely so no bulk process can put one there.
Every imported promise reads "status not established from available records"
until a human publishes an assessment against the records. What it does import is
the factual half — what was promised, what was asked, what came back, what was
attached — which is transcription, and transcription is what a script should do.

A record with neither `source_note` nor `source_url` is refused: an anonymous PDF
is not evidence. A reply-due date is computed from the filing date at 30 days
(s.7(1) of the RTI Act) when the file omits it.

### Research Centre and Knowledge Hub

```sh
.venv/bin/python -m backend.scripts.import_research --template
.venv/bin/python -m backend.scripts.import_research --file judgments.csv --dry-run
```

`source_url` is required on every row — a catalogue entry with no link to the
original is an unverifiable assertion that a document exists, and this library is
also what the AI assistant grounds its answers in.

`licence` decides whether a copy may be hosted or only linked. It defaults to
`linked_only`, and a row that supplies `file_url` **without** stating a licence is
refused rather than guessed: hosting somebody's report under an assumed licence is
a redistribution problem nobody notices until a takedown arrives.

## Importing real representative data

Demo data aside, the Representative Database is filled from published open data
rather than by hand:

```sh
.venv/bin/python -m backend.scripts.import_representatives --list-sources

# Always dry-run first. Nothing is written and you see exactly what would change.
.venv/bin/python -m backend.scripts.import_representatives \
    --source myneta_affidavits --file uttarakhand-2022.csv \
    --source-url https://myneta.info/uttarakhand2022/ --dry-run
```

It takes a downloaded CSV or JSON file (or `--url` to fetch a published dataset).
It is **not** a scraper, and that is deliberate: every source listed in
IMPLEMENTATION_PLAN.md §124 publishes this data as a file you are permitted to
download, and the plan says to prefer those downloads to scraping. Parsing a
published file is stable and attributable; parsing someone's HTML is neither, and
needs a licence review first.

Three things it guarantees, because it writes claims about named living people in
bulk with nobody reading each row:

| Guarantee | Why |
| --- | --- |
| Every claim is written **UNVERIFIED** | It renders behind a "pending citation review" marker until a Fact Checker follows the source. There is no flag to change this. |
| A **reviewed claim is never overwritten** | If a Fact Checker has accepted, disputed or retracted a figure, the import leaves it alone and reports the disagreement as a conflict for a human. |
| New profiles are **drafts** | Publishing a profile about a real person is a human decision. `--publish` makes it explicit. |

Claims on high-risk fields — criminal cases, assets, liabilities, attendance —
are refused outright unless the citation URL is a primary public record, because
for those fields "this is what the public record says" is the platform's legal
defence and a news report about an affidavit is not the affidavit.

Re-running is safe: representatives match on slug, claims on
(representative, field, period), and anything unchanged is left untouched.

### Editing seeded content

Editing a constitution article through the admin panel is permanent — seeding only
inserts rows that are missing, so a redeploy never overwrites an improvement. The one
exception is the RTI/representation templates, which are legal texts maintained in
the repository: a change to `seed_templates.py` DOES reach the deployed template, and
doing so resets it to `draft`, so a redeploy can never put unreviewed legal wording in
front of the public. Someone with `legal.review` has to approve it again.

## Troubleshooting

**All `/api/*` calls return 500.** Check the function logs (Vercel -> your
deployment -> Functions -> `api/index.py`). A `KeyError: 'MONGO_URL'` (or another
name) means an environment variable is missing or was added after the deploy -
add it and redeploy.

**API times out or logs `ServerSelectionTimeoutError`.** Atlas is refusing the
connection: confirm Network Access includes `0.0.0.0/0` and that the username,
percent-encoded password and cluster host in `MONGO_URL` are correct.

**Frontend loads but every request 404s at `undefined/api/...`.** A stale
`REACT_APP_BACKEND_URL` is set in the project's environment variables. Remove it
and redeploy.

**Build fails with `ERESOLVE unable to resolve dependency tree`.** The install
command lost its `--legacy-peer-deps` flag - restore it in `vercel.json` or in
Settings -> Build & Development Settings.

**Build fails on CRA warnings ("Treating warnings as errors").** `CI=false` is
missing from the build command.

**404 on a deep link like `/campaigns` after a hard refresh.** The SPA fallback
rewrite is missing or was reordered; the `/(.*)` -> `/index.html` rewrite must
stay last in `vercel.json`.

**The site shows a Python response, or a 404, instead of the React app.** Vercel's
framework auto-detection has taken over: it found `api/index.py` and decided this is
a Python project, so the static build is not being served. Set the Framework Preset
back to **Other** in Project Settings, confirm Root Directory is the repo root (not
`frontend/`), and redeploy.

**Build settings in the dashboard disagree with `vercel.json`.** The dashboard wins.
Clear the Install/Build/Output fields in Project Settings so `vercel.json` is the
single source, otherwise a change committed to `vercel.json` will appear to do
nothing.

**Endpoints 500 with a missing-table or missing-column error after a deploy.** The
release added a migration and it has not been applied. Run
`python -m backend.scripts.migrate` against the same `DATABASE_URL`. See "Releases
that add a migration" in step 3.

**A preview deployment wrote to production data.** Expected: preview builds inherit
the project's environment variables, including `DATABASE_URL`. Give previews their
own database if that matters — see "After the first deploy" in step 3.

**Admin login says "Invalid email or password" with the right credentials.** The
admin user was seeded before you changed `ADMIN_EMAIL`; the old account still
exists under the previous address. Log in with the old email, or delete the
document from the `users` collection and redeploy.

**`/api/constitution/articles` returns an empty list.** Module seeding did not run.
Check the function logs for "Module seeding failed", and confirm `DATABASE_URL` is
set — in Mongo-only mode there is nothing to seed and every relational endpoint
answers 503. Running `python -m backend.scripts.migrate` from your machine reseeds it.

**A representative profile refuses to publish.** That is the fact-check gate working.
`POST /api/admin/representatives/{id}/publish` lists the claims still marked
unverified; a Fact Checker has to confirm each against its cited source, or the claim
has to be removed. The permission is `representatives.publish`, held by the Fact
Checker and Super Admin roles, and the person who entered a claim cannot verify their
own.

**A template returns 409 "awaiting legal review".** Someone edited it, which resets
its review status by design. Someone with `legal.review` approves it via
`POST /api/admin/tools/templates/{key}/review`.

**QR codes 503 on the event ticket page.** `qrcode` is missing from the deployed
function. It is in all three requirements files; confirm the build installed the root
`requirements.txt`. The ticket code itself is always shown as text, so check-in still
works by typing it.

**The assistant only lists sources instead of answering.** No `GEMINI_API_KEY`, or the
free-tier daily quota is exhausted. Both are expected operating conditions and the
fallback is deliberate — `GET /api/health` shows which.

**`TypeError: connect() got an unexpected keyword argument 'sslmode'`.** An older
build. `sslmode` is a `psql` parameter that the async driver does not accept; the app
now translates it. Pull the latest code and re-run.

**`ConfigurationError: A DNS label is empty`.** `MONGO_URL` still contains the
literal `...` from a copied example. Put your real Atlas string in `backend/.env`.

**Demo data will not load: "DATABASE_URL is not set".** The dataset lives entirely in
the relational database. Export the same `DATABASE_URL` the deployment uses.

**Demo data loaded but pages are still empty.** Run `--status`. If it reports 0, the
load did not commit — check the output for an error. If it reports records but the
site shows nothing, you are pointed at a different database than the deployment.

**`[DEMO]` profiles are visible on a live site.** Run
`python -m backend.scripts.load_demo --purge`. It removes everything and restores the
campaign stages it changed; real data is untouched.
