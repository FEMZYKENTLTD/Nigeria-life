# 03 · Staged plan and status

Status as of 14 November 2026. "Done" means it runs and has a passing test. "Written" means code exists that has never been executed.

| Stage | Item | Status |
| --- | --- | --- |
| 1 | Architecture, database, backend API | Done |
| 1 | Dashboard foundation | Built; not yet viewed in a browser by the author |
| 1 | Git integration (read, gaps, branch, commit, push) | Done against a local remote |
| 1 | Pull-request creation | Written |
| 2 | HTTP capture, retries, time-outs, run log | Done |
| 2 | Chromium, Firefox, WebKit capture, screenshots, console errors, mobile emulation, login profiles | Written |
| 3 | Planner, continuity, completeness criteria | Done (rule-based) |
| 3 | Page understanding, findings, features, knowledge base, search, versions | Done |
| 3 | Import of existing research | Done |
| 4 | Analytics with explanations | Done |
| 4 | Evidence archive and manual evidence entry | Done |
| 4 | Reports in six formats | Done |
| 4 | Screenshot comparison (pixels) and annotations | Done |
| 4 | Vision-model analysis of screenshots | Not started |
| 5 | Cross-browser verification | Not done: needs a machine with browsers. CI workflow added to run it |
| 5 | Desktop packaging | Written, never compiled |
| 5 | Reliability: logging, retry, checkpoint, backup, validation, dedupe, cancel | Done |
| 5 | Performance test | One pipeline timing test. No load test |
| 5 | PostgreSQL | Not verified |
| 6 | End-to-end tests | Done for the HTTP path |
| 6 | Documentation and readiness review | Done |
| — | Language model used inside the pipeline | Not started (adapter only) |
| — | Browser-extension adapter | Not started |
| — | Scheduled recurring runs | Not started (planning is triggered by a person) |
| — | Rendering the page-link and dependency graphs as diagrams in the dashboard | Not started (shown as tables; Mermaid export exists) |

## Next steps, in order

1. On a machine with internet: `playwright install`, run the three skipped browser tests, fix what fails.
2. Open the dashboard and go through each section; fix layout and interaction faults.
3. Build the Tauri shell; bundle Python as a sidecar.
4. Run the test suite against PostgreSQL.
5. Connect a model: use it for summaries and feature drafting, stored as hypothesis-class until a person verifies.
6. Do the human-led play-through recommended in the research and enter it as manual evidence.
