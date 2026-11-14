# 01 · Repository audit

Audited 14 November 2026 at commit `fd18506` on `main`.

## What the repository held

| Path | Content |
| --- | --- |
| `README.md` | Title and a one-line pointer to the research (under 40 words) |
| `docs/research/README.md` | Index of the Lagos Life research package |
| `docs/research/00-investigation-log.md` | Method, evidence classes, 35-route discovery checklist, 7 source conflicts, 8 open items |
| `docs/research/01` to `11` | Executive report, feature inventory, page audit, journeys, UI/UX reference, architecture, entity model, business model, gap analysis, blueprint, roadmap |
| `docs/research/12-evidence-register.md` | Evidence E01 to E29 with class tags |

About 17,700 words. No product code, no tests, no CI, no licence, no `.gitignore`, no contribution guide.

## What that meant for the engine

1. **There was no product to integrate with**, so "repository integration" means reading and extending the research, not touching game code.
2. **The research is the only existing asset.** The engine imports it and never rewrites the files. Evidence IDs and class tags (C, S, I, H, U) are carried over unchanged.
3. **The research target forbids automation.** Lagos Life's Terms prohibit scraping, and its Developer Agreement bars using its tools to build a competing platform (recorded in `00-investigation-log.md` §6). The engine therefore registers it as manual-only and unapproved. New facts about it must be entered by a researcher.
4. **The package's own limits carry over.** It was produced without a browser: no screenshots, no in-game observation. 55 of the 98 imported features rest on secondary sources.

## Gaps the engine now reports for this repository

Missing: `LICENSE`, `CONTRIBUTING.md`. Thin: root `README.md`. These are shown on the GitHub page of the dashboard; fixing them is the owner's decision.
