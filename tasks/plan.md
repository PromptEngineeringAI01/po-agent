# Implementation Plan: PO Agent MVP (slices M0b, M1–M6)

**Status:** **Approved by Joey, 16 Oct 2026** (Open questions 2–8 answered as recommended); frozen when the freeze commit merges · written by `/agent-skills:plan`; revised the same day after a doubt-driven review (decisions D1–D5 below), then given a small fix pass after a second review (D6, D7, and the guard, dependency and safety fixes)
**Planned from:** `SPEC.md` **v1.10**, `docs/screen-map.md` v1.1, `docs/specs/spec.md` v1.6, `docs/decisions.md` (16 Oct 2026), `docs/workflow.md` v5.9, `docs/macmini-setup.md` v1.1, `CLAUDE.md`.
**Git state:** those versions are on `main` (PRs #1–#5 merged; `origin/main` at `73d468d`, the same commit as `plan-mvp`). The local `main` is stale at `58cde2b`: fast-forward it (`git switch main && git merge --ff-only origin/main`) before branching. A stale local branch `m1-walking-skeleton` already exists at `58cde2b`; Joey deletes it or resets it to `origin/main` before M1 starts, or Stage 5's `git switch -c m1-walking-skeleton` fails.
**Freeze point:** when Joey approves this file (`docs/workflow.md` Stage 4.4). After that, a behaviour change needs a dated `docs/decisions.md` entry plus `SPEC.md` and this file, in the same commit.

## Overview

Build the MVP PO Agent so that it books the 3 trial POs (2609017B → pln_66935, 2609034B → pln_66938, 2610002B → pln_66940) on the MySys test site, unattended, from a launchd job on the office Mac Mini. Every check runs before any write. Every write goes through the action guard and is read back. Anything uncertain goes back to the Agent Pool. The slices run in order: M0b (screens still to map, by hand) → M1 walking skeleton and Mac Mini spike → M2 decision seam (offline) → M3 decide-only → M4 first booking → M5 safety → M6 demo. M0b is done by hand alongside M1–M2. M0b.1 must be written up before 1.8 (the spike needs its panel anchors and reload behaviour, rows 26–27), and M0b.2 before M4.

## Architecture decisions (from the spec; restated so each task can lean on them)

- **ADR-001 hybrid.** The script does every click. Claude (the reader) has no tools and only returns the reading schema. The decision engine (`b1/decision.py`) has no browser code: it is seam 1.
- **One guard, in two halves (D3).** `src/po_agent/mysys/guard.py` is the only module that may call click, fill, check, select, upload, evaluate or dispatch_event. `guard.vet(action, scope, target, value=None)` finds the element and returns allow (with the one element it resolved) or refuse; it contains **no** page-action call. `value` is the text to type or the option label to choose (D5 checks the label). `guard.act(action, scope, target, value=None)` calls `vet()` first and acts only on allow, on the **same element** `vet()` resolved, never a fresh lookup. (It's `vet`, not `check`, because the build check below bans the name `check`, Playwright's tick action.) `scripts/guard_check.py` (an AST scan, in the check command) fails the build if any action call appears outside `act()`. A guard refusal aborts the run.
- **Scoped locators.** Each floating window is found by its heading. Screens that aren't floating windows (the login page, the Note Pool panel, the Projects panel) are found by the anchor mapped in M0b.1 (row 26). Inside a scope, elements are found by role and name, or by visible label where the screen map marks them weak. Unlabelled controls use the row-26 anchor (e.g. "the select that contains the option `--Select Pool--`"). Generated ids and `nth` are never used. Zero or more than one match is a refusal.
- **No state between runs.** MySys is the state. `logs/` (detailed JSON lines) is written only when the CLI gets `--detailed-log`. The Mac Mini wrapper never passes it, so the Mac Mini writes no `logs/` and keeps only the short stdout in `runs.log`.
- **The PO PDF on disk (D2).** Chromium writes every download to disk, so "in memory only" isn't possible with `expect_download`. The browser is launched with `downloads_path` set to a run-scoped directory under the system temp dir (`po-agent-dl-<run_id>`); in Playwright this is a **launch** option, not a context option, and without it downloads land in Playwright's own `playwright-artifacts-*` temp dir, which the cleanup below would miss. The driver reads the file into memory and deletes it straight after the download. The directory is removed in a `finally` block, and every run removes leftover `po-agent-dl-*` directories before login. W1 uploads from the in-memory bytes (`set_input_files` with a file payload), never from a path. The Mac Mini's disk is FileVault-encrypted.
- **Host-agnostic `src/`.** Nothing in `src/` is tied to macOS. Everything Mac-specific lives in `scripts/macmini-run.sh` and the plist.
- **Typed errors → exit codes** in `cli.py`: 0 finished · 1 stopped (unexpected screen, failed write, partial write, guard refusal) · 2 config, secrets or login · 3 accuracy breach. The errors live in a new `core/errors.py` (not listed in SPEC → Project Structure; see Doc drift).
- **`UNEXPECTED_SCREEN` stops the run.** The decision engine may return `Skip(UNEXPECTED_SCREEN)` (e.g. the project window's Client Internal No. doesn't match), and the driver may raise `UnexpectedScreen`. The run loop treats both the same way: return the Note to the pool through the normal path, then stop the run (exit 1), as SPEC → In the MVP §8 requires.
- **The booker accepts only a `Proceed` decision object** made by the decision engine. This is type-checked, and a test asserts that no module other than `b1/decision.py` constructs `Proceed`, so no code path reaches Create New Task without passing every §2 check. `Proceed` is frozen and names what it's for (`note_id`, internal number, pln), so the booker can refuse to apply it to any other Note or project (4.1). Offline tests get their `Proceed` from `decide()` on fixtures, never by building one.
- **Run controls come before the first write (D1).** The kill switch, Perth window, run cap, assignee check and the stale-Note stop (D6) are built in M3 (3.5, 3.6), before any booking code. Every W step starts with `controls.before_write(note_id, step)`: it re-reads `enabled` every time, and runs the assignee check only before W1 and W4 (D7), so W1 → W2 → W3 never leave the project window. Together with the `Proceed` type, this is what Must never #7 needs.
- **Order before a Note-window write:** `before_write` → untick Send Email Notification → read it back unticked → the one committing click. The assignee check can leave and reopen the Note window, and the box is ticked again every time the window opens (screen map row 02), so unticking before `before_write` isn't enough.

## Decisions from the doubt review (16 Oct 2026, Joey)

Each needs a dated `docs/decisions.md` entry and the SPEC change, in the freeze commit.

| # | Decision | Changes |
|---|---|---|
| D1 | Build the kill switch, Perth window, run cap and assignee check **before** booking. After the S1 spike, unload the Mac Mini job (`launchctl bootout`); it is loaded again only for 4.6 and from M6. Until 4.5, plain `run` refuses (exit 2). | Old 5.1 and 5.2 become 3.5 and 3.6; M5 keeps alerts and the safety cases; SPEC → Expected slices (M3/M5 rows); `docs/macmini-setup.md` §8 |
| D2 | The trial PDF may sit on the Mac Mini's disk only for the moment of the download, as in "The PO PDF on disk" above. CEO decision 2 was asked on "in memory only", so Joey tells the CEO about this change before the CEO confirms it (3.4). | SPEC → Trial conditions and Real client data ("never on the Mac Mini's disk" becomes "deleted straight after download; leftovers removed at the next run start"); CLAUDE.md Must never #6 ("in memory", Joey edits by hand; wording in Doc drift) |
| D3 | Real-page refusal tests (Discard, a Hold-dialog checkbox) call only `guard.vet()`, which has no action code, so nothing can be pressed. `act()` refusing is tested on local HTML. Recorded as not "targeting" under Must never #2. | SPEC → Testing Strategy (seam 2); `docs/specs/spec.md` §5 (vet/act) |
| D4 | The live host may appear only in `guard_bash.py`'s deny regex and its test; `ANTHROPIC_API_KEY` only in the secrets test that proves it's ignored; a fake `sk-ant-` string only in the hook test, allowlisted for gitleaks by path. | CLAUDE.md Must never #3 and Conventions (Joey edits by hand; wording in Doc drift) |
| D5 | For a `<select>`, the denylist checks the select's accessible name plus the label of the option being chosen, never every option's text. | `docs/specs/spec.md` §5; SPEC → Guard additions |
| D6 | **Stale-Note stop.** At the start of every `run` and `run --decide-only`, after login and before taking any Note, the agent looks for a Pending Note still assigned to `agent_user_name`. One is only left there by an earlier run's partial write or failed return. If there is one: `ALERT UNEXPECTED_SCREEN` (fixed detail "a Note is still assigned to the agent from an earlier run", with its `note_id`), take no Note, exit 1. This **reverses** SPEC's "Note left assigned to the agent (so later runs ignore it)": later runs now stop until Joey clears it, so one systematic bug can't leave a half-booked Note every hour. MySys is the state, so nothing is kept between runs. | SPEC → partial-write row ("so later runs ignore it" becomes "later runs stop until Joey clears it") and §8 run controls; `docs/specs/spec.md` §8; `docs/workflow.md` 6.1 (the reset clears Notes left with the agent) |
| D7 | **Assignee check before W1 and W4 only** (Open question 10, option A; Joey, 16 Oct 2026). Before W1 it runs just before Create New Task opens; before W4 once the booker is back on the Note window, and that covers W5 seconds later. W1 → W2 → W3 stay in the project window, so the filled form never makes the round trip through the Note Pool. `before_write` still re-reads `enabled` before every step. Cost: a person taking the Note during W1–W3 is caught at W4 as `PARTIAL_WRITE`. | SPEC → §8 run controls and MySys screen rules ("before each of W1–W5" becomes "before W1 and W4", for the MVP); `docs/specs/spec.md` §8 ("before each write" gets an MVP note) |

## Cross-cutting rules (apply to every task)

- **TDD (CLAUDE.md):** write the failing test, run it and show it fails for the expected reason. Stop for Joey before writing code only on 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2; on the other tasks, commit the test and carry on (decisions, 24 Oct 2026). The test goes in its own `test:` commit, then the code. CLAUDE.md wins over `/agent-skills:build auto`: in M2, auto stops at the failing tests of 2.2–2.5 (Open question 9).
- **Done means:** `uv run scripts/check.py` ends with `check: all passed`, and its output is shown. If a task touches readers, prompt, model or address rules: ask Joey first, then run the live-Claude seam and show `false PROCEED: 0`. The live seam exists only from 2.5, so 2.2–2.4 are done on the stubbed seam, and 2.5's first live run covers them (say so in each PR). If a task touches `mysys/` or the booker: run seam 2 on the test site, or ask Joey to run it (reset first, workflow 6.1).
- **References.** "workflow 6.1" means `docs/workflow.md` section 6.1 (the test-site reset). A bare number such as 4.3 is a task in this plan.
- **No real data in output.** Test-site and real-PO tests must never print an address, client name, PDF text or Note body: not in assertion messages, not in reports, not in run output. Assert on booleans, counts, enum values and the trial identifiers only, because pytest's assertion rewriting prints compared values. Test-site captures count as real data.
- **New dependencies** need Joey's OK (list in Open question 2). **Ask-first files:** `.github/workflows/`, `config/test.toml`, `docs/macmini-setup.md`, `scripts/macmini-run.sh`, the plist. They appear in this plan, but each task still says what changes in them.
- **Seam-2 tests check their precondition and clean up what they can.** A fixture verifies the reset state (e.g. exactly one Pending, unlinked Note per trial PO in the Agent Pool; no non-Cancelled Compaction Test task on the trial plns where the test needs none). If the state is wrong, it fails early with a clear message instead of booking on top of old state. Its first version (1.8) checks only the Note Pool; 3.2 adds the project reads. Every test's teardown returns a Note it left with the agent to the pool through the normal path, in a fresh browser context. Tasks a test created can only be cancelled by Joey, so W-step tests run one at a time with a reset between them.
- **Finding a Note again.** Whenever the agent needs a Note it has already assigned to itself (after closing a browser context, after leaving its window, for the assignee check, for W5's read-back), it uses the Note Pool with Assigned Pool = All Pools and Search/filter = the Note ID, and requires the row's ID cell to **equal** the Note ID (the search is a substring filter: 123 also matches 1234). Under Assigned Pool = Agent Pool the Note is hidden (screen map row 04).
- **One agent at a time.** The laptop and the Mac Mini log in as the same agent account, so the assignee check can't tell their runs apart, and two runs could each pass every check and both Submit. So there are **no laptop test-site runs** (seam-2 tests, `run`, `run --decide-only`, `spike`) while the Mac Mini job is loaded (`launchctl print gui/<uid>/au.com.prompteng.po-agent` finds it), and no manual Mac Mini run while a laptop run is going. This applies at 4.6 and in M6.
- File counts below don't include `uv.lock` or empty `__init__.py` files.

## Dependency graph

```
M0b.1 (rows 21–23, 25–28) + its write-up ───────────────┐   blocks 1.8 and M3
M0b.2 (rows 19, 20, 24) + its write-up ───────────────┐ │   blocks M4
                                                      │ │
M1: 1.1 uv+check ─► 1.2 hooks ─► 1.3 pre-commit+CI ─► 1.5 config/secrets/errors ─► 1.4 guard+guard_check
        ─► 1.6 output+CLI ─► 1.7 eligibility ─► 1.8 spike (needs M0b.1) ─► 1.9 wrapper+plist ─► 1.10 Mac Mini spike (S1), then bootout
                                                                                   │
M2: 2.1 models+fake fixtures ─► 2.2 reader+steps 2a–4 ─► 2.3 project match+duplicate ─► 2.4 address+agreement ─► 2.5 Claude reader+model pin ─► 2.6 prices+real-PO seam (S3)
                                                                                   │
M3 (needs M2, M0b.1): 3.1 take/return Note ─► 3.2 attachments+reads ─► 3.3 decide-only run ─► 3.4 laptop + Mac Mini (CEO decision 2)
                      ─► 3.5 kill switch/window/cap ─► 3.6 assignee check            (D1: controls before any write)
                                                                                   │
M4 (needs M3, M0b.2): 4.1 W1 ─► 4.2 W2 ─► 4.3 W3 ─► 4.4 W4+W5 ─► 4.5 run mode ─► 4.6 first bookings on the Mac Mini
                                                                                   │
M5: 5.1 alerts+exit codes ─► 5.2 seam-2 safety cases
                                                                                   │
M6: 6.1 go/no-go ─► 6.2 demo 1 ─► 6.3 demos 2–3 (S8) ─► 6.4 CEO note
```

1.5 now comes before 1.4 because the guard raises `GuardRefusal` from `core/errors.py`. 3.5 and 3.6 don't need 3.4 (a by-hand run), only 3.3.

Serial, one task per session, no parallel agents (`docs/workflow.md` → Decisions). The only overlap is that M0b is done by hand during M1–M2: M0b.1 early enough to be written up and merged before 1.8, M0b.2 any time before M4.

## Pace (from `docs/workflow.md` → Build pace)

| Slice | Pace |
|---|---|
| M0b | **by hand**: Joey clicks, Claude observes, no code |
| M1 | **step**: `/agent-skills:build`, one task at a time, plan mode first; follow Appendix A; source-driven-development for library calls |
| M2 | **auto**: `/agent-skills:build auto` once M1 is merged. It pauses at each failing test (TDD) and at the ask-first points: generator dependency (2.1), address rules (2.4), Claude prompt and model ID (2.5), prices (2.6) |
| M3 | **step** |
| M4 | **step**, plan mode first; `doubt-driven-development` on the booker design (fresh session) before 4.1 |
| M5 | **step** |
| M6 | **by hand**, with `/agent-skills:ship` |

Tasks inside a code slice that Joey does himself (1.10, 3.4, 4.6) are marked **by hand**. M3 (3.5, 3.6) and M5 are step pace.

---

## Phase M0b: screens still to map (by hand; Stage 3E)

### M0b.1: Note attachments, assignee read and moving between screens (rows 21–23, 25–28), then write-up · by hand

**Description:** Joey clicks and Claude snapshots, as in Stage 3A. Nothing here writes to a task.
- Row 21: a Note with no attachment. Row 22: a Note with two PDFs.
- Row 23: whether an open Note window refreshes its Assignee after someone else reassigns the Note, and the Note Pool search by Note ID (Assigned Pool = All Pools) with a project window open.
- Row 25: one Note's whole path: Note window → Projects sub-tab → project window → back to the same Note window. Which windows stay open and visible after a sub-tab change, and how to get back to the Note window (taskbar entry, or reopen it from the Note Pool by its ID).
- Row 26: an anchor for every control with no name or label, so the agent never needs `nth`: the Note window's user and pool lists, the login page, the Note Pool panel, the Projects panel (the container or heading each sits in).
- Row 27: the Note Pool after a filter change (does the list reload by itself or need Refresh; what shows when it's done), and after a page reload and after a fresh login (do the filters and the Search/filter text persist).
- Row 28: opening a project that's already open in a window: one window or two.
- Also, for rows 23 and 06: whether setting the Note Pool's Search/filter and the Projects Search with `fill` alone (no key press) runs the search. The guard bans `type` and `press`, so if a key is needed, the write-up says so and Joey decides.
- Also, for row 15: returning a Note to the pool from a freshly opened Note window (where the user list pre-selects the agent). Is it one Assign with `--Select User--` + pool, as SPEC says, or two Assigns, as the walkthrough did?

Then Claude writes rows 21–23 and 25–28 into the screen map and SPEC.
**Needs:** M0 (done). **Blocks:** 1.8 (the login page and Note Pool panel anchors from row 26, and the filter reload from row 27) and M3.
**Acceptance:**
- `private/captures/test/` holds a `.yml` and a `.png` for each row, plus notes in `notes.md`.
- `docs/screen-map.md` has rows 21–23 and 25–28 (fake values only); open items 8 (for the Note-window lists and panels) and 10 are closed. `SPEC.md` → MySys screen rules has no "M0b" left for attachments, the assignee check, panels, list anchors or moving between windows, with a dated `docs/decisions.md` entry.
- The row 21–23 Notes are moved out of the Agent Pool afterwards (or Solved by Joey).
- **If the plan is already frozen:** the same commit updates the affected tasks in this file (1.8, 3.1, 3.2, 3.6), as CLAUDE.md requires.

**Verify:** Joey checks the captures exist and reads the diff for real data; Claude used only `open`, `snapshot`, `screenshot`, `find`, `generate-locator` and `close`.
**Files:** `private/captures/test/*` (git-ignored), `docs/screen-map.md`, `SPEC.md`, `docs/decisions.md`, `tasks/plan.md` (only if frozen).

### M0b.2: Task detail, Link to Project, PO Number prefill (rows 19, 20, 24), then write-up · by hand

**Description:** Joey books 2609017B again by hand up to Submit, filling Note with the Note's body (as the agent will), and opens the new task's detail screen (row 19), noting the empty **Documents** upload area before Submit. Before Submit, Claude also snapshots the anchor for each remaining weak locator in open item 8 (Creator, Multiple Units, PO Number, PO Contact, Delivery Office, the Note textarea, both Choose File inputs) and records whether the PO Documents upload is already saved before Submit (e.g. it shows in the project's Documents after the form is abandoned in a second, throwaway attempt; Joey judges whether that attempt is worth it). He finishes Hold, and Claude snapshots the Hold confirm button's anchor inside the `Hold Task: …` window, then maps Link to Project's search and select screens (row 20), and checks whether PO Number is prefilled (row 24). Then he resets (workflow 6.1). Claude then updates the screen map and SPEC from the captures for rows 19, 20 and 24.
**Needs:** M0 (done). **Blocks:** M4.
**Acceptance:**
- `docs/screen-map.md` has rows 19, 20 and 24 (fake values only), and its open items 2, 4 and 5 are closed, and open item 8 is closed in full (every weak locator has a label or container anchor, none needing `nth` or a generated id). Whether the upload is saved before Submit is recorded.
- Row 20 records the element the agent selects in Link to Project's results and its accessible name. If its name or text holds the project address, the denylist's `close` would refuse a project on a "… Close" street: the write-up then names a target without the address (e.g. the `pln_…` cell) or records the problem for Joey.
- `SPEC.md` → MySys screen rules has no "M0b" left (W2 task-detail read-back, W4 search and select, PO prefill, empty Documents area), with a dated `docs/decisions.md` entry.
- **If the plan is already frozen:** the same commit updates the affected tasks in this file (4.1, 4.2, 4.4), as CLAUDE.md requires.

**Verify:** Joey reads the diff for real data (no addresses, names or PDF content; only the trial identifiers) and opens the PR. `uv run scripts/check.py` passes if M1 has landed by then.
**Files:** `docs/screen-map.md`, `SPEC.md`, `docs/decisions.md`, `tasks/plan.md` (only if frozen).

### Checkpoint: M0b
- [ ] Rows 19–28 captured; screen map and SPEC have no M0b items left; both PRs merged.
- [ ] Test site reset (workflow 6.1): the row-19/20 task cancelled, a fresh 2609017B Note placed, the row 21–23 Notes out of the Agent Pool.

---

## Phase M1: walking skeleton + Mac Mini spike (step)

### 1.1 uv project and the check command · step

**Description:** Create the uv project and `scripts/check.py`, so every later task has one command to prove it's green.
**Needs:** none.
**Acceptance:**
- `uv sync --locked` works on Python 3.12 (pinned in `.python-version`, which also avoids the Mac Keychain trap). `[project.scripts] po-agent = "po_agent.cli:main"` is set, and the pytest markers `live_claude`, `testsite` and `real_data` are registered.
- `uv run scripts/check.py` runs `ruff format --check .` → `ruff check .` → repo-data check → `pytest tests -m "not live_claude and not testsite and not real_data"`. It stops on the first failure and prints `check: all passed` on success. Task 1.4 inserts `guard_check.py` before the repo-data check, giving SPEC → Commands' order.
- The repo-data check fails, naming the path, on any tracked path in a folder named `private/`, `logs/`, `state/`, `.state/`, `traces/`, `secrets/`, `.env/` or `.playwright-cli/`, at any depth; any `.env` or `.env.*` file and any `config/live*.toml`, at any depth; any `.pdf` outside `tests/seam1/fixtures/pdfs/`; any image (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`); and any trace or capture file (`*trace*.zip`, `*.har`, `*.webm`). Folder names and extensions match in any case (decisions, 19 Oct 2026, widened 21 and 24 Oct). The test exercises this with a temporary git repo.

**Verify:** `uv run scripts/check.py` → `check: all passed`.
**Files:** `pyproject.toml`, `.python-version`, `src/po_agent/__init__.py`, `scripts/check.py`, `tests/test_check.py`. **Scope:** M.

### 1.2 Claude Code hooks · step

**Description:** Write the three hook scripts from `docs/workflow.md` Appendix A and their tests, then extend `.claude/settings.json` **as the very last edit**: once the hooks are in, Claude can no longer edit `.claude/**`.
**Needs:** 1.1; Joey's CLAUDE.md edit for D4 (Must never #3) merged, because this task is the first to write the live host.
**Acceptance:**
- `protect_paths.py` **blocks** `.claude/**`, `config/live*.toml`, `.env*`, `secrets/**`, `state/**` and paths outside the repo, except `~/.claude/plans/`, this project's memory folder and `<temp>/claude/` (decisions, 24 Oct 2026). Paths are resolved (absolute, `..` collapsed, symlinks followed) before matching and matched by whole folders; tests cover each allowed folder, `~/.claude/settings.json`, `settings.local.json` and `hooks/`, a lookalike folder and a `../` escape. It **asks** for `.github/workflows/**`, `docs/macmini-setup.md`, `scripts/macmini-run.sh` and existing files under `tests/seam1/fixtures/**`.
- `guard_bash.py` blocks every pattern in the Appendix A table: the live-site regex exactly as Appendix A gives it, `(?<!test-)prompt\.mysys\.com\.au`, which skips the test host (it contains the live host as a substring); the tests cover both hosts, and `playwright-cli open` on the test URL is allowed; non-observe `playwright-cli` commands and `open` without the test URL or with `--persistent`/`--profile`; `printenv`, bare `env`, `/proc/*/environ` and `PO_AGENT_`; force-push, pushes to `main` and `gh pr merge`; `rm -rf`; `git add`/`commit` of `private/`, `state/`, `logs/` and `.env*`; the `sk-ant-` key regex. It also blocks `export -p`, `declare -x`, a bare `set`, `os.environ` and PowerShell `env:`, and a bare `git push` while the current branch is `main`. `format_python.py` runs ruff format and ruff check --fix on edited `.py` files.
- The hooks are a backstop, not the main control (they match text, so a determined command can get past them); the guard, the repo-data check and gitleaks are the main controls.
- The live host appears only in the deny regex and its test (D4).
- Tests send tool-call JSON on stdin and assert exit 2 (block), the `ask` JSON, or allow, for each rule. `settings.json` keeps every existing Playwright CLI allow/deny rule and adds the Appendix A permissions and hooks.

**Verify:** `uv run scripts/check.py`; then Joey runs the five guardrail prompts in a fresh session (`docs/workflow.md` → Straight after M1 merges): four are blocked and one asks.
**Files:** `.claude/hooks/protect_paths.py`, `.claude/hooks/guard_bash.py`, `.claude/hooks/format_python.py`, `tests/test_hooks.py`, `.claude/settings.json` (last). **Scope:** M.

### 1.3 Pre-commit and CI · step

**Description:** A pre-commit hook (gitleaks plus the repo-data path rule) and the GitHub Actions check, so CI and every commit enforce the same rules as `scripts/check.py`.
**Needs:** 1.2.
**Acceptance:**
- `.pre-commit-config.yaml` runs gitleaks and a local hook that reuses `scripts/check.py`'s repo-data rule (`--repo-data-only`). A staged `private/` path, a stray `.pdf` or a fake `sk-ant-…` string is rejected. `.gitleaks.toml` allowlists only `tests/test_hooks.py` for the fake key (D4), so the hook test can be committed and CI's gitleaks stays green.
- `.github/workflows/check.yml` follows Appendix A, plus one added step, `uv run playwright install --with-deps chromium`, so the guard tests (1.4) can run a headless browser on local HTML (Open question 5). It has no secrets.
- CI is green on this task's PR.

**Verify:** `uv run pre-commit run --all-files`; the PR's **check** is green on GitHub.
**Files:** `.pre-commit-config.yaml`, `.gitleaks.toml`, `.github/workflows/check.yml` (ask-first), `pyproject.toml` (pre-commit dev dependency), `scripts/check.py`. **Scope:** S–M.

### 1.4 Action guard and `guard_check.py` · step

**Description:** The main safety control: named, allowlisted, scoped actions with a denylist checked on the element itself, split into `vet()` and `act()` (D3), plus the build check that no other code can act on the page.
**Needs:** 1.3, 1.5 (`GuardRefusal` lives in `core/errors.py`).
**Acceptance:**
- `guard.vet(action, scope, target, value=None)` takes an action name, the scope (a window found by its heading, or a panel anchor from M0b.1 row 26; the tests here use local HTML, so 1.4 doesn't wait for M0b.1), a target locator, and the value to type or the option label to choose. It returns allow with the one element it resolved, or a refusal reason, and contains no page-action call. An unknown action name, a scope not found, or a target matching 0 or more than 1 visible element → refuse. `guard.act(action, scope, target, value=None)` calls `vet()`, raises `GuardRefusal` on a refusal **before any page interaction**, and only then acts, on the element `vet()` returned (no second lookup, so a hidden copy in a minimised window can't be the one acted on). Locators by role and name use `exact=True` (a substring "Hold" also matches "Un-Hold"; the screen map's Cancel needed it too). The allowlist is `docs/specs/spec.md` §5 plus the SPEC additions plus the login and navigation actions in Open question 3.
- The denylist is checked on the acted-on element's own accessible name and text, case-insensitive substrings: Discard, Unlink, Cancel (which catches Undo Cancellation), Un-Hold, Change Project, Unassign, Remove, Delete, close. For a `<select>` it checks the select's accessible name plus the **label of the option being chosen** (D5), so the Note Pool's Discard option is refused and a user named "…Close…" elsewhere in the list doesn't block Assign. It also covers the **Pending** button in the Note's Status buttons and **any checkbox inside a `Hold Task` window**. A hit refuses even when an allowlisted action resolved to it. An allowed button in a window that also has a Close control is still allowed.
- Typed values are never logged (the password). The guard keeps each action name and outcome in memory (`guard.history`); 3.1's run log writes it out.
- `scripts/guard_check.py` (AST) scans `src/`, `scripts/` and `tests/` and fails on a **call or attribute reference** to any of these outside `act()` in `mysys/guard.py`, and on `getattr(…, "<name>")` with one of them as a string literal:
  - Page actions: `click`, `dblclick`, `tap`, `fill`, `clear`, `type`, `press`, `press_sequentially`, `check`, `uncheck`, `set_checked`, `select_option`, `select_text`, `set_input_files`, `set_files`, `hover`, `focus`, `drag_to`, `drag_and_drop`, `dispatch_event`.
  - Scripts and dialogs: `evaluate`, `evaluate_handle`, `evaluate_all`, `add_init_script`, `add_script_tag`, `expose_function`, `expose_binding`, `accept`, `dismiss`.
  - Network and navigation: `route`, `route_from_har`, the `request` attribute (`page.request`, `context.request`, `playwright.request`: an APIRequestContext could submit a form past the guard, and banning the attribute covers its `get`, `post`, `delete` and the rest without banning those common names, which would catch `download.delete()` (D2) and `mock.patch`), `goto`, `reload`, `go_back`, `go_forward`.
  - Disk: `storage_state`, `tracing`, `screenshot`, `record_video_dir`, `record_har_path`.
  - `keyboard.*`, `mouse.*` and `touchscreen.*`.
  - Exceptions: `driver.py` may call `goto` and `reload` only on the configured `base_url` (one helper, `driver.go_home()`), and tests may call `page.set_content` and `goto` on local HTML. A name that clashes with non-Playwright code (e.g. `args.type`) is fixed by renaming the code, never by a waiver comment.
  It passes on the repo. `scripts/check.py` runs it as step 3.
- Tests run headless Chromium against local HTML (`page.set_content`), offline: one `act()` refusal per denylist entry, a select with a Discard option and one with a "Close…" option that isn't chosen, the Hold-dialog checkbox, 0 or 2 matches, an unknown action, the allowed case, `vet()` returning refuse without touching the page, and a hidden duplicate of the target that `act()` doesn't touch. `tests/test_guard_check.py` proves the scan fails on `locator.check()`, `page.request.post(...)` and `getattr(x, "click")`, and passes `guard.vet(...)`, `download.delete()` and `mock.patch(...)`.

**Verify:** `uv run scripts/check.py`. Review against Must never #1 and #2.
**Files:** `src/po_agent/mysys/guard.py`, `scripts/guard_check.py`, `scripts/check.py`, `tests/test_guard.py`, `tests/test_guard_check.py`. **Scope:** M.

### 1.5 Config, secrets and typed errors · step

**Description:** Load and validate `config/test.toml`, read secrets env-first then keyring, and define the typed errors with their exit codes.
**Needs:** 1.1.
**Acceptance:**
- `config/test.toml` (SPEC shape; `claude_model_id` and prices left as placeholders until 2.5 and 2.6) loads into a pydantic model that rejects unknown keys. A `base_url` whose host isn't exactly `test-prompt.mysys.com.au`, or a `site` other than `test`, raises a config error. The test uses only the test host plus a made-up host; the live host never appears here (Must never #3; D4 allows it only in `guard_bash.py` and its test).
- `secrets.get(name)` reads `PO_AGENT_<NAME>` first, else keyring service `po-agent`, for `anthropic_api_key`, `mysys_test_username` and `mysys_test_password`. A missing secret raises an error whose message names the secret but holds no value. `ANTHROPIC_API_KEY` is never read: the test sets it and asserts it's ignored, the one place the name appears (D4).
- `core/errors.py` defines `UnexpectedScreen`, `WriteNotStarted`, `PartialWrite`, `AccuracyBreach`, `GuardRefusal` (re-exported for the guard), `LoginFailed` and `ConfigError`, with the exit-code table. Their messages come from fixed templates plus identifiers only (action name, step, `note_id`, trial pln): never an element's text, a page string or a Playwright message, which can hold an address (e.g. a "… Close" street behind a guard refusal).

**Verify:** `uv run scripts/check.py`.
**Files:** `src/po_agent/core/config.py`, `src/po_agent/core/secrets.py`, `src/po_agent/core/errors.py`, `config/test.toml` (ask-first), `tests/test_config_secrets.py`. **Scope:** M.

### 1.6 Output contract and CLI · step

**Description:** `core/output.py` as the only printer of the stdout contract, and the `po-agent` CLI with its exit-code mapping.
**Needs:** 1.4, 1.5.
**Acceptance:**
- `INFO`, `NOTE`, `ALERT` and `RUN_SUMMARY` lines exactly as SPEC → Code style. NOTE, ALERT and RUN_SUMMARY are pydantic models with exactly the contract fields. INFO messages and ALERT `detail` come from fixed templates, so PDF text, addresses or Note bodies can't reach stdout. `RUN_SUMMARY` is always the last line.
- `run_id` = UTC start time plus 4 random hex characters (`20261016T013507Z-3fa2`), made before the config is loaded, so even an exit-2 `RUN_SUMMARY` has one.
- `guard_check.py` also fails on `print(` in `src/` outside `core/output.py`.
- `po-agent spike|run --site test [--decide-only] [--headed] [--slow-mo N] [--detailed-log]`. A config or secret error → `ALERT CONFIG` + `RUN_SUMMARY … "exit_code": 2`, before any browser is launched. A site other than `test` → exit 2. Until 4.5, `run` without `--decide-only` → `ALERT CONFIG` (fixed detail "run mode not built yet"), exit 2, no browser (D1).
- A catch-all in `cli.py` from the start: any exception not mapped to a typed error → `ALERT UNEXPECTED_SCREEN` with a fixed detail, exit 1. Nothing goes to stderr: the traceback goes to `logs/` only with `--detailed-log`, else nowhere, because Playwright's error text can quote page content. 5.1 tests every path end to end.
- At start, before login, the CLI deletes leftover `po-agent-dl-*` download directories (D2).

**Verify:** `uv run scripts/check.py`; `uv run po-agent spike --site test` with no secrets set → exit 2 and the two lines; `uv run po-agent run --site test` → exit 2, "run mode not built yet".
**Files:** `src/po_agent/core/output.py`, `src/po_agent/cli.py`, `scripts/guard_check.py`, `tests/test_output_cli.py`. **Scope:** S–M.

### 1.7 Eligibility (step 0) · step

**Description:** The list-view eligibility rule, the first piece of the decision engine, so the spike can report eligible Notes.
**Needs:** 1.5.
**Acceptance:**
- Test rule: the Subject/Note cell contains `<internal no>_048[_n].pdf`, the Project cell reads `---` **and** the Assignee cell reads `pool_name` (so a person's Note is never taken, even if the pool filter didn't apply). This returns the internal number. Live rule (offline only): title `[B1 Homes] Order <internal no>/048`, Project `---` and Assignee `pool_name`.
- `_023` files, linked Notes and other text → not eligible. Both test title styles (plain body; live-style title plus body) are eligible.
- Pure function, no browser code.

**Verify:** `uv run scripts/check.py`.
**Files:** `src/po_agent/b1/models.py` (`NotePoolRow`), `src/po_agent/b1/decision.py`, `tests/seam1/test_eligibility.py`. **Scope:** S.

### 1.8 Spike: login and Note Pool read · step

**Description:** The first test-site path, end to end: log in, filter the Note Pool, list the eligible Notes and print the summary. Read-only.
**Needs:** 1.6, 1.7, M0b.1 written up and merged (row 26: login page and Note Pool panel anchors; row 27: how the list reloads after a filter change).
**Acceptance:**
- A fresh login through guarded actions (username, password, Log in), with no storage state saved. A failed login → `ALERT LOGIN_FAILED`, exit 2.
- Project tab → Note Pool → Assigned Pool = `pool_name` and Locked/Unlocked = Locked (label-anchored inside the row-26 panel anchor, guarded). Each filter is read back as set, and the driver waits for the list to finish reloading as mapped in row 27; otherwise `UnexpectedScreen`. Status and every other filter stay at their defaults, and are read back as defaults, with Search/filter empty (a Note ID left there by an earlier assignee check would silently hide every Note; row 27 says whether it can persist). Rows are read from page 1 only (ID cell, Assignee, Project, Subject/Note), with an `INFO` line if there are more pages. No Note is opened.
- The list is read **once per run**. The run works through that fixed list of Note IDs, so a Note it skips and returns to the pool is not picked up again in the same run.
- Output: `INFO` lines with counts only, then `RUN_SUMMARY` with `"mode": "spike"`, `seen`, `eligible` and `exit_code` 0.
- `tests/seam2/conftest.py` gives the `testsite` fixtures and the reset-state precondition helper (Note Pool part only; 3.2 adds the project part). In a default run (`-m "not testsite …"`) they're deselected; when `-m testsite` is selected explicitly, a missing secret or a failed precondition is an **error**, not a skip, so "green with nothing run" can't count as Done.
- **Failure output carries no real data (Must never #6).** A `pytest_runtest_makereport` hook in `tests/seam2/conftest.py` replaces the failure report of every `testsite` test with the test name and the exception type only, so Playwright call logs ("resolved to <td>…</td>"), strict-mode and timeout text and `to_have_text` diffs never reach the terminal, the chat or a PR. A test proves it: a failing test whose message holds a fake address prints only the exception type. 2.6 reuses the hook for `real_data`.

**Verify:** `uv run scripts/check.py`; after a reset, `uv run pytest tests/seam2 -m testsite -k spike` and `uv run po-agent spike --site test --headed` → `eligible: 3`.
**Files:** `src/po_agent/mysys/driver.py`, `src/po_agent/core/run.py`, `src/po_agent/cli.py`, `tests/seam2/conftest.py`, `tests/seam2/test_spike.py`. **Scope:** M.

### 1.9 Mac Mini wrapper and launchd plist · step

**Description:** `scripts/macmini-run.sh` and the plist, as `docs/macmini-setup.md` §8 describes, with the fixes below (update §8 in the same PR).
**Needs:** 1.8.
**Acceptance:**
- The wrapper accepts only `run|spike|decide-only` and maps them to `po-agent run`, `po-agent spike` and `po-agent run --decide-only`, each with `--site test` and never `--detailed-log`. It sets its own `PATH`, with an optional `MACMINI_RUN_PATH_PREFIX` first so the tests' stubs win.
- It runs `git pull --ff-only`, `uv sync --locked` and `uv run playwright install chromium`. **If any of these fails, it doesn't run the agent**, because stale code would ignore `enabled = false` on `main`. It writes a fixed line to `runs.log` and opens the alert issue (exit code 2).
- Then it runs the agent with a 20-minute hard limit. macOS has no GNU `timeout`, so the wrapper implements it, starting the agent in **its own process group** and killing the whole group, Python and Chromium included, so no orphan can overlap the next run.
- It appends a timestamp line and the agent's stdout to `~/Library/Logs/po-agent/runs.log`. The agent's stderr goes to `/dev/null` (the CLI writes nothing there by design, and a crash's text could quote page content).
- On any `ALERT` line or a non-zero exit, it runs `gh issue create --label po-agent-alert`, titled `po-agent alert <run_id or "no run_id">`, and the body is only the ALERT lines and the exit code.
- The plist has label `au.com.prompteng.po-agent`, `ProgramArguments` `/Users/poagent/po-agent/scripts/macmini-run.sh run`, and 55 `StartCalendarInterval` entries (Weekday 1–5 × Hour 7–17, Minute 7). It has absolute log paths and no `RunAtLoad` or `KeepAlive`.
- Tests run the wrapper under bash with stub `git`, `uv` and `gh` via `MACMINI_RUN_PATH_PREFIX` (in CI and Git Bash): a clean run writes no issue; an ALERT run calls `gh` with only the ALERT lines; a failed `git pull` runs no agent and opens an issue; `decide-only` calls `po-agent run --decide-only`; a hung run whose stub spawns a child is killed at the limit (shortened for the test) with **no surviving child**. A plist test parses the XML and checks the 55 entries.

**Verify:** `uv run scripts/check.py`; on the Mac Mini (by hand, in 1.10), `plutil -lint` passes.
**Files:** `scripts/macmini-run.sh` (ask-first), `scripts/au.com.prompteng.po-agent.plist` (ask-first), `docs/macmini-setup.md` §8 (ask-first), `tests/test_macmini_wrapper.py`. **Scope:** M.

### 1.10 Mac Mini setup and spike (S1) · by hand

**Description:** Once M1 is merged: Joey stores the laptop secrets, runs the guardrail prompts, runs the context-engineering check on CLAUDE.md, then sets up the Mac Mini (`docs/macmini-setup.md`: "This Mac Mini", §2 hand login first, then §§3–9) and runs the spike as `poagent`.
**Needs:** 1.1–1.9 merged.
**Acceptance:**
- A hand login in Safari on the Mac Mini works with no challenge (§2). If not: stop, add a decisions entry and tell the CEO.
- As `poagent`, `scripts/macmini-run.sh spike` → `runs.log` ends with `RUN_SUMMARY … "exit_code": 0` (S1). No Keychain dialog is left waiting.
- If §8 was followed and the job loaded, it is **unloaded** again afterwards (`launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`), and `launchctl print` shows it isn't loaded (D1). It stays unloaded until 4.6.
- The password-expiry answer from the MySys admin is recorded (SPEC open question 3).

**Verify:** `tail -50 ~/Library/Logs/po-agent/runs.log` on the Mac Mini.
**Files:** none in the repo (a `docs/decisions.md` entry only if something is blocked).

### Checkpoint: M1
- [ ] `uv run scripts/check.py` → `check: all passed`; CI green on `main` (S2).
- [ ] Guardrail prompts behave as expected (four blocked, one asks).
- [ ] Laptop spike lists the 3 trial Notes as eligible; Mac Mini spike S1 passes; the Mac Mini job is unloaded afterwards (D1).
- [ ] `/agent-skills:review` and `security-and-hardening` on the M1 PRs, with Important findings fixed.
- [ ] Joey reviews before M2 starts.

---

## Phase M2: decision seam (auto)

### 2.1 Seam-1 models and the fake fixture POs · auto (pauses for the generator dependency)

**Description:** The seam-1 data shapes, and a generator that makes 3 **fake** B1-style POs plus every mutation the seam needs. The trial PDFs are real, so they are never used as fixtures.
**Needs:** M1 merged; Joey's OK on the generator dependency (Open question 2).
**Acceptance:**
- `b1/models.py`: `Reading`, `NoteSnapshot` (title, body, attachment names, project linked or not), `MySysLookup` (every search row: pln, Client Ref No. and Company; `more_pages` (a second results page exists); project Client Internal No.; the raw Address string; Compaction Test tasks with status), `Proceed` (frozen: `note_id`, internal number, pln, PO number, email body, PDF file name and bytes, and the existing Compaction Test task numbers that W2 compares against) and `Skip` (reason), and `SkipReason` exactly as `docs/specs/spec.md` §3, including `NOTE_ALREADY_LINKED`.
- `scripts/make_fixture_pdfs.py` writes deterministic PDFs (same bytes on every run) with a text layer in the B1 layout: issuer `B1 Homes Pty Ltd`, `COMPACTION`, Purchase Order No, and a Job Address block. Values are fake: `2600001B`–`2600003B`, `pln_10001`–`pln_10003`, `Sample Lane`-style addresses. Claude learns the layout from `private/pdfs/` and copies no real value into it.
- Mutations cover every row of the seam-1 table in `docs/specs/spec.md` plus SPEC → Testing Strategy's extra cases. Each case in `tests/seam1/fixtures/cases.toml` lists its Note snapshot, lookup, stub Claude reading and expected result.
- A local check (not committed) confirms that no string from `private/` PDFs appears in the fixtures.
- A committed test regenerates the fixture PDFs into a temp folder and requires every PDF under `tests/seam1/fixtures/pdfs/` to match a generated one byte for byte, so a real PDF copied there fails the check (the repo-data rule allows any PDF in that folder; decisions, 19 Oct 2026, widened 21 Oct).

**Verify:** `uv run scripts/check.py` (the repo-data rule allows these PDFs); fixtures go in their own `test:` commit.
**Files:** `src/po_agent/b1/models.py`, `scripts/make_fixture_pdfs.py`, `tests/seam1/fixtures/pdfs/*` (generated), `tests/seam1/fixtures/cases.toml`, `tests/seam1/conftest.py`. **Scope:** M.

### 2.2 Deterministic reader and steps 2a–4 · auto

**Description:** pdfplumber reading and the checks before the project lookup, in both reader modes.
**Needs:** 2.1.
**Acceptance:**
- Text layer only: an image-only or corrupt PDF → `PDF_UNREADABLE`. Issuer → `NOT_B1`; no COMPACTION → `NOT_COMPACTION`; PDF PO ≠ file-name PO, or a live-style title whose PO differs → `PO_MISMATCH`.
- `NOTE_ALREADY_LINKED` (step 2a), `NO_PDF` (none, or not `.pdf`), `MULTIPLE_PDFS`, in §2 order.
- The email body comes from the deterministic side: the Note body as MySys shows it, never the title and never Claude.

**Verify:** `uv run scripts/check.py`; the matching seam-1 cases pass.
**Files:** `src/po_agent/b1/reader_rules.py`, `src/po_agent/b1/decision.py`, `tests/seam1/test_seam1_reader_checks.py`. **Scope:** S.

### 2.3 Project match and duplicate check · auto

**Description:** Steps 8 and 10 against the lookup, plus the deterministic-only path to the end.
**Needs:** 2.2.
**Acceptance:**
- Match rule, as one pure function `match_project(rows, more_pages, internal_no, site)` in `decision.py`: Company B1 Homes and Client Ref No. (trimmed, case-insensitive) = `<internal no>` (test) or `<internal no>/048` (live). Other suffixes are ignored. None → `PROJECT_NOT_FOUND`; more than one, or `more_pages` → `PROJECT_AMBIGUOUS`. The driver (3.2) calls this same function to choose which `pln_…` link to open, so the rule exists once. The project window's Client Internal No. not matching → `Skip(UNEXPECTED_SCREEN)`, which the run loop turns into a stop (Architecture decisions).
- Order: `decide()` checks in §2 order on the inputs it's given. The run loop gathers inputs in the same order and stops gathering at the first skip: no Claude call if steps 2a–4 already skip, and no project read if steps 6–7 skip.
- Duplicate: any non-Cancelled Compaction Test task → `DUPLICATE_TASK`, whatever its PO number. Cancelled tasks are ignored only when `duplicate_ignores_cancelled = true` (both settings tested). The existing task numbers go into `Proceed` for W2.
- In deterministic-only mode, a PO that passes every earlier step → `ADDRESS_UNVERIFIABLE`. Zero false PROCEED across all fixtures.

**Verify:** `uv run scripts/check.py`.
**Files:** `src/po_agent/b1/decision.py`, `src/po_agent/b1/models.py`, `tests/seam1/test_seam1_lookup.py`. **Scope:** S.

### 2.4 Address verify and agreement (hybrid, stubbed Claude) · auto (pauses: address rules)

**Description:** §4 verify-not-extract with the project-address parse, and step 7 agreement, using stub readings from the fixtures.
**Needs:** 2.3.
**Acceptance:**
- Normalisation and parse exactly as `docs/specs/spec.md` §4 and SPEC → Project address: lot after `Lot` (`12A` kept), `(#n)` dropped, postcode and state dropped, no leading `Lot` → `ADDRESS_UNVERIFIABLE`. Normalised Claude street + suburb must equal *R*, and each value must appear in the PDF's Job Address block. The fake example in SPEC passes.
- Agreement on issuer, COMPACTION, PO number and internal number → else `READERS_DISAGREE`. Stub cases: a wrong lot found elsewhere in the PDF → SKIP; wrong PO → `READERS_DISAGREE`; invalid output → `CLAUDE_INVALID_OUTPUT`; timeout → `CLAUDE_UNAVAILABLE`.
- The 3 fake POs PROCEED with the right pln, PO number and email body. The injected-text fixture never PROCEEDs with the injected value. The seam prints `false PROCEED: 0`.

**Verify:** `uv run scripts/check.py`.
**Files:** `src/po_agent/b1/address.py`, `src/po_agent/b1/decision.py`, `tests/seam1/test_address_normaliser.py`, `tests/seam1/test_seam1_hybrid_stub.py`. **Scope:** M.

### 2.5 Claude reader and the model ID · auto (pauses: prompt review, model ID)

**Description:** The real Claude reader: no tools, structured output, validated again by pydantic. Use the `claude-api` and `source-driven-development` skills. The model ID is pinned here, because the live seam below needs it.
**Needs:** 2.4; Joey approves the prompt and the exact model ID before the first live run.
**Acceptance:**
- `config/test.toml` has an exact dated Sonnet-class `claude_model_id` (ask-first).
- The request has **no tools**, temperature 0, bounded output tokens, a timeout of about 60 s, one retry on a transient error, and structured output in the reading schema. Its input is the PDF as a document plus the Note title and body, framed as untrusted data. The key comes from `secrets.get("anthropic_api_key")` and is passed to the client explicitly.
- Invalid or missing fields → `CLAUDE_INVALID_OUTPUT`; repeated failure → `CLAUDE_UNAVAILABLE`. Usage and AUD cost are calculated from the config price table.
- `tests/seam1/test_seam1_live_claude.py` (`-m live_claude`) runs every fixture through both real readers and prints per-field agreement (field names only), tokens, cost and `false PROCEED: N`. It fails if N > 0.

**Verify:** `uv run scripts/check.py` (fake client); `uv run pytest tests/seam1 -m live_claude` → `false PROCEED: 0`.
**Files:** `src/po_agent/b1/reader_claude.py`, `src/po_agent/b1/decision.py`, `config/test.toml` (ask-first), `tests/seam1/test_reader_claude.py`, `tests/seam1/test_seam1_live_claude.py`. **Scope:** M.

### 2.6 Prices and the real-PO seam (S3) · auto (pauses: prices; laptop runs)

**Description:** Fill the price table, add the laptop-only real-PO seam, and produce the S3 evidence.
**Needs:** 2.5; Joey's OK on the prices (from the pricing page).
**Acceptance:**
- `config/test.toml` has `claude_price_usd_per_mtok` for the pinned model. 2.5's cost line used zero prices until now.
- `tests/seam1/test_seam1_real_data.py` (`-m real_data`) reads `private/fixtures/cases.toml` (the 3 recent real POs plus the 3 trial POs, with test-site lookups as MySys shows them), is skipped when `private/` is absent (an error instead when `-m real_data` is selected explicitly), reports per-field agree/disagree **without values**, coverage and cost per PO, and fails on any false PROCEED. `tests/seam1/conftest.py` applies 1.8's failure-report hook to `real_data` tests (pydantic's `input_value=…` on invalid Claude output would otherwise print PDF text).
- S3: `-m live_claude` run 3 times → `false PROCEED: 0` each time; deterministic-only → 0; real-data → 0, and the 3 trial POs PROCEED with the right pln and PO number. Every skip of a clean real PO is reviewed with Joey before M3.

**Verify:** `uv run scripts/check.py`; the three seam commands above, with output shown.
**Files:** `config/test.toml` (ask-first), `tests/seam1/test_seam1_real_data.py`, `tests/seam1/conftest.py`. **Scope:** S.

### Checkpoint: M2 (S3)
- [ ] `check: all passed`; live-Claude ×3 `false PROCEED: 0`; deterministic-only 0; real-PO 0 with the report shown.
- [ ] Skips of clean real POs reviewed with Joey.
- [ ] `/agent-skills:review` on the M2 PRs.
- [ ] **Gate for M3:** M0b.1 written up (attachments, assignee read, panels and list anchors, moving between windows) and merged; test site reset.

---

## Phase M3: decide-only (step)

### 3.1 Take a Note and hand it back · step

**Description:** The Note-window actions every run needs: open a Note, untick Send Email Notification, assign it to the agent, read step 2a, and assign it back to the pool, each read back.
**Needs:** M2, M0b.1.
**Acceptance:**
- The Note opens from its Note Pool row (ID cell), in a window scoped by the heading `Note <id> - `. Before **every** Assign: untick Send Email Notification and read it back unticked.
- `core/runlog.py` (written only with `--detailed-log`): JSON lines in `logs/<run_id>.jsonl`, one object per event, `{"ts", "run_id", "note_id", "step", "event", "ok"}`. Events: `guard_action` (from `guard.history`, action name only), `assignee_check`, `email_notification_unticked`, `read_back` (field name only), `skip`, `error` (type name only; the traceback is a separate `traceback` event). No values except the trial identifiers. 5.2 asserts on these events.
- Assign to agent: user list = `agent_user_name`, pool list = `--Select Pool--`, Assign. Both lists are found by their row-26 anchors, never by position. Read back "Assignee:" and the new "User Assigned" log line. Then step 2a: **Link to Project** shown → continue; project button or Change Project → `NOTE_ALREADY_LINKED`.
- Assign to pool: `--Select User--` + `pool_name`, Assign. Read back Assignee = pool, a new log line, Status Pending. The reset lists and disabled Assign afterwards are expected. No key presses.
- Navigation: the driver reloads `base_url` between Notes (`driver.go_home()`), logging in again if the login page shows. To reach a Note it already assigned to itself, it follows "Finding a Note again" (Cross-cutting rules) and row 25.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k note_window` on one trial Note → it ends in the Agent Pool, Pending, with only two new log lines.
**Files:** `src/po_agent/mysys/driver.py`, `src/po_agent/core/runlog.py`, `src/po_agent/cli.py` (`--detailed-log`), `tests/seam2/test_note_window.py`, `tests/test_runlog.py`. **Scope:** M.

### 3.2 Attachments, download and project reads · step

**Description:** The read-only lookups the decision engine needs from MySys.
**Needs:** 3.1.
**Acceptance:**
- "Download document" links are counted in the Note window **before** any click (0 or 2 → `NO_PDF`/`MULTIPLE_PDFS`, as mapped in M0b rows 21–22). Download inside `expect_download` into the run's `po-agent-dl-<run_id>` directory; read the first file into memory and delete it at once (D2). A second download is deleted unread. The preview window is never used.
- Projects sub-tab, Search label-anchored inside the Projects panel (row 26). Wait up to 15 s for "No record found." or rows that each contain the internal number, else `UnexpectedScreen`. Parse every row (pln, Client Ref No., Company, Address) and whether there is a second page. Choose the row with `match_project()` (2.3) and open it by its `pln_…` link. Read Client Internal No., Address, and every "(tsk_…) | Compaction Test" header row with the Status from its details row, into `MySysLookup`.
- The seam-2 precondition helper gains its project part: no non-Cancelled Compaction Test task on a trial pln where the test needs none.
- Tests assert structure and the trial identifiers only, never an address. An offline test checks the download directory is empty after a Note, and after an exception mid-Note.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k reads` for the 3 trial plns.
**Files:** `src/po_agent/mysys/driver.py`, `src/po_agent/b1/models.py`, `tests/seam2/conftest.py`, `tests/seam2/test_reads.py`, `tests/test_download_cleanup.py`. **Scope:** M.

### 3.3 Decide-only run · step

**Description:** `po-agent run --site test --decide-only`: for each eligible Note, assign → 2a → attachments → download → decide → back to the pool, with NOTE lines.
**Needs:** 3.2; Open question 4 (NOTE outcome for a would-book Note).
**Acceptance:**
- Eligible Notes come from the list read once at the start (1.8), oldest first by Note ID, up to `max_notes_per_run`. Untouched Notes are never opened. Every processed Note ends back in the Agent Pool, and nothing is booked.
- One `NOTE` line per Note (reason, po_number, pln, tokens, cost_aud), then `RUN_SUMMARY` with `"mode": "decide-only"`.
- An `UnexpectedScreen` error or a `Skip(UNEXPECTED_SCREEN)` before any write → one attempt to return the Note to the pool through the normal path, in a fresh browser context if the old one was closed ("Finding a Note again"), then stop the run (exit 1). If the return fails, the Note stays with the agent and the ALERT says so.
- An offline loop test with a fake driver (not `testsite`) covers ordering, untouched Notes, a skipped Note not taken twice, reload between Notes and stop-on-first-failure.

**Verify:** `uv run scripts/check.py`; after a reset, `uv run pytest tests/seam2 -m testsite -k decide_only` → 3 NOTE lines, all 3 Notes back in the Agent Pool, no task created.
**Files:** `src/po_agent/core/run.py`, `src/po_agent/cli.py`, `src/po_agent/core/output.py`, `tests/seam2/test_run_loop_offline.py`, `tests/seam2/test_decide_only.py`. **Scope:** M.

### 3.4 Decide-only on the laptop, then the Mac Mini · by hand

**Description:** Joey resets and runs decide-only headed on the laptop. Then, **after the CEO confirms decision 2**, he runs it on the Mac Mini as `poagent`.
**Needs:** 3.3 merged; CEO decision 2 confirmed **on D2's terms** (the trial PDF briefly on the Mac Mini's disk, not "in memory only"), for the Mac Mini part only.
**Acceptance:**
- Laptop: `uv run po-agent run --site test --decide-only --headed` → each trial Note's NOTE line shows the decision the real-PO seam predicted; all back in the Agent Pool.
- Mac Mini: `scripts/macmini-run.sh decide-only` → `runs.log` ends with `RUN_SUMMARY … "exit_code": 0`, holds no PDF text or addresses, and no alert issue was opened.

**Verify:** Joey reads the terminal output and `runs.log`.
**Files:** none.

### 3.5 Kill switch, Perth window, run cap · step

**Description:** The run controls that decide whether a run may touch MySys at all, and when it must stop taking Notes. Built before any booking code (D1).
**Needs:** 3.3.
**Acceptance:**
- `enabled = false` → `INFO` + `RUN_SUMMARY` exit 0, no browser launched.
- Outside Mon–Fri 07:00–18:00 Australia/Perth (an injectable clock in tests) → exit 0, no MySys contact. The window applies to `run` and `run --decide-only`; `spike` and seam-2 tests ignore it, so laptop work after 18:00 still runs.
- The cap (`max_notes_per_run` 10, `max_run_minutes` 12) is checked before starting each Note. A Note in progress is finished, never abandoned mid-write (Open question 7).
- `controls.before_write(note_id, step)` exists for the booker: it re-reads `enabled` from `config/test.toml` before every step (Open question 6) and calls the assignee check (3.6) only for W1 and W4 (D7). Before W1 or W2 (nothing submitted yet), `enabled = false` → close the browser context and return the Note to the pool in a fresh context, then exit 0. From W3 on → `PartialWrite`.

**Verify:** `uv run scripts/check.py` (offline tests with a fake driver that records whether login was called).
**Files:** `src/po_agent/core/run.py`, `src/po_agent/core/controls.py`, `src/po_agent/core/config.py`, `tests/test_run_controls_offline.py`. **Scope:** S–M.

### 3.6 Assignee check · step

**Description:** A fresh Note Pool read before W1 and before W4 (D7), so the agent stops if a person has taken the Note, plus the stale-Note stop at run start (D6). Built and tested before any booking code (D1).
**Needs:** 3.5, M0b.1 (rows 23, 25).
**Acceptance:**
- Note Pool with Assigned Pool = All Pools and Search/filter = the Note ID, as mapped in row 23, then back to the window the booker was in, as mapped in row 25. The row whose ID cell **equals** the Note ID must have Assignee `agent_user_name`. Zero such rows, or more than one → `UnexpectedScreen`.
- Someone else at the W1 check (nothing written) → close the browser context and stop work on that Note without any write or reassign: `"outcome": "untouched"`, `"reason": "NOTE_TAKEN"` (Open question 4). Someone else at the W4 check (the task exists and is on hold) → `PartialWrite`. `before_write` for W2, W3 and W5 doesn't leave the window it's in (D7).
- **Stale-Note stop (D6).** In `run` and `run --decide-only`, after login and before the eligible list is read (1.8), the Note Pool is read with Assigned User = `agent_user_name`, Assigned Pool = All Pools, Locked/Unlocked = All, Search/filter empty and Status left at Pending (the filters anchored as mapped in row 26). Any row whose Assignee is `agent_user_name` → `ALERT UNEXPECTED_SCREEN` with the fixed detail "a Note is still assigned to the agent from an earlier run" and that `note_id`; no Note is taken; exit 1. `spike` skips this read (it takes no Note). Seam-2 teardowns and the reset (workflow 6.1) leave no Pending Note with the agent, so the stop doesn't fire in the tests that follow.
- The testsite test proves the read returns the agent for an assigned trial Note (then the teardown returns it to the pool). An offline fake-driver test proves the stop logic, including a Note ID that is a prefix of another, and the stale-Note stop: one Pending Note with the agent → exit 1, no Note opened.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k assignee`.
**Files:** `src/po_agent/mysys/driver.py`, `src/po_agent/core/controls.py`, `src/po_agent/core/run.py`, `tests/seam2/test_assignee_check.py`, `tests/test_assignee_offline.py`. **Scope:** S–M.

### Checkpoint: M3
- [ ] `check: all passed`; seam-2 decide-only and assignee green after a reset.
- [ ] Mac Mini decide-only green (only after CEO decision 2).
- [ ] `/agent-skills:review`. **Gate for M4:** M0b.2 merged; `doubt-driven-development` on the booker design (4.1–4.5) against `docs/screen-map.md`, in a fresh session; test site reset.

---

## Phase M4: first booking (step, plan mode first)

Each W-step test books **only as far as its step** on the test site and leaves the task for Joey to cancel (reset). Its teardown returns the Note to the pool in a fresh context. W-step tests run one at a time, with a reset between them (Cross-cutting rules). The booker's `book()` takes an optional `stop_after` step for these tests (Open question 8). Every test gets its `Proceed` by running all checks on a trial PO first. Every W step starts with `controls.before_write(note_id, step)` (3.5, 3.6); only W1's and W4's run the assignee check (D7).

### 4.1 W1: fill Create New Task and read it back · step

**Description:** Open the project, then Create New Task: Creator, Compaction Test, PO Number, PO Documents upload and Note, with the full pre-Submit read-back.
**Needs:** M3, M0b.2 (PO prefill, row 24; the Create New Task anchors from open item 8); PO Documents confirmed as the upload area with the PO admin (SPEC open question 11, "confirm before M4").
**Acceptance:**
- `book()` accepts only a `Proceed` (type-checked). Before anything else it checks that the `Proceed` is for this Note and project: its `note_id` matches the Note being worked on (the run loop passes it) and its pln matches the project window's heading; otherwise `WriteNotStarted`. It uses the project window 3.2 opened if it's still open, as mapped in row 28, rather than opening a second one. The window is scoped by the heading `Create New Task`. Creator (label "Creator", Client section) = Perth Scheduling; tick `- Compaction Test` (exact name); PO Number (label-anchored) replaces any prefill; upload to **PO Documents** (never Documents) from the in-memory PDF bytes (D2); Note (label-anchored textarea) = the email body as plain text. `field_by_label` lives in `driver.py`.
- Read back before Submit, per SPEC → W1: Creator; Compaction Test is the only ticked checkbox in the window; Task Client "Same as Project"; Task Name empty; PO Number; exactly one PO Documents row with the PDF's file name; the Documents area empty as mapped in M0b.2; Note; Sale Office; PO Contact and Delivery Office "Choose...". Any mismatch → close the browser context, `WriteNotStarted`.
- The testsite test stops after W1 and closes the context. The project then has no new task.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k booker_w1` (2609017B).
**Files:** `src/po_agent/b1/booker.py`, `src/po_agent/mysys/driver.py`, `tests/seam2/test_booker_w1.py`. **Scope:** S.

### 4.2 W2: Submit and read back on the task detail screen · step

**Description:** Submit, find the one new task, and read back PO number, document and Note on its detail screen (M0b row 19).
**Needs:** 4.1.
**Acceptance:**
- After Submit, wait up to 15 s for the Create New Task window to close and the project's task table to show a Compaction Test number not in the set recorded at step 10. The new task is the **one** such number. Its details row shows Lodged By the agent, Task Creator Perth Scheduling and Status "New Project" or "Inspection Analysis" (row 07: it can move on by itself). No new task, more than one, or the form still open after 15 s → `PartialWrite`. A Submit error (row 17) isn't mapped, so the state is unknown and Joey checks it by hand.
- On the task detail screen (opened read-only, as mapped in M0b): the PO number, the PO document's file name and Note = email body. A wrong value → `AccuracyBreach`. A screen not as mapped → `PartialWrite`.
- The testsite test stops after W2. Joey cancels the task afterwards.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k booker_w2`; reset.
**Files:** `src/po_agent/b1/booker.py`, `src/po_agent/mysys/driver.py`, `tests/seam2/test_booker_w2.py`. **Scope:** S.

### 4.3 W3: Hold · step

**Description:** Hold the new task with "ON HOLD UNTIL CALL UP", reading every dialog check before confirming, without touching a checkbox.
**Needs:** 4.2.
**Acceptance:**
- **Hold** is pressed only in the new task's header row. The dialog is scoped by the heading `Hold Task: <new task no>`. Type the note; before confirming, read: the heading names the new task; every Related Tasks checkbox and Select-all are unticked; Reset turn around time is unticked; "every … days" is ticked with 0 and "at this date" is unticked; the note text is exact. Anything else → close the context, `PartialWrite`. Confirm with the dialog's own Hold.
- Read back: the task's row shows **Un-Hold**, and its Status starts "On-hold" and contains the note.
- The testsite test also calls `guard.vet()` (never `act()`) on a Related Tasks checkbox in the open dialog and asserts it refuses (D3). Afterwards the checkbox still reads unticked; then the test closes the context.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k booker_w3`; reset.
**Files:** `src/po_agent/b1/booker.py`, `src/po_agent/mysys/driver.py`, `tests/seam2/test_booker_w3.py`. **Scope:** S.

### 4.4 W4 Link to Project and W5 Solved · step

**Description:** Link the Note to the pln through the search and select screens (M0b row 20), then press Solved.
**Needs:** 4.3, M0b.2 (row 20), M0b.1 (row 25).
**Acceptance:**
- Back to the Note window as mapped in row 25. Before each Note-window write, in this order: `before_write`, untick Send Email Notification, read it back unticked, then the one committing click (Architecture decisions). For W4 the read-back is repeated after the search and select screens, just before the final select. W4: Link to Project → search the pln → select the target named in row 20. Read back: the Note's project button reads the pln, and Status is still Pending.
- W5: Status buttons → **Solved**. Read back: "Solved by Agent 1 (MySys Only)", a "Status changed … Pending to Solved" log line, Solved disabled, and the Note gone from the Pending list, checked with Assigned Pool = All Pools and Search/filter = the Note ID (under Agent Pool it's hidden anyway).
- Pending, Discard, Change Project and Unlink are never targeted (the guard refuses them anyway).

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k booker_w4_w5` (one full booking); reset.
**Files:** `src/po_agent/b1/booker.py`, `src/po_agent/mysys/driver.py`, `tests/seam2/test_booker_w4_w5.py`. **Scope:** S.

### 4.5 Run mode: book end to end · step

**Description:** `po-agent run --site test`: PROCEED → booker; partial writes and accuracy breaches handled the MVP way.
**Needs:** 4.4.
**Acceptance:**
- PROCEED → W1–W5 → `NOTE` outcome `booked` with `task_id`. A skip → back to the pool. `PartialWrite` → `ALERT PARTIAL_WRITE`, Note left assigned to the agent, run stops (exit 1). `AccuracyBreach` → `ALERT ACCURACY_BREACH`, exit 3. `WriteNotStarted` → Note back to the pool, run stops (exit 1).
- `run` without `--decide-only` now books (it no longer refuses, 1.6).
- Seam 2 (testsite, after a reset): the 3 trial POs are booked to S4. An immediate rerun changes nothing (SPEC → Reruns).
- Two cases need Notes only a person can create. `test_run_book.py` has a second test that runs only after Joey has placed a fresh copy of 2609034B and a non-`/048` Note in the Agent Pool. Its precondition fixture checks both are there, and skips with a clear message if they aren't. The fresh copy → `DUPLICATE_TASK`, back in the Agent Pool, no new task (S5). The non-`/048` Note stays untouched.
- The offline loop test covers the partial-write, accuracy-breach and write-not-started paths with a fake driver.

**Verify:** `uv run scripts/check.py`; `uv run pytest tests/seam2 -m testsite -k run_book`; reset. **By hand:** Joey runs `--headed --slow-mo 500` and assigns the Note to himself from his own browser mid-run → the agent stops on that Note without writing (taken before the W1 check) or alerts `PARTIAL_WRITE` at the W4 check (taken during W1–W3).
**Files:** `src/po_agent/core/run.py`, `src/po_agent/cli.py`, `tests/seam2/test_run_book.py`, `tests/seam2/test_run_loop_offline.py`. **Scope:** S–M.

### 4.6 First bookings from the Mac Mini · by hand

**Description:** Book 2609017B from a manual run on the Mac Mini, then 2609034B, then 2610002B, one per run, then reset.
**Needs:** 4.5 merged; Mac Mini pulled; CEO decision 2 confirmed.
**Acceptance:**
- At the start, the job is loaded (`launchctl bootstrap`, `docs/macmini-setup.md` §8); at the end it's unloaded again (`bootout`) until M6 (D1). Scheduled runs may fire in between; that's acceptable because the controls from 3.5–3.6 exist and only one trial Note is in the pool at a time. No laptop test-site run while the job is loaded (Cross-cutting rules → One agent at a time).
- For each run, only that trial PO's Note is in the Agent Pool (the others are moved out, because the run cap of 10 would otherwise book all three at once). Then `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent`.
- Each pln has exactly one non-Cancelled Compaction Test task with the right PO number, the PDF in PO Documents, Creator Perth Scheduling, Note = email body and On Hold "ON HOLD UNTIL CALL UP". Each Note is linked and Solved. `runs.log` shows `exit_code: 0` and no ALERT.
- Reset afterwards (workflow 6.1).

**Verify:** Joey checks each pln and Note in MySys, and `runs.log`.
**Files:** none.

### Checkpoint: M4
- [ ] `check: all passed`; seam-2 booking cases green; Mac Mini bookings correct; test site reset.
- [ ] `/agent-skills:review` + `security-and-hardening` on the M4 PRs, with Important findings fixed.
- [ ] Joey reviews before M5.

---

## Phase M5: MVP safety (step)

The run controls and the assignee check moved to M3 (3.5, 3.6) under D1. M5 now proves the alerts and the safety cases end to end.

### 5.1 Alerts and exit codes, end to end · step

**Description:** Every typed error maps to its ALERT line and exit code through the real run paths, and `RUN_SUMMARY` is always printed. 1.6 built the mapping and the catch-all; this task proves every path.
**Needs:** M4.
**Acceptance:**
- `LoginFailed`/`ConfigError` → exit 2; `UnexpectedScreen`/`WriteNotStarted`/`PartialWrite`/`GuardRefusal` → exit 1; `AccuracyBreach` → exit 3. Each has its `ALERT` line. A guard refusal raised by `act()` aborts the whole run (a fake-driver test).
- Any other exception → `ALERT UNEXPECTED_SCREEN` with a fixed detail, exit 1, nothing on stderr. `RUN_SUMMARY` is always the last line, even after a crash.
- A test raises an error whose message contains fake PDF text and an address, and asserts neither reaches stdout or stderr.

**Verify:** `uv run scripts/check.py`.
**Files:** `src/po_agent/cli.py`, `src/po_agent/core/run.py`, `src/po_agent/core/output.py`, `tests/test_exit_codes.py`. **Scope:** S–M.

### 5.2 Seam-2 safety cases on the test site · step

**Description:** The remaining seam-2 cases, run together after a reset.
**Needs:** 5.1.
**Acceptance:**
- In an open trial Note window, the harness calls `guard.vet()` (never `act()`) on **Discard** and asserts it refuses (D3). Afterwards there is no new Note log line, and the assignee and status are unchanged.
- From the detailed log (`--detailed-log`, 3.1's format): before every Note-window write in a full run, an `email_notification_unticked` event that comes **after** the most recent `assignee_check` event (W4's, for both W4 and W5; D7). A non-`/048` Note in the pool is never assigned or opened.
- "Full seam 2 green" means one fixed sequence of `uv run pytest tests/seam2 -m testsite -k <name>` runs, each started from the reset state it needs, with a reset (workflow 6.1) after every W-step or booking run (Cross-cutting rules): spike, note_window, reads, decide_only, assignee, booker_w1, booker_w2, booker_w3 (includes the Hold-checkbox refusal), booker_w4_w5, run_book (booking, rerun, skip), safety. `tests/seam2/README.md` lists the sequence and which runs need a reset first; the output of every run is shown.

**Verify:** `uv run pytest tests/seam2 -m testsite` with the output shown; reset afterwards.
**Files:** `tests/seam2/test_safety.py`, `tests/seam2/README.md`. **Scope:** S.

### Checkpoint: M5
- [ ] `check: all passed`; full seam 2 green; manual mid-run takeover check (4.5) done.
- [ ] `/agent-skills:review` + `security-and-hardening` on the M5 PRs.
- [ ] Context check: CLAUDE.md, SPEC.md and `docs/macmini-setup.md` still match the code (flag drift).

---

## Phase M6: MVP demo (by hand)

### 6.1 Go/no-go and stop rehearsal · by hand
**Acceptance:** `/agent-skills:ship` checklist against S1–S8 with the rollback (`launchctl bootout`; `enabled = false`) is written and Joey decides go. The job is loaded again (`launchctl bootstrap`; it was unloaded after 4.6, D1). `enabled = false` merged → `launchctl kickstart` exits before login (S6). Set back to `true`. `bootout` stops the job and `bootstrap` restores it.
**Verify:** `runs.log` shows the exit-before-login run. **Files:** `config/test.toml` (two PRs, by Joey's choice).

### 6.2 Demo 1: scheduled run, then the skip · by hand
**Acceptance:** after a reset with exactly one Pending Note per trial PO, the next **scheduled** launchd run meets S4. A fresh 2609034B copy → the next run meets S5. S6 controls checked. S7: NOTE lines carry tokens and AUD cost, and there is no ALERT and no guard refusal.
**Verify:** each pln and Note in MySys; `runs.log`.

### 6.3 Demos 2 and 3 (S8) · by hand
**Acceptance:** reset per `docs/demo-runbook.md` and repeat S4 + S5 twice more, with no code or config change between demos. At least one is shown from the laptop (`--headed --slow-mo 500`), with the Mac Mini job unloaded (`bootout`) for that demo and loaded again afterwards (Cross-cutting rules → One agent at a time).
**Verify:** three consecutive passing demos recorded (RUN_SUMMARY lines kept).

### 6.4 One-page demo note for the CEO · by hand
**Acceptance:** what ran and where (office Mac Mini), the trial conditions, cost per PO (from NOTE/RUN_SUMMARY), the S3 real-PO result, open concerns. No real data beyond the trial identifiers. Location is Joey's choice (default: the claude.ai project, not the repo).
**Verify:** Joey reads it before sending.

### Checkpoint: Complete
- [ ] S1–S8 met; three demos in a row; CEO note sent.
- [ ] Next: `docs/workflow.md` Stage 8 (`/agent-skills:code-simplify`, architecture review).

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| A merge to `main` deploys to the Mac Mini (the wrapper pulls every run) while the job is loaded | High | D1: run controls and assignee check before any booking code; job unloaded after S1 and loaded only for 4.6 and from M6; plain `run` refuses until 4.5; a failed pull runs nothing |
| Moving between MySys windows isn't mapped (Note → project → Hold → back to the Note) | High | M0b.1 rows 25–28 before M3; "Finding a Note again" rule; a Note already assigned is re-found with All Pools + exact ID; D7 cuts the Note Pool trips to two per booking and keeps W1–W3 in the project window |
| Denylist refuses a safe action (a "… Close" street in a target's text; a dropdown option) and blocks every run | Med | D5 for dropdowns; M0b.2 row 20 names a W4 target without the address; a refusal opens an alert issue, so Joey sees it on the first run |
| Trial PDF left on the Mac Mini's disk after a crash or kill | Med | D2: read into memory and delete at once; `finally` cleanup; leftovers removed at every run start; FileVault |
| Orphaned Python/Chromium after the 20-minute kill overlaps the next run (double booking) | Med | The wrapper kills the whole process group; a test checks that no child survives (1.9) |
| MySys refuses or challenges logins from the Mac Mini | High | Hand login in Safari first (1.10); if blocked, stop and tell the CEO (SPEC open question 2) |
| Guard misses a dangerous control (name not resolved, substring missed, unscoped hidden copy) or code acts past it (APIRequestContext, dialogs, aliasing) | High | Denylist checked on the element itself; scoping; exactly-one-match; real-browser unit tests (1.4); `exact=True` names and `act()` on the element `vet()` resolved (1.4); the widened AST scan (1.4); `guard.vet()` on a real Note window and a real Hold dialog (4.3, 5.2) |
| The laptop and the Mac Mini book the same Note at once (same agent account, so neither run's checks see the other) | High | Cross-cutting rule "One agent at a time"; 4.6 and 6.3 follow it |
| A systematic bug leaves a half-booked Note on every hourly run (no state between runs) | Med | D6: the run stops at start while any Pending Note is still with the agent |
| Real data leaks via test output (pytest prints compared values), run output or stderr | High | Cross-cutting rule: assert on booleans and identifiers only; fixed-template INFO/ALERT; nothing on stderr (1.6); test in 5.1 |
| A booking on top of stale test-site state | Med | Seam-2 precondition fixture; reset after every W-step test |
| Mac Keychain "allow access" dialog after a Python change hangs an unattended run | Med | `.python-version` pin (1.1); 20-minute wrapper limit plus alert (1.9); spike at the Mac after any Python change |
| macOS lacks GNU `timeout`; wrapper behaves differently in bash on Windows/CI | Med | Wrapper implements its own limit; tests with stub commands; `plutil -lint` and one real spike on the Mac (1.10) |
| gitleaks via pre-commit needs Go or Docker on Windows | Low | Source-driven check in 1.3; fall back to the gitleaks binary as a system hook if the Go bootstrap fails |
| M0b screens differ from assumptions (task detail, Link search) | Med | M3 waits for M0b.1, M4 for M0b.2; each write-up updates the affected tasks here in the same commit |
| CEO decision 2 not confirmed in time | Med | Laptop work isn't blocked; only Mac Mini runs that download a trial PO (3.4, 4.6, M6) wait. The job stays unloaded (D1), so no scheduled run downloads one early |
| Two Notes for one PO in the pool | Low | First booked, the other `DUPLICATE_TASK` (SPEC rule); runbook keeps one per PO |

### Accepted for the MVP (known, not planned as tasks)

Found in the 16 Oct 2026 reviews and accepted for a 3-PO trial on the test site. Revisit in `docs/workflow.md` Stage 8 or before go-live.

- **Build-check gaps:** the AST scan doesn't catch page JS through `wait_for_function`, calls through `operator.methodcaller("click")`, or keyword arguments such as `record_har_path=`; nor does it forbid `force=True` inside the guard. Code review is the control.
- **No runtime host block:** nothing stops the browser following a link or redirect to the live host; `base_url` is pinned in config, and the guard only acts on mapped test-site controls.
- **gitleaks** is allowlisted by path (`tests/test_hooks.py`), so a real key pasted into that file would pass; allowlisting the exact fake string is the stricter option.
- **Branch protection on `main`** isn't set; `guard_bash.py` patterns are a backstop only (Joey's call).
- **Disk leftovers on the Mac Mini:** Chromium's HTTP cache and temp profile may hold the PDF or pages until the OS cleans `$TMPDIR`; a SIGKILL at the 20-minute limit skips the `finally` cleanup until the next run. FileVault is on.
- **Fixture PDFs are byte-checked only from 2.1:** until the generator exists, a real PDF copied into `tests/seam1/fixtures/pdfs/` would pass the repo-data rule. The "no `private/` strings" check stays local only.
- **Page 1 only:** with more than 50 Pending Notes in the pool, older eligible Notes wait. Not an issue at trial volume.
- **Process-group kill** is tested only under Git Bash and CI, not macOS `/bin/bash` 3.2, until the first hung run on the Mac Mini.
- **CI gitleaks action** needs a `GITLEAKS_LICENSE` secret if the GitHub owner is an organisation; check in 1.3, or use the gitleaks binary directly.

## Open questions (Joey)

1. ~~**Merge the PR stack first?**~~ **Done:** PRs #1–#5 are merged (`origin/main` at `73d468d`, the same commit as `plan-mvp`). Still to do: fast-forward the local `main`, and delete or reset the stale `m1-walking-skeleton` branch (see the header). At the freeze (workflow 4.4), one commit holds `tasks/`, the D1–D7 `docs/decisions.md` entry and the SPEC changes in Doc drift.
2. ~~**New dependencies.**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** M1: `playwright`, `pdfplumber`, `anthropic`, `pydantic`, `keyring`; dev: `pytest`, `ruff`, `pre-commit`. M2: a fake-PDF generator. Recommended: `reportlab` (BSD; `invariant=1` gives byte-identical output), dev-only. OK to treat approving this plan as approving this list? Anything else still gets asked.
3. ~~**Guard allowlist additions**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** beyond `docs/specs/spec.md` §5: the login actions (fill username, fill password, click "Log in") and the module navigation clicks (Project top tab, Note Pool, Projects sub-tab). Both are needed to reach the screens §5 already allows. Recommended: yes, with a dated decisions entry and §5 updated at the freeze.
4. ~~**NOTE values the contract doesn't define:**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** (a) a decide-only Note that would have been booked, and (b) a Note a person took mid-run. Recommended: (a) `"outcome": "skipped"`, `"reason": "DECIDE_ONLY"`; (b) `"outcome": "untouched"`, `"reason": "NOTE_TAKEN"`. Both are run-output values only, not new skip reasons in the decision engine. Recorded in decisions + SPEC.
5. ~~**CI installs Chromium**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** (one step added to Appendix A's YAML) so the guard's tests use a real browser on local HTML. Recommended: yes. The alternative, a fake locator, wouldn't test accessible-name resolution, which is the denylist's weak point.
6. ~~**Kill switch mid-run:**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** re-read `enabled` from `config/test.toml` before each write step (`controls.before_write`, 3.5), as §8 says (it only matters for laptop runs; the Mac Mini reads `main` once per run). Recommended: yes.
7. ~~**Run cap:**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** checked before each new Note; a Note in progress is finished. Kill switch and window exits are exit code 0. Recommended: yes.
8. ~~**Booker `stop_after`**~~ **Answered (Joey, 16 Oct 2026): yes, as recommended.** (test-only parameter) so seam-2 can test W1, W2 and W3 one at a time. Recommended: yes. Without it, every booker test is a full booking, and a failure is harder to pin to a step. `run` never passes it (a test asserts that).
9. ~~**TDD stop vs `/agent-skills:build auto` in M2.**~~ **Answered (Joey, 16 Oct 2026):** keep the stop (CLAUDE.md wins); auto only chains the M2 tasks.
10. ~~**Proposed D7: run the assignee check before W1 and W4 only, not before each of W1–W5.**~~ **Answered (Joey, 16 Oct 2026): option A**, applied as D7 (Decisions table, 3.5, 3.6, 4.5, 5.2). The write-up below is kept for the decisions entry.
    - **Context.** SPEC → §8 run controls, SPEC → MySys screen rules ("Assignee check (§8), before each of W1–W5") and `docs/specs/spec.md` §8 ("before each write") all ask for a fresh Note Pool read before every write. Each read leaves the window the booker is in, goes to the Note Pool, and comes back (row 25).
      - **Before W2**, the check leaves a filled, unsubmitted Create New Task form with the PDF already uploaded. No screen-map row records whether the form survives that trip. Submit then fires without a fresh read-back. This is the riskiest step in the plan, and the first write only Joey can undo.
      - **Before W3**, it leaves the project window between Submit and Hold.
    - **Option A (recommended): before W1 and before W4.**
      - **Before W1** the check runs just before Create New Task is opened.
      - **Before W4** it runs once the booker is back on the Note window; W5 follows on the same window seconds later.
      - W1 → W2 → W3 run in the project window without leaving it.
      - `before_write` still re-reads `enabled` before every step. That is a file read with no navigation.
    - **Option B (keep SPEC): before each of W1–W5.** M0b.2 must then also map a filled Create New Task form surviving a trip to the Note Pool and back. W2 must repeat W1's whole read-back after the check and before Submit. And row 25 must cover getting back to the form and to the project window, not only Note ↔ project.
    - **Option C (rejected): read the assignee from the open Note window**, which needs no navigation. The screen map doesn't know whether that window refreshes (row 23). That's why SPEC chose a fresh Note Pool read.
    - **What A costs.** A person who takes the Note while W1–W3 run isn't noticed until W4. That is a minute or so at normal speed. By then the task exists and is on hold, so it's `PARTIAL_WRITE`: ALERT, nothing more written, and Joey reconciles by hand. Under B, the same person is caught one step earlier, but it's `PARTIAL_WRITE` from W3 on anyway. And B still leaves a gap of a few seconds between each check and its click, so B narrows the window but doesn't close it.
    - **What A gains.**
      - It removes the unmapped round trip with a filled form.
      - It cuts three of the five Note Pool trips per booking. Each trip is a chance to stop a booking that was fine with `UNEXPECTED_SCREEN` or `PARTIAL_WRITE`.
      - Row 25 only needs Note ↔ project, which it already covers.
      - Bookings get shorter, which also helps the 12-minute cap.
    - **If A is chosen, the same freeze commit changes:**
      - a dated `docs/decisions.md` entry;
      - SPEC → §8 run controls and MySys screen rules ("before W1 and W4"; the MVP only, v1 may go back to every write);
      - `docs/specs/spec.md` §8;
      - in this plan:
        - Architecture decisions (`before_write` runs the assignee check only for W1 and W4);
        - 3.5;
        - 3.6 (someone else before W1 → `untouched`/`NOTE_TAKEN`; at W4 → `PartialWrite`);
        - 4.5's by-hand check (taking the Note mid-run → stop before W1, or `PARTIAL_WRITE` at W4);
        - 5.2's event order (W5's untick comes after W4's assignee check);
        - the Risks table.
    - **If B is chosen:** add those M0b.2 captures and W2's second read-back to 4.2, and leave SPEC as it is.

## Doc drift to fix at the freeze (CLAUDE.md "Flag it")

- `SPEC.md` → Project Structure: add `src/po_agent/core/errors.py` and `src/po_agent/core/controls.py`.
- `docs/specs/spec.md` §5: the login and navigation actions (if Open question 3 is yes); the `vet()`/`act()` split (D3); the select rule (D5); the widened build check (1.4), which bans the `request` attribute instead of HTTP verb names. §8: the stale-Note stop (D6).
- `docs/workflow.md` Appendix A: the Chromium install step in `check.yml` (if Open question 5 is yes); the extra `guard_bash.py` patterns (1.2); `.gitleaks.toml` (D4).
- `SPEC.md` → Code style: the NOTE values from Open question 4; `run_id`'s format; nothing on stderr.
- `SPEC.md` → Expected slices: M3 gains the run controls and assignee check, M5 keeps alerts and the safety cases (D1). → Testing Strategy: real-page refusals use `guard.vet()` (D3). → Trial conditions and Real client data: the D2 download rule. → The partial-write row and §8 run controls: the stale-Note stop (D6); the assignee check before W1 and W4 only (D7, also in MySys screen rules and `docs/specs/spec.md` §8). → Never or MySys screen rules: no laptop test-site run while the Mac Mini job is loaded (Cross-cutting rules → One agent at a time). → MySys screen rules: eligibility also needs Assignee = pool; the Note Pool is read once per run; "Finding a Note again"; the assignee check's exact ID match; W2 accepts "Inspection Analysis".
- `docs/macmini-setup.md` §8: the mode mapping (`decide-only` → `run --decide-only`), a failed pull runs nothing, killing the process group, stderr to `/dev/null`; and "unload after the S1 spike, load again only for 4.6 and from M6" (D1). §11 stop 1 works only from 3.5.
- `CLAUDE.md` (Joey edits by hand, D2–D4; the #3 edit is needed before 1.2). Suggested wording:
  - Must never #3, append: "The one exception is the deny regex in `.claude/hooks/guard_bash.py` and its test, which must name the host to block it."
  - Conventions, Secrets, append: "…except `tests/test_config_secrets.py`, which sets it to prove it's ignored."
  - Must never #2, append: "Tests may call `guard.vet()` (no action code) on these controls to prove it refuses (decisions, 16 Oct 2026)."
  - Must never #6, replace "the Mac Mini reads them from the test site in memory" with: "the Mac Mini reads them from the test site; a trial PDF is on the Mac Mini's disk only from its download until it's read into memory, a moment later, and leftovers are removed at the next run start (decisions, 16 Oct 2026, D2)."
