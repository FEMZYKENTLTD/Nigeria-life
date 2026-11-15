# Nigeria Life Intelligence Engine — Architecture

Version 1.0 · 2026-11-14 · Status: implemented, tested (38/38), running

This document describes the system as it is **actually implemented** under
`platform/`. Where a capability is limited by the current environment, the
limitation is stated explicitly — the platform's contract is to report gaps,
not to hide them.

---

## 1. Purpose and design principles

A standalone, general-purpose, multi-project AI website research,
intelligence and analysis platform. It plans, executes, analyses, persists
and reports on research autonomously.

**No target, product, page structure or business model is hardcoded anywhere
in the core.** Lagos Life (the existing `docs/research/` package) is merely
the first project, imported through the same generic import pipeline any
future project uses.

Design principles, enforced in code:

| Principle | Where enforced |
|---|---|
| Evidence integrity — every finding has ID, page ref, evidence ref, class (C/S/I/H/U), confidence, status | `models.py` (NOT NULL FK chains), `evidence_import.py`, `knowledge.py` |
| Honest failure — nothing is marked complete that is only a mockup; failures persist with reasons | `agent_loop.py` (loud failure paths, `_incomplete_summary`), analytics (no fake coverage) |
| No arbitrary percentages — every score ships its formula and inputs | `analytics.py` — each metric returns `score`, `components`, `explanation` |
| Strict permissions — no stealth, no evasion, no credential storage; manual import is the sanctioned restricted path | `systems.py` source approval, `agent_loop.py` `PermissionGate` + human `Decision` rows |
| Local-first — works fully offline; cloud AI is an optional adapter | `ai/registry.py`, `ai/offline.py` (deterministic heuristics are the default) |
| Multi-project isolation — projects own tasks, evidence, sessions, reports; core is shared | every table carries `project_id`; queries are scoped |

## 2. System overview

```
                        ┌────────────────────────────────────────────┐
                        │           React + TS dashboard             │
                        │  (Vite dev :5173 → proxy /api → :8787)     │
                        │  production: same origin, served by API    │
                        └──────────────────────┬─────────────────────┘
                                               │ REST (JSON)
┌──────────────────────────────────────────────▼─────────────────────────────┐
│                        FastAPI application (app/main.py)                   │
│  /api/*  projects · tasks · decisions · pages · features · evidence ·      │
│           observations · questions · sources · analytics · reports ·       │
│           agent · browsers · knowledge · github · health                   │
│  /data/* evidence files, screenshots, report exports (static)              │
└──────┬───────────────────────┬───────────────────────────────┬─────────────┘
       │                       │                               │
┌──────▼───────┐   ┌───────────▼──────────┐   ┌────────────────▼────────────┐
│ Storage      │   │ Engine layer         │   │ Integrations                │
│  SQLite (WAL) │   │ planner · agent_loop │   │ ai/  offline | openai-compat│
│ 25 tables    │   │ page_understanding   │   │        | ollama (pluggable) │
│ platform/    │   │ feature_engine       │   │ browser/ chromium|firefox   │
│ data/rice.db │   │ analytics · reports  │   │          |webkit (adapters) │
│ → Postgres   │   │ knowledge (TF-IDF)   │   │ github_int/ gh CLI, local   │
│   via env    │   │ evidence_import      │   │          checkout, PR gate  │
└──────────────┘   └──────────────────────┘   └─────────────────────────────┘
```

## 3. Repository layout

