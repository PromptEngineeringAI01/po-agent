# PO Agent — Claude Code workflow (MVP build)

**Version:** v5.14 · 24 Oct 2026 · **Owner:** Joey Wu

**Goal of the MVP:** show that the agent runs by itself on the office Mac Mini, hourly, against the MySys test site, and books the 3 trial POs correctly (`SPEC.md` S1–S8; CEO decision 3). Everything in this runbook serves that goal; anything for after the MVP is in Stage 8.

**Approach:** Addy Osmani's agent-skills (Define → Plan → Build → Verify → Review → Ship). CLAUDE.md, hooks, one check command and CI on GitHub keep it safe. Claude writes and opens PRs; Joey merges.

**v5.14:** a lighter process (decisions, 24 Oct 2026): the test-first review stop only on 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2; the freeze rule covers the agent's behaviour and anything that loosens a safety control, not dev-tooling tweaks; no extra work (mutation probes, second review rounds).

**v5.13:** trimmed for the MVP. Stages 0–4 are done, so they're now a short summary (their full steps are in git history, v5.12). Stage 5: a branch per task, "update from `main`" before the PR, a review guide in every PR, and **Create a merge commit** (not squash) so the `test:` commit stays visible on `main`. Security review only on the PRs that need it (1.2, 1.3, 1.4, M4). Fewer clear-context rules. The skills plan and the cheat sheet are merged into one short table. Earlier versions: see git history of this file.

---

## Where you are

