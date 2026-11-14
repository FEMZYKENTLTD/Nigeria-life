# Acceptance Evidence — Nigeria Life Intelligence Engine

Date: 2026-11-14 · Environment: Linux sandbox, Python 3.11, Node 22 · Branch: `arena/c9cd611a-nigeria-life`

This document records **what was actually executed and observed** in
support of the acceptance criteria. Anything that could not be verified in
this environment is listed under "Not verified here" with the reason.

## 1. Test suite (real output)

Command: `cd platform/backend && .venv/bin/python -m pytest tests/ -q`

```
38 passed in 25.20s
```

Verbose (all 38):

```
$(see tests/ — reproduced 2026-11-14)
tests/test_page_understanding.py — 9 passed
tests/test_analytics.py          — 10 passed
tests/test_reports.py            — 6 passed
tests/test_knowledge.py          — 4 passed
tests/test_evidence_import.py    — 1 passed (ingests the real docs/research package)
tests/test_agent_e2e.py          — 4 passed (full pipeline; gate→decision→reject→skipped; loud failure; recovery)
tests/test_api.py                — 4 passed
```

### What the e2e agent tests prove

1. **Full pipeline** — task `queued → planned → running → complete`;
   features ≥ 2 documented; a report generated and persisted; knowledge
   entries upserted; the task summary states what was done.
2. **Human gate** — a fetch subtask without browser capability stops the
   task at `waiting_decision`, creates exactly one pending
   `manual_evidence` Decision; `resume_after_decision(approved=False)`
   marks the subtask `skipped` and the task completes with the gap stated.
3. **Loud failure** — an unknown report type fails the subtask with
   `last_error`, fails the task with an incomplete-work summary. No silent
   completion.
4. **Recovery** — a task left `running` is re-queued to `queued` by the boot
   recovery path.

## 2. Seeded real project (import of the existing research package)

Command: `python platform/scripts/seed_lagos_life.py`

Observed result (persisted in `platform/data/rice.db`):

```
project: "Lagos Life Reconnaissance"  id=01M7E5S35PC0076QEHDG693JX8
evidence: 29 (E01–E29, classes C/S/I/H/U preserved)
pages: 28   features: 98   questions: 12   observations: 29
sources: 2  (lagoslife.app kept pending_approval — never auto-authorised)
contradictions: 7 (field-level, e.g. place-count 23 vs 37 across sources)
```

The 14-document `docs/research/` package was consumed by the **generic**
import pipeline — no Lagos-Life-specific code exists in `app/`.

## 3. End-to-end demo run (real output)

Command: `python platform/scripts/demo_run.py`

Observed:

- Agent task `01M7E5S5YR12RT7J969FN2D6HE` executed
  understand → document → analyse, then **stopped at the first-party
  browser boundary**: status `waiting_decision` @ 11%, pending Decision
  kind=`manual_evidence` (browser binaries absent in this sandbox — the
  honest gate, not a failure).
- Analytics (all with explanations): completeness **0.474**, feature
  documentation rate **0.731**, page coverage **21/29**, evidence quality
  **0.891**, 12 open questions, 7 contradictions, 2 duplicate candidates.
- Top scored opportunities: "Buy a business" (0.58), "Business rankings,
  employees, P&L" (0.56), "Player-to-player item trading" (0.56).
- Reports generated and persisted: executive (5,747 chars), feature
  inventory (21,706), completion report (4,557).
- GitHub: local checkout read OK (branch `arena/c9cd611a-nigeria-life`),
  15 markdown docs under `docs/`, research README digested.
- Knowledge search: top hit "Feature: Governor election" (score 0.584).
- Browser health: all three engines `installed: false` with the exact
  install command in the error field — reported, not hidden.

## 4. Dashboard (frontend)

- `npm install` + `npm run build` → **build passes** (tsc strict + vite):
  `dist/assets/index-*.js 626.86 kB (gzip 176.58 kB)`.
- Served live: FastAPI `:8787` (single origin, SPA fallback verified —
  `/` and `/agent` both return 200 HTML) and Vite dev `:5173`
  (preview host accepted, `/api` proxied, health endpoint verified through
  the proxy).
- Live API smoke checks against the seeded DB:
  - `GET /api/overview` → 1 project, 29 pages / 21 documented, 98 features,
    29 evidence.
  - `GET /api/agent/status` → 1 pending decision (the demo's manual-evidence
    gate) — visible in the dashboard's AI Agent Centre for approve/reject.
  - `GET /api/projects/{id}/analytics` → all metric shapes consumed by the
    charts (score/components/explanation) verified field-by-field.

## 5. Constraints honored (spot checks)

- No target/product/feature name appears in `platform/backend/app/`
  (grep-clean; Lagos Life exists only as data).
- The AI key path is process-local; logging is structured JSON with no
  credential fields.
- Source `lagoslife.app` remains `pending_approval` — the scheduler will
  not capture it without a human decision.
- `.gitignore` keeps `platform/data/`, `node_modules/`, `dist/`, `.venv/`
  out of the source tree; runtime data stays local-first.

## 6. Not verified here (honest gap list)

| Item | Why | Mitigation |
|---|---|---|
| Live capture of lagoslife.app | No network path to the domain from this sandbox (also documented in the original investigation log E29) | Manual-evidence path + waiting decision in the dashboard; works against any reachable target |
| Real browser sessions (Chromium/Firefox/WebKit) | Playwright CDN unreachable → binaries not installed | Health probe reports `installed=false` with install command; degradation path is tested |
| LLM-assisted planning/synthesis | No external AI provider configured by design | Deterministic offline path fully tested; adapter layer present and selectable via env |
| Tauri desktop build (Win/macOS) | No Rust toolchain in this Linux sandbox | Out of v1.0 scope; see ARCHITECTURE §14 |
| Load testing against real targets | Requires live targets + time | Documented as post-v1.0 production hardening |
