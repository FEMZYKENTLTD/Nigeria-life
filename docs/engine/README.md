# Nigeria Life Intelligence Engine

A local research platform for this repository. It reads the research already in `docs/research/`, keeps it in a searchable database with evidence and version history, captures web pages from sources a person has approved, and produces analytics and reports.

Version 0.1.0, written 14 November 2026. Read **[What works and what does not](#what-works-and-what-does-not)** before relying on it.

## Install and run

Needs Python 3.11+ and Node 20+.

```
cd engine
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt pytest      # Windows: .venv\Scripts\pip
.venv/bin/python -m playwright install chromium firefox webkit   # browser engines (optional but recommended)

cd frontend && npm install && npm run build && cd ..
cd backend && ../.venv/bin/python -m nlie                     # dashboard at http://127.0.0.1:8000
```

Run the tests with `cd engine/backend && ../.venv/bin/python -m pytest -v -rs`.

On first start the engine creates one project for this repository, with `lagoslife.app` registered as a **manual-only, unapproved** source, and imports `docs/research/`. It fetches nothing from the internet.

## Settings (environment variables)

| Variable | Purpose | Default |
| --- | --- | --- |
| `NLIE_DATA_DIR` | Database, archived evidence, screenshots, reports, backups, browser profiles | `./nlie-data` |
| `NLIE_DATABASE_URL` | Central database, e.g. `postgresql+psycopg://…` | SQLite file in the data folder |
| `NLIE_REPO_PATH` | Repository to treat as the knowledge base | The repository this code is in |
| `NLIE_AI_BASE_URL`, `NLIE_AI_API_KEY` | Any OpenAI-compatible endpoint (cloud, Ollama, LM Studio, vLLM) | none: rule-based mode |
| `NLIE_AI_MODEL_SIMPLE`, `_COMPLEX`, `_VISION` | Model per task difficulty | none |
| `GITHUB_TOKEN` | Used by `git`/`gh` for pushes and pull requests | none |

Secrets are read from the environment only. They are never written to the database, logs or reports.

## What works and what does not

| Area | State | Evidence |
| --- | --- | --- |
| Database (SQLite), 17 tables, version history, backup | Working, tested on Linux, Windows, macOS | `04-test-evidence.md` |
| Import of existing `docs/research/` | Working, tested against the real files | 29 evidence items, 98 features, 35 pages, 22 questions |
| Task queue: retry, cancel, pause, recovery after a crash, no duplicate work | Working, tested | |
| Permission gate: approval, manual-only, scope, page limit, robots.txt | Working, tested | |
| Page understanding, findings, feature records | Working, tested on server-rendered HTML | |
| Analytics with formulas and inputs | Working, tested | |
| Reports: Markdown, JSON, CSV, HTML, PDF, Mermaid | Working, tested | |
| Knowledge search | Working. Word-based (TF-IDF), **not** meaning-based | |
| Git: read repository, find doc gaps, branch + commit + push after approval | Working, tested against a local throwaway remote | |
| Opening a pull request | Written, **not tested** (would have created a stray branch on GitHub) | |
| Dashboard, eight sections | Builds and type-checks; served by the engine. **Not viewed in a browser by the author** (none available) | |
| Chromium, Firefox, WebKit: rendering, console errors, screenshots, profile folder | Working in CI on Linux, Windows and macOS against a local test page. **Not yet run through the full capture pipeline against a live site**, and a saved login surviving a restart is unverified | CI run 43652042188 |
| PostgreSQL | Same models; **never run** against PostgreSQL | |
| Language-model adapter | Tested against a mock server only. **No part of the pipeline calls a model yet**; planning and analysis are rule-based | |
| Vision analysis of screenshots | **Not implemented.** Pixel comparison only | |
| Desktop app (Tauri 2) | Configuration and launcher written, **never compiled** | `engine/desktop/README.md` |
| Browser extension adapter | **Not started** | |
| Sign-in, user accounts, access control on the dashboard | **None.** Run it on your own machine only | |

## Documents

- [01 Repository audit](01-repository-audit.md)
- [02 Architecture](02-architecture.md)
- [03 Staged plan and status](03-staged-plan.md)
- [04 Test evidence](04-test-evidence.md)
- [05 Production-readiness review](05-production-readiness.md)