```
platform/
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, lifespan, recovery, static serving
│   │   ├── config.py          # 12-factor settings (env prefix RICE_)
│   │   ├── db.py              # async engine, session_scope, WAL pragmas
│   │   ├── models.py          # 21 SQLAlchemy models (the contract)
│   │   ├── schemas.py         # Pydantic response schemas
│   │   ├── logging_conf.py    # structured JSON logging
│   │   ├── api/               # routers: projects, research, tasks, systems,
│   │   │                        #   access (scopes/connectors/assets/manual)
│   │   ├── engine/
│   │   │   ├── planner.py           # objective → typed subtask graph
│   │   │   ├── agent_loop.py        # autonomous execution + permission gates
│   │   │   ├── page_understanding.py# HTML → structured page record
│   │   │   ├── feature_engine.py    # feature extraction + 20 categories
│   │   │   ├── analytics.py         # deterministic, explained metrics
│   │   │   ├── reports.py           # 14 report types, MD/JSON/CSV/HTML
│   │   │   ├── knowledge.py         # TF-IDF semantic search + upserts
│   │   │   ├── evidence_import.py   # docs/research package → project
│   │   │   ├── textsim.py           # token/Jaccard similarity utilities
│   │   │   ├── robots.py            # robots.txt compliance (TTL-cached)
│   │   │   ├── politeness.py        # sha256 + ETag/Last-Modified headers
│   │   │   ├── http_fetch.py        # polite GET capture + fetch cache
│   │   │   ├── api_connect.py       # official API connectors (env creds)
│   │   │   ├── data_import.py       # licensed CSV/JSON/XML → findings
│   │   │   └── browser/             # base adapter, engines, session manager
│   │   ├── ai/                  # base, offline, openai_compat, registry
│   │   └── github_int/          # gh CLI wrapper + local checkout + write gate
│   ├── tests/                 # 38 tests: unit, integration, e2e
│   ├── requirements.txt       # pinned dependencies
│   └── pytest.ini
├── frontend/                  # React 18 + TS + Vite + Tailwind + Recharts
│   └── src/
│       ├── App.tsx            # shell: sidebar nav, project selector
│       ├── api.ts             # typed client (relative URLs only)
│       ├── components/ui.tsx  # cards, KPIs, status pills, data hooks
│       └── pages/             # 10 dashboard sections
├── scripts/
│   ├── seed_lagos_life.py     # imports docs/research as project #1
│   └── demo_run.py            # full pipeline demonstration
└── data/                      # local-first runtime state (git-ignored)
    └── rice.db                # SQLite (WAL)
```

## 4. Data model (25 tables, `models.py`)

All primary keys are ULIDs (time-sortable, collision-safe strings); every
domain row carries `project_id` for isolation; timestamps are ISO-8601 UTC.

