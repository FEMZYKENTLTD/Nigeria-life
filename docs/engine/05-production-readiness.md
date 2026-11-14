# 05 · Production-readiness review

**Verdict: not production-ready.** It is a working local tool for one researcher on one machine. The parts in the first list below are solid; the parts in the second must be dealt with before wider use.

## Ready to use locally

- Research import, knowledge base, search, version history
- Manual evidence entry with archived files and hashes
- Permission gate and approvals
- Task queue with retry, cancel, pause and crash recovery
- Analytics and reports
- Commit of generated reports to a new branch after approval

## Blocking issues

| # | Issue | Why it matters | What to do |
| --- | --- | --- | --- |
| 1 | Real browser engines never executed | The Playwright adapter is about 100 untested lines. Rendering, screenshots, console capture, mobile emulation and saved login sessions are all unproven | Install browsers, run the three skipped tests, fix |
| 2 | Dashboard never viewed | Layout, charts and forms may have visible faults that type-checking cannot find | Walk through all eight sections |
| 3 | No sign-in on the dashboard or API | Anyone who can reach the port can approve actions and trigger commits | Keep it bound to 127.0.0.1 (the default). Add authentication before exposing it |
| 4 | Desktop app never compiled; Python not bundled | No installer exists | Build on each OS; add a PyInstaller sidecar; add icons |
| 5 | PostgreSQL never run | JSON columns and the backup function behave differently there (built-in backup is SQLite only) | Run the suite against PostgreSQL; add migrations (there are none: tables are created at start-up, and schema changes are not handled) |
| 6 | Language model not used | The "agent" is a rule-based planner. It does not reason, summarise or draft | Wire the tested adapter into summarising and feature drafting, stored as hypothesis-class |
| 7 | Pull-request creation untested | May fail on first use | Test on a scratch repository |

## Known weaknesses

- **One worker thread.** Projects share it, so a long task in one delays the others. Rate limits are kept in memory and reset on restart.
- **A running task cannot be interrupted.** Cancelling marks it cancelled and its result is discarded when it returns, but the fetch itself completes.
- **No mid-task checkpoints.** Recovery restarts the interrupted task from its beginning. Tasks are small (one page each), so little is repeated.
- **Search is word matching.** "Cost" will not find "price".
- **Contradictions are not detected automatically.** Only conflicts already written in the research are listed.
- **Feature extraction from pages is shallow.** It recognises forms (sign-in, search, upload). Anything richer needs a researcher or a model.
- **Duplicate detection compares names only.**
- **robots.txt is cached in memory until restart**, and `Crawl-delay` is not read; the per-source delay is used instead.
- **Redaction is pattern-based.** It catches common token shapes, bearer strings, JWTs and card-like numbers. An unusual secret pasted into a note would get through.
- **Report PDFs replace characters outside Latin-1 with "?"** (the ₦ sign, for example) because built-in PDF fonts are used.
- **Uploads go through JSON as base64**, capped at 15 MB.
- **No scheduled runs.** A person presses "Plan next steps".
- **The CI workflow has not been observed running.**

## What the engine will not do, by design

- Fetch from a source that is unapproved, manual-only, out of scope, over its page limit, or disallowed by robots.txt
- Submit forms, log in by itself, solve CAPTCHAs, or disguise itself (it sends an identifying User-Agent)
- Store passwords, cookies or tokens in research records (login sessions live only in the browser profile folder)
- Change a researcher-verified feature without an explicit overwrite, or change anything without saving the earlier version
- Commit to the repository without an approval, or reuse an existing branch
- Present a figure without its formula and inputs

## On the research target

Lagos Life's Terms prohibit scraping and its Developer Agreement bars building a competing platform with its tools. The engine ships with that source set to manual-only and unapproved. Approving it for automation would be a decision against those terms; take legal advice first. The intended route is the human-led play-through recommended in `docs/research/`, entered through "Add evidence by hand".
