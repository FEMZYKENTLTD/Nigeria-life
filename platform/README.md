# Nigeria Life Intelligence Engine — Runbook

A standalone, multi-project AI website research, intelligence and analysis
platform. FastAPI + SQLite (local-first) + Playwright multi-browser +
pluggable AI adapters + React dashboard. See
[docs/platform/ARCHITECTURE.md](../docs/platform/ARCHITECTURE.md) for the
design and [docs/platform/ACCEPTANCE.md](../docs/platform/ACCEPTANCE.md) for
test evidence.

```
platform/
├── backend/    FastAPI app (engine, API, tests)
├── frontend/   React + TS + Vite + Tailwind + Recharts dashboard
├── extension/  WebExtension (Manifest V3) manual-evidence bridge
├── desktop/    Tauri 2 shell scaffold + build instructions
├── scripts/    seed_lagos_life.py, demo_run.py
└── data/       local-first runtime state (git-ignored)
```

## Quickstart

### 1. Backend

```bash
python3.11 -m venv .venv                          # once, at repo root
.venv/bin/pip install -r platform/backend/requirements.txt
cd platform/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

- API + docs: http://localhost:8787/docs
- Health: http://localhost:8787/api/health
- The app also serves the built dashboard at `/` (when `frontend/dist`
  exists) — single origin, no CORS needed in production.

### 2. Frontend

```bash
cd platform/frontend
npm install
npm run dev        # dev server :5173, proxies /api + /data -> :8787
npm run build      # production bundle -> dist (served by the backend)
```

Theme is "Midnight & Copper" (midnight-blue base, ivory text, copper accent —
deliberately not gold/black). It lives entirely in the Tailwind token *values*
(`tailwind.config.js`) plus a few CSS/template constants, so recolouring is a
one-file change.

### 3. Seed the first project (optional demo)

The existing `docs/research/` package is imported through the **generic**
pipeline — Lagos Life is data, not code:

```bash
.venv/bin/python platform/scripts/seed_lagos_life.py   # imports 14 documents
.venv/bin/python platform/scripts/demo_run.py          # full pipeline demo
```

### 4. Tests

```bash
cd platform/backend
.venv/bin/python -m pytest tests/ -q        # 57 passed
```

### 5. Data & Access (dashboard section)

Sanctioned collection controls, per project:

- **Collection scopes** — per-domain allowed methods (`http` / `browser` /
  `manual` / `api`), politeness delay, page cap, robots.txt posture. A
  robots exception is a *permission change*: the request stays `respect`
  until a human approves it in the AI Agent Centre.
- **Polite HTTP capture** — declared UA, delays, ETag / Last-Modified
  conditional re-requests (304 = cache hit, no re-processing).
- **Official API connectors** — the target's official API with *your own*
  credentials (env var name only; values never stored or logged). Starts
  pending approval; sync on demand.
- **Licensed data assets** — CSV/JSON/XML you lawfully hold, with mandatory
  provenance + license; every row becomes a finding citing the evidence.
- **Manual evidence queue** — everything the agent could not collect
  automatically (pending decisions + blocked fetches with reasons), plus a
  capture form and a read-only robots.txt check.

### 6. Data & Ops (dashboard section)

Platform operations, independent of the selected project:

- **Backups** — "Create Backup" WAL-checkpoints and copies the database to
  `platform/data/backups/` (keeps the last 20). The list shows each file,
  size and timestamp. On a Postgres deployment the endpoint returns a clear
  503 pointing at the documented `pg_dump` path instead of guessing.
- **Plugin registry** — read-only view of the four extensible component
  kinds (`ai_provider`, `browser_engine`, `report_format`,
  `analysis_module`) with built-ins marked. External plugins install via the
  `rice.plugins` setuptools entry-point group; a broken plugin is logged and
  skipped, never fatal.
- **Export / import a project** — export downloads a versioned JSON bundle
  of one project (pages, features, evidence, findings, questions, sources,
  scopes, assets, reports); evidence references are normalised so the bundle
  is portable. Import recreates it as a **new, fully isolated** project with
  fresh ids and remapped cross-references. Robots exceptions and approvals do
  **not** travel — re-decide them locally.

### 7. Reports: five formats

Every one of the 14 report types renders to Markdown (source of truth),
JSON, CSV, self-contained HTML and — new — **PDF** (a dependency-free
multi-page A4 writer; view inline or download from the Reports viewer).

### 8. Browser captures (where available)

```bash
.venv/bin/python -m playwright install chromium   # and/or firefox, webkit
```

If the Playwright CDN is unreachable (as in the original sandbox), the
browser health service reports `installed=false` and the agent falls back to
the manual-evidence path: it raises a `manual_evidence` decision that a
human approves (import evidence) or rejects (capture skipped, gap stated).

### 9. WebExtension evidence bridge

`chrome://extensions` → Developer mode → Load unpacked → select
`platform/extension`. Open the side panel **from the toolbar icon** (that
click is what grants the temporary page access), pick a project, optionally
add a title/notes, and capture the current page — rendered HTML + visible-tab
screenshot included, posted as confirmed manual evidence. No background
reading, no restriction bypass.

### 10. Desktop (Tauri 2)

See `platform/desktop/README.md` — scaffold + per-OS build instructions;
no pre-built binaries are committed.

## Configuration (env, prefix `RICE_`)

| Var | Default | Notes |
|---|---|---|
| `RICE_DB_URL` | sqlite in `platform/data/` | set a `postgresql+asyncpg://` URL for central storage |
| `RICE_DATA_DIR` | `platform/data` | evidence files, screenshots, exports |
| `RICE_AI_PROVIDER` | `off` | `off` (deterministic) / `openai_compatible` / `ollama` |
| `RICE_AI_BASE_URL`, `RICE_AI_API_KEY`, `RICE_AI_MODEL_SMALL`, `RICE_AI_MODEL_LARGE` | — | the key is used in-process only, never logged or persisted |
| `RICE_BROWSER_TIMEOUT_MS` / `RICE_BROWSER_MAX_RETRIES` | 30000 / 2 | capture robustness |
| `RICE_MAX_PAGES_PER_SESSION` | 40 | politeness cap |
| `RICE_GITHUB_REPO` | `FEMZYKENTLTD/Nigeria-life` | central knowledge repo |
| `RICE_LOCAL_REPO_PATH` | — | set to a local checkout for local git reads |
| `RICE_PORT` / `RICE_HOST` | 8787 / 0.0.0.0 | API bind |

## Operating rules the engine enforces

1. **Read before research** — the research README + investigation log are
   read from the repo before any new investigation starts.
2. **No silent failure** — every failed step persists its reason; tasks
   report exactly what remains incomplete; nothing is "complete" that is
   only a mockup.
3. **Human gates** — new sources, permission changes, publication,
   repository changes, destructive acts and manual-evidence swaps all stop
   at a pending decision (dashboard: AI Agent Centre).
4. **No evasion** — no stealth, no CAPTCHA bypass, no credential storage.
   robots.txt is respected (unreadable file = safe default *disallowed*);
   restricted sources use the manual-evidence path; a robots exception is
   only possible through a recorded human approval.
5. **Explained scores** — every analytics metric returns its formula and
   inputs; no arbitrary percentages.
