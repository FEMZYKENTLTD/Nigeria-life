<div align="center">

![Nigeria Life Intelligence Engine — hero](docs/images/hero.jpg)

# Nigeria Life — Intelligence Engine

### A multi-project AI website research, intelligence & analysis platform

**Autonomous. Evidenced. Auditable. Local-first.**

<br>

![Python](https://img.shields.io/badge/Python-3.11-43d692?style=flat)
![Backend](https://img.shields.io/badge/Backend-FastAPI%20·%20SQLAlchemy-6fb1ff?style=flat)
![Frontend](https://img.shields.io/badge/Frontend-React%20·%20TypeScript%20·%20Vite-97a3c0?style=flat)
![Tests](https://img.shields.io/badge/Tests-60%20passing-43d692?style=flat)
![Mode](https://img.shields.io/badge/Mode-local--first%20→%20multi--user-c17d4f?style=flat)
![Theme](https://img.shields.io/badge/Theme-Midnight%20%26%20Copper-c17d4f?style=flat)

<br>

</div>

---

The **Nigeria Life Intelligence Engine** is a general-purpose platform for
researching any public website: it plans investigations, collects public
evidence through sanctioned channels, builds a multi-browser capture
pipeline, stores every finding as *class-tagged evidence*, and renders
**14 report types in 5 formats** — each score shipped with its formula and
inputs, so nothing on a report is arbitrary.

It started from one target (the Lagos Life research package in
[`docs/research/`](docs/research/README.md)) but is built **without a single
hardcoded product**: that package is *data*, imported through the same
generic pipeline any new project would use.

> **"Scores are computed, never arbitrary. Findings carry evidence."** — the
> platform's operating motto, enforced in code, not prose.

---

## What makes it different

| | |
|---|---|
| 🔍 **Honest by construction** | Every failed step persists *why* it failed. Nothing is marked "complete" that is a mockup; gaps are surfaced, never hidden. |
| 🧾 **Evidence integrity** | Every finding carries an ID, a page reference, an evidence reference, a **class (C/S/I/H/U)** and a confidence. The chain of custody is a NOT-NULL foreign-key chain in the database. |
| 📐 **Explained metrics** | Every analytics number returns `{score, components, explanation}` — formula + inputs. If you can't see how a number was made, it isn't a metric here. |
| ⛨ **Human gates** | New sources, permission changes, publication, repo changes, destructive acts and manual-evidence swaps all stop at a *pending decision* until a human approves or rejects. |
| 🌍 **Local-first, cloud-optional** | Runs fully offline on SQLite with deterministic offline AI. Supabase Auth + Postgres and cloud AI are *adapters you switch on with env vars* — not prerequisites. |
| 👥 **Multi-user with admin oversight** | Self-serve email+password accounts, per-user project ownership, and an admin view of **who is using the tool, what each is scraping, and what they are getting**. |
| 🧩 **Extensible** | Four plugin kinds (`ai_provider`, `browser_engine`, `report_format`, `analysis_module`) — third-party components install via a setuptools entry point; a broken plugin is logged and skipped, never fatal. |

---

## Architecture at a glance

```
                       ┌────────────────────────────────────────────┐
                       │            React dashboard (SPA)           │
                       │   Midnight & Copper · Recharts · routes    │
                       └───────────────┬────────────────────────────┘
                                       │ /api/*  /data/*  (same origin)
                       ┌───────────────▼────────────────────────────┐
                       │              FastAPI app (uvicorn)         │
                       │  projects · tasks · research · systems ·   │
                       │  access · users   ──  security (JWT)       │
                       └───────────────┬────────────────────────────┘
             ┌──────────────┬──────────┼───────────────┬───────────────┐
     ┌───────▼───────┐ ┌────▼─────┐ ┌──▼──────────┐ ┌──▼──────────┐ ┌──▼─────────┐
     │  Agent loop   │ │ Browser  │ │  AI layer   │ │   Access &  │ │  Reports & │
     │ planner →     │ │ engines  │ │ pluggable:  │ │   Data:     │ │   Analytics│
     │ subtasks →    │ │ chromium │ │ off /       │ │ scopes,     │ │   (formulas│
     │ exec → gates  │ │ firefox  │ │ openai-compat│ │ connectors, │ │   + inputs)│
     │               │ │ webkit   │ │ ollama      │ │ assets,     │ │            │
     └───────┬───────┘ └────┬─────┘ └─────────────┘ │ manual      │ └────────────┘
             │              │                       │ evidence    │
     ┌───────▼──────────────▼───────────────────────▼─────────────▼──────┐
     │            Storage — SQLite (local) or Supabase Postgres          │
     │   25 tables, every research row carries project_id + evidence FKs │
     └───────────────────────────────────────────────────────────────────┘
```

Full design: [`docs/platform/ARCHITECTURE.md`](docs/platform/ARCHITECTURE.md) ·
Stage-by-stage delivery history: [`docs/platform/IMPLEMENTATION-PLAN.md`](docs/platform/IMPLEMENTATION-PLAN.md) ·
Test evidence: [`docs/platform/ACCEPTANCE.md`](docs/platform/ACCEPTANCE.md) ·
Deployment: [`docs/platform/DEPLOYMENT.md`](docs/platform/DEPLOYMENT.md)

---

## Evidence & integrity — the core contract

Every fact the platform records is an **evidence row**:

```
finding ──cites──▶ evidence ──captured at──▶ page ──collected by──▶ source
  id          ref_code      url / file         project             approval
  class       C|I|S|H|U     checksum           owner_id            status
  confidence  0.0 – 1.0     capture_method
```

| Class | Meaning | Weight |
|---|---|---|
| **C** — Confirmed | Observed first-hand on the public site (read, captured, screenshotted) | `1.00` |
| **I** — Inferred | Derived by the engine from confirmed observations | `0.70` |
| **S** — Sourced | Taken from an identified secondary source (press, registry…) | `0.55` |
| **H** — Hearsay | Second-hand, attributed but not independently checked | `0.30` |
| **U** — Unverified | A claim that exists but has not been checked | `0.15` |

Weights are the *only* place these numbers live
(`EVIDENCE_WEIGHTS` in `models.py`); every metric that touches evidence is a
weighted combination of these, and the report shows the sum.

---

## Metrics you can interrogate

No metric in this platform is a bare percentage. Each returns its formula and
its inputs — for example, **evidence strength** (from `analytics.py`):

```
score = Σ (weight(class) × count(class)) / Σ count(all classes)
```

with the class counts and weights printed as `components` and the arithmetic
shown in `explanation`. A 72% is never just "72%" — it is *29 evidence rows:
12 C, 9 I, 4 S, 3 H, 1 U → (12×1.0 + 9×0.7 + 4×0.55 + 3×0.3 + 1×0.15) / 29*.

---

## Multi-user & admin oversight

<div align="center">

![Admin view — one operator, every user's activity](docs/images/admin-view.jpg)

</div>

The platform ships **local-first**: with no cloud env vars set, there is a
single local operator who is the implicit admin — the same code path, zero
behavior change, all tests included.

Switch on Supabase and it becomes a real multi-user service:

- **Self-serve signup** — email + password in Supabase Auth; the backend
  verifies the JWT (HS256) on every request and registers the profile
  automatically.
- **Strict ownership** — members see *only their own projects*; any other
  project id returns `404` (not `403`) so users can't even probe each
  other's existence. Admins see everything.
- **Admin oversight** — the **Users & Activity** page lists every user with
  live volume (projects, tasks, pages captured, evidence gathered, sessions)
  and a per-user drill-in: *what they are scraping* (URLs, engines, status,
  errors), *what they are getting* (evidence items, task results), and their
  recent activity trail.
- **Role control** — promote/demote with one click; admin emails listed in
  `RICE_ADMIN_EMAILS` are auto-promoted on first login (sticky — never
  silently demoted).
- **RLS defense-in-depth** — the Supabase migration enables row-level
  security on all 25 tables; even the direct (anon-key) surface can only read
  the caller's own projects.

---

## Data & Access — sanctioned collection

Collection is **declared, permission-gated and auditable**. Per project:

- **Collection scopes** — per-domain allowed methods (`http` / `browser` /
  `manual` / `api`), politeness delay, page cap, robots posture. The agent
  reads the scope *before every fetch*. A robots exception is a
  **permission change**: it stays `respect` until a human approves it in the
  AI Agent Centre — and the approval is recorded on the row.
- **Polite HTTP capture** — declared, identifiable user agent (configurable
  via `RICE_BROWSER_UA`), per-scope delays, `ETag` / `Last-Modified`
  conditional re-requests (304 = cache hit, no re-processing).
- **Official API connectors** — the target's *official* API with **your own**
  credentials (the env-var name is stored; the value is never stored or
  logged). Connectors start pending approval; sync is on demand.
- **Licensed data assets** — CSV/JSON/XML you lawfully hold, with mandatory
  provenance + license fields; every row becomes a finding citing the
  evidence file.
- **Manual evidence queue** — everything the agent could not collect
  automatically (pending decisions + blocked fetches *with reasons*), a
  capture form, and a read-only robots.txt posture check. The companion
  **WebExtension** (`platform/extension`) captures the current page from a
  real browser tab as confirmed manual evidence.

### Browser engine

Three Playwright engines (chromium / firefox / webkit) behind one adapter
interface:

- full-page + viewport + **responsive-set** screenshots (sizes recorded),
- console errors, navigation history, per-session execution logs,
- `wait_until` control (`domcontentloaded` / `load` / `networkidle`),
- **standalone page probe** — `POST /api/browsers/inspect` returns an honest
  `{url, status, title, screenshot_size, error}` dict and never raises: a
  failed target is *reported*, a failed engine is *distinguished* (500).
- **Honest degradation** — no binaries installed? Health says so, and the
  agent falls back to the manual-evidence decision gate. No pretending.

---

## Reports — 14 types, 5 formats

Every report type (executive summary, feature inventory, competitive read,
business-model analysis, risk register, and more) renders to:

| Format | Use |
|---|---|
| **Markdown** | source of truth, diffable, in-repo |
| **JSON** | machine-readable bundle |
| **CSV** | spreadsheet / BI ingestion |
| **HTML** | self-contained single file |
| **PDF** | dependency-free multi-page A4 writer (correct xref, 200-page cap) — view inline or download |

---

## Quickstart — local (2 minutes)

```bash
git clone https://github.com/FEMZYKENTLTD/Nigeria-life.git
cd Nigeria-life

# backend
python3.11 -m venv .venv
.venv/bin/pip install -r platform/backend/requirements.txt
cd platform/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
# → API + OpenAPI docs: http://localhost:8787/docs
# → health:            http://localhost:8787/api/health
```

```bash
# frontend (separate shell, repo root)
cd platform/frontend
npm install
npm run dev          # :5173, proxies /api + /data → :8787
# or: npm run build  → dist/, served by the backend itself (single origin)
```

```bash
# optional: browser capture
.venv/bin/python -m playwright install chromium

# optional: import the Lagos Life research package + run a demo pipeline
.venv/bin/python platform/scripts/seed_lagos_life.py
.venv/bin/python platform/scripts/demo_run.py

# the test suite (local + multi-user modes)
cd platform/backend && .venv/bin/python -m pytest tests/ -q     # 60 passed
```

## Full split deployment (production)

Three pieces, each on its own platform — full guide in
[`docs/platform/DEPLOYMENT.md`](docs/platform/DEPLOYMENT.md):

```
 Vercel (static dashboard) ──/api,/data rewrite──▶ Engine container (FastAPI)
        │                                              │  RICE_DB_URL
        │ Supabase Auth REST (email+password)          ▼
        └────────────────────────────────▶  Supabase Postgres (shared DB + RLS)
```

| Piece | Where | Key env |
|---|---|---|
| Dashboard | **Vercel** (`nigeria-life` project) | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `RICE_API_BASE` |
| Engine | any container host — `docker build -f platform/backend/Dockerfile .` | `RICE_DB_URL` (asyncpg DSN), `RICE_SUPABASE_URL`, `RICE_SUPABASE_JWT_SECRET`, `RICE_ADMIN_EMAILS`, `RICE_DATA_DIR` (volume) |
| DB + Auth | **Supabase** | run `platform/supabase/0001_multiuser.sql` once |

Leave all Supabase vars unset and the same container runs in **local mode** —
SQLite, single admin, nothing else to configure.

---

## API at a glance

| Area | Highlights |
|---|---|
| `GET /api/health` · `GET /api/me` | liveness · who am I (identity + role) |
| `/api/projects` | CRUD + `overview` (member-scoped) + **export / import** (portable bundle) |
| `/api/projects/{id}/tasks` | research tasks: create, run, pause, cancel; subtask plans |
| `/api/decisions/{id}/{approve\|reject}` | the human gates |
| `/api/agent/status` · `/api/agent/logs` | the AI Agent Centre (member-scoped) |
| `/api/projects/{id}/pages` `features` `evidence` `observations` `questions` `sources` | the research record |
| `/api/projects/{id}/analytics` | every metric with formula + inputs |
| `/api/projects/{id}/reports[/generate]` | 14 types × 5 formats |
| `/api/projects/{id}/knowledge/search` | semantic-style search over everything |
| `/api/projects/{id}/scope` `connectors` `data-assets` `manual-captures` `manual-queue` `robots-check` | sanctioned collection controls |
| `/api/browsers/health` `profiles` `inspect` · `/api/sessions` | browser engine management |
| `/api/users` `users/{id}` `users/{id}/role` | admin: who's using the tool + what they're getting |
| `/api/systems/backup` `backups` · `/api/plugins` · `/api/github/*` | platform ops |

Interactive docs at `/docs` when the backend is running.

---

## Repository layout

```
Nigeria-life/
├── README.md                     ← you are here
├── .github/workflows/ci.yml      ← CI gate on main (pytest + tsc + build)
├── docs/
│   ├── research/                 ← the Lagos Life research package (data)
│   ├── platform/                 ← ARCHITECTURE · ACCEPTANCE · DEPLOYMENT · PLAN
│   └── images/                   ← README artwork (Midnight & Copper)
└── platform/
    ├── backend/                  ← FastAPI app: engine, API, security, tests
    │   ├── app/
    │   │   ├── api/              ← projects · tasks · research · systems · access · users
    │   │   ├── engine/           ← agent loop, analytics, reports, browser, pdf, plugins…
    │   │   ├── security/         ← Supabase JWT + ownership + roles
    │   │   ├── models.py         ← 25 tables · evidence classes & weights
    │   │   └── main.py           ← app factory, lifespan, static serving
    │   ├── tests/                ← 60 tests (local + multi-user + browser inspect)
    │   ├── Dockerfile            ← engine container
    │   └── requirements.txt
    ├── frontend/                 ← React + TS + Vite + Tailwind + Recharts
    │   ├── src/                  ← pages, api client, auth, Midnight & Copper theme
    │   └── vercel.json           ← /api + /data → RICE_API_BASE, SPA fallback
    ├── extension/                ← Manifest V3 manual-evidence bridge
    ├── desktop/                  ← Tauri 2 shell scaffold + build instructions
    ├── scripts/                  ← seed_lagos_life.py · demo_run.py
    ├── supabase/                 ← 0001_multiuser.sql (profiles + owner_id + RLS)
    └── data/                     ← local-first runtime state (git-ignored)
```

---

## Development

- **Tests** — `platform/backend/tests/`: 60 tests covering the API
  lifecycle, agent end-to-end, evidence import, analytics, reports,
  knowledge, browser behaviour, data-ops (backup/export/import), **and
  multi-user mode end-to-end** (unauth 401, ownership isolation, admin
  visibility, role changes) in-process against a temp DB.
- **CI** — every push/PR to `main` runs `backend-pytest` and
  `frontend-build` (tsc + production build); Vercel builds a preview on each
  branch. Branch protection on `main` makes the gate binding
  (setup: DEPLOYMENT.md §4).
- **Frontend theming** — the "Midnight & Copper" palette lives entirely in
  Tailwind token *values* (`tailwind.config.js`) — midnight-blue base
  `#0d1322`, ivory text `#ece7db`, copper accent `#c17d4f` — so a recolor is
  a one-file change.

### Configuration (env, prefix `RICE_`)

| Variable | Default | Notes |
|---|---|---|
| `RICE_DB_URL` | SQLite in `platform/data/` | `postgresql+asyncpg://` DSN for shared Postgres |
| `RICE_DATA_DIR` | `platform/data` | evidence files, screenshots, exports, backups |
| `RICE_SUPABASE_URL` + `RICE_SUPABASE_JWT_SECRET` | unset | **both set → multi-user JWT mode** |
| `RICE_ADMIN_EMAILS` | unset | comma-separated emails auto-granted admin (sticky) |
| `RICE_AI_PROVIDER` | `off` | `off` (deterministic) / `openai_compatible` / `ollama` |
| `RICE_AI_BASE_URL` `RICE_AI_API_KEY` `RICE_AI_MODEL_SMALL` `RICE_AI_MODEL_LARGE` | — | the key is in-process only — never logged, never persisted |
| `RICE_BROWSER_UA` | declared research UA | the identifiable user agent for all captures |
| `RICE_BROWSER_TIMEOUT_MS` / `RICE_BROWSER_MAX_RETRIES` | 30000 / 2 | capture robustness |
| `RICE_MAX_PAGES_PER_SESSION` | 40 | politeness cap |
| `RICE_GITHUB_REPO` / `RICE_LOCAL_REPO_PATH` | this repo / unset | knowledge repo + local git reads |
| `RICE_HOST` / `RICE_PORT` | 0.0.0.0 / 8787 | API bind |

---

## Operating rules the engine enforces

1. **Read before research** — the research README + investigation log are
   read from the repo before any new investigation starts.
2. **No silent failure** — every failed step persists its reason; tasks
   report exactly what remains incomplete; nothing is "complete" that is
   only a mockup.
3. **Human gates** — sources, permissions, publication, repo changes,
   destructive acts and manual-evidence swaps stop at a pending decision
   (dashboard: AI Agent Centre).
4. **Declared collection** — an identifiable, configurable user agent; no
   credential storage. robots.txt is respected (unreadable file = safe
   default *disallowed*); restricted sources use the manual-evidence path; a
   robots exception is only possible through a recorded human approval.
5. **Explained scores** — every analytics metric returns its formula and
   its inputs; no arbitrary percentages.

---

## Documentation map

| Document | What it is |
|---|---|
| [`docs/platform/ARCHITECTURE.md`](docs/platform/ARCHITECTURE.md) | full design: 10 subsystems, data model, engine behaviour |
| [`docs/platform/IMPLEMENTATION-PLAN.md`](docs/platform/IMPLEMENTATION-PLAN.md) | stage-by-stage delivery history (Stages 1–9) |
| [`docs/platform/ACCEPTANCE.md`](docs/platform/ACCEPTANCE.md) | test + live-run evidence per stage |
| [`docs/platform/DEPLOYMENT.md`](docs/platform/DEPLOYMENT.md) | Supabase → engine container → Vercel, end to end |
| [`platform/README.md`](platform/README.md) | the operational runbook (dashboard sections, browser setup, extension) |
| [`docs/research/README.md`](docs/research/README.md) | the Lagos Life research package (14 documents, evidence register) |

---

<div align="center">

**Built to be read, audited and trusted.**
Every number explains itself · every finding cites its evidence · every
gap is named.

*FEMZYK Enterprises Ltd — `FEMZYKENTLTD/Nigeria-life`*

</div>
