# 04 · Test evidence

Two runs on 14 November 2026.

**1. Continuous integration, three operating systems, real browsers.** GitHub Actions run `43652042188`: **34 passed, 0 failed, 0 skipped** on each of Ubuntu, Windows and macOS, with Chromium, Firefox and WebKit installed. The dashboard build job also passed. See it under the repository's Actions tab.

**2. Build sandbox** (Linux, Python 3.11.2, Node 22.22.3, no browsers): 31 passed, 3 skipped. Raw output:

- [`test-evidence/pytest-2026-11-14.txt`](test-evidence/pytest-2026-11-14.txt)
- [`test-evidence/live-run-2026-11-14.txt`](test-evidence/live-run-2026-11-14.txt): the running engine on this repository's real data, including a kill and restart

The three tests skipped in the sandbox are the real-browser tests; they ran and passed in CI. Each opens a local HTML file, and checks that JavaScript ran, a console error was captured, a screenshot was saved and the profile folder was created.

CI found one real fault, now fixed: on Windows the archived HTML was written in text mode, which changed line endings, so the stored hash did not match the file.

Pipeline tests capture from a small fake website served in memory, so no real site was contacted. Nothing was fetched from lagoslife.app.

## Acceptance criteria

| # | Criterion | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Installation | **Met** | Dependencies install and tests run on Linux, Windows and macOS in CI |
| 2 | Working dashboard | **Partly met** | `npm run build` passes TypeScript checking and builds; the engine serves it (HTTP 200); every API route it calls is tested. Not looked at in a browser by the author |
| 3 | Working database | **Met (SQLite)** | All tests use a real SQLite file. `test_backup_is_a_readable_copy`. on three operating systems. PostgreSQL not run |
| 4 | Multiple browser engines | **Met, with a limit** | `test_real_browser_engine` passes for chromium, firefox and webkit on three operating systems. Limit: against a local page, not through the full pipeline on a live site |
| 5 | Persistent sessions | **Partly met** | Each engine launches with a persistent profile folder and the folder is created. That a login survives a restart was not tested |
| 6 | Task planning | **Met, rule-based** | `test_agent_plans_captures_and_records_evidence`, `test_no_duplicate_work_on_replan`. No language model is involved |
| 7 | Structured observations | **Met** | `test_page_understanding_structures_a_page`; findings checked for ID, page, observation, evidence, time, confidence, status |
| 8 | Evidence management | **Met** | Archived HTML re-hashed and compared to the stored SHA-256; manual upload via API in `test_source_approval_flow_and_manual_evidence` |
| 9 | Screenshot organisation | **Partly met** | Upload, listing, annotation and pixel comparison tested (`test_visual_comparison`). Browsers save screenshots in CI; filing them through the pipeline is not run with a real browser |
| 10 | Analytics | **Met** | `test_analytics_values_match_their_inputs`, `test_empty_project_has_no_made_up_numbers` |
| 11 | Report generation | **Met** | `test_reports_in_every_format`: six formats, PDF header and size checked; live run produced five files |
| 12 | GitHub integration | **Partly met** | Branch, commit and push verified against a local bare remote, with the working tree untouched and an existing branch refused. Pull-request creation not run |
| 13 | Recovery after interruption | **Met** | `test_recovery_after_interruption`; live run: server killed with SIGKILL, task recovered and finished after restart |
| 14 | Cross-platform build | **Partly met** | Engine and dashboard build and pass on Linux, Windows and macOS. The Tauri desktop app was never compiled, so there is no installer |
| 15 | Complete documentation | **Met for what exists** | This folder |

Eight met, two met with a stated limit (3 and 4), five partly met (2, 5, 9, 12, 14). None fully unmet; the largest remaining gaps are the unviewed dashboard and the uncompiled desktop app.

## Safety rules that have tests

| Rule | Test |
| --- | --- |
| Unapproved source is never fetched | `test_unapproved_and_manual_only_sources_are_never_fetched` (zero requests reached the site) |
| Manual-only source is never fetched | same test |
| robots.txt disallow is obeyed and explained | `test_robots_disallow_is_respected_and_explained` |
| Off-site links are not followed | `test_agent_plans_captures_and_records_evidence` |
| Page limit holds | `test_page_budget` |
| A failed task stays visible with its reason | `test_failure_is_recorded_not_lost` |
| Secrets are removed from stored text | `test_redaction_removes_secrets`, and the token check in the API test |
| Verified research is not overwritten; changes keep history | `test_feature_update_keeps_history_and_protects_verified`, `test_recapture_versions_changed_page` |
| Nothing is committed before approval; rejection does nothing | `test_github_publish_needs_approval_and_leaves_working_tree_alone`, `test_rejected_approval_does_nothing` |
| "Not found" in the research stays not found after import | `test_import_of_real_repository_research` |

## Import of this repository's research (live run)

| Imported | Count |
| --- | --- |
| Evidence items (E01 to E29) | 29 (22 confirmed, 7 secondary) |
| Features | 98 (39 confirmed, 55 secondary, 4 unknown) |
| Pages from the discovery checklist | 35 |
| Open questions and recorded conflicts | 22 (7 conflicts) |

Engine measures on that data: documentation completeness 27.4% (376 of 1,372 fields filled); features citing evidence 94.9% (93 of 98); archived evidence 0% (imported evidence has no stored copy); page capture coverage: no data, because the engine has captured nothing itself.

## Performance

One measurement only: the capture pipeline handled 4 tasks in 0.11 s (28 ms each) with the network removed. This says the engine's own processing is not the bottleneck; real captures are limited by the per-source delay (default 2 s) and the site. No load or soak test was done.
