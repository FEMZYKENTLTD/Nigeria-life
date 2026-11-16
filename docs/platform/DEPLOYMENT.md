# Deployment Guide — Full Split

Three pieces, each on its own platform:

```
┌────────────────────┐        ┌──────────────────────────┐
│  Vercel (static)   │        │  Engine container        │
│  Dashboard (SPA)   │  /api  │  FastAPI + Playwright    │
│  VITE_SUPABASE_*   │───────▶│  RICE_DB_URL ─────────────┼──▶ Supabase Postgres
└─────────┬──────────┘  /data └──────────────────────────┘         (shared DB, RLS)
          │ Supabase Auth REST (email + password, self-serve)
          ▼
┌────────────────────┐
│  Supabase Auth     │  issues HS256 JWTs — verified by the engine
└────────────────────┘
```

* **Supabase** — authentication (email + password, self-serve signup) and the
  shared PostgreSQL database. The engine verifies every JWT with the project
  JWT secret; ownership + RLS keep users isolated.
* **Engine container** — the FastAPI backend + research engine + browser
  capture. Connects to Supabase Postgres as the `postgres` role (trusted
  backend; RLS still guards the direct/anon surface).
* **Vercel** — the built dashboard. All `/api/*` and `/data/*` requests are
  rewritten to the engine host (`RICE_API_BASE`).

Local development is unchanged: no env → SQLite + single local operator.

---

## 1. Supabase

> **Status (2026-11-15):** not created yet — the org's free plan is at its
> 2-project limit (`femzyk-fleet`, `klc-cbt`). Free one of those slots (pause
> one) or upgrade the plan, then follow these steps.

1. **Create the project** (supabase.com/dashboard → New project).
2. **Boot the engine once** against this project's database so it creates its
   schema (any container host, or the steps below with a temporary DB URL).
   Tables the engine owns are created automatically.
3. **Apply the multi-user migration**
   [`platform/supabase/0001_multiuser.sql`](../platform/supabase/0001_multiuser.sql)
   in SQL Editor (idempotent): `profiles`, `projects.owner_id`, RLS on all
   tables, `is_admin()` / `can_see_project()` helpers.
4. **Auth settings** (Authentication → Providers → Email):
   * enable **Email**, disable others you don't want;
   * set **Site URL** to the Vercel deployment URL (used in confirm emails);
   * keep **Confirm email** on for safety (or off for open self-serve).
5. **Collect the values you need:**

   | Value | Where | Used as |
   |---|---|---|
   | Project URL | Settings → API | `RICE_SUPABASE_URL` (engine) + `VITE_SUPABASE_URL` (Vercel) |
   | `anon` / `public` key | Settings → API | `VITE_SUPABASE_ANON_KEY` (Vercel only — never on the server) |
   | JWT Secret | Settings → API → JWT | `RICE_SUPABASE_JWT_SECRET` (engine only — never shipped to clients) |
   | DB connection string | Settings → Database | `RICE_DB_URL` (engine) — rewrite the scheme to `postgresql+asyncpg://` |

6. **Seed the admin** — the admin email is granted the role automatically on
   first login (sticky): set `RICE_ADMIN_EMAILS` on the engine (e.g.
   `femzykenterprisesltd@gmail.com`). No SQL seeding needed.

## 2. Engine container

Build from the repository root:

```sh
docker build -f platform/backend/Dockerfile --build-arg INSTALL_BROWSERS=1 -t rice-engine .
```

`INSTALL_BROWSERS=1` adds Chromium for real browser capture; without it the
engine degrades honestly to manual evidence import.

Run on any container host (Railway / Fly / Render / a VPS):

```sh
docker run -d --name rice -p 8787:8787 \
  -e RICE_DB_URL="postgresql+asyncpg://postgres:***@db.<ref>.supabase.co/postgres" \
  -e RICE_SUPABASE_URL="https://<ref>.supabase.co" \
  -e RICE_SUPABASE_JWT_SECRET="***" \
  -e RICE_ADMIN_EMAILS="you@example.com" \
  -e RICE_DATA_DIR=/data \
  -v rice-data:/data \
  rice-engine
```

Environment reference:

| Variable | Required | Notes |
|---|---|---|
| `RICE_DB_URL` | shared mode | `postgresql+asyncpg://` DSN |
| `RICE_SUPABASE_URL` + `RICE_SUPABASE_JWT_SECRET` | shared mode | enables JWT auth; leave unset for local mode |
| `RICE_ADMIN_EMAILS` | shared mode | comma-separated admin emails |
| `RICE_DATA_DIR` | — | evidence files / screenshots / backups; mount a volume |
| `RICE_AI_PROVIDER` / `RICE_AI_BASE_URL` / `RICE_AI_API_KEY` / `RICE_AI_MODEL_*` | optional | AI layer; key is never logged or persisted |
| `RICE_BROWSER_UA` | optional | declared, identifiable user-agent for captures |

## 3. Vercel

> **Status (2026-11-15):** the project **`nigeria-life`** already exists in the
> `fan-card` team, linked to `FEMZYKENTLTD/Nigeria-life` (production branch
> `main`, root `platform/frontend`, build `npm run build`, output `dist`).
> Auto-deployments are disabled on this team, so the **first deployment needs
> one manual trigger** in the Vercel dashboard (or enable auto-deployments on
> the project after that).

1. **First deployment:** Vercel dashboard → `nigeria-life` → *Deploy* (or
   Settings → Git → enable "Auto Deploy"). It builds from `main`, so it picks
   up the platform code once PR #3 is merged.
2. **Environment variables** (all environments):

   | Variable | Value |
   |---|---|
   | `VITE_SUPABASE_URL` | Supabase project URL |
   | `VITE_SUPABASE_ANON_KEY` | Supabase `anon` key |
   | `RICE_API_BASE` | Engine public URL, e.g. `https://rice.example.app` (no trailing slash) |

3. **Deploy.** `platform/frontend/vercel.json` rewrites:
   `/api/* → $RICE_API_BASE/api/*`, `/data/* → $RICE_API_BASE/data/*`,
   everything else → `index.html` (SPA).
4. **Custom domain** (optional) → set it as the **Site URL** in Supabase Auth.

## 4. Branch protection on `main` (one-time)

The CI gate is active; to make it binding, set the protection rule once in
the GitHub web UI (the arena integration token cannot write branch rules):

1. GitHub → `FEMZYKENTLTD/Nigeria-life` → **Settings** → **Branches** →
   **Add branch protection rule** → pattern `main`.
2. Tick:
   * **Require status checks to pass before merging** → select
     `backend-pytest` and `frontend-build` → also tick
     "Require branches to be up to date before merging".
   * **Do not allow force pushes**, **Do not allow deletions**.
   * **Include administrators** (so nobody can bypass the gate).
3. Save. From then on, nothing lands on `main` unless the whole suite is
   green.

## 5. Smoke test

```sh
curl -s $RICE_API_BASE/api/health
# {"status":"ok","ai_provider":"off","db":"postgresql"}
```

1. Open the Vercel URL → **Create account** → sign in.
2. First request registers your profile; the admin email gets the `admin` role.
3. Admin: **Users & Activity** in the sidebar lists every user with their
   scraping volume and lets you drill into what they scraped and got.
4. Members see only their own projects; other users' project ids 404.

## 6. Upgrading

1. Merge to `main` (CI must be green — branch protection enforces it).
2. Rebuild + redeploy the engine container. The schema migrator
   (`app/db.py::_ensure_schema`) applies additive changes idempotently; for
   anything more than that, run the migration in the Supabase SQL editor and
   then roll the container.
3. Vercel picks up `main` automatically.
