# Spec: PO Agent MVP (test site, run by an Anthropic cloud routine)

**Status:** **Approved by Joey, 15 Oct 2026** · v1.5 (1.5: the demo must be repeatable at least 3 times, S8 and `docs/demo-runbook.md`; 1.4: approved; the test site is reset by Joey cancelling tasks with his own account, and the test profile's duplicate check ignores cancelled tasks; Pro plan; 1.3: screens mapped with Playwright CLI while Joey clicks; `po-agent capture` dropped; all 3 trial POs named at every stage; 1.2: the 3 trial POs only, test-site reset, skip shown with a duplicate copy; 1.1: real client data allowed, kept on Joey's laptop)
**Active spec.** Build this first. The full v1 design stays in `docs/specs/spec.md` and is built after the MVP has proved the agent works (roadmap phase 2).
**Built from:** `docs/intent.md`, `docs/decisions.md` (wins if anything disagrees), `docs/specs/spec.md` v1.2, `docs/specs/ADR-001-po-agent-architecture.md` (Accepted), `docs/specs/ADR-002-po-agent-hosting.md` (trial amendment, 14 Oct 2026).

## Assumptions

1. **Every booking is on the test site.** The MVP's code has no live profile and refuses any URL that isn't `test-prompt.mysys.com.au`.
2. **The agent may read real client data** (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real PO PDFs and view-only captures of live screens are used to understand the pages and to test the readers. They stay on Joey's laptop in the git-ignored `private/` folder, never in GitHub or the cloud routine. See [Real client data](#real-client-data).
3. **The trial runs as an Anthropic cloud routine running the script** (ADR-002 Option C). Gates H2 and H5 are waived for the trial only, on the conditions in [Trial waiver](#trial-waiver). Joey decided this on 14 Oct 2026.
4. **ADR-001 is unchanged.** The script does every click; the Claude reader only reads; the routine's own Claude session runs fixed commands and reports.
5. **No state between routine runs.** MySys is the state: a resolved Note is done, the duplicate check stops double bookings, and a skipped Note is simply checked again next run. Each run's transcript is its log.
6. **Production hosting isn't decided** (CEO decision 3); Joey expects a Sydney cloud VM. So the code is host-agnostic: secrets from env vars or keyring, and nothing routine-specific in `src/`.
7. **CEO decision 1 stands.** Decision 2 is Joey's call pending the CEO's confirmation; decision 3 is pending. Neither blocks the MVP.
8. **Built on Joey's Windows laptop** in VS Code with Claude Code; Python 3.12 via uv; private GitHub repo (routines only clone from GitHub); Addy Osmani's agent-skills.

→ Correct any of these before `/plan`.

## Objective

Prove, early and cheaply, that the hybrid PO Agent does the admin's job on the MySys test site with no human help, unattended, from the cloud.

The MVP proves that:

- the cloud routine can reach the test site, log in and drive it with headless Chromium (the biggest unknown, so first)
- the two readers agree on the 3 fake POs **and on a set of real B1 POs**, and never approve a bad one
- the script books each fake PO exactly as the SOP says and reads every write back
- a PO it shouldn't book goes back to the Agent Pool, and a non-`/048` Note is left untouched
- a second run changes nothing
- Claude's cost per PO is measured.

**Users:** Joey (builds and runs the trial); the CEO (reads the one-page MVP demo note). The PO admin isn't affected.

**The 3 trial POs, everywhere:**

| Client internal no. | Project | M0 walkthrough | Seam 1 | M4 first bookings | Seam 2 and S4 trial |
|---|---|---|---|---|---|
| 2609017B | pln_66935 | Full SOP by hand, then reset | Fixture + mutations | Booked first | Booked |
| 2609034B | pln_66938 | Read-only screens | Fixture + mutations | Booked | Booked; its fresh copy is the S5 skip case |
| 2610002B | pln_66940 | Read-only screens | Fixture + mutations | Booked | Booked |

### In the MVP

| `docs/specs/spec.md` section | MVP |
|---|---|
| §2 processing order | Steps 0, 2–4 and 6–12. The decision engine knows **both title rules** (test: title contains `<internal no>_048[_n].pdf`; live: `[B1 Homes] Order <internal no>/048`) so real live Notes can be tested offline; only the test profile exists. Step 1 (skip list) is v1; step 5 (live sender check) is v1 |
| §3 reading schema and skip reasons | All, except live-only checks |
| §4 address check (verify, not extract) | All |
| §2 step 10 duplicate check | As specified, except that the **test profile ignores Compaction Test tasks whose status is Cancelled** (`duplicate_ignores_cancelled = true`), because Joey resets the test site by cancelling tasks. Any other status, and every status on live, still counts as a duplicate |
| §5 action guard + build check | All. It's cheap and it's the main safety control |
| §6 booker W1–W5 with read-back | All |
| §7 Claude reader | All: no tools, structured output validated again by pydantic, temperature 0, pinned model ID, 60 s timeout, one retry |
| §8 run controls | `enabled` kill switch, Perth window, run cap, fresh login, assignee check before each write, **stop the run on the first unexpected screen or failed write** |
| Skip → back to pool | Through **Assign** with the pool as assignee (depends on C3) |
| `reader_mode = deterministic-only` | Yes: every PO skips `ADDRESS_UNVERIFIABLE` (approved C4 behaviour); a few lines of code |
| `--decide-only` | Runs every check, returns each Note to the pool, books nothing. Used before the first booking |

### Deferred to v1 (after the MVP demo)

| Deferred | MVP behaviour instead | Why it's acceptable on the test site |
|---|---|---|
| Skip list and 24 h retry of `PROJECT_NOT_FOUND` | Nothing persisted. A skipped Note is checked again every run | Same answer each time; costs one Claude call per skipped Note per run |
| Partial-write auto-resume | `ALERT PARTIAL_WRITE`, Note **left assigned to the agent** (so later runs ignore it), run stops (exit 1). Joey finishes it by hand | Duplicate check blocks a second task anyway |
| `STOP` file written by the agent after an accuracy breach | `ALERT ACCURACY_BREACH`, exit 3. Joey turns the routine off and sets `enabled = false`; restart needs the CEO (approved safeguard) | Joey is told by the GitHub alert issue |
| Email/Teams alerts | `ALERT` lines; the routine opens a GitHub issue labelled `po-agent-alert` (GitHub emails Joey) | — |
| Circuit breaker (3 failures) | Stricter: the first unexpected screen or failed write stops the run | — |
| Single-run lock, start-of-run sweep | None | Runs take minutes and are hourly; don't press **Run now** during a scheduled run |
| Daily log files and 90-day retention | Full detail only in local runs (`logs/`, git-ignored). Routine runs keep the short run output in the transcript | Routine runs only touch the test site |
| Live profile, live URL, sender check (C6), go-live flag | Not built (the live title rule exists only inside the decision engine, for offline tests) | — |

## Tech Stack

As `docs/specs/tech-stack.md`: Python 3.12 (uv, locked), Playwright for Python with Chromium (headless on the routine, headed on the laptop), pdfplumber (text layer only), Anthropic Python SDK (structured output, no tools), pydantic v2, pytest, ruff, `zoneinfo`, `tomllib`, `keyring`.

**Host for the MVP:** a Claude Code cloud routine (research preview) on Joey's account, in a dedicated cloud environment (Ubuntu 24.04, Custom network access, setup script installs Chromium). Exact steps: `docs/routine-setup.md`.

**Secrets:** one function reads `PO_AGENT_<NAME>` from the environment first (routine; later the VM), else keyring service `po-agent` (laptop).

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
Laptop extras:       --headed (watch the browser), --slow-mo 500
```

`scripts/check.py` runs, in order, stopping on the first failure: `ruff format --check .` → `ruff check .` → `python scripts/guard_check.py` → repo data check (nothing under `private/` tracked; no PDF outside `tests/seam1/fixtures/pdfs/`) → `pytest tests -m "not live_claude and not testsite and not real_data"`.

**Screen mapping with Playwright CLI** (`@playwright/cli`, M0 and whenever a screen changes; laptop, test site only). Joey opens a headed browser and does every click and every typed value himself, including the login. Claude Code only **observes**: `playwright-cli snapshot` (the accessibility tree, with the role and name of every element, which is what the guard's lookups use), `screenshot`, `find` and `generate-locator`. Claude never runs a command that acts on the page (click, fill, type, press, hover, check, select, upload, drag, drop, eval, run-code, dialog, goto, reload), saves state or cookies, or lists network requests; `.claude/settings.json` denies them and, from M1, the `guard_bash.py` hook allows only the observe commands. `.playwright/cli.config.json` keeps the browser profile in memory, blocks the live origin and writes output to `private/captures/test/`; `.playwright-cli/` (snapshot files) is git-ignored. Fallback if Node.js can't be installed: the classic recorder that ships with Playwright for Python (`playwright codegen`), plus screenshots.

**Exit codes:** 0 run finished (bookings and skips are normal) · 1 run stopped (unexpected screen, failed write, partial write, guard refusal) · 2 config, secrets or login problem · 3 accuracy breach.

## Project Structure

```text
SPEC.md                         active spec (this file)
CLAUDE.md                       rules for every Claude Code session
tasks/plan.md, tasks/todo.md    written by /plan
pyproject.toml, uv.lock         [project.scripts] po-agent = "po_agent.cli:main"
src/po_agent/
  cli.py                        argument parsing; maps errors to exit codes
  core/                         reusable for the next MySys automations
    config.py                   load + validate config/<site>.toml; refuse non-test URLs
    secrets.py                  PO_AGENT_* env var, else keyring
    output.py                   the ONLY module that prints (stdout contract below)
    runlog.py                   detailed JSON-lines log to logs/ (local runs)
    run.py                      kill switch, Perth window, run cap, Note loop, RUN_SUMMARY
  mysys/                        reusable
    guard.py                    action guard: the ONLY module that clicks, types, ticks or uploads
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
tests/seam1/                    decision seam; fixtures/ = fake PDFs + case files
tests/seam2/                    run seam on the test site (marker testsite)
private/                        GIT-IGNORED, laptop only: real data
  pdfs/                         real B1 PO PDFs
  fixtures/cases.toml           expected results for real POs, entered by Joey from MySys
  captures/                     Playwright CLI snapshots and screenshots (test), live screenshots
docs/                           intent, decisions, workflow, routine setup, screen map, v1 spec pack
.claude/settings.json, hooks/   permissions (now, incl. the Playwright CLI deny list) and hooks (added in M1)
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

Python 3.12, ruff format and ruff check, type hints throughout, pydantic models at every boundary, small pure functions in `b1/`. Every MySys write is a **named guarded action** on one element found by accessible role and name, then read back:

```python
# src/po_agent/b1/booker.py
def set_po_number(guard: ActionGuard, form: Locator, po_number: str) -> None:
    field = form.get_by_role("textbox", name="PO Number")
    guard.fill("set_po_number", field, po_number)        # refuses if not allowlisted or denylisted
    if field.input_value() != po_number:
        raise WriteNotStarted("PO Number did not read back as expected")
```

- Names: `snake_case` functions, `PascalCase` models and errors, skip reasons exactly as in `docs/specs/spec.md` §3.
- Typed errors (`UnexpectedScreen`, `WriteNotStarted`, `PartialWrite`, `AccuracyBreach`, `GuardRefusal`, `LoginFailed`) mapped to exit codes in `cli.py`.

**Run output (stdout) contract.** The routine's Claude session reads this, so it is short and holds no PDF text, addresses, Note bodies or Claude readings:

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

Never print or log a secret, the environment, cookies or browser storage state. PDF and Note text are untrusted data.

## Testing Strategy

- **pytest at the two seams** in `docs/specs/spec.md` → Testing Decisions; behaviour, not private functions (normaliser unit tests allowed as a development aid).
- **Seam 1 (offline):** every case in the spec's seam-1 table, including the live-title rows. Stubbed Claude in CI; real Claude with `-m live_claude`, run 3 times. **Zero false PROCEED in hybrid and deterministic-only modes.** Two extra cases: a project with a **Cancelled** Compaction Test task for the same PO → PROCEED with the test config, `DUPLICATE_TASK` with `duplicate_ignores_cancelled = false`.
- **Seam 1, real POs (`-m real_data`, laptop only, real Claude):** 10–20 recent real B1 Notes (mostly `/048`, plus a few other suffixes and any odd ones you remember). For each, `private/fixtures/cases.toml` holds the Note title and body, the PDF file name, the MySys lookup Joey copied by hand (pln, project lot/street/suburb, existing Compaction Test PO numbers) and the expected result (PROCEED with values, or SKIP with reason). The test reports agreement per field, coverage (PROCEED ÷ clean POs) and cost per PO, and fails on any false PROCEED. Skipped automatically when `private/` is absent (CI, routine).
- **Seam 2 (`-m testsite`, from the laptop; reset the test site first):** the 3 trial POs booked; a fresh copy of a booked trial Note → skipped `DUPLICATE_TASK` and returned to the Agent Pool (the skip case, using only trial POs); any non-`/048` Note in the pool untouched; immediate rerun changes nothing; `enabled = false` → exits before login; outside the window → no MySys contact; a denylisted action (Discard, a Hold-dialog checkbox) refused before any page interaction; a person taking the Note mid-run → agent stops on that Note without writing. Address and other mutations are covered offline in seam 1.
- **Test first** on every task: failing test, shown failing for the right reason, stop for Joey, then code.
- CI (`.github/workflows/check.yml`) runs the check command and gitleaks on every push and PR, with no secrets.

## Boundaries

**Always**
- Show `uv run scripts/check.py` output before calling a task done.
- Finish every check before opening Create New Task; read back every write.
- Return a skipped Note through **Assign**, never Unassign. Untick Send Email Notification wherever it appears and read it back.
- Keep real client data (PDFs, live screenshots, captures, addresses) in `private/` only. Anything committed (fixtures, `docs/screen-map.md`, test-site screenshots) is fake or redacted and holds no credentials.

**Ask Joey first**
- New dependency; a change to the model ID, the Claude prompt or the address rules (then rerun live-Claude seam 1).
- A change to any test, fixture or expected result (its own commit).
- Changes to `.github/workflows/`, `config/test.toml` or `docs/routine-setup.md`.
- Anything that would tie `src/` to the cloud routine.

**Never**
- Touch the live site (`prompt.mysys.com.au`) or build a live profile.
- Call click, fill, check, set_input_files, evaluate or dispatch_event outside `mysys/guard.py`. Never target Discard, Unlink, Cancel, Unassign, Remove, Delete, remove-document or any Hold-dialog checkbox. Abandon a dialog by closing the browser context.
- Give the Claude reader tools, or let Claude's output choose what to click.
- Run a Playwright CLI command that acts on the page, saves state or cookies, or lists network requests; or point Playwright CLI at anything but the test site.
- Send, reply to, forward or delete email; touch Outlook.
- Put a secret anywhere but the routine's environment variables or keyring.
- Commit anything from `private/`, or copy real client data into a committed file, a PR, an issue, run output or the cloud routine.
- Push to `main`, force-push or merge. Joey merges.

## Trial waiver

ADR-002 gates H2 (secrets unreadable by an AI session) and H5 (company-owned host) are waived **for the test-site trial only**, on these conditions:

- The cloud environment `po-agent-trial` is Joey's own (Pro plan, so it isn't shared with anyone), and holds only the `PO_AGENT_*` variables, the two timeouts and `PLAYWRIGHT_BROWSERS_PATH`.
- The MySys credentials are the **test-site** agent account's. The Anthropic key is dedicated, named `po-agent-trial`, with a low monthly spend limit.
- The routine has no connectors and a fixed prompt (`docs/routine-setup.md`); the hooks block `printenv`, `env` and any command mentioning `PO_AGENT_`.
- Run output follows the stdout contract (no PO content beyond PO number and pln).
- At the end of the trial, Joey revokes the key, has the test password changed, and archives the environment.
- **Never** live credentials, real client data or production on this pattern unless ADR-002 is re-scored. Real data stays on the laptop (see below).

## Real client data

Joey decided on 14 Oct 2026 that the agent may read real client data (CEO to confirm; it settles CEO decision 2 once confirmed). The agent's own MySys account exists on live.

| Allowed | Where it lives | Not allowed |
|---|---|---|
| The Claude reader reads real PO PDFs and Note text (Anthropic API, commercial terms) | Only in memory during a run | Anything except the PDF and Note text going to Claude |
| Claude Code on the laptop reads real PDFs, live screenshots and captures to understand the pages and write the screen map | `private/` (git-ignored) | Committing them; putting them in GitHub, an issue, a PR or the cloud routine |
| Joey views live screens with the agent's account by hand: the PO Allocation Pool, real Notes, real PDFs | Screenshots and saved PDFs in `private/` | Any change on live during capture (no Assign, no edits, no bookings) |
| Real POs as seam-1 test cases | `private/pdfs/`, `private/fixtures/cases.toml` | Real POs in CI or in the routine |

- **Bookings still happen only on the test site.** The MVP's code never logs into live; go-live needs the CEO's sign-off after the trial (decision 1).
- **Turn off model training first:** Joey is on a **Pro** plan, so before Claude Code reads any real data, the model-training setting in claude.ai privacy settings must be off. (The reader's API key is under commercial terms and isn't used for training by default.)
- `.gitignore` excludes `private/`; a commit hook and CI check also block any staged path under `private/` and any PDF outside `tests/seam1/fixtures/pdfs/`.

## Expected slices (input for `/plan`)

| Slice | Delivers | Needs |
|---|---|---|
| **M0** (by hand, Claude observing) | Test site, with Playwright CLI (Joey clicks, Claude snapshots): the full SOP for 2609017B, and the read-only screens (Note, PDF, project search, project page) for 2609034B and 2610002B; then reset. Checks C1, C3, Send Email Notification screens, MFA/password expiry, how a cancelled task shows. Live, view-only by hand: pool and Note screenshots, 10–20 real PO PDFs and their project data into `private/`. Claude writes `docs/screen-map.md` (redacted) | — |
| **M1** Walking skeleton + cloud spike | uv project, config, secrets, output, guard + `guard_check.py`, check command, hooks (incl. the `private/` block and the Playwright CLI allowlist), CI; `po-agent spike`; routine environment and routine created; spike passes **from the routine** | M0 (MFA answer) |
| **M2** Decision seam | `reader_mode` switch (hybrid + deterministic-only), both title rules, both readers, address verify, agreement, skip reasons, fixtures; stubbed in CI; live-Claude ×3; **real-PO run** (`-m real_data`); model pinned | M1 |
| **M3** Decide-only | `run --decide-only`: assign → download → decide → back to pool; NOTE lines; from the routine | M2, C3 |
| **M4** First booking | Booker W1–W5 with read-back; 2609017B booked from **Run now**; then 2609034B and 2610002B the same way; then the test site reset | M3, C1 |
| **M5** MVP safety | `enabled` kill switch, Perth window, run cap (10 Notes, 12 minutes), assignee check, stop on first failure, `ALERT`s and exit codes, guard-refusal and other seam-2 cases | M4 |
| **M6** MVP demo | Test site reset; `/ship` go/no-go; schedule on; the 3 trial POs, then a fresh copy of 2609034B as the skip case; reset and repeat (3 demos in a row, S8); cost per PO; one-page demo note for the CEO | M5 |

## Success Criteria

- **S1 Cloud spike:** a routine **Run now** logs into the test site and lists the eligible Notes, read-only, and prints `RUN_SUMMARY` with `exit_code: 0`.
- **S2 CI:** `uv run scripts/check.py` is green on `main`, including `guard_check.py`.
- **S3 Decision seam:** the 3 trial POs PROCEED in hybrid mode with the right pln, PO number and email body; **0 false PROCEED** across the MVP fixture set in stubbed mode, in 3 live-Claude runs, and in deterministic-only mode. On the real-PO set (laptop): **0 false PROCEED**, with per-field agreement, coverage and cost per PO reported. If coverage of clean real POs is under 80%, the skip reasons are reviewed before M3.
- **S4 Trial run (scheduled routine run, no human help):** with the test site reset and the 3 trial Notes (2609017B, 2609034B, 2610002B) in the Agent Pool:
  - pln_66935, pln_66938 and pln_66940 each have exactly one Compaction Test task: correct PO number, PDF attached, Creator "Perth Scheduling", Note = email body, On Hold with "ON HOLD UNTIL CALL UP", no notification sent; each Note linked to its pln and resolved
  - any non-`/048` Note already in the pool was not assigned or opened.
- **S5 Rerun and skip:** Joey places a fresh copy of the 2609034B Note in the Agent Pool. The next run skips it as `DUPLICATE_TASK`, returns it to the Agent Pool with no new task (its NOTE line shows the reason), and changes nothing else.
- **S6 Controls:** `enabled = false` on `main` → next run exits before login; outside 07:00–18:00 Perth on weekdays → no MySys contact; a denylisted action → refused before any page interaction.
- **S7 Evidence:** NOTE lines carry tokens and AUD cost per PO; `RUN_SUMMARY` totals them; the trial run has no `ALERT` lines and no guard refusals.
- **S8 Repeatable demo:** after a reset by Joey (`docs/demo-runbook.md`: cancel the 3 tasks with his own account, place fresh copies of the 3 Notes), S4 and S5 pass again, **at least 3 times in a row**, with no code or config change between demos. Each demo can be shown from the laptop (`--headed --slow-mo 500`) or the routine (**Run now**).

## Open Questions

1. **C1 and C3** (by hand in M0): are Hold-dialog related-task checkboxes ever pre-ticked? Can a Note go back to the Agent Pool through Assign? C3 blocks M3; C1 blocks M4.
2. **Can the routine reach MySys?** Outbound traffic leaves from Anthropic's addresses through a proxy. S1 answers it. If blocked: run the MVP demo from the laptop, record it, and go straight to the Sydney VM for the trial.
3. **MFA or password expiry** on the test agent account? Unattended runs need neither.
4. **CEO/IT OK** for a private GitHub repo (no real client data) and the cloud-routine trial. **CEO to confirm** that Claude may read real client data (decision 2).
5. ~~Your Claude plan~~ **Answered:** Pro. Environments aren't shared; routine runs draw on Pro usage (about 11 short runs a weekday once scheduled); the model-training setting must be off before real data is read.
6. **Reader model:** pin an exact Sonnet-class model ID in M2; try a Haiku-class model only after it passes seam 1.
7. **Playwright download hosts** for the allowlist (`cdn.playwright.dev`, `playwright.download.prss.microsoft.com` expected); confirm from the setup log in M1.
8. **Opening a live Note:** does viewing a Note or downloading its PDF change anything (lock it, mark it read, log an action against the agent)? Check on the test site first; if it does, capture live from the pool list and saved PDFs only.
9. ~~Resetting the test site~~ **Answered:** Joey's own account can **cancel** a task on the test site. Reset = Joey cancels the trial POs' Compaction Test tasks and places fresh copies of the 3 Notes; the test profile's duplicate check ignores Cancelled tasks. The agent itself still never presses Cancel. Still to see in M0: how a cancelled task looks on the project page (row 07), so the duplicate check can read its status. Also check in M0 whether an **On Hold** task can be cancelled directly, or must be released from hold first (this decides the reset steps).
