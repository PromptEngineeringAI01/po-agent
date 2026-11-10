# Spec: PO Agent MVP (test site, run on the office Mac Mini)

**Status:** **Approved by Joey, 15 Oct 2026** · v1.34 (1.34: Claude may read live project lookups (Projects search, project page, Tasks list) for the real-PO seam in the built-in browser pane, after Joey logs in himself with the agent account; read only, values only in `private/` (decisions, 10 Nov 2026, live lookups); 1.33: the live profile (G.3): committed `config/live.toml` (no secrets, `enabled = false` until just before the live spike, one PO per run), `LIVE_HOST` in `core/config.py`, each profile refusing any URL but its own site's host, the live secret pair `mysys_live_username` / `mysys_live_password`, `--site live`, the wrapper's required site argument with `enabled` read from that site's config on main, launchd running `run live`; live answers from Joey's look: the project match is the bare internal number on both sites, PO Documents and Solved as on test, the stale-Note read filters Assigned User = the agent on live, W2 expects Type Client Documents on live; alert issues carry no Note ID (decisions, 10 Nov 2026, live profile); 1.32: go-live plan: the CEO gave Joey every go-live decision; P5's week skipped, its 5.2 trace check moves to the first watched live booking; the real-PO seam on the 3-5 real POs that exist, plus live decide-only; gate 2 by Joey's own look at live; no backlog cut-off; the backup admin and heartbeat before unattended hourly live runs; alert issues drop `note_id`, the repo stays public; code frozen until live runs hourly (decisions, 9 Nov 2026, go-live plan); 1.31: release pinning (7.4): the Mac Mini runs the `production` tag, which only Joey moves, so a merge no longer deploys; the wrapper reads `enabled` from `origin/main` first, so `enabled = false` still stops the next run without a tag move; a failed fetch, a missing tag or an unreadable `enabled` on main runs nothing and alerts (decisions, 9 Nov 2026, release pinning); 1.30: ADR-002 H2 waived on the test site: Claude may run in `poagent` for another project, never near the agent; removed before go-live (decisions, 6 Nov 2026); 1.29: the safe trace (7.3): every run whose config sets `trace_dir` and whose trace folder's parent exists (the Mac Mini) writes `~/Library/Logs/po-agent/trace/<date>.jsonl`, allowlisted fields only, kept 90 days; run output unchanged; 1.28: a Note Pool second page is `ALERT MORE_PAGES`, exit 1, before any Note is taken (the stale-Note read and the eligible read, `spike` too); no `ALL_SKIPPED` alert: the run already stops on its first `UNEXPECTED_SCREEN` (decisions, 5 Nov 2026, 7.2); 1.27: from the Submit click on, Ctrl+C is `PARTIAL_WRITE` too; the opening clicks' retry prints nothing (decisions, 5 Nov 2026, M4 security pass); 1.26: run mode built: plain `run` books a PROCEED W1-W5 (NOTE "booked" with the task number); from the Submit click on a Note is never returned, its ALERT names it and RUN_SUMMARY counts it as partial; NOTE_TAKEN at the W1 check closes that context and the next Note runs in a fresh browser (decisions, 5 Nov 2026, run mode); 1.25: W4 and W5 built: the guard selects only a cell in Choose Project; back to the Note by a second Note ID search after the W4 assignee check; W5's Pending search reads page 1 only; every W4/W5 error closes the context and carries its step (decisions, 4 Nov 2026, W4 and W5); 1.24: W3 built: the Hold dialog read counts hidden checkboxes too and every related job; every W3 error closes the context and carries step W3 (decisions, 4 Nov 2026, W3); 1.23: W2 built: errors after Submit carry step W2, a stop at W2 closes the context, the four W2 guard actions pinned to their one target each (decisions, 4 Nov 2026, W2); 1.22: go-live gate 6, production operations: heartbeat, silent-skip alert, safe trace, release pinning, ops runbook, alert triage; planned as tasks 7.1-7.7, built later (decisions, 4 Nov 2026); 1.21: slice M0b.2 written up: W2 reads PO number and Note on the task detail screen and the PDF in the project's Documents tab; W4 selects the Choose Project result by its pln cell; PO Number isn't prefilled; the upload is saved only by Submit; every weak Create New Task field and the Hold confirm anchored; an open Note window doesn't refresh its Assignee (decisions, 3 Nov 2026); 1.20: the run controls' INFO lines; the kill switch stops every mode, the Perth window only `run` and decide-only; `tzdata` added (decisions, 2 Nov 2026, 3.5); 1.19: decide-only opens each Note by "Finding a Note again" and checks it is still in the pool before taking it (NOTE_TAKEN); a stopped Note has no NOTE line, its ALERT names it (decisions, 2 Nov 2026, 3.3); 1.18: the Claude reader is dropped to keep the agent free: two code readers (pdfplumber and pypdf) must agree, and the PDF's Job Address block is checked against the project's address in MySys (decisions, 2 Nov 2026); 1.17: caught up with the 28 Oct 2026 MVP demo (PRs #19-#30): the Projects search runs on Enter; new [Production](#production) section: what's in, what's out and the go-live gates; the code stays test site only (decisions, 29 Oct 2026); 1.16: slice M0b.1 written up: row-26 anchors, the Note Pool search runs when focus leaves the box (fill + Refresh), filters persist across a reload, the agent reloads instead of minimising windows, one Assign returns a Note, the attachment rule without rows 21–22, row 23 moved to M0b.2 (25 Oct 2026); 1.15: decision 2 made (delegated to Joey: yes); Milestone A, a decide-only demo on the Mac Mini, comes first, and 3.6 moves after it but before any booking; the repo is public (25 Oct 2026); 1.14: outside the repo, the protect_paths hook writes only to the plan, project-memory and Claude temp folders (24 Oct 2026); 1.13: a lighter build process: the review stop after the failing test only on the guard, hooks, decision and MySys-acting tasks (24 Oct 2026); 1.12: the repo-data check is stricter: banned folders at any depth and in any case, plus `.state/`, `traces/`, `secrets/` and `.env/`; `.env*` files, `config/live*.toml` and images banned too (19, 21 and 24 Oct 2026); 1.11: the plan freeze, decisions D1–D7 in `docs/decisions.md` (16 Oct 2026): run controls and the assignee check built before booking (M3); the trial PDF briefly on the Mac Mini's disk; real-page refusal tests call `guard.vet()` only; the live host named only in the Bash hook's deny regex; the select rule; the stale-Note stop; the assignee check before W1 and W4 only; one agent at a time; M0b grows to rows 19–28; 1.10: the 3 trial POs are **real** B1 POs, kept by Joey with changed real-data rules; SPEC fixed against `docs/screen-map.md` v1.1: new [MySys screen rules](#mysys-screen-rules), project match on the one `/048` result, strict MVP duplicate check, `NOTE_ALREADY_LINKED`, "close" denylisted, fake CI fixtures, slice M0b (16 Oct 2026; the defaults in `docs/decisions.md` accepted by Joey the same day); 1.9: M0 checks answered from the screen map, C1 and C3 pass on the test site; the denylist adds Pending, Undo Cancellation, Un-Hold and Change Project (16 Oct 2026); 1.8: the real-PO decision seam uses the 3 most recent real POs for the MVP, 10–20 before go-live (16 Oct 2026); 1.7: the last write is the Note's **Solved** button, because the test site has no Resolve button (16 Oct 2026); 1.6: CEO decision 3, the trial runs on the office Mac Mini instead of an Anthropic cloud routine: a launchd job as a separate standard user, secrets in its Keychain, the trial waiver replaced by Trial conditions, `docs/macmini-setup.md` replaces `docs/routine-setup.md`; 1.5: the demo must be repeatable at least 3 times, S8 and `docs/demo-runbook.md`; 1.4: approved; the test site is reset by Joey cancelling tasks with his own account, and the test profile's duplicate check ignores cancelled tasks; Pro plan; 1.3: screens mapped with Playwright CLI while Joey clicks; `po-agent capture` dropped; all 3 trial POs named at every stage; 1.2: the 3 trial POs only, test-site reset, skip shown with a duplicate copy; 1.1: real client data allowed, kept on Joey's laptop)
**Active spec.** Build this first. The full v1 design stays in `docs/specs/spec.md` and is built after the MVP has proved the agent works (roadmap phase 2).
**Built from:** `docs/intent.md`, `docs/decisions.md` (wins if anything disagrees), `docs/specs/spec.md` v1.2, `docs/specs/ADR-001-po-agent-architecture.md` (Accepted), `docs/specs/ADR-002-po-agent-hosting.md` (Accepted, CEO decision 3, 15 Oct 2026).

## Assumptions