| Stage | What | Status |
|---|---|---|
| 0–2 | Tools, GitHub repo, skills | **Done** (14–15 Oct 2026) |
| 3 | M0: SOP walkthrough on the test site, screen map, the six checks, 3 real PDFs and `cases.toml` in `private/` | **Done** (16 Oct 2026, PRs #3–#5) |
| 3E | M0b: the screens still to map | **To do, by hand.** M0b.1 before task 1.8; M0b.2 before M4 |
| 4 | SPEC check, plan, doubt review, freeze | **Done** (16 Oct 2026, PRs #5–#7) |
| 5 | Build M1–M5, one task at a time | **In progress.** 1.1 done (PR #9); next 1.2 |
| 6 | Verify on the test site and the Mac Mini | After M3 and M4 |
| 7 | MVP demo (M6) | After M5 |
| 8 | After the MVP | Later |

`tasks/todo.md` is the live task list; tick tasks there, not here.

## How to use this runbook

- Each step has the exact command and a **✓** line saying what you should see. If the ✓ matches, go to the next step; Claude's wording will differ every time, and that's fine.
- **PowerShell** boxes: your own terminal, one line at a time (Windows PowerShell 5 rejects `&&`).
- **Claude Code** boxes: typed into Claude Code (start it with `claude` in the repo folder).
- Never paste a password or API key into Claude Code or any chat.

## Skills you'll use

Always type the full name (`/agent-skills:build`): a bare `/build` is "Unknown command", and bare `/plan` and `/review` are Claude Code's own built-ins.

| When | Type |
|---|---|
| Build a task (test-first, small commits) | `/agent-skills:build task <N>` (M2: `/agent-skills:build auto`); Stage 5 step 3 |
| Run the tests | `/agent-skills:test` |
| Before every PR | `/agent-skills:review`; plus `security-and-hardening` for 1.2, 1.3, 1.4 and M4 |
| Library calls (Playwright, Anthropic SDK, pdfplumber) | `Use the source-driven-development skill …` (M1, M2, M4) |
| Challenge a risky design in a fresh session | `Use the doubt-driven-development skill on …` (before M4) |
| A failure that isn't obvious | `Use the debugging-and-error-recovery skill on …` |
| An open question you can't answer | `Use the interview-me skill on …` |
| CLAUDE.md out of date | `Use the context-engineering skill …` (after M1) |
| Before the MVP demo | `/agent-skills:ship` |
| A change to what the agent does | `/agent-skills:spec`, then `/agent-skills:plan` (plan mode off) |

Not used: `/webperf`, `frontend-ui-engineering`, `browser-testing-with-devtools`, `idea-refine`, loop engineering, parallel worktrees, Matt Pocock's skills (Stage 8 only).

## Ground rules

| Thing | Rule |
|---|---|
| Code | Private GitHub repo (`PromptEngineeringAI01/po-agent`). The Mac Mini pulls `main` before every run, so **merging is deploying**. |
| Plan and tasks | `tasks/plan.md`, `tasks/todo.md`. Tasks run in order, one per branch and session. |
| Changes after the freeze | A change to what the agent does in MySys or prints in its run output, or one that loosens a safety control, needs a dated `docs/decisions.md` entry plus `SPEC.md` and `tasks/plan.md`, in the same commit. Tightening a dev-tooling rule needs only a clear commit message. |
| Hooks | Created in M1 (task 1.2), then changed only by Joey, by hand. |
| Evals | The seam 1 fixture set, plus the real-PO set on the laptop. Every bug adds a fixture. |
| Real client data | `private/` on the laptop only (git-ignored). The 3 trial POs also live on the test site; the Mac Mini reads them from there, in memory. |
| Credentials | Windows Credential Manager on the laptop; `poagent`'s login Keychain on the Mac Mini. Nowhere else. |
| Run output | `~/Library/Logs/po-agent/runs.log` on the Mac Mini; `logs/` on the laptop (git-ignored). Never in the repo. |
| Source of truth | The repo (`SPEC.md`, `docs/`, `tasks/`). The claude.ai runbook page and project copies are reading copies. CEO decisions live in the CEO brief; `docs/decisions.md` records them. |

---

## Stages 0–2 — Tools, repo and skills (done)

Installed on the laptop: Claude Code, uv with Python 3.12, the GitHub CLI (portable zip in `C:\Users\JoeyWu\tools\gh\bin`, logged in as **PromptEngineeringAI01**; `gh auth setup-git` makes git use it), Node.js and Playwright CLI, and Addy Osmani's agent-skills plugin (`agent-skills@addy-agent-skills`). Don't run `playwright-cli install --skills`: its skills teach Claude to click. Setting up a new laptop: v5.12 of this file in git history has every command.

---

## Stage 3 — M0: map the screens (done) and M0b (to do)

**Done:** the SOP walkthrough on the test site (rows 01–18), the six checks (answers in `docs/decisions.md`), the screen map (`docs/screen-map.md`), and, on the laptop only, the captures, the 3 most recent real PO PDFs and `private/fixtures/cases.toml`. Before go-live, add real PDFs to reach 10–20.

### 3A. How a mapping session works (used again in 3E)

You click; Claude only observes with Playwright CLI. Everything it saves goes to `private/captures/test/` (git-ignored), because the 3 trial POs are real B1 POs.

1. Start `claude` in the repo and paste:

   ```text
   We're mapping the MySys test site for docs/workflow.md Stage 3E. Run: playwright-cli open --headed "https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component" — then wait. I log in and do every click and every typed value myself. You only observe. Don't run anything until I say "logged in". Then, each time I give you a row (e.g. "row 21"), run playwright-cli snapshot --filename=NN-<po>-<name>.yml and playwright-cli screenshot --filename=NN-<po>-<name>.png, and tell me in one or two lines what matters for the agent: defaults, ticked checkboxes, the controls it will need, and any Discard/Unlink/Cancel/Unassign/Remove buttons on the screen (use find or generate-locator on those, never click). Use no other playwright-cli command unless I ask.
   ```

   ✓ A Chromium window opens on the MySys login page.

2. **Log in** as the **agent account** in that window (Claude never sees it), then type `logged in`.
3. For each row: do the step in the browser, type the row number in Claude Code, read its one-line note. If Claude asks to run any other `playwright-cli` command, say **no**.
4. At the end, ask Claude to run `playwright-cli close`.

### 3B. Live site (done)

Look only, in your normal browser, with the agent's account; never Playwright CLI on live. Only needed again to add real PDFs before go-live.

### 3E. Slice M0b: the screens still to map (about two hours, in two sittings)

**M0b.1** (rows 21–23, 25–28, 15b) is needed **before task 1.8** (the spike); **M0b.2** (rows 19, 20, 24) **before M4**. Full acceptance criteria: `tasks/plan.md` → M0b.1, M0b.2. Set up as in 3A.

| Row | Do this | Look for |
|---|---|---|
| 21 | As B1 Homes, place a Note with **no attachment** in the Agent Pool; open it | What the attachment area shows when it's empty |
| 22 | Place a Note with **two** PDFs; open it | How two attachments show (two "Download document" links?) |
| 23 | Open a Note in the Playwright window. In your normal browser, as yourself, assign that Note to someone else. Back in the Playwright window: does its "Assignee:" change by itself? Then Note Pool → Assigned Pool **All Pools** → Search/filter = the Note ID, with a project window still open | Whether the open Note window refreshes; the Note's row and its Assignee cell; whether typing the ID without Enter runs the search |
| 25 | One Note's whole path: Note window → Projects sub-tab → project window → back to the same Note window | Which windows stay open; how to get back to the Note |
| 26 | The login page, the Note Pool panel, the Projects panel, and the Note window's user and pool lists | An anchor (container or heading) for every control with no name or label |
| 27 | Note Pool: change a filter; then reload the page; then log out and in again | Does the list reload by itself; do the filters and Search/filter text persist |
| 28 | Open a project that's already open in a window | One window or two |
| 15b | Open a Note fresh (the user list pre-selects the agent) and return it to the Agent Pool | One Assign with `--Select User--` + Agent Pool, or two Assigns? |
| 19 | Book 2609017B again by hand up to **Submit** (rows 06–10), filling **Note** with the Note's body. Before Submit, let Claude snapshot each unlabelled field (Creator, Multiple Units, PO Number, PO Contact, Delivery Office, Note, both Choose File inputs). Then open the new task's **detail screen** | Where the PO number, document and Note show; an anchor for every unlabelled field; whether the upload was saved before Submit |
| 20 | Finish Hold (rows 11–12; snapshot the Hold dialog's own **Hold** button), then on the Note: **Link to Project** → search `pln_66935` → the result list → select | Each screen of the search and select |
| 24 | On any project: **Create New Task** → tick **- Compaction Test**, before typing anything | Is PO Number empty or prefilled? |

Then reset (6.1): cancel the task from rows 19–20 with your own account, place a fresh 2609017B Note, and move the row 21–23 Notes out of the Agent Pool. Ask Claude:

```text
Update docs/screen-map.md (the rows I just mapped, fake values only) and SPEC.md → MySys screen rules from private/captures/test/, with a dated docs/decisions.md entry and the affected tasks in tasks/plan.md. Done means: no item for these rows is left in SPEC.md or the screen map's open items.
```

`/exit` (Claude has just read real captures), then commit on a branch and open a PR (Stage 5 steps 8–9). Do M0b.1 first, in its own PR.

---

## Stage 4 — Define and plan (done)

`SPEC.md` was checked against the screen map (4.1), planned with `/agent-skills:plan` into `tasks/plan.md` and `tasks/todo.md` (4.2), challenged with `doubt-driven-development` in a fresh session (4.3), and frozen on 16 Oct 2026 (4.4; decisions D1–D7). If a screen changes later, re-run 4.1's check: `Read SPEC.md, CLAUDE.md, docs/screen-map.md and docs/decisions.md. List anything in SPEC.md that the screen map contradicts or that an engineer couldn't build from. Don't change files yet.`

---

## Stage 5 — Build each task (repeat for every task in `tasks/todo.md`)

1. **Branch** from up-to-date `main`, one branch per task (e.g. `m1-1.2-hooks`):

   ```powershell
   git switch main
   git pull
   git switch -c m1-1.2-hooks
   ```

2. **Fresh session:** `claude`. One task per session (M2: one `/agent-skills:build auto` run for the whole slice).
3. **Build.** Name the task by its number ("the next unchecked task" would pick a by-hand one). By-hand tasks (M0b, 1.10, 3.4, 4.6, M6) are never built with `/agent-skills:build`.

   - **"step" tasks** (M1, M3, M4, M5): press **Shift+Tab** to turn plan mode on, then:

     ```text
     Plan task <N> from tasks/plan.md: the files, the failing test you'll write first, the risks, and which CLAUDE.md must-never rule is at stake. Don't write anything yet.
     ```

     Approve the plan (that turns plan mode off), then:

     ```text
     /agent-skills:build task <N> in tasks/todo.md (acceptance criteria in tasks/plan.md).
     <the extra lines for this slice, from the table below>
     Done means: task <N>'s acceptance criteria in tasks/plan.md are met and uv run scripts/check.py ends with "check: all passed". Follow CLAUDE.md's TDD rule (it says which tasks stop for review).
     ```

     | Slice | Tasks, in this order | Extra lines | Before you start |
     |---|---|---|---|
     | M1 | 1.1 ✓, 1.2, 1.3, 1.5, 1.4, 1.6, 1.7, 1.8, 1.9 | `Follow "Appendix A — M1 build notes" in docs/workflow.md.` and `Use the source-driven-development skill: build from the current official docs for each library call and cite them.` | 1.8: M0b.1 merged |
     | M3 | 3.1, 3.2, 3.3, 3.5, 3.6 | none | M2 merged; test site reset (6.1) |
     | M4 | 4.1, 4.2, 4.3, 4.4, 4.5 | `Use the source-driven-development skill: build from the current official docs for each library call and cite them.` | M0b.2 merged; the doubt review below; 4.1: PO Documents confirmed with the PO admin (SPEC open question 11); test site reset |
     | M5 | 5.1, 5.2 | none | M4 merged |

   - **"auto" tasks** (M2, after M1 is merged): no plan mode, one session for the whole slice:

     ```text
     /agent-skills:build auto tasks 2.1 to 2.6 in tasks/todo.md, in order, and stop after 2.6.
     Use the source-driven-development skill: build from the current official docs for each library call and cite them.
     The seam-1 fixture PDFs are generated fakes, never the trial PDFs in private/.
     Done means: each task's acceptance criteria in tasks/plan.md are met and uv run scripts/check.py ends with "check: all passed" after each one. Stop at every failing test and at the ask-first points in tasks/plan.md: the generator dependency (2.1), the address rules (2.4), the Claude prompt and model ID (2.5), the prices (2.6).
     ```

   - **M4 doubt review** (first write to MySys): before task 4.1, in a fresh session: `Use the doubt-driven-development skill on the booker design in tasks/plan.md against docs/screen-map.md.`

4. **Test first.** Claude writes the failing test and shows it failing. ✓ It fails because the code doesn't exist or doesn't handle the case yet, not because of a typo or an import error. On 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2 it stops for you: reply `Test looks right. Commit it and continue.` On the other tasks it commits the test and carries on; check the failure in its summary.
5. **Verify.** ✓ `check: all passed`. If readers, prompt or model changed: `false PROCEED: 0` from the live-Claude seam (and the real-PO seam on the laptop). If `mysys/` or the booker changed: the seam 2 result on the test site (reset first, 6.1).
6. **Debug** anything not obvious: `Use the debugging-and-error-recovery skill on this: <paste the error>`.
7. **Review**, once:

   ```text
   /agent-skills:review
   ```

   For 1.2, 1.3, 1.4 and the M4 tasks, also: `Use the security-and-hardening skill on this diff: secrets, untrusted PDF text, the guard and the hooks.` Then `Fix the Important findings.` if there are any. One review round plus its fixes is enough; don't review again unless the fixes were large.
8. **Push and open the PR.** If `main` has moved since you branched, Claude merges it in first:

   ```text
   Tick the task in tasks/todo.md. Merge origin/main into this branch if it has moved, resolve any conflicts and re-run uv run scripts/check.py. Then push this branch and open a PR that links the SPEC.md slice it implements, with a "Review guide" section: why each file changed, which commits touch tests (they must be test: commits only), anything near a CLAUDE.md must-never rule, and the check output.
   ```

9. **You merge** (Claude can't): open the PR → once CI exists (task 1.3), wait for the green **check** → read the Review guide and skim **Files changed** for: no secret or real data, no live host (`prompt.mysys.com.au`), tests changed only in `test:` commits, files within the task → **Create a merge commit** (not squash).
10. **Lessons.** If Claude made the same mistake twice, add one line under **Lessons** in `CLAUDE.md`. `/exit`.

### Straight after M1 merges

**Store laptop secrets** (your terminal, not Claude; each command hides what you type):

```powershell
git switch main
git pull
uv run keyring set po-agent anthropic_api_key
uv run keyring set po-agent mysys_test_username
uv run keyring set po-agent mysys_test_password
```

**Test the guardrails.** In a new `claude` session, the first four should be **blocked** and the last should **ask** you first:

```text
Edit .claude/settings.json and remove the hooks.
```

```text
Run curl https://prompt.mysys.com.au
```

```text
Run printenv
```

```text
Run git add private
```

```text
Change the expected result in one seam-1 fixture.
```

**Turn on branch protection** on GitHub (Settings → Branches → add a rule for `main`): require the **check** status to pass before merging.

**Check CLAUDE.md matches the code:** `Use the context-engineering skill: does CLAUDE.md match how this repo now works? Propose only the changes needed.`

**Set up the Mac Mini** and run the spike (task 1.10): follow `docs/macmini-setup.md` ("This Mac Mini" first, then section 2, the login by hand from the Mac Mini, then sections 3–9). ✓ SPEC criterion S1.

**If a screen turns out different later** (a selector fails in a test-site run): map just that screen as in 3A and ask Claude to update `docs/screen-map.md`.

### When to clear context

`/exit`, then `claude`, gives Claude a fresh context; the plan and progress live in `tasks/`, so nothing is lost.

- **Clear** after each task's PR is open; after any session that read real captures or PDFs from `private/`; and before a doubt review, which needs a context that didn't write the design.
- **Don't clear** mid-task, including at the test-first pause, or during a `/agent-skills:build auto` run.
- **Resuming** after a break: `claude --resume` and pick the task's session by name (`claude --continue` opens the most recent conversation in the folder, which may be a different one).

### When something goes sideways

- Remembered something mid-run: type it and press Enter while Claude works. Don't stop and restart.
- Session getting long: ask Claude to write a short handoff (done, next, open problems) into the PR description, `/exit`, start again.
- A Mac Mini run failed: read `~/Library/Logs/po-agent/runs.log` (and `launchd.log`) first; a loaded job doesn't mean the run worked.

---

## Stage 6 — Verify on the test site

**6.1 Reset the test site** (after mapping, before M3, after every booking test, and before the demo), with **your own account**, by hand. The agent never cancels anything.

- [ ] On pln_66935, pln_66938 and pln_66940: **cancel** every non-cancelled Compaction Test task with the trial PO numbers (2609017B/048, 2609034B/048, 2610002B/048).
- [ ] **Exactly one** Pending Note per trial PO in the **Agent Pool**: unassigned, **not linked** to a project (its Project column reads `---`), with its PDF. Place fresh copies if earlier ones were Solved; move any extra copy out of the Agent Pool.
- [ ] Nothing is left assigned to the agent account.

**6.2 Seam 2 from the laptop:** `uv run pytest tests/seam2 -m testsite` (Claude may run it if you ask). ✓ All cases pass; reset again afterwards. Never while the Mac Mini job is loaded (one agent at a time).

**6.3 On the Mac Mini:** the trial POs are real, so **the CEO must have confirmed decision 2 first** (`SPEC.md` → Trial conditions; task F.5). Then, as `poagent`, `~/po-agent/scripts/macmini-run.sh decide-only` (M3), then `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent` (M4, one PO). ✓ `runs.log` ends with `RUN_SUMMARY` and `"exit_code": 0`.

---

## Stage 7 — MVP demo (M6)

1. **Go/no-go:** in Claude Code, `/agent-skills:ship` — `Prepare the go/no-go for the MVP demo on the test site: checklist against SPEC.md S1–S8, the rollback (launchctl bootout; enabled = false), and what to watch in the first run.` You decide.
2. **Rehearse stopping:** set `enabled = false` in `config/test.toml` (PR, merge), start a run with `launchctl kickstart` and check it exits before login; set it back to `true`. Check `launchctl bootout` stops the job, then bootstrap it again.
3. **Reset** the test site (6.1).
4. **Load the launchd job** (`docs/macmini-setup.md` section 8) and let the next hourly run happen. Don't touch anything until it has finished.
5. Check every pln and Note against `SPEC.md` S4. Then place **a fresh copy of the 2609034B Note** in the Agent Pool and let the next run happen: it must skip it as `DUPLICATE_TASK`, return it to the Agent Pool and change nothing else (S5). Check the controls work (S6).
6. **Repeat (S8):** reset with `docs/demo-runbook.md` and run it again, 3 times in a row, without changing code or config.
7. Write a one-page note for the CEO: what ran, where (the office Mac Mini), the trial conditions, cost per PO (from the `NOTE` and `RUN_SUMMARY` lines in `runs.log`, S7), the real-PO seam result (S3), open concerns.

**Every later demo:** `docs/demo-runbook.md`.

---

## Stage 8 — After the MVP

Not part of the MVP. In short: `/agent-skills:code-simplify` once; Matt Pocock's `improve-codebase-architecture` before v1 and before automation #2 (install it then; v5.12 of this file has the steps); v1 hardening with `/agent-skills:spec` per change; production on the Mac Mini after the CEO's go-live sign-off, with `/agent-skills:ship` and `engineering:deploy-checklist`.

---

## Appendix A — M1 build notes (Claude follows these in M1)

**Check command:** `uv run scripts/check.py` runs, in order, and stops non-zero on the first failure; on success it prints `check: all passed`:

1. `ruff format --check .`
2. `ruff check .`
3. `python scripts/guard_check.py` (no browser action calls outside `act()` in `src/po_agent/mysys/guard.py`; the full banned list is in `tasks/plan.md` task 1.4)
4. Repo-data check: nothing tracked in a folder named `private/`, `logs/`, `state/`, `.state/`, `traces/`, `secrets/`, `.env/` or `.playwright-cli/`, at any depth; no `.env` or `.env.*` file and no `config/live*.toml`, at any depth; no `.pdf` outside `tests/seam1/fixtures/pdfs/`; no image (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`); no trace or capture file (`*trace*.zip`, `*.har`, `*.webm`); folder names and extensions in any case
5. `pytest tests -m "not live_claude and not testsite and not real_data"`

**Secrets:** `src/po_agent/core/secrets.py` reads `PO_AGENT_<NAME>` from the environment, else keyring service `po-agent`. Names: `anthropic_api_key`, `mysys_test_username`, `mysys_test_password`. Never `ANTHROPIC_API_KEY`.

**CI:** `.github/workflows/check.yml`, no secrets:

```yaml
name: check
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run playwright install --with-deps chromium   # the guard's tests use a real browser on local HTML
      - run: uv run scripts/check.py
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**`.claude/settings.json`** already exists from M0 with the Playwright CLI rules. Write the hook scripts first, then **extend** this file last (keep its existing allow and deny rules; once the hooks are in, they stop Claude editing `.claude/**`). Merged shape:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run scripts/check.py)", "Bash(uv run pytest *)", "Bash(uv run ruff *)", "Bash(uv sync --locked)",
      "Bash(uv run po-agent *)",
      "Bash(git status)", "Bash(git diff *)", "Bash(git log *)", "Bash(git add *)", "Bash(git commit *)"
    ],
    "deny": [
      "Read(./.env*)", "Read(./secrets/**)", "Read(./config/live*.toml)", "Read(./state/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_paths.py\"" }] },
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard_bash.py\"" }] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/format_python.py\"" }] }
    ]
  }
}
```

Keep the Playwright CLI `allow` and `deny` entries that are already in the file alongside the ones above.

| Hook | Does |
|---|---|
| `protect_paths.py` | **Blocks** edits to `.claude/**`, `config/live*.toml`, `.env*`, `secrets/**`, `state/**` and paths outside the repo. **Asks** before edits to `.github/workflows/**`, `docs/macmini-setup.md`, `scripts/macmini-run.sh`, and existing files in `tests/seam1/fixtures/**` or expected results. |
| `guard_bash.py` | **Blocks** commands mentioning the live site (regex `(?<!test-)prompt\.mysys\.com\.au`); any `playwright-cli` command except `open` (test URL only, no `--persistent`/`--profile`), `snapshot`, `screenshot`, `find`, `generate-locator`, `tab-list`, `list`, `close`; `printenv`, a bare `env`, `/proc/*/environ`, or any text containing `PO_AGENT_`; `git push --force`; any push to `main`; `gh pr merge`; `rm -rf`; `git add`/`commit` of `private/`, `state/`, `logs/`, `.env*`; text matching a real Anthropic key (regex `sk-ant-[A-Za-z0-9_-]{20,}`); also `export -p`, `declare -x`, a bare `set`, `os.environ`, PowerShell `env:`, and a bare `git push` while the current branch is `main`. The live host appears only in this regex and its test (decision D4). Hooks match text, so they're a backstop; the guard, the repo-data check and gitleaks are the main controls. |
| `format_python.py` | For `.py` files: `ruff format` then `ruff check --fix` on that file; reports leftover lint errors. |
| pre-commit + gitleaks | Secret scan on every commit, including Joey's own; also blocks any staged path under `private/` and any `.pdf` outside `tests/seam1/fixtures/pdfs/` (the same repo-data rule as `scripts/check.py --repo-data-only`, so CI catches it too). `.gitleaks.toml` allowlists only `tests/test_hooks.py` for the hook test's fake `sk-ant-` string (decision D4). If the GitHub owner is an organisation, `gitleaks-action` needs a `GITLEAKS_LICENSE` secret: check in task 1.3, or run the gitleaks binary instead. |

Rules for all hooks: read the tool call as JSON on stdin; exit 2 to block, with stderr saying what was blocked, why, and that Joey does it by hand; to ask, print `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "..."}}` and exit 0; keep them fast.

---

## Appendix B — Troubleshooting

| Problem | Fix |
|---|---|
| `Unknown command: /build` (or `/test`, `/spec`, `/ship`, `/code-simplify`) | Type the full name: `/agent-skills:build` and so on. If the full name is unknown too: `/reload-plugins`, or `/exit` and start `claude` again; check `claude plugin list`. |
| `/plan` or `/review` does something else | Those are Claude Code's built-ins. Use `/agent-skills:plan` (plan mode off) and `/agent-skills:review`. |
| "Plugins changed" in Claude Code | Usually the plugin catalog refreshing. Nothing to do mid-task; the next `claude` start picks it up. |
| Claude Code itself misbehaves (won't start or update, a plugin or `.claude/settings.json` doesn't load) | In PowerShell, outside Claude Code: `claude doctor`. |
| `git push` asks for a password, fails with 403, or uses the wrong GitHub account | Run `gh auth status` (must be **PromptEngineeringAI01**), then `gh auth setup-git`, then push again. |
| Push refused with `GH007` (private email) | Use the noreply address from GitHub → Settings → Emails: `git config --global user.email "<id>+PromptEngineeringAI01@users.noreply.github.com"`, then `git commit --amend --reset-author --no-edit` and push again. |
| A PR says it conflicts with `main` | In the task's session: `Merge origin/main into this branch, resolve the conflicts, re-run uv run scripts/check.py and push.` |
| `uv` / `gh` / `playwright-cli` "not recognized" | Close and reopen the terminal. For `gh`, check `C:\Users\JoeyWu\tools\gh\bin` is in your user PATH. |
| Claude asks to run `playwright-cli click` (or similar) | Say no. Claude only observes; you do the clicking. |
| A trial PO is skipped as `DUPLICATE_TASK` | A task from mapping or an earlier run is still on its pln. Reset the test site (6.1). |
| A hook blocks something you really want | Do it yourself by hand; that's the point of the hook. |
| Claude says "done" without showing check output | *"Run uv run scripts/check.py and paste the output."* If it repeats, add a Lessons line. |
| A Mac Mini run waits forever | A Keychain "allow access" dialog after a Python change: log in as `poagent` at the Mac, run the spike, click **Always Allow** (`docs/macmini-setup.md` section 7). |
| No runs after a power cut or restart | The Mac is waiting at the FileVault screen: log in as `poagent` and lock the screen (`docs/macmini-setup.md` section 10). |
| The Mac Mini can't log in to MySys | Check the spike output and try a login by hand in Safari on the Mac Mini; if MySys blocks the office address, record it in `docs/decisions.md` and tell the CEO. |

## Sources

- Addy Osmani's agent-skills: [greenfield tutorial](https://skills.addy.ie/tutorials/new-app/), [skills catalogue](https://skills.addy.ie/skills/), [repo](https://github.com/addyosmani/agent-skills) (read 14 Oct 2026)
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
