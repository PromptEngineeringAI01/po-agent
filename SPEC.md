# Spec: PO Agent MVP (test site, run on the office Mac Mini)

**Status:** **Approved by Joey, 15 Oct 2026** · v1.16 (1.16: slice M0b.1 written up: row-26 anchors, the Note Pool search runs when focus leaves the box (fill + Refresh), filters persist across a reload, the agent reloads instead of minimising windows, one Assign returns a Note, the attachment rule without rows 21–22, row 23 moved to M0b.2 (25 Oct 2026); 1.15: decision 2 made (delegated to Joey: yes); Milestone A, a decide-only demo on the Mac Mini, comes first, and 3.6 moves after it but before any booking; the repo is public (25 Oct 2026); 1.14: outside the repo, the protect_paths hook writes only to the plan, project-memory and Claude temp folders (24 Oct 2026); 1.13: a lighter build process: the review stop after the failing test only on the guard, hooks, decision and MySys-acting tasks (24 Oct 2026); 1.12: the repo-data check is stricter: banned folders at any depth and in any case, plus `.state/`, `traces/`, `secrets/` and `.env/`; `.env*` files, `config/live*.toml` and images banned too (19, 21 and 24 Oct 2026); 1.11: the plan freeze, decisions D1–D7 in `docs/decisions.md` (16 Oct 2026): run controls and the assignee check built before booking (M3); the trial PDF briefly on the Mac Mini's disk; real-page refusal tests call `guard.vet()` only; the live host named only in the Bash hook's deny regex; the select rule; the stale-Note stop; the assignee check before W1 and W4 only; one agent at a time; M0b grows to rows 19–28; 1.10: the 3 trial POs are **real** B1 POs, kept by Joey with changed real-data rules; SPEC fixed against `docs/screen-map.md` v1.1: new [MySys screen rules](#mysys-screen-rules), project match on the one `/048` result, strict MVP duplicate check, `NOTE_ALREADY_LINKED`, "close" denylisted, fake CI fixtures, slice M0b (16 Oct 2026; the defaults in `docs/decisions.md` accepted by Joey the same day); 1.9: M0 checks answered from the screen map, C1 and C3 pass on the test site; the denylist adds Pending, Undo Cancellation, Un-Hold and Change Project (16 Oct 2026); 1.8: the real-PO decision seam uses the 3 most recent real POs for the MVP, 10–20 before go-live (16 Oct 2026); 1.7: the last write is the Note's **Solved** button, because the test site has no Resolve button (16 Oct 2026); 1.6: CEO decision 3, the trial runs on the office Mac Mini instead of an Anthropic cloud routine: a launchd job as a separate standard user, secrets in its Keychain, the trial waiver replaced by Trial conditions, `docs/macmini-setup.md` replaces `docs/routine-setup.md`; 1.5: the demo must be repeatable at least 3 times, S8 and `docs/demo-runbook.md`; 1.4: approved; the test site is reset by Joey cancelling tasks with his own account, and the test profile's duplicate check ignores cancelled tasks; Pro plan; 1.3: screens mapped with Playwright CLI while Joey clicks; `po-agent capture` dropped; all 3 trial POs named at every stage; 1.2: the 3 trial POs only, test-site reset, skip shown with a duplicate copy; 1.1: real client data allowed, kept on Joey's laptop)
**Active spec.** Build this first. The full v1 design stays in `docs/specs/spec.md` and is built after the MVP has proved the agent works (roadmap phase 2).
**Built from:** `docs/intent.md`, `docs/decisions.md` (wins if anything disagrees), `docs/specs/spec.md` v1.2, `docs/specs/ADR-001-po-agent-architecture.md` (Accepted), `docs/specs/ADR-002-po-agent-hosting.md` (Accepted, CEO decision 3, 15 Oct 2026).

## Assumptions

1. **Every booking is on the test site.** The MVP's code has no live profile and refuses any URL that isn't `test-prompt.mysys.com.au`.
2. **The agent may read real client data** (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real PO PDFs and view-only captures of live screens are used to understand the pages and to test the readers. They stay on Joey's laptop in the git-ignored `private/` folder, never in GitHub or on the Mac Mini during the MVP. **The 3 trial POs are real B1 POs too** (found 16 Oct 2026: the test site's 2609017B PDF is byte-identical to the live one). Joey keeps them as the trial POs: their internal numbers, PO numbers and test-site plns may appear in committed files and run output; their PDFs, site addresses, client names and other PDF content may not. The Mac Mini handles them only as the agent reads them from the test site. See [Real client data](#real-client-data).
3. **The trial runs on the office Mac Mini** (CEO decision 3, 15 Oct 2026; ADR-002 Option D, Accepted): a launchd job as a separate standard macOS user, secrets in that user's Keychain. ADR-002's gates all pass there, so no waiver is needed; the trial still follows [Trial conditions](#trial-conditions). Setup: `docs/macmini-setup.md`.
4. **ADR-001 is unchanged.** The script does every click; the Claude reader only reads. On the Mac Mini a shell script (`scripts/macmini-run.sh`) starts the agent; no Claude session is involved.
5. **No state between runs** (Joey, 14 Oct 2026, kept for MVP scope). MySys is the state: a Solved Note is done, the duplicate check stops double bookings, and a skipped Note is simply checked again next run. The Mac Mini appends each run's short output to a log for Joey; the agent never reads it.
6. **Production runs on the same Mac Mini** (CEO decision 3), after the CEO's go-live sign-off. The code stays host-agnostic: secrets from env vars or keyring, and nothing Mac-specific in `src/` (launchd and the wrapper live in `scripts/` and `docs/macmini-setup.md`).
7. **CEO decisions 1 and 3 are made.** Decision 2 is Joey's call pending the CEO's confirmation. Because the trial POs are real, it now gates the **first Mac Mini run that downloads a trial PO** (M3 on the Mac Mini); work on the laptop isn't blocked.
8. **Built on Joey's Windows laptop** in VS Code with Claude Code; Python 3.12 via uv; GitHub repo, public so the CEO can read it (the Mac Mini pulls `main` from it; decisions, 25 Oct 2026); Addy Osmani's agent-skills.

→ Correct any of these before `/agent-skills:plan`.

## Objective

Prove, early and cheaply, that the hybrid PO Agent does the admin's job on the MySys test site with no human help, unattended, from the office Mac Mini.

The MVP proves that:

- the Mac Mini can reach the test site from the office, log in and drive it with headless Chromium (the biggest unknown, so first)
- the two readers agree on 3 fake fixture POs and their mutations, on the 3 trial POs **and on a set of real B1 POs**, and never approve a bad one
- the script books each trial PO exactly as the SOP says and reads every write back
- a PO it shouldn't book goes back to the Agent Pool, and a non-`/048` Note is left untouched
- a second run creates, changes or links no task and solves no Note (see [MySys screen rules](#mysys-screen-rules) → Reruns)
- Claude's cost per PO is measured.

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
| §2 processing order | Steps 0, 2 (with 2a), 3–4 and 6–12. The decision engine knows **both title rules** (test: the Note Pool's Subject/Note cell, which joins title and body, contains `<internal no>_048[_n].pdf`; live: title `[B1 Homes] Order <internal no>/048`) so real live Notes can be tested offline; only the test profile exists. On both, step 0 also needs the row's Project cell to read `---` (not linked). A test Note whose title has the live form must also agree on the PO number (`PO_MISMATCH`). Step 1 (skip list) is v1; step 5 (live sender check) is v1 |
| §2 step 2a (new) | After Assign, a Note window that shows a project button instead of **Link to Project** → skip `NOTE_ALREADY_LINKED` (final), before any download or write |
| §3 reading schema and skip reasons | All, except live-only checks; plus `NOTE_ALREADY_LINKED` |
| §2 step 8 project lookup | Exactly one **matching** row, by the match rule in [MySys screen rules](#mysys-screen-rules) → Project search: Company B1 Homes and Client Ref No. exactly `<internal no>` (test) or `<internal no>/048` (live); rows with other suffixes are ignored (on live 3–4 projects come back per internal number and only one ends with `/048`, Joey 16 Oct 2026) |
| §4 address check (verify, not extract) | All, with the project-address rule in [MySys screen rules](#mysys-screen-rules) → Project address (MySys holds one address string, not separate fields) |
| §2 step 10 duplicate check | **Stricter than v1:** any Compaction Test task on the project counts as a duplicate, whatever its PO number, because the project's task table doesn't show PO numbers (screen map row 07). The **test profile ignores Compaction Test tasks whose status is Cancelled** (`duplicate_ignores_cancelled = true`), because Joey resets the test site by cancelling tasks. Every other status, and every status on live, counts |
| §5 action guard + build check | All, plus the denylist and allowlist additions in [MySys screen rules](#mysys-screen-rules). It's cheap and it's the main safety control |
| §6 booker W1–W5 with read-back | All, with the values and read-backs in [MySys screen rules](#mysys-screen-rules). W2's task-detail read-back and W4's search need slice M0b.2 first |
| §7 Claude reader | All: no tools, structured output validated again by pydantic, temperature 0, pinned model ID, 60 s timeout, one retry |
| §8 run controls | `enabled` kill switch (at start and before every write step), Perth window, run cap, fresh login, assignee check **before W1 and W4** (D7), the **stale-Note stop** at run start (D6), **stop the run on the first unexpected screen or failed write** |
| Skip → back to pool | Through **Assign** with the pool as assignee (C3 answered yes, 16 Oct 2026); exact steps in [MySys screen rules](#mysys-screen-rules) → Note window |
| `reader_mode = deterministic-only` | Yes: every PO skips `ADDRESS_UNVERIFIABLE` (approved C4 behaviour); a few lines of code |
| `--decide-only` | Runs every check, returns each Note to the pool, books nothing. Used before the first booking |

### Deferred to v1 (after the MVP demo)

| Deferred | MVP behaviour instead | Why it's acceptable on the test site |
|---|---|---|
| Skip list and 24 h retry of `PROJECT_NOT_FOUND` | Nothing persisted. A skipped Note is checked again every run | Same answer each time; costs one Claude call per skipped Note per run |
| Partial-write auto-resume | `ALERT PARTIAL_WRITE`, Note **left assigned to the agent**, run stops (exit 1). Joey finishes it by hand. Until he does, every later run stops at the start (the stale-Note stop, D6), so one systematic bug can't leave a half-booked Note every hour | Duplicate check blocks a second task anyway |
| `STOP` file written by the agent after an accuracy breach | `ALERT ACCURACY_BREACH`, exit 3. Joey unloads the Mac Mini's launchd job and sets `enabled = false`; restart needs the CEO (approved safeguard) | Joey is told by the GitHub alert issue |
| Email/Teams alerts | `ALERT` lines; the Mac Mini's run script opens a GitHub issue labelled `po-agent-alert` (GitHub emails Joey) | — |
| Circuit breaker (3 failures) | Stricter: the first unexpected screen or failed write stops the run | — |
| Single-run lock, start-of-run sweep | No lock: by rule, **one agent at a time** (no laptop test-site run while the Mac Mini job is loaded). Instead of the sweep, the stale-Note stop (D6): a Pending Note still assigned to the agent stops the run before any Note is taken | Runs take minutes and are hourly; launchd never starts the job while it's still running; don't start a manual run near :07 |
| Daily log files and 90-day retention | Full detail only in local runs with `--detailed-log` (`logs/`, git-ignored; the Mac Mini never passes it). The Mac Mini appends the short run output to `~/Library/Logs/po-agent/runs.log` | MVP runs only touch the test site |
| Live profile, live URL, sender check (C6), go-live flag | Not built (the live title rule exists only inside the decision engine, for offline tests) | — |
| Duplicate check by PO number | Any non-Cancelled Compaction Test task on the project → `DUPLICATE_TASK` | Only costs coverage on projects with an older compaction task; v1 reads PO numbers from the task detail screen |
| Note Pool paging | Page 1 of the filtered list only (50 rows by default); an `INFO` line when there are more pages | The test site's Agent Pool holds a handful of Notes |

## Tech Stack

As `docs/specs/tech-stack.md`: Python 3.12 (uv, locked), Playwright for Python with Chromium (headless on the Mac Mini, headed on the laptop), pdfplumber (text layer only), Anthropic Python SDK (structured output, no tools), pydantic v2, pytest, ruff, `zoneinfo`, `tomllib`, `keyring`.

**Host for the MVP:** the office Mac Mini (CEO decision 3). A standard macOS user `poagent` runs `scripts/macmini-run.sh` from a launchd LaunchAgent at 7 minutes past each hour, 07:07–17:07 Monday–Friday, clock on Australia/Perth. FileVault on; no Claude Code for that user. Exact steps: `docs/macmini-setup.md`.

**Secrets:** one function reads `PO_AGENT_<NAME>` from the environment first (CI and tests), else keyring service `po-agent` (laptop: Windows Credential Manager; Mac Mini: `poagent`'s login Keychain).

| Secret | Env var | keyring name |
|---|---|---|
| MySys test username | `PO_AGENT_MYSYS_TEST_USERNAME` | `mysys_test_username` |
| MySys test password | `PO_AGENT_MYSYS_TEST_PASSWORD` | `mysys_test_password` |
| Anthropic key for the reader | `PO_AGENT_ANTHROPIC_API_KEY` | `anthropic_api_key` |

The reader's key is passed to the SDK client explicitly and is never called `ANTHROPIC_API_KEY`.

## Commands

```text
Install:             uv sync --locked
Browser (laptop):    uv run playwright install chromium
Check (= CI):        uv run scripts/check.py        healthy: last line "check: all passed", exit 0
Decision seam, real Claude: uv run pytest tests/seam1 -m live_claude    healthy: "false PROCEED: 0"
Run seam, test site: uv run pytest tests/seam2 -m testsite
Spike (read-only):   uv run po-agent spike --site test       login, filter Agent Pool + Locked, list eligible Notes
Screen mapping (M0): playwright-cli open --headed "<test-site URL>"   Claude opens it; YOU log in and click; Claude runs snapshot / screenshot
Real-PO seam (laptop): uv run pytest tests/seam1 -m real_data   uses private/fixtures; skipped when absent; never in CI
Decide only:         uv run po-agent run --site test --decide-only
Real run:            uv run po-agent run --site test
Supervised demo:     uv run po-agent demo --site test --headed [--until-check]   one PO, Enter before every write (decisions, 27 Oct 2026)
Link probe:          uv run po-agent demo --site test --probe-link   opens Choose Project, searches, snapshots, selects nothing (decisions, 28 Oct 2026)
Laptop extras:       --headed (watch the browser), --slow-mo 500, --detailed-log (JSON lines in logs/)
Mac Mini (poagent):  scripts/macmini-run.sh run|spike|decide-only   pull main, sync, run, log, alert
Mac Mini run now:    launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent
```

`scripts/check.py` runs, in order, stopping on the first failure: `ruff format --check .` → `ruff check .` → `python scripts/guard_check.py` → repo data check (nothing tracked in a folder named `private/`, `logs/`, `state/`, `.state/`, `traces/`, `secrets/`, `.env/` or `.playwright-cli/`, at any depth; no `.env` or `.env.*` file and no `config/live*.toml`, at any depth; no `.pdf` outside `tests/seam1/fixtures/pdfs/`; no image (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`); no trace or capture file (`*trace*.zip`, `*.har`, `*.webm`); folder names and extensions in any case) → `pytest tests -m "not live_claude and not testsite and not real_data"`.

**Screen mapping with Playwright CLI** (`@playwright/cli`, M0 and whenever a screen changes; laptop, test site only). Joey opens a headed browser and does every click and every typed value himself, including the login. Claude Code only **observes**: `playwright-cli snapshot` (the accessibility tree, with the role and name of every element, which is what the guard's lookups use), `screenshot`, `find` and `generate-locator`. Claude never runs a command that acts on the page (click, fill, type, press, hover, check, select, upload, drag, drop, eval, run-code, dialog, goto, reload), saves state or cookies, or lists network requests; `.claude/settings.json` denies them and, from M1, the `guard_bash.py` hook allows only the observe commands. `.playwright/cli.config.json` keeps the browser profile in memory, blocks the live origin and writes output to `private/captures/test/`; `.playwright-cli/` (snapshot files) is git-ignored. Fallback if Node.js can't be installed: the classic recorder that ships with Playwright for Python (`playwright codegen`), plus screenshots.

**Exit codes:** 0 run finished (bookings and skips are normal) · 1 run stopped (unexpected screen, failed write, partial write, guard refusal) · 2 config, secrets or login problem · 3 accuracy breach.

## Project Structure

```text
SPEC.md                         active spec (this file)
CLAUDE.md                       rules for every Claude Code session
tasks/plan.md, tasks/todo.md    written by /agent-skills:plan
pyproject.toml, uv.lock         [project.scripts] po-agent = "po_agent.cli:main"
src/po_agent/
  cli.py                        argument parsing; maps errors to exit codes
  core/                         reusable for the next MySys automations
    config.py                   load + validate config/<site>.toml; refuse non-test URLs
    secrets.py                  PO_AGENT_* env var, else keyring
    output.py                   the ONLY module that prints (stdout contract below)
    runlog.py                   detailed JSON-lines log to logs/ (only with --detailed-log)
    run.py                      Note loop, RUN_SUMMARY
    controls.py                 kill switch, Perth window, run cap, before_write, assignee check, stale-Note stop
    errors.py                   typed errors and their exit codes
  mysys/                        reusable
    guard.py                    action guard: vet() resolves and allows or refuses; act() is the ONLY code that clicks, types, ticks or uploads
    driver.py                   login, navigation, reads; writes only through guard.py
  b1/                           rules for this automation
    models.py                   Reading, Decision, SkipReason (pydantic)
    reader_rules.py             deterministic reader (pdfplumber + patterns)
    reader_claude.py            Claude reader (no tools)
    address.py                  normaliser + verify-not-extract
    decision.py                 decision engine = seam 1; no browser code
    booker.py                   W1–W5 with read-back
config/test.toml                test-site profile; no secrets
scripts/check.py                the one check command
scripts/guard_check.py          fails if browser action calls appear outside mysys/guard.py
scripts/macmini-run.sh          Mac Mini wrapper: pull main, uv sync, run, append to runs.log, alert issue
scripts/au.com.prompteng.po-agent.plist   launchd job (Mon–Fri 07:07–17:07)
tests/seam1/                    decision seam; fixtures/ = generated fake PDFs + case files (never a real or trial PDF)
tests/seam2/                    run seam on the test site (marker testsite)
private/                        GIT-IGNORED, laptop only: real data
  pdfs/                         real B1 PO PDFs, including the 3 trial POs
  fixtures/cases.toml           expected results for real POs and the 3 trial POs, entered by Joey from MySys
  captures/                     Playwright CLI snapshots and screenshots (test), live screenshots
docs/                           intent, decisions, workflow, Mac Mini setup, screen map, v1 spec pack
.claude/settings.json, hooks/   permissions (now, incl. the Playwright CLI deny list) and hooks (added in M1; protect_paths writes outside the repo only to ~/.claude/plans/, the project memory folder and <temp>/claude/)
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
reader_mode = "hybrid"            # hybrid | deterministic-only
enabled = true                    # kill switch: false on main → next run exits before login
claude_model_id = "<exact model ID, pinned in M2>"
duplicate_ignores_cancelled = true   # test only: Joey resets the test site by cancelling tasks; never true on live
max_notes_per_run = 10           # MVP values; v1 defaults are 25 Notes / 12 minutes
max_run_minutes = 12
run_window = { days = "Mon-Fri", start = "07:00", end = "18:00", tz = "Australia/Perth" }
aud_per_usd = 1.433
claude_price_usd_per_mtok = { input = 0.0, output = 0.0 }   # filled from the pricing page in M2
```

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
- Typed errors (`UnexpectedScreen`, `WriteNotStarted`, `PartialWrite`, `AccuracyBreach`, `GuardRefusal`, `LoginFailed`, `ConfigError`) in `core/errors.py`, mapped to exit codes in `cli.py`. Their messages come from fixed templates plus identifiers only, never page text or a Playwright message (which can quote an address).

**Run output (stdout) contract.** The Mac Mini's run log and alert issues are built from this, so it is short and holds no PDF text, addresses, Note bodies or Claude readings:

```text
INFO  <progress message, no PO data>
NOTE  {"note_id": "...", "outcome": "booked|skipped|untouched|partial", "reason": "ADDRESS_MISMATCH",
       "field": "street", "po_number": "2609034B/048", "pln": "pln_66938", "task_id": "...",
       "tokens_in": 0, "tokens_out": 0, "cost_aud": 0.0}
ALERT <PARTIAL_WRITE|ACCURACY_BREACH|GUARD_REFUSAL|UNEXPECTED_SCREEN|LOGIN_FAILED|CONFIG> {"note_id": "...", "step": "W3", "detail": "<no PO data>"}
RUN_SUMMARY {"run_id": "...", "site": "test", "mode": "run|decide-only|spike", "seen": 0, "eligible": 0,
       "booked": 0, "skipped": 0, "partial": 0, "duration_s": 0, "tokens_in": 0, "tokens_out": 0,
       "cost_aud": 0.0, "exit_code": 0}
```

- `outcome` values beyond a skip reason: a decide-only Note that would have been booked is `"outcome": "skipped", "reason": "DECIDE_ONLY"`; a Note a person took mid-run is `"outcome": "untouched", "reason": "NOTE_TAKEN"`. These are run-output values only, not skip reasons in the decision engine.
- `run_id` = UTC start time plus 4 random hex characters (e.g. `20261016T013507Z-3fa2`), made before the config is loaded, so even an exit-2 `RUN_SUMMARY` has one. `RUN_SUMMARY` is always the last line, even after a crash.
- **Nothing goes to stderr.** An unexpected exception becomes `ALERT UNEXPECTED_SCREEN` with a fixed detail; its traceback goes to `logs/` only with `--detailed-log`, else nowhere, because Playwright's error text can quote page content.

Never print or log a secret, the environment, cookies or browser storage state. PDF and Note text are untrusted data.

## MySys screen rules

What the driver and booker do on each screen, built from `docs/screen-map.md` v1.2 (row numbers below). Where a screen isn't mapped yet, the rule names slice **M0b.2**; code that depends on it waits for M0b.2.

**Windows and locators**
- Every locator is scoped to its floating window, found by its heading: `Note <note id> - …` (a pln appears in it after linking), the project heading starting `<pln> `, `Create New Task`, `Hold Task: <task no>`. Minimised windows stay in the page, so an unscoped locator can match a hidden copy.
- Inside a window, an element is found by accessible role and **exact** name (a substring "Hold" would also match "Un-Hold"), or, for a field the screen map marks **weak** (open item 8), by its visible label in that window (`field_by_label` in `mysys/driver.py`), or by the row-26 anchor in the screen map: the Note Pool filters by their fixed `name` attribute (`filter_allocation_pool_id`, `filter_lock_status`, `filter_status`, `filter_user_id`, ...), the Note window's lists as "the select in this window that contains the option `--Select User--`" / "`--Select Pool--`", the Note Pool panel as the one holding **New Note** and **Search/filter**, the Projects panel as the one holding the label **Search**, **Reset Filter** and the option **All Projects**. Never generated ids (`#project_list_<digits>`, `p_<digits>`, `…_s_po_1_6`) or position-only locators (`nth`, `:nth-child`). Zero or more than one match → guard refusal. `guard.act()` acts on the element `guard.vet()` resolved, never a second lookup, so a hidden copy is never the one acted on.
- The agent never clicks a window's Close, Maximize or Minimize, or a taskbar entry. **Between Notes the driver reloads `base_url`** (a navigation, not a click) so no window is left open; if the reload shows the login page, it logs in again. A half-filled form is still abandoned by closing the browser context.
- **Moving between windows** (rows 25, 27, 28): an open Note window stays on top when the Projects tab opens and covers the results, so the agent never goes from the Note window to the Projects panel directly. After the Note-window steps (assign, step 2a, attachment count, download) it **reloads `base_url`** (every window closes, nothing in MySys changes), clicks **Project** (after a reload the tab bar is hidden until then) → **Projects**, searches and opens the project. To get back to the Note it reloads again and reopens it from the Note Pool ("Finding a Note again"). A reopened Note window is a fresh one: Send Email Notification is ticked again and the user list pre-selects the agent. Opening a project that is already open gives the same single window (row 28), but the agent always reloads first anyway.
- A banner "Your internet connection appears to be disconnected ..." may show the whole time (M0b.1); the agent ignores it and relies on its read-backs.
- No key presses: after Assign, focus lands on **Unlink** (row 04).

**Guard additions** (on top of `docs/specs/spec.md` §5)
- **Denylist:** any element whose accessible name or own text contains `close` (case-insensitive). This blocks the PO Documents table's "close" cell (removes the PDF), the Task Client "close" (clears the client), and every window Close. The denylist is checked against the acted-on element itself, not the text of the window around it.
- **Denylist on a `<select>`** (D5): the select's own name plus the label of the option being chosen, never every option's text. So the Note Pool's Discard status option is refused, and a user elsewhere in the list whose name contains a denylisted word doesn't block Assign.
- **Allowlist:** log in (username, password, "Log in") and the module navigation (Project top tab, Note Pool, Projects sub-tab); select user / pool in the Note window's lists (including the `--Select User--` placeholder); search the Note Pool by Note ID and press its **Refresh** button (row 27); search for and open a task's detail screen (read-only, mapped in M0b.2). Demo only (decisions, 27 Oct 2026): `leave_project_menu` (click the inert header text "Welcome Agent" to close the Project hover menu) and `run_project_search` (click the Projects panel's "Search" label). And `link_run_search` (click the Choose Project window's heading so its search runs; 28 Oct 2026).
- **Refusal tests on the real site** (D3) call `guard.vet()` only, which has no action code, so nothing can be pressed; `guard.act()` refusing is tested offline on local HTML.

**Note Pool (row 01)**
- Filters: Assigned Pool = `pool_name`, Locked/Unlocked = **Locked** (the captures show the trial Notes listed under Locked). Every other filter stays at its default; Status stays **Pending** and is never set. Each filter is read back, and Search/filter must read empty (a Note ID left there would hide every Note).
- **How the list reloads** (row 27): changing a filter select reloads the list by itself. Search/filter does **not** search on `fill` alone: the search runs when focus leaves the box. So a search is: `fill` → click the panel's **Refresh** → wait up to 15 s for the footer "Page 1 of 1(N Items)" (or "No record could be found.") → read. If the number of table rows differs from N (Refresh plus the focus change can add the same rows twice), click Refresh once more and read again; still different → `UNEXPECTED_SCREEN`. After any filter change the driver waits for the footer the same way before reading.
- **What persists** (row 27): a page reload keeps every filter and the Search/filter text; a fresh login resets them all to their defaults with Search/filter empty. Every run logs in fresh, so the list read at run start sees the defaults; within a run, the driver always sets and reads back the filters it needs instead of trusting what a reload kept.
- Eligible (step 0, list only): the Subject/Note cell matches the title rule, the Project cell reads `---` **and** the Assignee cell reads `pool_name` (so a person's Note is never taken, even if the pool filter didn't apply). Everything else is left untouched (outcome `untouched`).
- The list is read **once per run**; the run works through that fixed list, so a Note it skips and returns isn't taken again in the same run.
- **Stale-Note stop** (D6): in `run` and `run --decide-only`, after login and before the list is read, the Note Pool is read with Assigned User = `agent_user_name`, Assigned Pool = All Pools, Locked/Unlocked = All. Any Pending Note assigned to the agent was left by an earlier run's partial write or failed return: `ALERT UNEXPECTED_SCREEN` (fixed detail, with its `note_id`), no Note taken, exit 1.
- **Finding a Note again** (after a reload or closing a browser context, to return a Note to the pool, for the assignee check, for W5's read-back): Assigned Pool = All Pools and Search/filter = the Note ID, searched as above (fill → Refresh), and the row whose ID cell **equals** the Note ID (the search is treated as a substring filter: 123 also matches 1234). Under Assigned Pool = Agent Pool, a Note assigned to the agent is hidden (row 04).
- Order: oldest first by Note ID, up to `max_notes_per_run`, from page 1 only (deferred table). The Note ID is the row's ID cell, never the download link's `user_note_id` (row 05).
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
- A fresh read, not the open Note window's text (whether that refreshes is row 23, mapped in M0b.2 before 3.6; the check never relies on it): reload `base_url`, then "Finding a Note again" (above); the row whose ID cell equals the Note ID must have Assignee `agent_user_name`. Zero such rows or more than one → `UNEXPECTED_SCREEN`. Then the booker reopens the window it needs, as in "Moving between windows" (before W1 nothing is filled yet; before W4 it needs the Note window anyway).
- Only before W1 and W4, because each check leaves the window the booker is in: W1 → W2 → W3 stay in the project window, so a filled Create New Task form never makes the trip. `before_write` still re-reads `enabled` before every step.
- Someone else at the W1 check → close the browser context and stop work on that Note without any write or reassign (`"outcome": "untouched", "reason": "NOTE_TAKEN"`). Someone else at the W4 check → `PARTIAL_WRITE`.

**Project search (rows 06, 16)**
- Projects sub-tab, the Projects panel's Search field (anchored on the Projects panel, row 26; the page header has a hidden second "Search..."). Whether `fill` alone runs this search wasn't mapped (row 27); task 3.2 checks it on the test site first. If it doesn't, the driver clicks the panel's **Search** label (plain text, which moves focus) and that click joins the allowlist; if that doesn't run it either, 3.2 stops and Joey decides (the guard bans key presses). Wait up to 15 s until the list shows "No record found." or rows that each contain the internal number; otherwise `UNEXPECTED_SCREEN`.
- **Match rule:** a row matches when Company is **B1 Homes** and Client Ref No. (trimmed, case-insensitive) equals `<internal no>` (test site, row 06) or `<internal no>/048` (live, Joey 16 Oct 2026). Rows with any other value (another suffix, another number) are ignored. Exactly one match → its pln; none → `PROJECT_NOT_FOUND`; more than one, or a second results page → `PROJECT_AMBIGUOUS`. Stage 3B confirms on live that Client Ref No. is the column that ends `/048`.
- Open the match by its `pln_…` link. The project window's **Client Internal No.** must satisfy the same rule, else `UNEXPECTED_SCREEN`.

**Project address (rows 06–07), for §4**
- Source: the project window's **Address:** (the same string as the search row). Shape: `Lot <lot> [(#<house no>)] <street> <suburb> [<postcode>] [<state>]`, e.g. `Lot 123 (#45) Sample Lane Sampleville 6000 WA`.
- Parse after the §4 normalisation: drop a trailing state and postcode, drop the `(#…)` group, take the token after `Lot` as the lot (letters allowed, e.g. `12A`; compared as case-folded strings). The rest is the street-and-suburb text *R*. No leading `Lot` → `ADDRESS_UNVERIFIABLE`.
- Verify: lot equal, and normalised `<Claude street> <Claude suburb>` equals *R*, so the agent never has to guess where the street ends. Each of Claude's three values must also appear in the PDF's **Job Address** block (the "Job Address:" field and the line under it).
- Must pass (fake values): PDF "Job Address: Lot 123 / Sample Lane Sampleville WA" vs project "Lot 123 (#45) Sample Lane Sampleville 6000 WA".

**Duplicate check (row 07), step 10**
- Read every task header "(tsk_…) | Compaction Test" on the project's Tasks tab. On test, one whose Status cell reads **Cancelled** (it has **Undo Cancellation**) is ignored; any other → `DUPLICATE_TASK`. Record the set of Compaction Test task numbers for W2.

**W1 Create New Task (rows 08–09)**
- **Creator**: the one Creator field, in the Client section (label "Creator"; it defaults to the project's creator) → **Perth Scheduling**. Tick **- Compaction Test** (exact name; unique). **PO Number** (label-anchored) = the PO number; the fill replaces any prefill. Upload the PDF to **PO Documents** (as in the walkthrough), never the separate **Documents** upload. **Note** (label-anchored textarea) = the email body.
- Everything else stays at its default. Read back before Submit: Creator Perth Scheduling; **- Compaction Test** is the only ticked checkbox in the window (bundles, other services and Multiple Units unticked); Task Client "Same as Project"; Task Name empty; PO Number; PO Documents shows exactly one row, the PDF's file name; Documents shows none; Note = email body; Sale Office "Prompt Engineering Pty Ltd"; PO Contact and Delivery Office "Choose...". Any mismatch → close the browser context, `WRITE_NOT_STARTED`.

**W2 after Submit (row 10)**
- Wait up to 15 s for the Create New Task window to close. The new task is the **one** Compaction Test task number not in the set recorded at step 10 (after a reset, older Cancelled tasks are still there). Its details row: Lodged By `agent_user_name`, Task Creator Perth Scheduling, Status New Project or Inspection Analysis (row 07: it can move on by itself). No new task, more than one, or the form still open after 15 s → `PARTIAL_WRITE`.
- PO number, document and Note aren't in the project table: the agent opens the task detail screen (M0b.2) and reads them back. A wrong value → `ACCURACY_BREACH`; a screen not as mapped → `PARTIAL_WRITE`.

**W3 Hold (rows 11–12)**
- **Hold** in the new task's header row only. In the window with heading `Hold Task: <new task no>`, type **ON HOLD UNTIL CALL UP** in Note. Before confirming, read every check: the heading names the new task; every Related Tasks checkbox and Select-all unticked; Reset turn around time unticked; "Send me a reminder email every … days" **ticked with 0** and "… at this date" unticked; Note text exact. Anything else → close the browser context, `PARTIAL_WRITE`. Confirm with that window's own **Hold** (two Hold buttons are on the page).
- Read back: the new task's row shows **Un-Hold** and a Status starting "On-hold" containing "ON HOLD UNTIL CALL UP".

**W4 Link to Project (row 13)**: Link to Project → search the pln → select it (the search and select screens are mapped in M0b.2). Read back: the Note's project button reads the pln; Status still Pending.

**W5 Solved (row 14)**: Status buttons → **Solved**. Read back as `docs/specs/spec.md` §6 W5, plus Solved disabled.

**Reruns** (Objective, seam 2, S5): "changes nothing" means no task created or changed, no Note linked or Solved, and every Note's final assignee as before. With no state between runs, a skipped Note still in the pool is assigned to the agent and back on every run, which only adds two "User Assigned" log lines. That's expected.

## Testing Strategy

- **pytest at the two seams** in `docs/specs/spec.md` → Testing Decisions; behaviour, not private functions (normaliser unit tests allowed as a development aid).
- **Seam 1 (offline):** every case in the spec's seam-1 table, including the live-title rows, on the **3 fake fixture POs** (generated in M2 from a fake B1-style template; the generator's dependency needs Joey's OK) and their mutations. Stubbed Claude in CI; real Claude with `-m live_claude`, run 3 times. **Zero false PROCEED in hybrid and deterministic-only modes.** Extra cases from the screen map:
  - a project with a **Cancelled** Compaction Test task → PROCEED with the test config, `DUPLICATE_TASK` with `duplicate_ignores_cancelled = false`
  - a project with a non-Cancelled Compaction Test task for a **different** PO number → `DUPLICATE_TASK` (MVP strict rule)
  - search rows with other suffixes plus one `/048` row → PROCEED on that pln; two matching rows → `PROJECT_AMBIGUOUS`; a matching row with Company not B1 Homes → `PROJECT_NOT_FOUND`
  - project address with a `(#n)` house number, postcode and state, and a lot with a letter (`12A`) → PROCEED; the same with a different lot letter → `ADDRESS_MISMATCH`
  - a Note already linked → `NOTE_ALREADY_LINKED`; a Note with no attachment / two attachments → `NO_PDF` / `MULTIPLE_PDFS`
  - a test Note with a live-style title whose PO ≠ the file name's → `PO_MISMATCH`
- **Seam 1, real POs (`-m real_data`, laptop only, real Claude):** the **3 most recent** real B1 `/048` Notes and the **3 trial POs** with their test-site lookups for the MVP (Joey, 16 Oct 2026); **10–20** (mostly `/048`, plus a few other suffixes and any odd ones) before go-live. For each, `private/fixtures/cases.toml` holds the Note title and body, the PDF file name, the MySys lookup Joey copied by hand and the expected result (PROCEED with values, or SKIP with reason). The lookup is **what MySys shows**, so the parsing is tested too: every Projects search row (pln, Client Ref No., Company), the project's Address string as shown, and the existing Compaction Test tasks with their status. Hand-split lot/street/suburb fields are kept only as the expected values. The test reports agreement per field, coverage (PROCEED ÷ clean POs) and cost per PO, and fails on any false PROCEED. Skipped automatically when `private/` is absent (CI, Mac Mini).
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
- New dependency (including the fake-PO generator's in M2); a change to the model ID, the Claude prompt or the address rules (then rerun live-Claude seam 1).
- A change to any test, fixture or expected result (its own commit).
- Changes to `.github/workflows/`, `config/test.toml`, `docs/macmini-setup.md`, `scripts/macmini-run.sh` or the launchd plist.
- Anything that would tie `src/` to the Mac Mini or macOS.

**Never**
- Touch the live site (`prompt.mysys.com.au`) or build a live profile.
- Call click, fill, check, set_input_files, evaluate or dispatch_event outside `mysys/guard.py`. Never target Discard, Unlink, Cancel, Undo Cancellation, Un-Hold, Change Project, Unassign, Remove, Delete, anything named "close" (the attached PDF's remove cell, Task Client's clear, window Close), the Note's Pending button or any Hold-dialog checkbox. Abandon a dialog by closing the browser context.
- Give the Claude reader tools, or let Claude's output choose what to click.
- Run a Playwright CLI command that acts on the page, saves state or cookies, or lists network requests; or point Playwright CLI at anything but the test site.
- Send, reply to, forward or delete email; touch Outlook.
- Put a secret anywhere but keyring (the laptop's Credential Manager, `poagent`'s Keychain on the Mac Mini) or a `PO_AGENT_*` environment variable.
- Commit anything from `private/`, or copy real client data into a committed file, a PR, an issue, run output or the Mac Mini (exceptions: the trial POs' identifiers, assumption 2, and the Mac Mini reading the trial POs from the test site, with each PDF on disk only from its download until it's read, Trial conditions).
- Push to `main`, force-push or merge. Joey merges.

## Trial conditions

*Replaces the Trial waiver (v1.5) for the cloud routine. On the Mac Mini, ADR-002 gates H2 and H5 pass, so nothing is waived (CEO decision 3, 15 Oct 2026).* The trial runs on these conditions:

- The Mac Mini's agent user `poagent` is a **standard** (non-admin) account used only by the agent; Joey and a backup admin have the admin accounts. FileVault is on.
- The MySys credentials are the **test-site** agent account's. The Anthropic key is dedicated, named `po-agent-trial`, with a low monthly spend limit. Both, and the Mac Mini's GitHub token (this repo only: contents read, issues write), live only in `poagent`'s Keychain.
- No Claude Code or other AI tool is installed for `poagent`; nothing on the Mac Mini runs a Claude session apart from the reader's API calls.
- Run output follows the stdout contract (no PO content beyond PO number and pln).
- No real client data is copied to the Mac Mini during the MVP. The one exception is the **3 trial POs, which are real** (Joey, 16 Oct 2026): runs read their PDFs and Notes from the test site, keep them in memory and send them to Claude, as on live. The browser writes every download to disk, so a trial PDF is on the Mac Mini's disk only from its download until it's read into memory, a moment later; leftovers are removed at the next run start (D2, 16 Oct 2026). Nothing else from them is written to the Mac Mini's disk apart from the run output (PO number and pln). **The CEO must confirm decision 2, on these terms, before the first Mac Mini run that downloads a trial PO** (M3). Other real data stays on the laptop (see below).
- At the end of the trial, Joey unloads the job, revokes the key, has the test password changed and deletes the test items from the Keychain. Live credentials go onto the Mac Mini only after the CEO's go-live sign-off.

## Real client data

Joey decided on 14 Oct 2026 that the agent may read real client data (CEO to confirm; it settles CEO decision 2 once confirmed). The agent's own MySys account exists on live.

| Allowed | Where it lives | Not allowed |
|---|---|---|
| The Claude reader reads real PO PDFs and Note text (Anthropic API, commercial terms) | In memory during a run; the PDF is on disk only from its download until it's read (D2) | Anything except the PDF and Note text going to Claude |
| Claude Code on the laptop reads real PDFs, live screenshots and captures to understand the pages and write the screen map | `private/` (git-ignored) | Committing them; putting them in GitHub, an issue, a PR or on the Mac Mini |
| Joey views live screens with the agent's account by hand: the PO Allocation Pool, real Notes, real PDFs | Screenshots and saved PDFs in `private/` | Any change on live during capture (no Assign, no edits, no bookings) |
| Real POs as seam-1 test cases, including the 3 trial POs | `private/pdfs/`, `private/fixtures/cases.toml` | Real POs in CI or on the Mac Mini |
| The 3 trial POs (real) as the test site's trial Notes, booked by the agent | MySys test site; in memory during runs (laptop and Mac Mini); their internal numbers, PO numbers and test plns in docs and run output | Their PDFs, addresses or client names in a committed file, an issue, a PR or run output; their PDFs on the Mac Mini's disk beyond the moment of download (D2) |

- **Bookings still happen only on the test site.** The MVP's code never logs into live; go-live needs the CEO's sign-off after the trial (decision 1).
- **Turn off model training first:** Joey is on a **Pro** plan, so before Claude Code reads any real data, the model-training setting in claude.ai privacy settings must be off. (The reader's API key is under commercial terms and isn't used for training by default.)
- `.gitignore` excludes `private/`; a commit hook and CI check also block any staged path under `private/` and any PDF outside `tests/seam1/fixtures/pdfs/`.

## Expected slices (input for `/agent-skills:plan`)

**Milestone A first (decisions, 25 Oct 2026):** a decide-only demo to the CEO on the Mac Mini: 1.4, 1.6, 1.7, M0b.1, 1.8, 1.9, 1.10; M2 (2.1–2.6); M3's 3.1, 3.2, 3.3, 3.5, then 3.4. 3.6 (assignee check, stale-Note stop) follows the demo and is merged before any booking code. Then M0b.2, M4, M5, M6.

| Slice | Delivers | Needs |
|---|---|---|
| **M0** (by hand, Claude observing) | Test site, with Playwright CLI (Joey clicks, Claude snapshots): the full SOP for 2609017B, and the read-only screens (Note, PDF, project search, project page) for 2609034B and 2610002B; then reset. Checks C1, C3, Send Email Notification screens, MFA/password expiry, how a cancelled task shows. Live, view-only by hand: pool and Note screenshots, the 3 most recent real PO PDFs and their project data into `private/`. Claude writes `docs/screen-map.md` (redacted) | — |
| **M0b** (by hand, Claude observing; test site) | **M0b.1 done (25 Oct 2026):** moving between the Note and project windows, an anchor for every unlabelled control on the login page, Note Pool, Projects panel and Note window, the Note Pool after a filter change, search, reload or login, reopening an open project (rows 25–28); `fill` alone doesn't run the Note Pool search; one Assign returns a Note (15b). Rows 21–22 (0 or 2 attachments) dropped: the attachment rule stands without them. **M0b.2** (before M4; row 23 before 3.6): a Compaction Test task's **detail screen** (PO number, documents, Note) and how to open it from the project; **Link to Project**'s search and select screens; whether PO Number is prefilled; whether the upload is saved before Submit (rows 19, 20, 24); whether an open Note window refreshes its Assignee (row 23). Claude updates `docs/screen-map.md` and [MySys screen rules](#mysys-screen-rules) | M0 |
| **M1** Walking skeleton + Mac Mini spike | uv project, config, secrets, output, guard + `guard_check.py`, check command, hooks (incl. the `private/` block and the Playwright CLI allowlist), CI; `po-agent spike`; `scripts/macmini-run.sh` and the launchd plist; Mac Mini set up (`docs/macmini-setup.md`, starting with a test-site login by hand from it); spike passes **on the Mac Mini as `poagent`**, then the job is unloaded until the first bookings (D1) | M0 (MFA answer); M0b.1 before the spike |
| **M2** Decision seam | `reader_mode` switch (hybrid + deterministic-only), both title rules, both readers, address verify (with the project-address parse), project match rule, agreement, skip reasons; the 3 **fake** fixture POs generated and their mutations; stubbed in CI; live-Claude ×3; **real-PO run** (`-m real_data`, incl. the 3 trial POs); model pinned | M1 |
| **M3** Decide-only + run controls | `run --decide-only`: assign → download → decide → back to pool; NOTE lines; on the laptop, then on the Mac Mini (`scripts/macmini-run.sh decide-only`). Before any booking code (D1): `enabled` kill switch, Perth window, run cap, `before_write`, assignee check, stale-Note stop. Plain `run` refuses until M4 | M2, C3, M0b.1; **CEO decision 2 confirmed** before the Mac Mini run |
| **M4** First booking | Booker W1–W5 with read-back; 2609017B booked from a manual run on the Mac Mini (`launchctl kickstart`); then 2609034B and 2610002B the same way; then the test site reset | M3, C1, M0b (task detail, Link to Project) |
| **M5** MVP safety | `ALERT`s and exit codes end to end, stop on first failure, guard-refusal and other seam-2 cases (the run controls moved to M3, D1) | M4 |
| **M6** MVP demo | Test site reset; `/ship` go/no-go; launchd job loaded on the Mac Mini; the 3 trial POs, then a fresh copy of 2609034B as the skip case; reset and repeat (3 demos in a row, S8); cost per PO; one-page demo note for the CEO | M5 |

## Success Criteria

- **S1 Mac Mini spike:** after a test-site login by hand from the Mac Mini succeeds, `scripts/macmini-run.sh spike` run as `poagent` logs into the test site with the Keychain credentials and lists the eligible Notes, read-only, and `runs.log` shows `RUN_SUMMARY` with `exit_code: 0`.
- **S2 CI:** `uv run scripts/check.py` is green on `main`, including `guard_check.py`.
- **S3 Decision seam:** the 3 fake fixture POs (CI) and the 3 trial POs (laptop, `-m real_data`, test-site lookups) PROCEED in hybrid mode with the right pln, PO number and email body (the Note body, [MySys screen rules](#mysys-screen-rules)); **0 false PROCEED** across the MVP fixture set in stubbed mode, in 3 live-Claude runs, and in deterministic-only mode. On the real-PO set (laptop): **0 false PROCEED**, with per-field agreement, coverage and cost per PO reported. With only 3 real POs, coverage is reported but not judged against 80%: any skip of a clean real PO is reviewed before M3. The 80% line applies to the 10–20 POs collected before go-live.
- **S4 Trial run (scheduled launchd run on the Mac Mini, no human help):** with the test site reset and exactly one Pending Note for each trial PO (2609017B, 2609034B, 2610002B) in the Agent Pool:
  - pln_66935, pln_66938 and pln_66940 each have exactly one non-Cancelled Compaction Test task: correct PO number, PDF attached (PO Documents), Creator "Perth Scheduling", Note = email body, On Hold with "ON HOLD UNTIL CALL UP"; Send Email Notification read back unticked before every Note-window write; each Note linked to its pln and Solved
  - any non-`/048` Note already in the pool was not assigned or opened.
- **S5 Rerun and skip:** Joey places a fresh copy of the 2609034B Note in the Agent Pool. The next Mac Mini run (scheduled or `launchctl kickstart`) skips it as `DUPLICATE_TASK`, returns it to the Agent Pool with no new task (its NOTE line shows the reason), and changes nothing else (Reruns, in [MySys screen rules](#mysys-screen-rules)).
- **S6 Controls:** `enabled = false` on `main` → the next Mac Mini run (which pulls `main` first) exits before login; outside 07:00–18:00 Perth on weekdays → no MySys contact (and the launchd job only fires 07:07–17:07 Monday–Friday); `launchctl bootout` → no further runs; a denylisted action → refused before any page interaction.
- **S7 Evidence:** NOTE lines carry tokens and AUD cost per PO; `RUN_SUMMARY` totals them; the trial run has no `ALERT` lines and no guard refusals.
- **S8 Repeatable demo:** after a reset by Joey (`docs/demo-runbook.md`: cancel the 3 tasks with his own account, place fresh copies of the 3 Notes), S4 and S5 pass again, **at least 3 times in a row**, with no code or config change between demos. Each demo can be shown from the laptop (`--headed --slow-mo 500`) or the Mac Mini (`launchctl kickstart`, then `runs.log`).

## Open Questions

1. ~~C1 and C3~~ **Answered on the test site (16 Oct 2026, `docs/decisions.md`):** no Hold-dialog related-task checkbox was pre-ticked (C1), and a Note goes back to the Agent Pool through Assign (C3). Neither blocks M3 or M4. The agent still reads every Hold-dialog checkbox before confirming.
2. **Does MySys accept a login from the Mac Mini?** It connects from the office internet address. A login by hand in Safari on the Mac Mini answers it first (`docs/macmini-setup.md` section 2), then S1. If blocked or challenged: stop, record it in `docs/decisions.md` and tell the CEO.
3. **MFA or password expiry** on the test agent account? Unattended runs need neither. **Partly answered (16 Oct 2026):** no MFA step seen at login; password expiry still to confirm with the MySys admin.
4. ~~**CEO/IT OK** for a private GitHub repo; **CEO to confirm** decision 2.~~ **Answered (25 Oct 2026):** the repo is public so the CEO can read it (no real client data in it); decision 2 was delegated to Joey, who decided yes on the Trial conditions terms, and the CEO approved D2.
5. ~~Your Claude plan~~ **Answered:** Pro. The model-training setting must be off before real data is read. (Mac Mini runs don't use the plan; only the reader's API key is billed.)
6. **Reader model:** pin an exact Sonnet-class model ID in M2; try a Haiku-class model only after it passes seam 1.
7. ~~Playwright download hosts for the routine's allowlist~~ **No longer needed:** the Mac Mini has no network allowlist (CEO decision 3).
8. **Opening a live Note:** does viewing a Note or downloading its PDF change anything (lock it, mark it read, log an action against the agent)? **Answered on the test site (16 Oct 2026, check 3.5):** neither adds a log line or changes the assignee or status; lock state isn't visible. Stage 3B may open live Notes and download PDFs (no other button).
9. ~~Resetting the test site~~ **Answered:** Joey's own account can **cancel** a task on the test site. Reset = Joey cancels the trial POs' Compaction Test tasks and places fresh copies of the 3 Notes; the test profile's duplicate check ignores Cancelled tasks. The agent itself still never presses Cancel. Seen in M0 (16 Oct 2026, check 3.6): a cancelled task shows Status **Cancelled** with an **Undo Cancellation** button, and an **On Hold** task offers **Cancel** directly, so the reset doesn't need to release it first.
10. **Live Projects search** (Joey, 16 Oct 2026): 3–4 projects per internal number, and only one ends with `/048`. SPEC assumes the column is **Client Ref No.** (on test it holds the bare internal number). Confirm in Stage 3B with a view-only live search.
11. **PO Documents or Documents?** The SOP says "Documents → upload"; the walkthrough used PO Documents, so SPEC uses PO Documents. Confirm with the PO admin before M4.
12. **What makes a Note "Locked"?** The trial Notes show under the Locked filter, but lock state isn't visible on the Note. If a fresh Note ever doesn't show under Locked, the agent won't see it (safe, but it would cost coverage).
