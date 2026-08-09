# Deploying to Vercel

One Vercel project serves both halves of this app:

- the React (CRA + craco) frontend, built from `frontend/` into `frontend/build`
  and served as static files;
- the FastAPI backend, served as a single Python serverless function from
  `api/index.py`, which imports the app from `backend/server.py`.

Because both are on the same origin, the frontend talks to the API through the
relative path `/api` and needs no backend URL configured.

## Prerequisites

- A Vercel account.
- The `vercel` CLI (`npm i -g vercel`). This project deploys straight from your
  machine, so no git hosting account is required.
- A MongoDB database reachable from the public internet (Atlas free tier is
  fine). The bundled JSON files in `backend/content/` are seeded into it
  automatically on first boot.
- A Postgres database (Neon free tier is fine). Holds staff identity, roles and
  permissions, the states table and the audit log. See step 1b.
- Node 18+ and Python 3.12 locally if you want to run things before deploying.
  (Python 3.10 is the floor — several pinned dependencies require it — and 3.12
  matches what Vercel runs.)

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
2. Copy the connection string from the dashboard. A plain
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`
   is fine — the async driver prefix is added by the app.
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
{ "status": "ok", "mongo": true, "postgres": true }
```

Do **not** set `REACT_APP_BACKEND_URL`. Leaving it unset is what makes the
frontend use the same-origin `/api` path. Only set it if you deliberately point
the site at a backend hosted elsewhere. See `frontend/.env.example` and
`backend/.env.example` for local development templates.

## 3. Deploy

1. Import the repository in Vercel. Leave **Root Directory** as the repo root -
   `vercel.json` already handles building `frontend/` from there:
   - install: `cd frontend && npm install --legacy-peer-deps`
     (the `--legacy-peer-deps` flag is required: `react-day-picker@8` declares a
     peer range that excludes React 19)
   - build: `cd frontend && CI=false npm run build` (`CI=false` keeps CRA lint
     warnings from failing the build)
   - output: `frontend/build`
2. Add the environment variables from step 2 **before** the first deploy.
3. Deploy. Vercel builds the static frontend and, separately, installs the root
   `requirements.txt` and bundles `api/index.py` as a Python function.
4. Verify: `curl https://YOUR-DOMAIN/api/` should return
   `{"message":"Right to Recall Movement API","status":"ok"}`, and
   `curl https://YOUR-DOMAIN/api/health` should report `"postgres": true`.

Routing comes from the `rewrites` in `vercel.json`: `/api/*` goes to the Python
function, and anything that is not an existing static file falls through to
`/index.html` so React Router handles client-side routes on refresh/deep links.

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
citizen1@demo.rtr.invalid  ...  citizen14@demo.rtr.invalid
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

**Demo data will not load: "DATABASE_URL is not set".** The dataset lives entirely in
the relational database. Export the same `DATABASE_URL` the deployment uses.

**Demo data loaded but pages are still empty.** Run `--status`. If it reports 0, the
load did not commit — check the output for an error. If it reports records but the
site shows nothing, you are pointed at a different database than the deployment.

**`[DEMO]` profiles are visible on a live site.** Run
`python -m backend.scripts.load_demo --purge`. It removes everything and restores the
campaign stages it changed; real data is untouched.