| Table | Role |
|---|---|
| `projects` | name, slug, description, industry, target URL, permissions JSON, repo URL, status |
| `sources` | target URLs/domains; `status`: pending_approval / authorised / denied — scheduler refuses unapproved sources |
| `research_tasks` | objective, status (`queued/planned/running/waiting_decision/complete/failed/cancelled`), priority, progress, error, result summary |
| `subtasks` | typed steps (`discover/fetch/understand/document/analyse/report`), attempts, last_error, `requires_approval` flag (persisted — the gate must survive process restarts) |
| `decisions` | human approval gate rows: kind (`new_source`, `permission_change`, `manual_evidence`, `repo_change`, `publication`, `destructive`), question, context, verdict, decided_at |
| `page_records` | URL, title, purpose, content_category, regions/sections JSON, empty/error detection, capture method, evidence refs |
| `evidence` | ref_code (E01…), class **C**onfirmed/**S**econdary/**I**nferred/**H**ypothesis/**U**nknown, source URI/name, capture method, quality score |
| `screenshots` | page-linked capture registry, responsive-set grouping, perceptual-hash for change detection |
| `observations` | atomic findings: kind, observation text, key/value, class, confidence, linked page + evidence |
| `features` | 15-field records: name, category (20 categories), description, purpose, access, limitations, opportunities, dependencies, related, confidence, status, evidence refs |
| `unresolved_questions` | open research questions with context and status |
| `browser_profiles` | separate user-data dirs per project/purpose; engine + viewports |
| `browser_health` | last probe per engine: installed, version, error |
| `research_sessions` | one capture run: engine, mode, status, summary, error |
| `execution_logs` | per-session event log (level, event, message, ts) |
| `knowledge_entries` | versioned searchable entries (`is_current`, version, kind, title, body, embeddings metadata) |
| `reports` | generated report: type, title, format, content, generated_at |
| `github_state` | last sync state, digested docs, defaults |
| `activity_logs` | actor (user/agent/system), action, subject, detail |
| `agent_runs` | per run: mode, status, started/ended, task ids |
| `collection_scopes` | per-project, per-domain access declaration: allowed methods (browser/http/manual/api), min delay, page cap, robots posture. `robots_mode=approved_exception` is only ever set by an approved `permission_change` decision |
| `api_connectors` | official API of a target/provider: base URL, auth type, credential **env var name** (value never stored), endpoints, sync state |
| `data_assets` | licensed/purchased datasets: filename, format, provenance, license, row count, linked evidence |
| `fetch_cache` | ETag / Last-Modified / content-sha per URL per project — 304 and unchanged content short-circuit re-processing |

Storage engine: **SQLite in WAL mode** (`journal_mode=WAL`,
`busy_timeout=8000`, `synchronous=NORMAL`) — the documented, tested concurrency
recipe for overlapping async sessions. `RICE_DB_URL`
(`postgresql+asyncpg://…`) switches the same models to PostgreSQL for central
deployments; no code changes required.

## 5. Request flow

### 5.1 Normal research run (the agent loop)

```
POST /api/projects/{id}/tasks            create task (objective)
POST /api/tasks/{id}/run                 hand to scheduler → asyncio task
      │
      ▼
planner.plan(objective)                  typed subtask graph:
      discover → fetch* → understand → document → analyse → report
      (*fetch only if the scope allows a method, robots.txt permits it
        (or a human-approved exception), the page cap is not hit, AND a
        capable collector is available)
      │
      ▼
agent_loop.execute_task                  for-iteration (hard cap 250, loud
      │  for each subtask:                   failure if ever exceeded)
      │    execute → persist state → checkpoint
      │    on PermissionGate → PERSIST requires_approval=true,
      │      raise pending Decision, task → waiting_decision, STOP cleanly
      │    on failure → subtask last_error, task failed + _incomplete_summary
      │    on success → upsert knowledge entries, activity log
      ▼
task complete → result summary lists exactly what was done and what remains
```

Key invariants (all covered by `tests/test_agent_e2e.py`):

- **The permission gate is persisted, not in-memory.** A gated subtask keeps
  `requires_approval=true` across restarts; the loop cannot re-spawn work it
  is waiting on. (Regression fixed: the flag was once set on a detached ORM
  row, causing an infinite loop of repeated browser driver starts.)
- **Decisions resume or skip.** `POST /api/decisions/{id}/approve|reject`
  resumes the waiting task; a rejected capture marks the subtask `skipped`
  and the task completes with the gap stated in the summary.
- **Recovery on boot.** `main.py` lifespan re-queues any task found in
  `running/planned` after an interrupted process, with the reason logged.
- **Failure is loud.** An unknown report type, a missing binary, a refused
  source — each produces a persisted `last_error`, a failed task, and an
  activity-log line. Nothing disappears.

### 5.2 Human-in-the-loop boundary

Consequential actions stop at a `Decision` row and surface in the dashboard
(AI Agent Centre) and in the API (`/api/agent/status` → `pending_decisions`):

1. **New third-party source** — registered `pending_approval`; scheduler will
   not touch it until approved (covers registered API connectors too).
2. **Permission change** — per-project scope expansion requires approval,
   including **robots.txt exceptions**: the request saves the scope with
   `respect` posture and a pending decision; only approval flips it to
   `approved_exception` (with the sign-off recorded on the scope row).
3. **Manual evidence** — when a source disallows automation (or no browser is
   available), the agent asks for a human to import evidence instead of
   evading the restriction.
4. **Repository change** — GitHub write-back (branch + PR, `docs/**` only)
   requires an approved `repo_change` decision; secrets in generated content
   abort the write.
5. **Publication / destructive acts** — same gate pattern.

## 6. Engine layer details

### 6.1 Planner (`planner.py`)

Decomposes a natural-language objective into a subtask graph with priorities.
Offline heuristic planner (keyword-driven, deterministic) is the default;
when `RICE_AI_PROVIDER` is set (OpenAI-compatible or Ollama), the LLM plan
is used with the same schema. Plan output is persisted so interrupted runs
resume from the checkpoint, not from scratch.

### 6.2 Page understanding (`page_understanding.py`)

Pure-Python HTML → structured `page_records` row: title, purpose heuristic,
content category, region detection (header/nav/main/footer/sidebar),
navigation items, forms, controls, interactive components, sections,
outbound/internal links, and **state detection** (empty / error / loading /
auth-required). No AI required; the AI adapter may enrich the summary when
configured. 9 unit tests pin the behaviour.

### 6.3 Feature engine (`feature_engine.py`)

Extracts feature candidates from page content with a rule set that checks
**specific revenue terminology before generic economy terms** (e.g.
`billboard/subscription/checkout` → monetisation before `pay/price` →
economy), assigns one of 20 categories, and builds 15-field feature records
with evidence refs, limitations, opportunities and dependencies.

### 6.4 Analytics (`analytics.py`) — deterministic and explained

Every metric returns `{score, components, explanation}` where the
explanation is the human-readable formula with the actual inputs:

- **Research completeness** = 0.30·objective progress + 0.25·feature
  completeness + 0.20·page coverage + 0.15·evidence quality + 0.10·(1 − open
  questions pressure).
- **Page coverage** = documented pages / known pages (from the target's
  navigation/links + imported inventory).
- **Feature completeness** = documented features / identified features.
- **Evidence quality** = class-weighted mean (C=1.0, S=0.8, I=0.5, H=0.3, U=0.1).
- **Duplicates** = Jaccard similarity ≥ 0.60 on normalised token sets.
- **Contradictions** = field-level value conflicts across evidence items
  (topic + the conflicting values with their sources).
- **Missing information** = rule-based gap detection (unreferenced features,
  undocumented pages, questions without answers, …) with severity.
- **Opportunities** = 0.5·limitation pressure + 0.3·evidence weakness +
  0.2·category weight, ranked per feature.

Ten unit tests pin these formulas against synthetic fixtures — a score can
never regress silently.

### 6.5 Reports (`reports.py`)

14 types: executive summary, page audit, feature inventory, user journeys,
technical architecture, data model, business model, competitive matrix, gap
analysis, PRD, roadmap, evidence register, completion report, interaction
records. Formats: **Markdown (source of truth), JSON, CSV** (evidence /
feature / page tables), **self-contained HTML** (inline CSS + Mermaid CDN for
journey diagrams) and **PDF** (multi-page A4, see 6.9). Every report carries
an evidence footer citing the exact evidence items behind each finding.
Reports persist to `reports` table and are served from the dashboard (the
PDF viewer embeds a data URL and offers a download).

### 6.6 Knowledge base (`knowledge.py`, `textsim.py`)

Lexical semantic search: TF-IDF cosine over normalised tokens of versioned
`knowledge_entries` (features, pages, evidence, findings, questions, reports).
Incremental upserts after every document step; `is_current` + version
history so superseded entries remain auditable. **Works fully offline.**

### 6.7 Data & Access engines (sanctioned collection)

**`robots.py` — robots.txt compliance (politeness, not evasion).** Each
domain's robots.txt is fetched once per hour and applied with a declared
User-Agent: readable file → followed; 404 → nothing disallowed; 401/400/403
(unreadable) → safe default *disallowed*; network error → `unknown`
(proceed, and let the fetch fail honestly). A scope row may carry
`robots_mode=approved_exception` — set **only** through an approved
`permission_change` decision with the sign-off recorded on the row. A
disallowed URL raises a PermissionGate (manual-evidence decision) — never a
bypass.

**`politeness.py` + `http_fetch.py` — polite HTTP capture.** A plain `httpx`
GET (declared UA, no header spoofing, no stealth) with per-scope delay and
ETag / Last-Modified conditional re-requests: 304 or unchanged content-sha is
a cache hit (`fetch_cache`) and the page is not re-processed. No rendering —
JS-only content falls through to the browser path or the manual gate.
`http_fetch` records pages with the same idempotent upsert as the browser
path, so the understand/document pipeline treats both identically.

**`api_connect.py` — official API connectors.** A connector declares the
target's official API (base URL, endpoints, auth type). The credential is
referenced by **env var name only**; the value is read from the host
environment at call time, never stored/logged, and if it ever appears in the
returned data the import is aborted. Connectors start `pending_approval`
(`new_source` decision) and sync with a politeness delay between endpoint
calls; rows become observations (class C) linked to per-endpoint evidence.

**`data_import.py` — licensed dataset import.** CSV/JSON/XML the researcher
lawfully holds, with **mandatory provenance** and license, become one
evidence item (class per the researcher's choice) plus per-row observations
citing it, with a documented row cap.

### 6.8 Evidence import (`evidence_import.py`)

Ingests a Markdown research package (README, investigation log, page
inventory, feature inventory, evidence register, findings) into a project
through the generic pipeline — the exact path used for the Lagos Life
package (14 documents → 29 evidence, 28 pages, 98 features, 12 questions,
29 observations, 2 sources, 7 contradictions). Integrity checks: evidence
ref codes preserved, classes mapped C/S/I/H/U, every feature kept linked to
its evidence refs.

### 6.9 Plugins, PDF rendering, backups & portability (`plugins.py`, `pdf.py`, `export_import.py`)

**`plugins.py` — modular plugin registry.** Four extensible component kinds:
`ai_provider`, `browser_engine`, `report_format`, `analysis_module`. Built-ins
register at boot (`discover()`, idempotent); third-party plugins install via
the `rice.plugins` setuptools entry-point group, each a callable receiving the
registry. A failing plugin is logged and skipped — it can never take the core
down (the offline/no-provider guarantees hold). Exposed read-only at
`GET /api/plugins`.

**`pdf.py` — dependency-free PDF writer.** Builds valid multi-page A4 PDF 1.4
(Helvetica / Helvetica-Bold) from the report markdown: headings, bullets,
tables-as-text, code blocks, text wrapping, a 200-page hard cap, correct
xref/startxref. No system libraries, no network — same local-first
guarantee as the rest of the engine. Stored as a base64 data URL in the
`reports` table; the raw `.pdf` is also written under
`data/reports/<project>/`.

**`export_import.py` — backups + project portability.** Backups WAL-checkpoint
then copy the SQLite file into `data/backups/` (retention 20); Postgres
deployments get an honest 503 pointing at the documented `pg_dump` path.
Export serialises one project (pages, features, evidence, observations,
questions, sources, scopes, data assets, reports) into a versioned JSON
bundle; evidence references are normalised to positional indices so bundles
are portable across installations. Import regenerates every id, remaps
cross-references, and creates a fully isolated new project — robots
exceptions and approvals deliberately do **not** travel (they require local
re-approval). Endpoints: `POST /api/systems/backup`, `GET /api/systems/backups`,
`GET /api/projects/{id}/export`, `POST /api/projects/import`.

## 7. Browser layer (`engine/browser/`)

- `base.py` — `BrowserEngineAdapter` interface: health probe, launch,
  navigate, render DOM, visible text, components, screenshots (viewport +
  full page), responsive captures, console errors, close.
- `engines.py` — Chromium/Firefox/WebKit adapters registered in one
  registry; adding an engine = one adapter class.
- `manager.py` — research sessions: profile (user-data dir) resolution,
  retry with backoff for recoverable failures, timeout handling, per-session
  `execution_logs`, honest degradation.

**Honest degradation contract:** when a binary is missing (as in this
sandbox — the Playwright CDN is unreachable), `probe_engines()` reports
`installed=false` with the exact install command; the agent loop raises a
`PermissionGate` (kind `manual_evidence`) and the human chooses: approve
manual import, or reject and mark the capture skipped. The session row
persists the failure reason — never a silent drop.

## 8. AI adapter layer (`ai/`)

`registry.py` selects by `RICE_AI_PROVIDER`:

- `off` (default) — `offline.py`: deterministic heuristics for planning,
  page summarisation, categorisation, synthesis. **All core functionality
  works with no external provider.**
- `openai_compatible` — any `/chat/completions` endpoint (`RICE_AI_BASE_URL`,
  `RICE_AI_API_KEY` — the key is used in-process only; it is never logged,
  persisted, or written into research files).
- `ollama` — local model endpoint.

The key never appears in logs, activity records, reports or evidence.

## 9. GitHub integration (`github_int/`)

`FEMZYKENTLTD/Nigeria-life` is the persistent project knowledge base:

- **Read path (enforced before new investigations):** the agent reads the
  research README + investigation log (local checkout first via `gh`/`git`,
  remote fallback via `gh`), digests what was already done, and logs it.
- **Write path (gated):** branch → commit `docs/**` only → push → PR via
  `gh`, **only after** an approved `repo_change` decision. Generated content
  is secret-scanned (`sanitize()`); tokens abort the write. Existing repo
  work is checked for version conflicts before overwrite.
- **State:** `github_state` tracks last sync + digest; the dashboard shows
  connection state, commits, branches, docs tree and the sync action.

## 10. Frontend

React 18 + TypeScript + Vite 5 + Tailwind 3 + Recharts, "Midnight & Copper"
premium theme (deep midnight-blue base `#0d1322`, ivory text, restrained
copper accent — deliberately **not** the near-black + gold cliché; the
token *names* are unchanged, only the values, so every class keeps working).
Ten sections, all wired to live API data with a global project selector:

| Section | Data |
|---|---|
| Overview | KPIs, completeness + formula, confidence pie, activity feed, project cards |
| Research Workspace | new-objective form → agent run; task queue with subtask states; page/feature inventories; open questions; source approval list |
| AI Agent Centre | provider state, **pending-decision approve/reject**, task queue, activity log, run history |
| Data & Access | collection scopes (methods/delay/cap/robots posture + exception requests), API connectors (register/approve/sync), licensed data assets (upload/import), manual-evidence queue + capture form + robots.txt check |
| Browser Management | engine health (re-probe), profiles CRUD, session history with honest error reasons |
| Knowledge Base | semantic search (scored, with the method explained), evidence explorer with C/S/I/H/U pills, feature relationship graph |
| Analytics | coverage bars, category chart, contradictions, duplicates, missing info, opportunity ranking table with components |
| Reports | generate (14 types × 5 formats), library, viewer (MD/CSV/JSON pre, HTML/PDF iframe + download) |
| GitHub Integration | connection state, commits, docs tree, sync action, write-back policy |
| Data & Ops | create + list database backups, plugin registry by kind, project export (JSON bundle download) + import as new isolated project |

Serving: dev = Vite `:5173` proxying `/api` + `/data` to `:8787`;
production = the FastAPI app serves `frontend/dist` with SPA fallback at a
single origin (no CORS needed). All client URLs are relative.

## 11. Reliability and operations

- **Structured JSON logging** (`logging_conf.py`) — every agent action is a
  log line with task/subtask ids.
- **Task recovery** on boot (in-flight → re-queued with reason).
- **Idempotent upserts** everywhere (knowledge, features, pages, evidence).
- **Concurrency recipe:** WAL + busy_timeout + commit-before-nested-upsert.
- **Safety caps:** 250-iteration agent loop cap with loud failure; per-scope
  page caps (excess fetch subtasks are *skipped with an explanation*);
  retry caps with backoff; import row caps.
- **Tests:** 57 tests — page understanding (9), analytics (10), reports (6),
  knowledge (4), evidence import vs the real package (1), agent e2e (4: full
  pipeline, gate→decision→reject→skip, loud failure, recovery), API (4),
  data & access (11: ETag/304 cache, robots gate, robots-exception approval,
  page-cap skip, full HTTP pipeline, dataset import × formats, connector
  flow + credential hygiene + missing-env honesty, manual capture + batch,
  manual queue + robots check), data & ops (8: PDF structure + text
  round-trip, PDF render_report, plugin registry built-ins + errors, plugin
  isolation, backup endpoint, export/import remapping round-trip, bad-bundle
  rejection, plugins endpoint shape). Evidence in `docs/platform/ACCEPTANCE.md`.

## 12. Configuration (env, prefix `RICE_`)

| Var | Default | Purpose |
|---|---|---|
| `RICE_DB_URL` | `sqlite+aiosqlite:///…/platform/data/rice.db` | storage engine (Postgres URL supported) |
| `RICE_DATA_DIR` | `platform/data` | evidence files, screenshots, exports |
| `RICE_HOST` / `RICE_PORT` | `0.0.0.0` / `8787` | API bind |
| `RICE_CORS_ORIGINS` | `*` | dev origins |
| `RICE_AI_PROVIDER` | `off` | `off` \| `openai_compatible` \| `ollama` |
| `RICE_AI_BASE_URL` / `RICE_AI_API_KEY` / `RICE_AI_MODEL_SMALL` / `RICE_AI_MODEL_LARGE` | — | provider settings (key never logged) |
| `RICE_BROWSER_TIMEOUT_MS` / `RICE_BROWSER_MAX_RETRIES` / `RICE_BROWSER_RETRY_BACKOFF_S` | 30000 / 2 / 2.0 | capture robustness |
| `RICE_DEFAULT_DELAY_BETWEEN_FETCHES_S` / `RICE_MAX_PAGES_PER_SESSION` | 2.0 / 40 | politeness + caps |
| `RICE_GITHUB_REPO` | `FEMZYKENTLTD/Nigeria-life` | central knowledge repo |
| `RICE_LOCAL_REPO_PATH` | *(set to the checkout for local git reads)* | local checkout mode |

## 13. Honest limitations (this environment)

- **No network path to lagoslife.app** (documented in the original
  investigation log) → no live first-party captures from here; the manual
  evidence path is the sanctioned route, and the dashboard surfaces the
  waiting decision.
- **Browser binaries not installed** (Playwright CDN unreachable) → health
  reports `installed=false` with install instructions; sessions degrade per
  §7. On any machine with `playwright install chromium`, the same code
  drives real browsers.
- **No external AI provider by default** → all output is deterministic and
  offline, by design; the adapter layer accepts one when available.

## 14. Roadmap (out of scope for v1.0, explicitly)

- Tauri 2 desktop shell + per-OS installers (requires per-OS verification).
- WebExtensions manual-evidence bridge (Manifest V3 side panel posting into
  the API) — scaffolding tracked in the implementation plan.
- CI matrix, load testing against real targets, Postgres migration tooling.