1. **Two profiles: test and live** (decisions, 10 Nov 2026, live profile). `config/test.toml` and `config/live.toml` each refuse any URL but their own site's host. Live is run only by Joey (launchd, on the Mac Mini), in the live order under [Production](#production); Claude never runs anything against live (CLAUDE.md Must never #3).
2. **The agent may read real client data** (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real PO PDFs and view-only captures of live screens are used to understand the pages and to test the readers. They stay on Joey's laptop in the git-ignored `private/` folder, never in GitHub or on the Mac Mini during the MVP. **The 3 trial POs are real B1 POs too** (found 16 Oct 2026: the test site's 2609017B PDF is byte-identical to the live one). Joey keeps them as the trial POs: their internal numbers, PO numbers and test-site plns may appear in committed files and run output; their PDFs, site addresses, client names and other PDF content may not. The Mac Mini handles them only as the agent reads them from the test site. See [Real client data](#real-client-data).
3. **The trial runs on the office Mac Mini** (CEO decision 3, 15 Oct 2026; ADR-002 Option D, Accepted): a launchd job as a separate standard macOS user, secrets in that user's Keychain. ADR-002's gates all pass there, so no waiver is needed; the trial still follows [Trial conditions](#trial-conditions). Setup: `docs/macmini-setup.md`.
4. **ADR-001 holds for the clicks; its Claude reader is superseded** (decisions, 2 Nov 2026). The script does every click; two code readers (pdfplumber and pypdf) read the PDF and must agree, and the address is checked against MySys. No paid API, so the agent costs nothing per PO. On the Mac Mini a shell script (`scripts/macmini-run.sh`) starts the agent; no Claude session is involved.
5. **No state between runs** (Joey, 14 Oct 2026, kept for MVP scope). MySys is the state: a Solved Note is done, the duplicate check stops double bookings, and a skipped Note is simply checked again next run. The Mac Mini appends each run's short output to a log for Joey; the agent never reads it.
6. **Production runs on the same Mac Mini** (CEO decision 3), after the CEO's go-live sign-off. The code stays host-agnostic: secrets from env vars or keyring, and nothing Mac-specific in `src/` (launchd and the wrapper live in `scripts/` and `docs/macmini-setup.md`).
7. **CEO decisions 1 and 3 are made.** Decision 2 is Joey's call pending the CEO's confirmation. Because the trial POs are real, it now gates the **first Mac Mini run that downloads a trial PO** (M3 on the Mac Mini); work on the laptop isn't blocked.
8. **Built on Joey's Windows laptop** in VS Code with Claude Code; Python 3.12 via uv; GitHub repo, public so the CEO can read it (the Mac Mini fetches it and runs the `production` tag; decisions, 25 Oct 2026; 9 Nov 2026, release pinning); Addy Osmani's agent-skills.

→ Correct any of these before `/agent-skills:plan`.

## Objective

Prove, early and cheaply, that the hybrid PO Agent does the admin's job on the MySys test site with no human help, unattended, from the office Mac Mini.

The MVP proves that:

- the Mac Mini can reach the test site from the office, log in and drive it with headless Chromium (the biggest unknown, so first)
- the two readers agree on 3 fake fixture POs and their mutations, on the 3 trial POs **and on a set of real B1 POs**, and never approve a bad one
- the script books each trial PO exactly as the SOP says and reads every write back
- a PO it shouldn't book goes back to the Agent Pool, and a non-`/048` Note is left untouched
- a second run creates, changes or links no task and solves no Note (see [MySys screen rules](#mysys-screen-rules) → Reruns)
- the agent costs nothing per PO: no paid API (decisions, 2 Nov 2026).

**Users:** Joey (builds and runs the trial); the CEO (reads the one-page MVP demo note). The PO admin isn't affected.

**The 3 trial POs, everywhere:**

| Client internal no. | Project | M0 walkthrough | Seam 1 | M4 first bookings | Seam 2 and S4 trial |
|---|---|---|---|---|---|
| 2609017B | pln_66935 | Full SOP by hand, then reset | Real-PO case (laptop, `-m real_data`) | Booked first | Booked |
| 2609034B | pln_66938 | Read-only screens | Real-PO case (laptop) | Booked | Booked; its fresh copy is the S5 skip case |
| 2610002B | pln_66940 | Read-only screens | Real-PO case (laptop) | Booked | Booked |

**These 3 are real B1 POs** (assumption 2). Their PDFs live only in MySys and `private/`; they are never committed, so CI's seam 1 runs on **3 fake fixture POs** generated in M2 (fake internal numbers such as `2600001B`, fake addresses, the B1 layout), plus mutated copies of those.

### In the MVP

| `docs/specs/spec.md` section | MVP |
|---|---|
| §2 processing order | Steps 0, 2 (with 2a), 3–4 and 6–12. The decision engine knows **both title rules** (test: the Note Pool's Subject/Note cell, which joins title and body, contains `<internal no>_048[_n].pdf`; live: title `[B1 Homes] Order <internal no>/048`) each profile uses its own (`title_rule` in its config; live: `live-b1-title`, decisions, 10 Nov 2026). On both, step 0 also needs the row's Project cell to read `---` (not linked). A test Note whose title has the live form must also agree on the PO number (`PO_MISMATCH`). Step 1 (skip list) is v1; step 5 (live sender check) is v1 |
| §2 step 2a (new) | After Assign, a Note window that shows a project button instead of **Link to Project** → skip `NOTE_ALREADY_LINKED` (final), before any download or write |
| §3 reading schema and skip reasons | All, except live-only checks; plus `NOTE_ALREADY_LINKED` |
| §2 step 8 project lookup | Exactly one **matching** row, by the match rule in [MySys screen rules](#mysys-screen-rules) → Project search: Company B1 Homes and Client Ref No. exactly `<internal no>` on both sites (live: one row per internal number, Client Ref No. the bare number, Joey's look, 10 Nov 2026; `/048` is in the Note's title, not the project); rows with any other value are ignored |
| §4 address check | The project's address in MySys gives the lot and street-and-suburb; the PDF's Job Address block must hold them ([MySys screen rules](#mysys-screen-rules) → Project address; decisions, 2 Nov 2026). MySys holds one address string, not separate fields |
| §2 step 10 duplicate check | **Stricter than v1:** any Compaction Test task on the project counts as a duplicate, whatever its PO number, because the project's task table doesn't show PO numbers (screen map row 07). The **test profile ignores Compaction Test tasks whose status is Cancelled** (`duplicate_ignores_cancelled = true`), because Joey resets the test site by cancelling tasks. Every other status, and every status on live, counts |
| §5 action guard + build check | All, plus the denylist and allowlist additions in [MySys screen rules](#mysys-screen-rules). It's cheap and it's the main safety control |
| §6 booker W1–W5 with read-back | All, with the values and read-backs in [MySys screen rules](#mysys-screen-rules). W2's task-detail read-back and W4's search and select as mapped in slice M0b.2 (screen map rows 19-20) |
| §7 second reader | **Replaced** (decisions, 2 Nov 2026): pypdf reads the PDF's text again. Its issuer, COMPACTION, PO number and Job Address label line (normalised) must equal pdfplumber's, else `READERS_DISAGREE`; no pypdf text → `PDF_UNREADABLE`. The address check runs on both texts; different results → `READERS_DISAGREE` |
| §8 run controls | `enabled` kill switch (at start and before every write step), Perth window, run cap, fresh login, assignee check **before W1 and W4** (D7), the **stale-Note stop** at run start (D6), **stop the run on the first unexpected screen or failed write** |
| Skip → back to pool | Through **Assign** with the pool as assignee (C3 answered yes, 16 Oct 2026); exact steps in [MySys screen rules](#mysys-screen-rules) → Note window |
| `reader_mode` | Gone: one code-only mode, and no Claude setting in config, CLI or secrets (decisions, 2 Nov 2026; task 2.5b) |
| `--decide-only` | Runs every check, returns each Note to the pool, books nothing. Used before the first booking |

### Deferred to v1 (after the MVP demo)

| Deferred | MVP behaviour instead | Why it's acceptable on the test site |
|---|---|---|
| Skip list and 24 h retry of `PROJECT_NOT_FOUND` | Nothing persisted. A skipped Note is checked again every run | Same answer each time; costs nothing |
| Partial-write auto-resume | `ALERT PARTIAL_WRITE`, Note **left assigned to the agent**, run stops (exit 1). Joey finishes it by hand. Until he does, every later run stops at the start (the stale-Note stop, D6), so one systematic bug can't leave a half-booked Note every hour | Duplicate check blocks a second task anyway |
| `STOP` file written by the agent after an accuracy breach | `ALERT ACCURACY_BREACH`, Note **left assigned to the agent**, so the stale-Note stop (D6) holds every later run until Joey clears it; exit 3. Joey unloads the Mac Mini's launchd job and sets `enabled = false`; restart needs the CEO (approved safeguard) | Joey is told by the GitHub alert issue |
| Email/Teams alerts | `ALERT` lines; the Mac Mini's run script opens a GitHub issue labelled `po-agent-alert` (GitHub emails Joey) | — |
| Circuit breaker (3 failures) | Stricter: the first unexpected screen or failed write stops the run | — |
| Single-run lock, start-of-run sweep | No lock: by rule, **one agent at a time** (no laptop test-site run while the Mac Mini job is loaded). Instead of the sweep, the stale-Note stop (D6): a Pending Note still assigned to the agent stops the run before any Note is taken | Runs take minutes and are hourly; launchd never starts the job while it's still running; don't start a manual run near :07 |
| Daily log files and 90-day retention | Full detail only in local runs with `--detailed-log` (`logs/`, git-ignored; the Mac Mini never passes it). The Mac Mini appends the short run output to `~/Library/Logs/po-agent/runs.log`, and writes the safe trace (allowlisted fields only, one file per day, 90 days; [Production](#production) → Safe trace, 7.3) | MVP runs only touch the test site |
| Sender check (C6) | Not built. The live profile was built in G.3 (decisions, 10 Nov 2026) | — |
| Duplicate check by PO number | Any non-Cancelled Compaction Test task on the project → `DUPLICATE_TASK` | Only costs coverage on projects with an older compaction task; v1 reads PO numbers from the task detail screen |
| Note Pool paging | Page 1 of the filtered list only (50 rows by default); more pages is `ALERT MORE_PAGES`, exit 1, before any Note is taken (7.2) | The test site's Agent Pool holds a handful of Notes |

## Tech Stack

As `docs/specs/tech-stack.md`: Python 3.12 (uv, locked), Playwright for Python with Chromium (headless on the Mac Mini, headed on the laptop), pdfplumber (text layer only), pypdf (the second reader), pydantic v2, pytest, ruff, `zoneinfo`, `tomllib`, `keyring`.

**Host for the MVP:** the office Mac Mini (CEO decision 3). A standard macOS user `poagent` runs `scripts/macmini-run.sh` from a launchd LaunchAgent at 7 minutes past each hour, 07:07–17:07 Monday–Friday, clock on Australia/Perth. FileVault on; no Claude Code for that user. Exact steps: `docs/macmini-setup.md`.

**Secrets:** one function reads `PO_AGENT_<NAME>` from the environment first (CI and tests), else keyring service `po-agent` (laptop: Windows Credential Manager; Mac Mini: `poagent`'s login Keychain).

| Secret | Env var | keyring name |
|---|---|---|
| MySys test username | `PO_AGENT_MYSYS_TEST_USERNAME` | `mysys_test_username` |
| MySys test password | `PO_AGENT_MYSYS_TEST_PASSWORD` | `mysys_test_password` |

No Anthropic key: the Claude reader was dropped (decisions, 2 Nov 2026). `ANTHROPIC_API_KEY` is never read.

## Commands

```text
Install:             uv sync --locked
Browser (laptop):    uv run playwright install chromium
Check (= CI):        uv run scripts/check.py        healthy: last line "check: all passed", exit 0
Run seam, test site: uv run pytest tests/seam2 -m testsite
Spike (read-only):   uv run po-agent spike --site test       login, filter Agent Pool + Locked, list eligible Notes
Screen mapping (M0): playwright-cli open --headed "<test-site URL>"   Claude opens it; YOU log in and click; Claude runs snapshot / screenshot
Real-PO seam (laptop): uv run pytest tests/seam1 -m real_data   uses the main checkout's private/fixtures (or SEAM1_PRIVATE_DIR); skipped when absent, an error with -m real_data; never in CI
Decide only:         uv run po-agent run --site test --decide-only
Real run:            uv run po-agent run --site test
Supervised demo:     uv run po-agent demo --site test --headed [--until-check]   one PO, Enter before every write (decisions, 27 Oct 2026)
Link probe:          uv run po-agent demo --site test --probe-link   opens Choose Project, searches, snapshots, selects nothing (decisions, 28 Oct 2026)
Laptop extras:       --headed (watch the browser), --slow-mo 500, --detailed-log (JSON lines in logs/)
Mac Mini (poagent):  scripts/macmini-run.sh run|spike|decide-only test|live   site required; fetch, enabled from config/<site>.toml on main, production tag, sync, run, log, alert
Live (Joey only):    on the Mac Mini, through the wrapper or launchd (`run live`); never from the laptop, never by Claude (Must never #3)
Mac Mini run now:    launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent
```

`scripts/check.py` runs, in order, stopping on the first failure: `ruff format --check .` → `ruff check .` → `python scripts/guard_check.py` → repo data check (nothing tracked in a folder named `private/`, `logs/`, `state/`, `.state/`, `traces/`, `secrets/`, `.env/` or `.playwright-cli/`, at any depth; no `.env` or `.env.*` file and no `config/live*.toml` other than the committed `config/live.toml`, at any depth; no `.pdf` outside `tests/seam1/fixtures/pdfs/`; no image (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`); no trace or capture file (`*trace*.zip`, `*.har`, `*.webm`); folder names and extensions in any case) → `pytest tests -m "not live_claude and not testsite and not real_data"`.

**Screen mapping with Playwright CLI** (`@playwright/cli`, M0 and whenever a screen changes; laptop, test site only). Joey opens a headed browser and does every click and every typed value himself, including the login. Claude Code only **observes**: `playwright-cli snapshot` (the accessibility tree, with the role and name of every element, which is what the guard's lookups use), `screenshot`, `find` and `generate-locator`. Claude never runs a command that acts on the page (click, fill, type, press, hover, check, select, upload, drag, drop, eval, run-code, dialog, goto, reload), saves state or cookies, or lists network requests; `.claude/settings.json` denies them and, from M1, the `guard_bash.py` hook allows only the observe commands. `.playwright/cli.config.json` keeps the browser profile in memory, blocks the live origin and writes output to `private/captures/test/`; `.playwright-cli/` (snapshot files) is git-ignored. Fallback if Node.js can't be installed: the classic recorder that ships with Playwright for Python (`playwright codegen`), plus screenshots.

**Exit codes:** 0 run finished (bookings and skips are normal) · 1 run stopped (unexpected screen, Note Pool more pages, failed write, partial write, guard refusal) · 2 config, secrets or login problem · 3 accuracy breach.

## Project Structure

```text
SPEC.md                         active spec (this file)
CLAUDE.md                       rules for every Claude Code session
tasks/plan.md, tasks/todo.md    written by /agent-skills:plan
pyproject.toml, uv.lock         [project.scripts] po-agent = "po_agent.cli:main"
src/po_agent/
  cli.py                        argument parsing; maps errors to exit codes
  core/                         reusable for the next MySys automations
    config.py                   load + validate config/<site>.toml (test, live); each refuses any host but its own (TEST_HOST, LIVE_HOST)
    secrets.py                  PO_AGENT_* env var, else keyring; one MySys pair per site
    output.py                   the ONLY module that prints (stdout contract below)
    runlog.py                   detailed JSON-lines log to logs/ (only with --detailed-log), its one traceback writer; feeds the trace
    trace.py                    the safe trace (7.3): allowlisted fields only, one file per day, 90 days
    run.py                      Note loop, RUN_SUMMARY
    demo.py                     supervised demo: one trial PO, Enter before every write (decisions, 27 Oct 2026)
    controls.py                 kill switch, Perth window, run cap, before_write, assignee check, stale-Note stop
    errors.py                   typed errors, their exit codes and ALERT kinds
  mysys/                        reusable
    guard.py                    action guard: vet() resolves and allows or refuses; act() is the ONLY code that clicks, types, ticks or uploads
    driver.py                   login, navigation, reads; writes only through guard.py
    booking.py                  the demo's screens, Note to Solved, proven on the test site 28 Oct 2026; the base for the booker (4.1-4.5)
  b1/                           rules for this automation
    models.py                   Reading, Decision, SkipReason (pydantic)
    reader_rules.py             the code readers (pdfplumber and pypdf + patterns)
    address.py                  normaliser + address check against the project's address
    decision.py                 decision engine = seam 1; no browser code
    booker.py                   W1–W5 with read-back
config/test.toml                test-site profile; no secrets
config/live.toml                live profile; no secrets; ask-first for Claude (protect_paths)
scripts/check.py                the one check command
scripts/guard_check.py          fails if browser action calls appear outside mysys/guard.py
scripts/macmini-run.sh          Mac Mini wrapper `<mode> <test|live>`: fetch, enabled from config/<site>.toml on origin/main, check out the production tag, uv sync, run, append to runs.log, alert issue without Note IDs
scripts/au.com.prompteng.po-agent.plist   launchd job (Mon–Fri 07:07–17:07), `run live` after go-live
tests/seam1/                    decision seam; fixtures/ = generated fake PDFs + case files (never a real or trial PDF)
tests/seam2/                    run seam on the test site (marker testsite)
private/                        GIT-IGNORED, laptop only: real data
  pdfs/                         real B1 PO PDFs, including the 3 trial POs
  fixtures/cases.toml           expected results for real POs and the 3 trial POs, entered by Joey from MySys
  captures/                     Playwright CLI snapshots and screenshots (test), live screenshots
docs/                           intent, decisions, workflow, Mac Mini setup, screen map, v1 spec pack
.claude/settings.json, hooks/   permissions (now, incl. the Playwright CLI deny list) and hooks (added in M1; protect_paths writes outside the repo only to ~/.claude/plans/, the project memory folder and <temp>/claude/; inside a Claude Code worktree at .claude/worktrees/<name>/ the repo rules apply from that worktree's root, decisions 30 Oct 2026)
.playwright/cli.config.json     Playwright CLI config for screen mapping (in-memory profile, live origin blocked)
.github/workflows/check.yml     CI: uv sync --locked, check, gitleaks; no secrets
```

`config/test.toml` (shape; values confirmed in M1–M2):

```toml
site = "test"
base_url = "https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component"
pool_name = "Agent Pool"
agent_user_name = "Agent 1 (MySys Only)"
title_rule = "test-body-filename"
enabled = true                    # kill switch: false on main → next run exits before login
duplicate_ignores_cancelled = true   # test only: Joey resets the test site by cancelling tasks; never true on live
max_notes_per_run = 10           # MVP values; v1 defaults are 25 Notes / 12 minutes
max_run_minutes = 12
run_window = { days = "Mon-Fri", start = "07:00", end = "18:00", tz = "Australia/Perth" }
stale_read_by_agent = false       # the stale-Note read stays at All Users
project_document_type = "Purchase Order"   # W2: the Type of the new task's row in the project's Documents tab
trace_dir = "~/Library/Logs/po-agent/trace"   # the safe trace (7.3): written only where ~/Library/Logs/po-agent exists (the Mac Mini)
```

`config/live.toml` differs in (decisions, 10 Nov 2026, live profile): `site = "live"`, `base_url` on `LIVE_HOST`, `pool_name = "PO Allocation Pool"`, `title_rule = "live-b1-title"`, `enabled = false` (flipped by its own PR just before the live spike), `duplicate_ignores_cancelled = false` (required on live), `max_notes_per_run = 1` (watched runs; 10 for hourly, its own PR), `stale_read_by_agent = true`, `project_document_type = "Client Documents"`. The agent user name is the same as on test.

## Code Style

Python 3.12, ruff format and ruff check, type hints throughout, pydantic models at every boundary, small pure functions in `b1/`. Every MySys write is a **named guarded action** on one element inside its window (see [MySys screen rules](#mysys-screen-rules) → Windows and locators), found by accessible role and name, or by its visible label where the screen map marks the field weak, then read back:

```python
# src/po_agent/b1/booker.py
def set_po_number(guard: ActionGuard, task_form: Locator, po_number: str) -> None:
    field = field_by_label(task_form, "PO Number", role="textbox")   # weak: no accessible name (screen map row 09)
    guard.act("set_po_number", task_form, field, po_number)   # vet() first: refuses if not allowlisted, denylisted, or not exactly one match
    if field.input_value() != po_number:
        raise WriteNotStarted("PO Number did not read back as expected")
```

- Names: `snake_case` functions, `PascalCase` models and errors, skip reasons exactly as in `docs/specs/spec.md` §3.
- Typed errors (`UnexpectedScreen` and its `MorePages`, `WriteNotStarted`, `PartialWrite`, `AccuracyBreach`, `GuardRefusal`, `LoginFailed`, `ConfigError`) in `core/errors.py`; each class declares its exit code and its ALERT kind, and `cli.py` reports them. Their messages come from fixed templates plus identifiers only, never page text or a Playwright message (which can quote an address).

**Run output (stdout) contract.** The Mac Mini's run log and alert issues are built from this, so it is short and holds no PDF text, addresses, Note bodies or Claude readings:

```text
INFO  <progress message, no PO data>
NOTE  {"note_id": "...", "outcome": "booked|skipped|untouched|partial", "reason": "ADDRESS_MISMATCH",
       "field": "street", "po_number": "2609034B/048", "pln": "pln_66938", "task_id": "...",
       "tokens_in": 0, "tokens_out": 0, "cost_aud": 0.0}
ALERT <PARTIAL_WRITE|ACCURACY_BREACH|GUARD_REFUSAL|UNEXPECTED_SCREEN|MORE_PAGES|LOGIN_FAILED|CONFIG> {"note_id": "...", "step": "W3", "detail": "<no PO data>"}
RUN_SUMMARY {"run_id": "...", "site": "test|live", "mode": "run|decide-only|spike", "seen": 0, "eligible": 0,
       "booked": 0, "skipped": 0, "partial": 0, "duration_s": 0, "tokens_in": 0, "tokens_out": 0,
       "cost_aud": 0.0, "exit_code": 0}
```

- `outcome` values beyond a skip reason: a decide-only Note that would have been booked is `"outcome": "skipped", "reason": "DECIDE_ONLY"`; a Note a person took mid-run is `"outcome": "untouched", "reason": "NOTE_TAKEN"`. These are run-output values only, not skip reasons in the decision engine.
- **Run mode (4.5; decisions, 5 Nov 2026, run mode):** a booked Note is `"outcome": "booked"` with `po_number`, `pln` and `task_id`. A Note stopped from the Submit click on (`PARTIAL_WRITE`, `ACCURACY_BREACH` or `GUARD_REFUSAL` with step W2-W5; a Ctrl+C there is `PARTIAL_WRITE`) has no NOTE line: its ALERT names it, RUN_SUMMARY's `partial` counts it, it stays with the agent and the run stops. `"outcome": "partial"` is not printed in the MVP. A Note a person took before the W1 check is `untouched` / `NOTE_TAKEN`; its browser context is closed and the next Note runs in a fresh browser.
- Run-control `INFO` lines (3.5), each ending the run with exit 0 unless noted: `kill switch on: run not started` (any mode, before secrets or a browser), `outside the run window: run not started` (`run` and `run --decide-only` only), `kill switch on: run stopped` (switched off before W1 or W2: the Note is returned first), and `run cap reached: <n> notes left for the next run` (the run goes on to its summary).
- **Silent skips and more pages (7.2; decisions, 5 Nov 2026):** the run stops on its first `UNEXPECTED_SCREEN` (exit 1), so a MySys screen change can't skip every Note quietly; there is no separate all-skipped alert, and business skips (`NOT_B1`, `DUPLICATE_TASK`, ...) never alert. A Note Pool with a second page, which is never read, prints `ALERT MORE_PAGES` (fixed detail, no `note_id`) and exits 1 before any Note is taken: in `run` and `run --decide-only` from the stale-Note read (D6), which lists every Pending Note and so has a second page whenever the eligible read does; in `spike` from the eligible read, after its counts line. A typed error raised later has its own exit code (none can follow, since the run stops).
- **Alert issues (audit N4; decisions, 10 Nov 2026, live profile):** the repo is public, so the wrapper's alert issue body carries the ALERT lines without `note_id`: the JSON key and the detail's `note_id=<id>` are cut, and a line that still names one keeps only `ALERT <KIND>`. `runs.log` on the Mac Mini keeps every line whole; the Note is found there (`docs/ops-runbook.md`).
- `run_id` = UTC start time plus 4 random hex characters (e.g. `20261016T013507Z-3fa2`), made before the config is loaded, so even an exit-2 `RUN_SUMMARY` has one. `RUN_SUMMARY` is always the last line, even after a crash.
- **Nothing goes to stderr.** An unexpected exception becomes `ALERT UNEXPECTED_SCREEN` with a fixed detail; its traceback goes to `logs/` only with `--detailed-log` (`core/runlog.write_traceback`, for any error that ends the run), else nowhere, because Playwright's error text can quote page content.

Never print or log a secret, the environment, cookies or browser storage state. PDF and Note text are untrusted data.

## MySys screen rules

What the driver and booker do on each screen, built from `docs/screen-map.md` v1.3 (row numbers below). Every screen the MVP uses is mapped.

**Windows and locators**
- Every locator is scoped to its floating window, found by its heading: `Note <note id> - …` (a pln appears in it after linking), the project heading starting `<pln> `, `Create New Task`, `Hold Task: <task no>`. Minimised windows stay in the page, so an unscoped locator can match a hidden copy.
- Inside a window, an element is found by accessible role and **exact** name (a substring "Hold" would also match "Un-Hold"), or, for a field the screen map marks **weak** (open item 8), by its visible label in that window (`field_by_label` in `mysys/driver.py`), (the innermost element in that window holding the exact label text and the control: every Create New Task field sits in its own label block, rows 08-09), or by the row-26 anchor in the screen map: the Note Pool filters by their fixed `name` attribute (`filter_allocation_pool_id`, `filter_lock_status`, `filter_status`, `filter_user_id`, ...), the Note window's lists as "the select in this window that contains the option `--Select User--`" / "`--Select Pool--`", the Note Pool panel as the one holding **New Note** and **Search/filter**, the Projects panel as the one holding the label **Search**, **Reset Filter** and the option **All Projects**. Never generated ids (`#project_list_<digits>`, `p_<digits>`, `…_s_po_1_6`) or position-only locators (`nth`, `:nth-child`). Zero or more than one match → guard refusal. `guard.act()` acts on the element `guard.vet()` resolved, never a second lookup, so a hidden copy is never the one acted on.
- The agent never clicks a window's Close, Maximize or Minimize, or a taskbar entry. **Between Notes the driver reloads `base_url`** (a navigation, not a click) so no window is left open; if the reload shows the login page, it logs in again. A half-filled form is still abandoned by closing the browser context.
- **Moving between windows** (rows 25, 27, 28): an open Note window stays on top when the Projects tab opens and covers the results, so the agent never goes from the Note window to the Projects panel directly. After the Note-window steps (assign, step 2a, attachment count, download) it **reloads `base_url`** (every window closes, nothing in MySys changes), clicks **Project** (after a reload the tab bar is hidden until then) → **Projects**, searches and opens the project. To get back to the Note it reloads again and reopens it from the Note Pool ("Finding a Note again"). A reopened Note window is a fresh one: Send Email Notification is ticked again and the user list pre-selects the agent. Opening a project that is already open gives the same single window (row 28), but the agent always reloads first anyway.
- A banner "Your internet connection appears to be disconnected ..." may show the whole time (screen map, How MySys behaves); the agent ignores it and relies on its read-backs.
- No key presses: after Assign, focus lands on **Unlink** (row 04). The one exception: **Enter** in the Projects panel's "Search..." and in Choose Project's "Search/filter", through the guard's `press` kind (Joey, decisions 28 Oct 2026).

**Guard additions** (on top of `docs/specs/spec.md` §5)
- **Denylist:** any element whose accessible name or own text contains `close` (case-insensitive). This blocks the PO Documents table's "close" cell (removes the PDF), the Task Client "close" (clears the client), and every window Close. The denylist is checked against the acted-on element itself, not the text of the window around it.
- **Denylist on a `<select>`** (D5): the select's own name plus the label of the option being chosen, never every option's text. So the Note Pool's Discard status option is refused, and a user elsewhere in the list whose name contains a denylisted word doesn't block Assign.
- **Allowlist:** log in (username, password, "Log in") and the module navigation (Project top tab, Note Pool, Projects sub-tab); select user / pool in the Note window's lists (including the `--Select User--` placeholder); search the Note Pool by Note ID and press its **Refresh** button (row 27); open the new task's detail screen by its details row and go back with the project window's select set to "-- Select Task --", and the project window's **Documents** and **Tasks** buttons (all read-only, row 19; `open_new_task_detail` only on a table cell, `back_to_project` only to the option "-- Select Task --", `open_project_documents` / `open_project_tasks` only on the button with that exact name); in Choose Project, its Search/filter and the result's `pln_…` cell (row 20; `link_select_project` only on a table cell, Joey, 4 Nov 2026). Demo only (decisions, 27-28 Oct 2026): `move_pointer_off_menu` (the guard's only pointer move: no click, onto a list's status line below the header, after a Project menu choice), and `submit_project_search` / `submit_link_search` (Enter in the two project search boxes, the guard's only key press).
- **Refusal tests on the real site** (D3) call `guard.vet()` only, which has no action code, so nothing can be pressed; `guard.act()` refusing is tested offline on local HTML.

**Note Pool (row 01)**
- Filters: Assigned Pool = `pool_name`, Locked/Unlocked = **Locked** (the captures show the trial Notes listed under Locked). Every other filter stays at its default; Status stays **Pending** and is never set. Each filter is read back, and Search/filter must read empty (a Note ID left there would hide every Note).
- **How the list reloads** (row 27): changing a filter select reloads the list by itself. Search/filter does **not** search on `fill` alone: the search runs when focus leaves the box. So a search is: `fill` → click the panel's **Refresh** → wait up to 15 s for the footer "Page 1 of 1(N Items)" (or "No record could be found.") → read. If the number of table rows differs from N (Refresh plus the focus change can add the same rows twice), click Refresh once more and read again; still different → `UNEXPECTED_SCREEN`. After any filter change the driver waits for the footer the same way before reading.
- **What persists** (row 27): a page reload keeps every filter and the Search/filter text; a fresh login resets them all to their defaults with Search/filter empty. Every run logs in fresh, so the list read at run start sees the defaults; within a run, the driver always sets and reads back the filters it needs instead of trusting what a reload kept.
- Eligible (step 0, list only): the Subject/Note cell matches the title rule, the Project cell reads `---` **and** the Assignee cell reads `pool_name` (so a person's Note is never taken, even if the pool filter didn't apply). Everything else is left untouched (outcome `untouched`).
- The list is read **once per run**; the run works through that fixed list, so a Note it skips and returns isn't taken again in the same run.
- **Stale-Note stop** (D6): in `run` and `run --decide-only`, after login and before the list is read, the Note Pool is read with Assigned User = All Users (test: its Assigned User list has no agent; decisions, 3 Nov 2026) or = `agent_user_name` (live, `stale_read_by_agent = true`: live lists 153 Pending Notes over 4 pages at All Users; set back to All Users after the read; decisions, 10 Nov 2026), Assigned Pool = All Pools, Locked/Unlocked = All, Status Pending. Any row whose Assignee is `agent_user_name` was left by an earlier run's partial write or failed return: `ALERT UNEXPECTED_SCREEN` (fixed detail, with its `note_id`), no Note taken, exit 1. Only page 1 is read, so a second page stops the run too, as `ALERT MORE_PAGES`, exit 1 (after page 1's rows, so a stale Note there is named; 7.2). Status stays Pending: a Note left with the agent in another status is reported by its own `PARTIAL_WRITE` alert instead.
- **Finding a Note again** (after a reload or closing a browser context, to return a Note to the pool, for the assignee check, for W5's read-back): Assigned Pool = All Pools and Search/filter = the Note ID, searched as above (fill → Refresh), and the row whose ID cell **equals** the Note ID (the search is treated as a substring filter: 123 also matches 1234). Under Assigned Pool = Agent Pool, a Note assigned to the agent is hidden (row 04).
- Order: oldest first by Note ID, up to `max_notes_per_run`, from page 1 only (deferred table). The Note ID is the row's ID cell, never the download link's `user_note_id` (row 05).
- **Opening each Note** (decisions, 2 Nov 2026, 3.3): every Note the run works on is opened by "Finding a Note again", which also gives the reload between Notes. Before Assign to agent its "Assignee:" must read `pool_name`; otherwise a person has it: `"outcome": "untouched", "reason": "NOTE_TAKEN"`, never taken. A Note skipped before the project search has no download or search it doesn't need. Before it goes back, every Note is found again and its "Assignee:" must read `agent_user_name`; otherwise a person took it mid-run: `NOTE_TAKEN`, left with them.
- **A stop while the agent holds a Note** (decide-only, 3.3): the browser closes, one Assign to pool in a fresh browser context, then exit 1 (or the error's own code, e.g. 2 for a failed login); on Ctrl+C there is no return attempt. The stopped Note has no `NOTE` line: its `ALERT` carries the `note_id`, and says "Note not returned to the pool" when that return failed.
- **Two Notes for one PO** (row 01: older Notes have the plain title, newer ones the live-style title): the first one processed is booked; any other copy then skips `DUPLICATE_TASK` and goes back to the pool for the admin. The demo runbook keeps exactly one Pending Note per trial PO in the Agent Pool.

**Note window (rows 02–04, 13–15)**
- **Send Email Notification** is ticked every time a Note window opens (row 02). Before **every write on the Note window** (Assign to agent, Assign to pool, Link to Project, Solved) the agent unticks it and reads it back unticked, **after** `before_write` (whose assignee check can reopen the window, ticking the box again) and right before the committing click. The detailed log records each read-back.
- **Assign to agent** (step 2): user list = `agent_user_name` (it's pre-selected even when the Note is in the pool), pool list reads `--Select Pool--`, Assign. Read back: "Assignee:" reads the agent, and a new log line "User Assigned: … to <agent>".
- **Assign to pool** (every skip and decide-only): user list = `--Select User--`, pool list = `pool_name`, **one** Assign (row 15b: this works from a freshly opened window where the user list pre-selects the agent). Read back: "Assignee:" reads `pool_name`, a new log line "… From <agent> to <pool>", Status Pending. Never Unassign or Unlink.
- After an Assign both lists reset and Assign is disabled (row 04). That's expected, not an unexpected screen.
- **Already linked** (step 2a): after Assign to agent, the window must show **Link to Project**. A project button or **Change Project** → `NOTE_ALREADY_LINKED`, back to the pool.
- **Email body** (task Note, S3): the Note's body text as the Note window shows it (row 02), e.g. "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf". The title is not part of it.

**Attachment and download (rows 02, 05)**
- Count the "Download document" links in the Note window **before** clicking (decisions, 25 Oct 2026; rows 21–22 were not mapped): exactly one, whose URL's `file_name` parameter (URL-decoded) ends `.pdf` in any case, is the only case that goes on. None → `NO_PDF`; more than one → `MULTIPLE_PDFS`; one whose `file_name` is missing or doesn't end `.pdf`, or an attachment area the driver doesn't recognise → `NO_PDF`. Each is a skip: the Note goes back to the pool. The link's accessible name is only "Download document"; the file name is in its URL (row 02). Counting is a read, so two links give a skip, not a guard refusal.
- Download: the "Download document" click inside `expect_download`; keep the first file, delete a second download unread; never use the preview window.
- **The PDF on disk** (D2): the browser writes every download to disk, so the browser is launched with `downloads_path` set to a run-scoped temp folder (`po-agent-dl-<run_id>`). The file is read into memory and deleted at once; the folder is removed in a `finally` block, and leftover `po-agent-dl-*` folders are removed at every run start. W1 uploads from the bytes in memory, never from a path.

**Assignee check (§8), before W1 and before W4** (D7)
- A fresh read, not the open Note window's text: an open Note window **does not refresh** its Assignee, its log or the Note Pool row behind it after someone else reassigns the Note (row 23, 3 Nov 2026), so only a reload shows the change: reload `base_url`, then "Finding a Note again" (above); the row whose ID cell equals the Note ID must have Assignee `agent_user_name`. Zero such rows or more than one → `UNEXPECTED_SCREEN` before W1; before W4 any failure of the check is `PARTIAL_WRITE` (decisions, 3 Nov 2026, 3.6 review). Then the booker reopens the window it needs, as in "Moving between windows" (before W1 nothing is filled yet; before W4 it needs the Note window anyway).
- Only before W1 and W4, because each check leaves the window the booker is in: W1 → W2 → W3 stay in the project window, so a filled Create New Task form never makes the trip. `before_write` still re-reads `enabled` before every step.
- Someone else at the W1 check → close the browser context and stop work on that Note without any write or reassign (`"outcome": "untouched", "reason": "NOTE_TAKEN"`). Someone else at the W4 check → `PARTIAL_WRITE`.

**Project search (rows 06, 16)**
- Projects sub-tab, the Projects panel's Search field (anchored on the Projects panel, row 26; the page header has a hidden second "Search..."). `fill` alone doesn't run this search (seen live, 27 Oct 2026). The search runs by pressing **Enter** in the box (`submit_project_search`, the guard's `press` kind; decisions, 28 Oct 2026, PRs #26/#27), as proven in the demo (`mysys/booking.py`). Before searching, the Projects filters must read at their defaults, else `UNEXPECTED_SCREEN`. Wait up to 60 s for a settled list (two equal reads in a row) that isn't the stale "No record found." or the old list; the same row listed twice counts once; otherwise `UNEXPECTED_SCREEN`. Choose Project's "Search/filter" (W4) runs the same way (`submit_link_search`).
- **Match rule:** a row matches when Company is **B1 Homes** and Client Ref No. (trimmed, case-insensitive) equals `<internal no>` on both sites (test: row 06; live: Joey's look, 10 Nov 2026, one row with the bare number; the 16 Oct `/048` assumption was wrong). Rows with any other value (another suffix, another number) are ignored. Exactly one match → its pln; none → `PROJECT_NOT_FOUND`; more than one, or a second results page → `PROJECT_AMBIGUOUS`.
- Open the match by its `pln_…` link. The project window's **Client Internal No.** must satisfy the same rule, else `UNEXPECTED_SCREEN`.

**Project address (rows 06–07), for §4**
- Source: the project window's **Address:** (the same string as the search row). Shape: `Lot <lot> [(#<house no>)] <street> <suburb> [<postcode>] [<state>]`, e.g. `Lot 123 (#45) Sample Lane Sampleville 6000 WA`.
- Parse after the §4 normalisation: drop a trailing state and postcode, drop the `(#…)` group, take the token after `Lot` as the lot (letters allowed, e.g. `12A`; compared as case-folded strings). The rest is the street-and-suburb text *R*. No leading `Lot` → `ADDRESS_UNVERIFIABLE`.
- The lot is one word of letters and digits (`Lot 12-A` or `Lot 12/13` doesn't parse).
- Verify against the PDF's **Job Address** block (decisions, 30 Oct and 2 Nov 2026; no reader extracts the address): the label line must start `Lot <lot>`, the lot one word of letters and digits, equal to the project's. If more follows on that line, the rest must be exactly *R* plus an optional tail; if nothing follows, the line under it must end with *R* plus an optional tail, so the agent never has to guess where the street ends. The tail is nothing, a state, a 4-digit postcode, or both in either order. Compared on normalised text; exactly one `Job Address:` label, on one line.
- `ADDRESS_UNVERIFIABLE` when something can't be parsed: the project address, no single label, a label line not starting `Lot <lot>`, or a lone lot with nothing under it. `ADDRESS_MISMATCH` when both parse and the lot or *R* is not where the rule needs it.
- The check runs on pdfplumber's and pypdf's text; if the two results differ, `READERS_DISAGREE`. pypdf reads the Supplier column apart, so on its text the line under a lone lot must be **exactly** *R* plus the tail.
- Also `ADDRESS_UNVERIFIABLE` (2.5 review, 2 Nov 2026): *R* of fewer than two words; a second label in any spelling (`Job  Address`, `JobAddress`, `Job Address -`); a non-ASCII letter in the project address or the block.
- Must pass (fake values): PDF "Job Address: Lot 123 / Sample Lane Sampleville WA" vs project "Lot 123 (#45) Sample Lane Sampleville 6000 WA".

**Duplicate check (row 07), step 10**
- Read every task header "(tsk_…) | Compaction Test" on the project's Tasks tab, from a **settled** table: the rows render after the window shows, so the table is read until two reads in a row are equal and its Compaction Test numbers equal the `[Compaction Test]` options of the window's "-- Select Task --" select (row 10), else after 15 s `UNEXPECTED_SCREEN` (decisions, 3 Nov 2026, M4 gate). The rows and the options render together and an empty project shows nothing else (row 10, probe 4 Nov 2026), so "no tasks" counts only when every read for the full 15 s is empty (decisions, 4 Nov 2026). On test, one whose Status cell reads **Cancelled** (it has **Undo Cancellation**) is ignored; any other → `DUPLICATE_TASK`. Record the set of Compaction Test task numbers for W2.

**W1 Create New Task (rows 08–09)**
- First `before_write` (its assignee check reloads, so every window closes), then the project is reopened by its pln and checked again: heading, Client Internal No. and the settled Compaction Test task numbers equal to step 10's (a new one → `WRITE_NOT_STARTED`). Only then Create New Task.
- **Creator**: the one Creator field, in the Client section (label "Creator"; it defaults to the project's creator) → **Perth Scheduling**. Tick **- Compaction Test** (exact name; unique). **PO Number** (label-anchored) = the PO number; it is empty when the sub-form opens (row 24), and the agent reads it back. Upload the PDF to **PO Documents** (as in the walkthrough), never the separate **Documents** upload. The upload is saved only by Submit (row 09): an abandoned form leaves no document behind. **Note** (label-anchored textarea) = the email body.
- Everything else stays at its default. Read back before Submit: Creator Perth Scheduling; **- Compaction Test** is the only ticked checkbox in the window (bundles, other services and Multiple Units unticked); Task Client "Same as Project"; Task Name empty; PO Number; PO Documents shows exactly one row, the PDF's file name; the Documents area holds no file row (it shows empty by having no table at all, row 09); Note = email body; Sale Office "Prompt Engineering Pty Ltd"; PO Contact and Delivery Office "Choose...". Any mismatch → close the browser context, `WRITE_NOT_STARTED`.

**W2 after Submit (row 10)**
- Before Submit, `before_write(note_id, "W2")` re-reads `enabled` (no assignee check); a stop there closes the browser context, which abandons the filled form.
- **The Submit click is the partial-write line:** from the click on, every error (Ctrl+C included) is `PARTIAL_WRITE` and the Note is never returned to the pool, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their own ALERT and also leave the Note with the agent. Each carries step W2. Committing clicks (Submit, the Hold confirm, the Choose Project cell, Solved, each Assign) are made once, never retried (decisions, 3 Nov 2026, M4 gate).
- Wait up to 15 s for the Create New Task window to close. The new task is the **one** Compaction Test task number not in the set recorded at step 10 (after a reset, older Cancelled tasks are still there). Its details row: Lodged By `agent_user_name`, Task Creator Perth Scheduling, Status New Project or Inspection Analysis (row 07: it can move on by itself). No new task, more than one, or the form still open after 15 s → `PARTIAL_WRITE`.
- PO number, document and Note aren't in the project table (row 19):
  - **Task detail:** click the Task Creator cell of the new task's **details row**, the row right after the header row whose cell is exactly `(tsk_<n>) | Compaction Test` (never its header row, which holds Cancel and Hold). The task opens **in the same window**: its heading becomes `TSK_<n> PLN_<n> …` (upper case), and it must name the **new** task number, else `PARTIAL_WRITE`. In the section headed `tsk_<n> [Compaction Test]`, read **PO Number:** = the PO number, **Lodged By:** = `agent_user_name` and the **Notes** text = the email body; in the Client section, **Task Creator:** = Perth Scheduling. Nothing on this screen is clicked (Save, Complete and the uploads are danger).
  - **Back and the document:** choose **"-- Select Task --"** in the window's select (the heading returns to `<pln> …`), click the project's **Documents** button, and read the section headed `tsk_<n>` (the new task only; older tasks have their own copies): exactly one row, Type = the profile's `project_document_type` (**Purchase Order** on test, **Client Documents** on live; Joey's live screenshot, 10 Nov 2026), File starting with the PDF's file name. Then the project's **Tasks** button for W3. On test the task's own Documents tab is empty; on live it lists the PDF under Client Documents too, which the agent doesn't read.
  - A wrong value → `ACCURACY_BREACH`; a screen not as mapped → `PARTIAL_WRITE`.

**W3 Hold (rows 11–12)**
- **Hold** in the new task's header row only. In the window with heading `Hold Task: <new task no>`, type **ON HOLD UNTIL CALL UP** in Note. Before confirming, read every check: the heading names the new task; every Related Tasks checkbox and Select-all unticked; Reset turn around time unticked; "Send me a reminder email every … days" **ticked with 0** and "… at this date" unticked; Note text exact. Anything else → close the browser context, `PARTIAL_WRITE`. Confirm with that window's own **Hold** (two Hold buttons are on the page): the button "Hold" in the innermost element holding the heading `Hold Task: <new task no>` and a "Hold" button (row 11).
- Read back: the new task's row shows **Un-Hold** and a Status starting "On-hold" containing "ON HOLD UNTIL CALL UP".
- **Built (decisions, 4 Nov 2026, W3):** the checks are read as "exactly one ticked box in the dialog, hidden ones included, and it is the reminder", plus 0 days and the note; the "There are N related jobs" text inside the dialog with N row checkboxes plus Select-all in its table (none paged, loading or outside the read). Every W3 error closes the browser context and carries step W3: `PARTIAL_WRITE`, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their type; a Status without the note after Hold is `PARTIAL_WRITE`.

**W4 Link to Project (rows 13, 20)**: Link to Project opens the window **Choose Project** (anchored on its heading and its "After..." box). Fill its **Search/filter** with the pln, press **Enter** (`submit_link_search`), wait up to 60 s for the results, then click the **cell** whose name is exactly the pln (`getByRole('cell', name=<pln>, exact)` inside Choose Project); zero or more than one such cell → `PARTIAL_WRITE`. Never the row: its accessible name includes the Site Address, so a "… Close" street would trip the denylist. Choose Project then closes by itself. Read back: the Note's project button reads the pln (another pln is a wrong project: `ACCURACY_BREACH`); Status still starts "Pending" (it reads "Pending by <last user to set it>").

**W5 Solved (row 14)**: Status buttons → **Solved**. Read back as `docs/specs/spec.md` §6 W5, plus Solved disabled; "gone from the Pending list" is the Note ID search (Status filter read back Pending) showing no row whose ID cell equals the Note ID.

- **Built (decisions, 4 Nov 2026, W4 and W5):** before W4 the assignee check runs (any failure `PARTIAL_WRITE`), then the Note is found again (a second reload and Note ID search, row 25) and opened; Send Email is unticked and read back before Link to Project and read back again just before the cell. W5's `before_write` has no assignee check; Send Email is read back before Solved; the log line is the newest, one more than before Solved, "Status changed:" from Pending to Solved; the Pending search must be one page. Every W4/W5 error closes the browser context and carries its step: `PARTIAL_WRITE`, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their type. The demo's Link to Project uses the same cell-only select (its link, button and text fallbacks are gone).

**Reruns** (Objective, seam 2, S5): "changes nothing" means no task created or changed, no Note linked or Solved, and every Note's final assignee as before. With no state between runs, a skipped Note still in the pool is assigned to the agent and back on every run, which only adds two "User Assigned" log lines. That's expected.

## Testing Strategy

- **pytest at the two seams** in `docs/specs/spec.md` → Testing Decisions; behaviour, not private functions (normaliser unit tests allowed as a development aid).
- **Seam 1 (offline):** every case in the spec's seam-1 table, including the live-title rows, on the **3 fake fixture POs** (fake text in `tests/seam1/fixtures/cases.toml`; no PDF generator, decided by Joey at 2.1, 29 Oct 2026; the corrupt and image-only PDFs are bytes built inside the test) and their mutations. Each fake PO has both readers' text: pdfplumber's, where the Job Address block shares its lines with the Supplier column, and pypdf's, which reads the columns apart (decisions, 2 Nov 2026). The real PDFs are read only in the laptop's real-PO seam (`-m real_data`). **Zero false PROCEED.** Extra cases from the screen map:
  - a project with a **Cancelled** Compaction Test task → PROCEED with the test config, `DUPLICATE_TASK` with `duplicate_ignores_cancelled = false`
  - a project with a non-Cancelled Compaction Test task for a **different** PO number → `DUPLICATE_TASK` (MVP strict rule)
  - search rows with other suffixes plus one `/048` row → PROCEED on that pln; two matching rows → `PROJECT_AMBIGUOUS`; a matching row with Company not B1 Homes → `PROJECT_NOT_FOUND`
  - project address with a `(#n)` house number, postcode and state, and a lot with a letter (`12A`) → PROCEED; the same with a different lot letter → `ADDRESS_MISMATCH`
  - a Note already linked → `NOTE_ALREADY_LINKED`; a Note with no attachment / two attachments → `NO_PDF` / `MULTIPLE_PDFS`
  - a test Note with a live-style title whose PO ≠ the file name's → `PO_MISMATCH`
- **Seam 1, real POs (`-m real_data`, laptop only, both code readers):** the **3 most recent** real B1 `/048` Notes and the **3 trial POs** with their test-site lookups for the MVP (Joey, 16 Oct 2026); **10–20** (mostly `/048`, plus a few other suffixes and any odd ones) before go-live. For each, `private/fixtures/cases.toml` holds the Note title and body, the PDF file name, the MySys lookup Joey copied by hand and the expected result (PROCEED with values, or SKIP with reason). The lookup is **what MySys shows**, so the parsing is tested too: every Projects search row (pln, Client Ref No., Company), the project's Address string as shown, and the existing Compaction Test tasks with their status. Hand-split lot/street/suburb fields are kept only as the expected values. The test reports agreement per field and coverage (PROCEED ÷ clean POs), and fails on any false PROCEED. Skipped automatically when `private/` is absent (CI, Mac Mini).
- **Seam 2 (`-m testsite`, from the laptop; reset the test site first):** the 3 trial POs booked; a fresh copy of a booked trial Note → skipped `DUPLICATE_TASK` and returned to the Agent Pool (the skip case, using only trial POs); any non-`/048` Note in the pool untouched; immediate rerun changes nothing (as defined in [MySys screen rules](#mysys-screen-rules) → Reruns); Send Email Notification read back unticked before every Note-window write, after the latest assignee check (from the detailed log); a denylisted action (Discard, a Hold-dialog checkbox) refused by `guard.vet()` without touching the page (D3). The W-step tests book only as far as their step (`stop_after`, test-only) and run one at a time with a reset between them; "seam 2 green" means the fixed sequence of runs in `tests/seam2/README.md`. Moved out of seam 2 (D1): `enabled = false` and the Perth window are tested offline with a fake driver and an injectable clock, then shown on the Mac Mini in S6; a person taking the Note mid-run is a by-hand check (`--headed --slow-mo 500`). Address and other mutations are covered offline in seam 1.
- **No real data in test output.** Test-site and real-PO tests assert on booleans, counts, enum values and the trial identifiers only. A conftest hook cuts every `testsite` and `real_data` failure report to the test name and exception type, so Playwright call logs and pydantic errors can't print an address. Selecting `-m testsite` or `-m real_data` explicitly makes a missing secret or precondition an error, not a skip.
- **Test first** on every task: failing test, shown failing for the right reason, then code. Stop for Joey before the code only on 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2 (decisions, 24 Oct 2026).
- CI (`.github/workflows/check.yml`) runs the check command and gitleaks on every push and PR, with no secrets.

## Boundaries

**Always**
- Show `uv run scripts/check.py` output before calling a task done.
- Finish every check before opening Create New Task; read back every write.
- Return a skipped Note through **Assign**, never Unassign. Untick Send Email Notification before every write on the Note window and read it back.
- **One agent at a time:** no laptop run against the test site (seam-2 tests, `run`, `spike`) while the Mac Mini job is loaded, and no manual Mac Mini run while a laptop run is going. Both log in as the same agent account.
- Keep real client data (PDFs, live screenshots, captures, addresses) in `private/` only. Test-site screenshots and captures count as real data, because the trial POs are real. Anything committed (fixtures, `docs/screen-map.md`) is fake or redacted and holds no credentials; the only exception is the 3 trial POs' internal numbers, PO numbers and test-site plns (assumption 2).

**Ask Joey first**
- New dependency; a change to the readers or the address rules (then rerun seam 1, and the real-PO seam on the laptop).
- A change to any test, fixture or expected result (its own commit).
- Changes to `.github/workflows/`, `config/test.toml`, `docs/macmini-setup.md`, `scripts/macmini-run.sh` or the launchd plist.
- Anything that would tie `src/` to the Mac Mini or macOS.

**Never**
- Run anything against the live site (`prompt.mysys.com.au`), or name its host anywhere but `LIVE_HOST`, `config/live.toml` and the deny rules (CLAUDE.md Must never #3): only Joey runs the agent on live, on the Mac Mini.
- Call click, fill, check, set_input_files, evaluate or dispatch_event outside `mysys/guard.py`. Never target Discard, Unlink, Cancel, Undo Cancellation, Un-Hold, Change Project, Unassign, Remove, Delete, anything named "close" (the attached PDF's remove cell, Task Client's clear, window Close), the Note's Pending button or any Hold-dialog checkbox. Abandon a dialog by closing the browser context.
- Add an AI or paid-API reader, or let any reading choose what to click (decisions, 2 Nov 2026).
- Run a Playwright CLI command that acts on the page, saves state or cookies, or lists network requests; or point Playwright CLI at anything but the test site.
- Send, reply to, forward or delete email; touch Outlook.
- Put a secret anywhere but keyring (the laptop's Credential Manager, `poagent`'s Keychain on the Mac Mini) or a `PO_AGENT_*` environment variable.
- Commit anything from `private/`, or copy real client data into a committed file, a PR, an issue, run output or the Mac Mini (exceptions: the trial POs' identifiers, assumption 2, and the Mac Mini reading the trial POs from the test site, with each PDF on disk only from its download until it's read, Trial conditions).
- Push to `main` or force-push. Merge only with `gh pr merge <n> --merge --match-head-commit <sha>` (the commit `/verify-pr` checked), after `/verify-pr` passes and CI is green; a PR that touches the hooks, settings, the verify-pr skill, CI, the guard or the check, or loosens a safety control, stays Joey's (decisions, 2 Nov 2026).

## Trial conditions

*Replaces the Trial waiver (v1.5) for the cloud routine. On the Mac Mini, ADR-002 gates H2 and H5 pass, so nothing is waived (CEO decision 3, 15 Oct 2026), except H2 on the test site from 6 Nov 2026 (below).* The trial runs on these conditions:

- The Mac Mini's agent user `poagent` is a **standard** (non-admin) account used only by the agent; Joey and a backup admin have the admin accounts. FileVault is on.
- The MySys credentials are the **test-site** agent account's. They and the Mac Mini's GitHub token (this repo only: contents read, issues write), live only in `poagent`'s Keychain.
- No Claude Code or other AI tool is installed for `poagent`; nothing on the Mac Mini runs a Claude session or calls the Anthropic API. **Waived for the test site only (Joey, 6 Nov 2026):** Joey uses Claude in `poagent` for another project, under the conditions in `docs/decisions.md` (6 Nov 2026); it never touches `~/po-agent`, the agent's Keychain items or the test site, and it is removed from `poagent` before go-live (H2 must pass again).
- Run output follows the stdout contract (no PO content beyond PO number and pln).
- No real client data is copied to the Mac Mini during the MVP. The one exception is the **3 trial POs, which are real** (Joey, 16 Oct 2026): runs read their PDFs and Notes from the test site, keep them in memory, as on live. The browser writes every download to disk, so a trial PDF is on the Mac Mini's disk only from its download until it's read into memory, a moment later; leftovers are removed at the next run start (D2, 16 Oct 2026). Nothing else from them is written to the Mac Mini's disk apart from the run output (PO number and pln); `run` never writes a page snapshot (`booking.save_snapshot` is the demo's, never the booker's; decisions, 3 Nov 2026, M4 gate). **The CEO must confirm decision 2, on these terms, before the first Mac Mini run that downloads a trial PO** (M3). Other real data stays on the laptop (see below).
- At the end of the trial, Joey unloads the job, revokes the key, has the test password changed and deletes the test items from the Keychain. Live credentials go onto the Mac Mini only after the go-live sign-off (Joey's since 9 Nov 2026) and once H2 passes again.

## Real client data

Joey decided on 14 Oct 2026 that the agent may read real client data (CEO to confirm; it settles CEO decision 2 once confirmed). The agent's own MySys account exists on live.

| Allowed | Where it lives | Not allowed |
|---|---|---|
| The code readers read real PO PDFs on the Mac Mini (no outside service, decisions 2 Nov 2026) | In memory during a run; the PDF is on disk only from its download until it's read (D2) | Sending PDF or Note text to any outside service |
| Claude Code on the laptop reads real PDFs, live screenshots and captures to understand the pages and write the screen map | `private/` (git-ignored) | Committing them; putting them in GitHub, an issue, a PR or on the Mac Mini |
| Joey views live screens with the agent's account by hand: the PO Allocation Pool, real Notes, real PDFs | Screenshots and saved PDFs in `private/` | Any change on live during capture (no Assign, no edits, no bookings) |
| Claude reads live project lookups for the real-PO seam (Projects search, project page, Tasks list) in the built-in browser pane, after Joey logs in himself with the agent account (decisions, 10 Nov 2026, live lookups) | `private/fixtures/cases.toml` | Typing a password; the Note Pool or a Note window; any button that saves or writes; any value outside `private/` |
| Real POs as seam-1 test cases, including the 3 trial POs | `private/pdfs/`, `private/fixtures/cases.toml` | Real POs in CI or on the Mac Mini |
| The 3 trial POs (real) as the test site's trial Notes, booked by the agent | MySys test site; in memory during runs (laptop and Mac Mini); their internal numbers, PO numbers and test plns in docs and run output | Their PDFs, addresses or client names in a committed file, an issue, a PR or run output; their PDFs on the Mac Mini's disk beyond the moment of download (D2) |

- **Live bookings happen only in the live order** ([Production](#production)), run by Joey on the Mac Mini with the live profile; Claude never logs into live (decisions, 10 Nov 2026, live profile); it only reads project lookups in a session Joey logged in (decisions, 10 Nov 2026, live lookups).
- **Turn off model training first:** Joey is on a **Pro** plan, so before Claude Code reads any real data, the model-training setting in claude.ai privacy settings must be off. (The agent itself calls no AI API: its readers are code, decisions 2 Nov 2026.)
- `.gitignore` excludes `private/`; a commit hook and CI check also block any staged path under `private/` and any PDF outside `tests/seam1/fixtures/pdfs/`.

## Expected slices (input for `/agent-skills:plan`)

**Milestone A first (decisions, 25 Oct 2026):** a decide-only demo to the CEO on the Mac Mini: 1.4, 1.6, 1.7, M0b.1, 1.8, 1.9, 1.10; M2 (2.1–2.6); M3's 3.1, 3.2, 3.3, 3.5, then 3.4. 3.6 (assignee check, stale-Note stop) follows the demo and is merged before any booking code. Then M0b.2, M4, M5, M6.

| Slice | Delivers | Needs |
|---|---|---|
| **M0** (by hand, Claude observing) | Test site, with Playwright CLI (Joey clicks, Claude snapshots): the full SOP for 2609017B, and the read-only screens (Note, PDF, project search, project page) for 2609034B and 2610002B; then reset. Checks C1, C3, Send Email Notification screens, MFA/password expiry, how a cancelled task shows. Live, view-only by hand: pool and Note screenshots, the 3 most recent real PO PDFs and their project data into `private/`. Claude writes `docs/screen-map.md` (redacted) | — |
| **M0b** (by hand, Claude observing; test site) | **M0b.1 done (25 Oct 2026):** moving between the Note and project windows, an anchor for every unlabelled control on the login page, Note Pool, Projects panel and Note window, the Note Pool after a filter change, search, reload or login, reopening an open project (rows 25–28); `fill` alone doesn't run the Note Pool search; one Assign returns a Note (15b). Rows 21–22 (0 or 2 attachments) dropped: the attachment rule stands without them. **M0b.2 done (3 Nov 2026):** the task detail screen opens from the new task's details row in the project window and shows PO number and Note; the PDF is filed on the project's Documents tab under the task's section; Link to Project's Choose Project search and its `pln_…` result cell; PO Number not prefilled; the upload saved only by Submit; label anchors for every weak Create New Task field and the Hold confirm (rows 19, 20, 24); an open Note window doesn't refresh its Assignee (row 23). Written into `docs/screen-map.md` v1.3 and [MySys screen rules](#mysys-screen-rules) | M0 |
| **M1** Walking skeleton + Mac Mini spike | uv project, config, secrets, output, guard + `guard_check.py`, check command, hooks (incl. the `private/` block and the Playwright CLI allowlist), CI; `po-agent spike`; `scripts/macmini-run.sh` and the launchd plist; Mac Mini set up (`docs/macmini-setup.md`, starting with a test-site login by hand from it); spike passes **on the Mac Mini as `poagent`**, then the job is unloaded until the first bookings (D1) | M0 (MFA answer); M0b.1 before the spike |
| **M2** Decision seam | Both title rules, both code readers (pdfplumber and pypdf, decisions 2 Nov 2026), the address check against MySys (with the project-address parse), project match rule, agreement, skip reasons; the 3 **fake** fixture POs and their mutations in CI; **real-PO run** (`-m real_data`, incl. the 3 trial POs) | M1 |
| **M3** Decide-only + run controls | `run --decide-only`: assign → download → decide → back to pool; NOTE lines; on the laptop, then on the Mac Mini (`scripts/macmini-run.sh decide-only`). Before any booking code (D1): `enabled` kill switch, Perth window, run cap, `before_write`, assignee check, stale-Note stop. Plain `run` refuses until M4 | M2, C3, M0b.1; **CEO decision 2 confirmed** before the Mac Mini run |
| **M4** First booking | Booker W1–W5 with read-back; 2609017B booked from a manual run on the Mac Mini (`launchctl kickstart`); then 2609034B and 2610002B the same way; then the test site reset | M3, C1, M0b (task detail, Link to Project) |
| **M5** MVP safety | `ALERT`s and exit codes end to end, stop on first failure, guard-refusal and other seam-2 cases (the run controls moved to M3, D1) | M4 |
| **M6** MVP demo | Test site reset; `/ship` go/no-go; launchd job loaded on the Mac Mini; the 3 trial POs, then a fresh copy of 2609034B as the skip case; reset and repeat (3 demos in a row, S8); cost per PO; one-page demo note for the CEO | M5 |

## Success Criteria

- **S1 Mac Mini spike:** after a test-site login by hand from the Mac Mini succeeds, `scripts/macmini-run.sh spike` run as `poagent` logs into the test site with the Keychain credentials and lists the eligible Notes, read-only, and `runs.log` shows `RUN_SUMMARY` with `exit_code: 0`.
- **S2 CI:** `uv run scripts/check.py` is green on `main`, including `guard_check.py`.
- **S3 Decision seam:** the 3 fake fixture POs (CI) and the 3 trial POs (laptop, `-m real_data`, test-site lookups) PROCEED with the right pln, PO number and email body (the Note body, [MySys screen rules](#mysys-screen-rules)); **0 false PROCEED** across the MVP fixture set. On the real-PO set (laptop): **0 false PROCEED**, with per-field agreement and coverage reported. With only 3 real POs, coverage is reported but not judged against 80%: any skip of a clean real PO is reviewed before M3. The 80% line applied to the 10–20 POs to be collected before go-live; only 3-5 real POs exist, so it is dropped and live `run --decide-only` is the wider check (decisions, 9 Nov 2026, go-live plan).
- **S4 Trial run (scheduled launchd run on the Mac Mini, no human help):** with the test site reset and exactly one Pending Note for each trial PO (2609017B, 2609034B, 2610002B) in the Agent Pool:
  - pln_66935, pln_66938 and pln_66940 each have exactly one non-Cancelled Compaction Test task: correct PO number, PDF attached (PO Documents), Creator "Perth Scheduling", Note = email body, On Hold with "ON HOLD UNTIL CALL UP"; Send Email Notification read back unticked before every Note-window write; each Note linked to its pln and Solved
  - any non-`/048` Note already in the pool was not assigned or opened.
- **S5 Rerun and skip:** Joey places a fresh copy of the 2609034B Note in the Agent Pool. The next Mac Mini run (scheduled or `launchctl kickstart`) skips it as `DUPLICATE_TASK`, returns it to the Agent Pool with no new task (its NOTE line shows the reason), and changes nothing else (Reruns, in [MySys screen rules](#mysys-screen-rules)).
- **S6 Controls:** `enabled = false` on `main` → the next Mac Mini run (whose wrapper reads `enabled` from `origin/main` before it runs the `production` tag) exits before login; outside 07:00–18:00 Perth on weekdays → no MySys contact (and the launchd job only fires 07:07–17:07 Monday–Friday); `launchctl bootout` → no further runs; a denylisted action → refused before any page interaction.
- **S7 Evidence:** NOTE lines carry tokens and AUD cost per PO; `RUN_SUMMARY` totals them; the trial run has no `ALERT` lines and no guard refusals.
- **S8 Repeatable demo:** after a reset by Joey (`docs/demo-runbook.md`: cancel the 3 tasks with his own account, place fresh copies of the 3 Notes), S4 and S5 pass again, **at least 3 times in a row**, with no code or config change between demos. Each demo can be shown from the laptop (`--headed --slow-mo 500`) or the Mac Mini (`launchctl kickstart`, then `runs.log`).

## Production

From 29 Oct 2026 (decisions, 29 Oct 2026). The MVP demo on 28 Oct 2026 proved the booking steps on the test site under supervision: `po-agent demo` booked 2609017B from the laptop and from the Mac Mini, with Joey's Enter before every write (PRs #19-#30). Production is the agent doing the same **by itself**, hourly, on the office Mac Mini: first on the test site, then on live MySys once every go-live gate below has passed.

Since 10 Nov 2026 the code has the live profile (G.3; decisions, 10 Nov 2026, live profile), and CLAUDE.md Must never #3 lets the live host appear only in `LIVE_HOST`, `config/live.toml` and the deny rules (Joey's hand edit, PR 90). Claude still never runs anything against live; it only reads project lookups for the real-PO seam in a browser session Joey logged in (decisions, 10 Nov 2026, live lookups). **Since 9 Nov 2026 the CEO has given Joey full authority for every go-live decision**, so Joey's dated decision is the CEO's sign-off wherever this spec asks for it (decisions, 9 Nov 2026, go-live plan).

**In, in this order** (task numbers are `tasks/plan.md`'s; its Phase P has the detail)

| Step | Tasks | Done when |
|---|---|---|
| 1. Docs catch-up and this section | - | This section merged |
| 2. Decide | 2.1-2.6: read the PO with two code readers (pdfplumber and pypdf), check it against MySys (decisions, 2 Nov 2026) | `false PROCEED: 0` in seam 1 and the real-PO run (S3) |
| 3. Run controls and decide-only | 3.1-3.3, 3.5, 3.6 (take and return a Note, kill switch, Perth window, run cap, assignee check, stale-Note stop), then 3.4 | Decide-only runs green on the laptop and the Mac Mini |
| 4. Real booker | 4.1-4.5: the demo's proven steps (`src/po_agent/mysys/booking.py`) become the booker, which takes only a `Proceed` from the decision engine, has no Enter prompt and reads back after every write. Before 4.1: M0b.2 and a doubt-driven review of the booker design | Seam 2 booking cases green; plain `run` books (it refuses until 4.5) |
| 5. Unattended on the test site | 1.9 (wrapper and plist), 1.10 (Mac Mini as `poagent`, S1), 4.6, 5.1 (alerts), 5.2 (safety cases), 7.1 (heartbeat), 7.2 (silent-skip alert). **The hourly week is skipped** and 7.6 dropped (decisions, 9 Nov 2026, go-live plan) | Tasks built; the week replaced by the watched live order |
| 6. Go live | 7.3 (safe trace), 7.4 (release pinning), 7.5 (ops runbook), then the live-profile task (G.3: committed `config/live.toml`, live secrets only in `poagent`'s Keychain, alert issues without `note_id`; decisions, 10 Nov 2026); Must never #3 changed by Joey; then the live order below. Code frozen until full hourly runs (8.1-8.4 after) | One booking per run, watched, correct; then full hourly runs |

**Out**
- **No schedule change:** Monday-Friday, hourly 07:07-17:07 Australia/Perth, as in [Tech Stack](#tech-stack).
- **No Grok Bot.**
- **No fake-PDF generator unless a 2.1 case needs one** (decided at 2.1). Rule checks are tested on fake text; real PDFs only on the laptop (`-m real_data`); most "should skip" cases come from the MySys side.
- `po-agent demo` stays for supervised demos; it isn't the production path and isn't extended.

**Go-live gates** (every one before any contact with live MySys, including a read-only spike, except where a gate says later; reshaped by decisions, 9 Nov 2026, go-live plan)
1. **MySys permission:** MySys confirms in writing that automating the agent account is allowed (and says whether there's an API). If the answer is no, production stops. **Met, 29 Oct 2026:** automation on the website is allowed; no API, because Alltraders would charge for one (decisions, 29 Oct 2026).
2. **Live answers, from Joey's own look at live** (one `/048` Note and the Create New Task form opened with the agent's account, nothing saved): PO Documents or Documents (open question 11); Resolve or Solved on live; whether live's Client Ref No. column is the one ending `/048` (open question 10); whether the agent account's password expires (open question 3); the live pool's name and the agent's user name; the `/048` title format; and how many Pending Notes the stale-Note read lists (more than one page stops every run with `MORE_PAGES`). Any difference from the test site is a code change. **Answered (10 Nov 2026):** PO Documents and Solved, as on test (live's project Notes list shows "Resolved"; the Note log says Solved); Client Ref No. is the bare internal number (no `/048`); no password expiry; pool "PO Allocation Pool", agent user name as on test; title `[B1 Homes] Order <internal no>/048`; 153 Pending Notes at All Users, so live's stale-Note read filters by the agent; the eligible read (PO Allocation Pool + Locked) is under one page; W2 expects Type Client Documents. Each difference is in the live profile (decisions, 10 Nov 2026).
3. **Go-live sign-off** and the **backlog cut-off date**. **Met, 9 Nov 2026:** Joey signs off under the CEO's delegated authority; no cut-off: every `/048` Note in the agent's pool is processed like a new one.
4. **Accounts:** the Mac Mini's GitHub token and the `po-agent-alert` label for alerts (in place); a named backup admin for the Mac Mini **before unattended hourly live runs**, not before the watched ones.
5. ~~A week of hourly test-site runs~~ **Replaced, 9 Nov 2026:** the real-PO seam on the 3-5 real POs that exist (`false PROCEED: 0`, coverage reported, not judged); live `run --decide-only`, its NOTE lines read by Joey against the Notes; and the first live booking watched, with 5.2's trace check on it (every `assign_note`, `link_to_project`, `link_select_project` and `mark_solved` has an ok `email_notification_unticked` after the Note's latest ok `assignee_check` and its previous Note-window write; only that Note's `note_id` in the trace). A miss stops the live order.
6. **Production operations** (4 Nov 2026; `tasks/plan.md` 7.1-7.5, all built): a heartbeat that emails Joey when no run has finished for 2 hours inside the schedule (enabled before unattended hourly live runs); an alert when every eligible Note in a run skips as `UNEXPECTED_SCREEN`; a trace on the Mac Mini of allowlisted fields only, kept 90 days; the Mac Mini running a `production` tag that only Joey moves, so a merge no longer deploys; `docs/ops-runbook.md`. 7.6's triage loop is dropped (9 Nov 2026).

**Safe trace** (7.3, built 5 Nov 2026). The Mac Mini never passes `--detailed-log`, so the trace is what Joey reads after an alert:
- **Where:** `<trace_dir>/<YYYY-MM-DD>.jsonl`, `trace_dir` from config (`~/Library/Logs/po-agent/trace` in `config/test.toml`). Written only when the folder's parent exists: the Mac Mini wrapper makes `~/Library/Logs/po-agent`; the laptop and CI have none, so they write nothing. The date is the run window's (Perth), so one working day is one file.
- **Kept 90 days:** at run start, right after config is loaded, files named `<date>.jsonl` older than 90 days are deleted; nothing else in the folder is touched.
- **What:** one JSON object per event, exactly `run_id`, `ts` (UTC), `note_id`, `step` (0-11, `2a`, `W1`-`W5`, `return`, `decide`), `name` (a check: `assignee_check`, `email_notification_unticked`, `read_back.<field>`, `decision`, `error`, `run_end`; or a guard action's mapped name), `outcome` (`pass`, `fail`, a skip reason, `DECIDE_ONLY` or an error's type name) and `duration_ms` (since the run's previous event). Every field has a closed type (`src/po_agent/core/trace.py`); a value outside it is written as null. No message, no traceback, no page text, PDF text, address or Note body.
- **Events:** the run log's events (guard actions, assignee checks, read-backs, the skip decision, the error), with or without `--detailed-log`, and a last `run_end` event: `pass`, or the type of the error the run reported. Guard actions in the booker are written at the end of each W step with that step (5.2), or at the next run-log event, with that event's step (the error's step for a stopped one). The booker's assignee checks (W1, W4) and its Send Email read-backs (before Link to Project, the Choose Project select and Solved) are run-log events too. A run-log write that fails never stops a booking.
- **Never stdout:** the run output is unchanged. A trace that can't be written is dropped; the run goes on.

**Live order** (each step its own dated `docs/decisions.md` entry): read-only `spike` on live, then `run --decide-only` on live, then `run` booking **one PO per run, watched** (gate 5's trace check on the first), then full hourly runs (gate 4's backup admin and the heartbeat on first).

## Open Questions

1. ~~C1 and C3~~ **Answered on the test site (16 Oct 2026, `docs/decisions.md`):** no Hold-dialog related-task checkbox was pre-ticked (C1), and a Note goes back to the Agent Pool through Assign (C3). Neither blocks M3 or M4. The agent still reads every Hold-dialog checkbox before confirming.
2. **Does MySys accept a login from the Mac Mini?** It connects from the office internet address. A login by hand in Safari on the Mac Mini answers it first (`docs/macmini-setup.md` section 2), then S1. If blocked or challenged: stop, record it in `docs/decisions.md` and tell the CEO.
3. **MFA or password expiry** on the test agent account? Unattended runs need neither. **Partly answered (16 Oct 2026):** no MFA step seen at login; password expiry still to confirm with the MySys admin. **Answered (6 Nov 2026, Joey):** the password has no due date; the MySys admin may change it by hand if it is judged too weak. A changed password fails the next login (exit 2, alert issue); the fix is a new `mysys_test_password` in `poagent`'s Keychain (`docs/macmini-setup.md` section 7), then one spike at the Mac; 7.5's ops runbook must cover this.
4. ~~**CEO/IT OK** for a private GitHub repo; **CEO to confirm** decision 2.~~ **Answered (25 Oct 2026):** the repo is public so the CEO can read it (no real client data in it); decision 2 was delegated to Joey, who decided yes on the Trial conditions terms, and the CEO approved D2.
5. ~~Your Claude plan~~ **Answered:** Pro. The model-training setting must be off before real data is read. (Mac Mini runs don't use the plan and call no paid API, so there is no per-PO cost; decisions, 2 Nov 2026.)
6. **Reader model:** pin an exact Sonnet-class model ID in M2; try a Haiku-class model only after it passes seam 1.
7. ~~Playwright download hosts for the routine's allowlist~~ **No longer needed:** the Mac Mini has no network allowlist (CEO decision 3).
8. **Opening a live Note:** does viewing a Note or downloading its PDF change anything (lock it, mark it read, log an action against the agent)? **Answered on the test site (16 Oct 2026, check 3.5):** neither adds a log line or changes the assignee or status; lock state isn't visible. Stage 3B may open live Notes and download PDFs (no other button).
9. ~~Resetting the test site~~ **Answered:** Joey's own account can **cancel** a task on the test site. Reset = Joey cancels the trial POs' Compaction Test tasks and places fresh copies of the 3 Notes; the test profile's duplicate check ignores Cancelled tasks. The agent itself still never presses Cancel. Seen in M0 (16 Oct 2026, check 3.6): a cancelled task shows Status **Cancelled** with an **Undo Cancellation** button, and an **On Hold** task offers **Cancel** directly, so the reset doesn't need to release it first.
10. **Live Projects search** (Joey, 16 Oct 2026): 3–4 projects per internal number, and only one ends with `/048`. SPEC assumes the column is **Client Ref No.** (on test it holds the bare internal number). Confirm in Stage 3B with a view-only live search. **Answered (Joey's look, 10 Nov 2026):** one row per internal number, Client Ref No. the bare number, Company B1 Homes: the match rule is the same as on test.
11. **PO Documents or Documents?** The SOP says "Documents → upload"; the walkthrough used PO Documents, so SPEC uses PO Documents. Confirm with the PO admin before go-live (go-live gate 2; Joey, 3 Nov 2026: not an M4 blocker, the test site uses PO Documents). **Answered (Joey, 10 Nov 2026):** PO Documents, as on test; live files the upload as Type Client Documents (W2 reads that).
12. **What makes a Note "Locked"?** The trial Notes show under the Locked filter, but lock state isn't visible on the Note. If a fresh Note ever doesn't show under Locked, the agent won't see it (safe, but it would cost coverage). **Answered for live (10 Nov 2026):** PO Allocation Pool + Locked lists the new B1 Notes (Assignee the pool, Project `---`).
