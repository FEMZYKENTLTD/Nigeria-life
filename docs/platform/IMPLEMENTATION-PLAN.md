# Nigeria Life Intelligence Engine — Staged Implementation Plan

Status: **in progress** (see checkboxes; each item links to where it lives).
Updated: 2026-11-14.

The platform is **general-purpose by construction**: no module in the core
references "Lagos Life" or any specific target. Lagos Life (the existing
`docs/research/` package) is imported as *project #1* via the normal import
pipeline — the same pipeline any future project uses.

## Guiding constraints (from the master directive)

1. Standalone operation: the backend, planner, analytics, page understanding,
   reports and browser infrastructure all run without any external AI provider.
   The AI adapter layer is pluggable (cloud, local, or off).
2. Evidence integrity: every finding carries a unique ID, page reference,
   evidence reference, timestamp, confidence and status. Nothing is presented
   as fact without an evidence class.
3. Honest failure: a failed browser task is persisted with its reason; the UI
   says what failed and what remains incomplete. No silent drops.
4. Permissions: research scope and collection permissions are per-project,
   enforced by the scheduler. No stealth, no evasion, no credential storage.
   Manual evidence import is the sanctioned path for restricted sources.
5. Multi-project: projects are fully isolated (tasks, agents, evidence,
   reports); the core is shared.

## Stage 1 — Architecture, database, backend, dashboard foundation, GitHub ✅

- [x] Repository layout under `platform/` (backend / frontend / scripts).
- [x] Architecture document: `docs/platform/ARCHITECTURE.md`.
- [x] SQLite (local-first) schema + migrations via SQLAlchemy, async engine.
  PostgreSQL dialect is selectable via config (`RICE_DB_URL`) for central use.
- [x] FastAPI backend with structured logging, health endpoint, and full REST
  API: projects, objectives/tasks, sources, pages, observations, features,
  evidence, sessions, reports, analytics, agent, browsers, knowledge base,
  GitHub.
- [x] Knowledge base: structured queries + lexical semantic search
  (TF-IDF cosine) with incremental upserts and version history — works offline.
- [x] Import pipeline that ingested the existing `docs/research/` package as
  project 1 (14 documents, page inventory, feature inventory, evidence register).
- [x] React + TypeScript + Tailwind + Recharts dashboard, dark/gold theme,
  all eight sections (Overview, Research Workspace, AI Agent Centre, Browser
  Management, Knowledge Base, Analytics, Reports, GitHub Integration) wired to
  live API data.
- [x] GitHub integration module: repo/branch/commit reading via `gh`, docs
  discovery, sync state, write-back with branch + PR creation, token hygiene
  (never logged, never written into research files).

## Stage 2 — Browser automation, profiles, research sessions, screenshots ✅ (with environmental limits)

- [x] Playwright adapter with a reusable `BrowserEngineAdapter` interface
  (Chromium / Firefox / WebKit register in one registry).
- [x] Research profiles (separate user-data dirs per project + purpose),
  visible and headless modes, desktop/mobile viewports, session persistence.
- [x] Research sessions: navigation observation, rendered-DOM inspection,
  visible text + interface component extraction, screenshots (viewport and
  full page), responsive captures, console-error capture, timeout handling,
  retry with backoff for recoverable failures, execution logs persisted per
  run.
- [x] Browser health service: probes each engine, reports install state and
  version. In this sandbox the browser binary CDN is unreachable, so health
  honestly reports `binary_unavailable` and sessions degrade to the manual
  evidence path instead of failing silently. On any machine with
  `playwright install` run, the same code runs real browsers.

## Stage 3 — Autonomous research planner, page understanding, feature docs, knowledge base ✅

- [x] Task planner: decomposes a research objective into a typed task graph
  (discover → fetch → understand → document → analyse → report), priorities,
  checkpointing, resume after interruption. Heuristic planner works offline;
  LLM planner used when a provider is configured.
- [x] Page understanding engine: pure-Python HTML → structured page record
  (title, purpose heuristic, content category, regions, navigation, forms,
  controls, interactive components, sections, links, empty/error/loading
  state detection, repeated components). No AI required; AI can enrich.
- [x] Feature documentation subsystem: 15-field feature records across the
  20 required categories, with user journey, evidence, limitations,
  opportunities, implementation implications.
- [x] Agent loop: drives planner tasks end-to-end, persists state, records
  pending decisions requiring human approval (new sources, permission changes,
  publication, repo changes).

## Stage 4 — Advanced analytics, evidence management, reports, visual intelligence ✅

- [x] Deterministic, explained analytics (each score ships its formula and
  inputs): feature coverage, page coverage, completeness score, duplicate
  detection (Jaccard on normalised tokens), contradiction detection (field-level
  value conflicts), evidence quality scoring (from C/S/I/H/U classes),
  confidence assessment, missing-information detection, dependency analysis,
  gap analysis, opportunity scoring. No arbitrary percentages.
- [x] Evidence management: register, class, source URI, capture method,
  linked observations, quality score.
- [x] Report generation: 14 report types (executive, page audits, feature
  inventory, journeys, architecture, data model, business model, competitive
  matrix, gap analysis, PRD, roadmap, evidence register, completion report,
  interaction records) in Markdown, JSON, CSV and HTML; Mermaid for journey
  diagrams; every document carries evidence refs and investigation dates.
- [x] Visual intelligence foundation: screenshot registry with page links,
  categorisation, responsive-set grouping, pixel-diff change detection
  (perceptual hash) between captures of the same page.

## Stage 5 — Cross-browser adapters, cross-platform packaging, reliability ✅ (code-level) / ⚠️ (environmental)

- [x] Engine registry pattern: adding an engine = one adapter class.
- [x] Reliability: structured JSON logs, retries, checkpoints, task recovery on
  boot (in-flight tasks re-queued), job cancellation, idempotent upserts,
  duplicate prevention keys, import/export validation.
- [x] Test suites: unit + integration + browser-adapter tests (run with
  `pytest`). Evidence: `docs/platform/ACCEPTANCE.md`.
- [ ] Tauri 2 desktop shell and Windows/Linux/macOS installers: code and
  instructions provided (`platform/desktop/`), but packaging must be verified
  on each OS — cannot be produced from this Linux sandbox for Windows/macOS.
- [x] Optional WebExtensions adapter scaffolding (Manifest V3 + side panel)
  in `platform/extension/` — a manual-evidence bridge that posts observations
  and screenshots into the API.

## Stage 6 — Repo integration, E2E testing, documentation, production review ✅ (within sandbox reach)

- [x] Full integration of `FEMZYKENTLTD/Nigeria-life` as the persistent
  project knowledge base: reads the existing research README and investigation
  log before any new investigation (enforced in the agent loop), writes reports
  back to `docs/research/`, maintains indexes, creates research branches and
  PRs (requires human approval for consequential changes).
- [x] End-to-end demonstration: seed → plan → understand → document →
  analyse → report → GitHub, scripted in `platform/scripts/demo_run.py`.
- [x] Documentation: `docs/platform/ARCHITECTURE.md`, this plan,
  `ACCEPTANCE.md`, `platform/README.md` (runbook).
- [ ] Production hardening beyond sandbox: load testing against real targets,
  Tauri packaging on all three OSes, CI matrix — documented as the remaining
  external work.

## What is NOT claimed

- No live captures of lagoslife.app or any external site were made in this
  sandbox (no network path, per the existing investigation log). All live-data
  features are demonstrable against any reachable target and against local
  fixtures; the platform reports the gap instead of hiding it.
- Tauri binaries for Windows/macOS are not produced from this sandbox.
