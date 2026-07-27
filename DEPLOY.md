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
- Node 18+ and Python 3.9+ locally if you want to run things before deploying.

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
| `CORS_ORIGINS`   | no       | defaults to `*`; only needed for cross-origin callers   |

The five required variables are read at import time, so a missing one makes every
`/api/*` request fail with a 500 (`KeyError` in the function logs).

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
   `{"message":"Right to Recall Movement API","status":"ok"}`.

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

### Resetting the admin password

Change `ADMIN_PASSWORD` in the Vercel dashboard and redeploy. On the next cold
start the stored hash is rewritten to match the environment variable.

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
