# PO Agent - decision log (updated 9 Nov 2026, go-live)

Source of truth for decisions behind `docs/intent.md`, `SPEC.md` (MVP) and `docs/specs/` (v1 spec pack v1.2, ADR-001, ADR-002). If any spec disagrees with this log, this log wins. Author: Joey Wu.

After `tasks/plan.md` is approved (the freeze point), add a dated entry here for every change to what the agent does in MySys or prints in its run output, and for anything that loosens a safety control, in the same commit as the `SPEC.md` changes (`tasks/plan.md` only when a task's plan changes; 5 Nov 2026). Tightening a dev-tooling rule needs only a clear commit message (24 Oct 2026, below).

## Status

- **13 Oct 2026: the CEO approved decision 1** of the CEO decision brief: the two-reader design, its safeguards, and a trial on the test site with 3 fake POs. The build can start.
- **15 Oct 2026: the CEO made decision 3:** the agent runs on the **office Mac Mini** (already purchased), for the MVP trial and for production (entry below).
- **25 Oct 2026: decision 2 made.** The CEO delegated decision 2 (Claude reading real client POs) to Joey, and approved the trial PDF sitting briefly on the Mac Mini's disk (D2). Joey: yes, on the Trial conditions terms (entry below).
- **28 Oct 2026: MVP demo shown** on the test site: the supervised `po-agent demo` booked 2609017B from the laptop and the Mac Mini (PRs #19-#30).
- **29 Oct 2026: production started** (entry below).
- **29 Oct 2026: go-live gate 1 met.** MySys allows automating the workflow on the website; no API (entry below).
- **30 Oct 2026: task sessions run in worktrees;** `protect_paths` applies the repo rules inside them (entry below).
- **2 Nov 2026: Claude merges verified PRs and edits skills** (entry below).
- **2 Nov 2026: decide-only built** (task 3.3; entry below).
- **2 Nov 2026: run controls built** (task 3.5; entry below).
- **2 Nov 2026: Claude reader dropped.** The agent reads with two code readers and checks the address against MySys, so it costs nothing per PO (entry below). Joey informs the CEO, who approved the two-reader design with Claude as one reader (decision 1).
- **3 Nov 2026: M0b.2 mapped** (rows 19, 20, 23, 24; entry below). Every screen the MVP books through is now mapped.
- **3 Nov 2026: assignee check and stale-Note stop built** (task 3.6; entry below).
- **3 Nov 2026: M4 gate review** of the booker design (4.1-4.5; entry below).
- **3 Nov 2026: W1 built** (task 4.1; entry below).
- **4 Nov 2026: W1 review fixes** (task 4.1 follow-up; entry below).
- **4 Nov 2026: W2 built** (task 4.2; entry below).
- **4 Nov 2026: W3 built** (task 4.3; entry below).
- **4 Nov 2026: W4 and W5 built** (task 4.4; entry below).
- **4 Nov 2026: production operations planned** as go-live gate 6 (tasks 7.1-7.7; entry below).
- **4 Nov 2026: ADR-003 proposed** (`docs/specs/ADR-003-more-clients.md`): two more clients later, one rules package each behind a seam extracted when the second client is real; a read-only peek for a client known only from its PDF; no LLM framework. Nothing changes until then.
- **5 Nov 2026: run mode built** (task 4.5; entry below). Plain `run` books.
- **5 Nov 2026: a lighter build process** (entry below).
- **5 Nov 2026: M4 security pass, three Nits fixed** (entry below).
- **5 Nov 2026: heartbeat built** (task 7.1; entry below): a scheduled GitHub Action, not healthchecks.io.
- **5 Nov 2026: silent-skip alert and more pages** (task 7.2, M4 Nit #3; entry below).
- **6 Nov 2026: Claude on the Mac Mini's `poagent` account, test site only** (ADR-002 gate H2 waived for the test site; entry below).
- **6 Nov 2026: faster shipping** (decision batch, verify by CI, test-site queue, Must never #8 pre-authorised; entry below).
- **9 Nov 2026: release pinning built** (task 7.4; entry below): the Mac Mini runs the `production` tag; `enabled` is read from `origin/main`.
- **9 Nov 2026: CMU 06-643 practices** (GitHub protections on, print and debugger calls banned by ruff, CI timeout; entry below).
- **9 Nov 2026: 5.2 closed without the last seam-2 booking runs;** they are checked in the first P5 booking run instead (entry below).
- **9 Nov 2026: one error-report path** (task 8.2; entry below): `RunLog.error` goes, so its test changes.
- **9 Nov 2026: go-live plan.** The CEO gave Joey full authority for every go-live decision. P5's week is skipped, gates 2-5 are met or reshaped, code is frozen until live runs hourly (entry below).

## 9 Nov 2026 - Go-live plan: Joey decides, P5 skipped, code freeze (Joey)

- **Authority:** the CEO gave Joey full authority for every go-live decision (9 Nov 2026). Wherever `SPEC.md`, `tasks/plan.md` or this log asks for the CEO's go-live sign-off, Joey's decision, recorded here, is that sign-off. Must never #3 is still changed only by Joey, by hand, with the live-profile task.
- **Target:** live as fast as is safe, within 3 days (by 12 Nov 2026). Safety comes from the deterministic controls (guard, hooks, assignee check, read-backs before and after every write, kill switch, `production` tag) and from the watched live order, not from more test ceremony. None of those controls changes here.
- **Decisions**, each marked whether it loosens a gate or control:
  1. **P5 is skipped** (the week of hourly test-site runs, gate 5's first half). The 5.2 trace check (entry below) moves from P5's first booking run to the **first live booking, which is watched**: in that run's safe trace, every `assign_note`, `link_to_project`, `link_select_project` and `mark_solved` has an ok `email_notification_unticked` after both the Note's latest ok `assignee_check` and its previous Note-window write (D7), and only that Note's `note_id` appears. Joey pastes the `grep <run_id>` trace lines; Claude checks them (Claude doesn't read the Mac Mini's logs). A miss, or no booking in that run, stops the live order: `enabled = false` on `main` before any second booking, and a fix. **Loosens?** Yes, gate 5: no unattended week on the test site. Instead the first live bookings are watched one PO per run, and the guard, assignee check and Send Email read-back are unchanged in code.
  2. **Real POs:** only 3-5 real B1 `/048` POs exist, not 10-20. The real-PO seam (`uv run pytest tests/seam1 -m real_data`, laptop, `private/`) runs on those, with `false PROCEED: 0`; coverage is reported, not judged against 80%. Live `run --decide-only` is the wider real-PO check: it reads and decides on every eligible live Note and writes nothing; Joey reads its NOTE lines (PO number, pln, skip reason) against the Notes in MySys before the first booking run. **Loosens?** Yes, gate 5's second half and S3's 80% line.
  3. **Audit N4** (alert issues in a public repo would carry live Note IDs): **the repo stays public**, and the alert issue body drops `note_id`; the Note stays named in `runs.log` on the Mac Mini, which is where `docs/ops-runbook.md` sends the reader. Built in the live-profile task, before any live run. Joey chose this over a private repo: on a free personal account a private repo loses branch protection on `main` and GitHub's push protection, and gets 2,000 Actions minutes a month, while CI used about 1,680 in the 16 days to 9 Nov and the heartbeat needs about 480 a month; past the cap CI and the heartbeat stop without a word. GitHub Pro (about US$4 a month) was the alternative. **Loosens?** No: it removes live identifiers from a public place.
  4. **Gate 2 by Joey's own look at live:** Joey logs in to live MySys with the agent's account by hand, opens one `/048` Note and the Create New Task form, saves nothing, and reports: PO Documents or Documents; Resolve or Solved; live's Client Ref No. column holds `<internal no>/048`; whether the agent's password expires. The same look also reports (added by the advisor, 9 Nov 2026): the live pool's name and the agent's user name as the Assign list shows them; the `/048` Note title format (`[B1 Homes] Order <internal no>/048`); and **how many Pending Notes the Note Pool lists with Assigned Pool = All Pools, Locked/Unlocked = All and Assigned User = All Users** (the stale-Note read, D6): more than one page (50) stops every run with `MORE_PAGES` (entry 5 Nov 2026, 7.2), which would be a code change. Any difference from the test site is a code change and moves the date. **Loosens?** No: the PO admin's written answers become Joey's direct look.
  5. **Gate 3:** Joey signs off (Authority above). **No backlog cut-off:** every `/048` Note in the agent's pool is processed like a new one; one already booked by a person skips `DUPLICATE_TASK` and goes back to the pool. No code change. **Loosens?** No: it is the behaviour the code already has.
  6. **Code freeze** until live runs hourly: only fixes for what go-live finds, and the live-profile task. Tasks 8.1, 8.3 and 8.4 wait until after. Task 8.2 (PR 88) was merged earlier on 9 Nov, before the freeze reached it; it stays, since it changes no output line or exit code (its entry below), and it reaches live only with the go-live commit, after the live spike and decide-only have run it. **Loosens?** 8.4 (its retry refuses committing clicks) was a tightening planned before go-live; live starts without it. Today's retry is the proven demo one, and the booker's read-backs stay.
  7. **Dropped:** 6.1-6.4 (the M6 demos, superseded by the 28 Oct demo and P4) and 7.6's formal triage loop. Alerts are handled with `docs/ops-runbook.md`. **Loosens?** Yes, 7.6 (part of gate 6): an alert is no longer closed with one of four recorded outcomes.
  8. **Gate 4 and the heartbeat** are needed before **unattended hourly live runs**, not before the watched ones (live spike, decide-only and one-PO runs, all with Joey there): a named backup admin for the Mac Mini, and `gh workflow enable heartbeat`. The Mac Mini's GitHub token and the `po-agent-alert` label are already in place. **Loosens?** Yes, gate 4 and 7.1 move later, while Joey is watching each run.
- **Unchanged before any live contact** (read-only spike included): gate 1 (met 29 Oct); ADR-002 H2 passes again (Claude and every other AI tool removed from `poagent` before any live credential reaches the Mac Mini; entry 6 Nov 2026); live secrets only in `poagent`'s Keychain under their own names; the Mac Mini runs the `production` tag, moved by Joey to the go-live commit; Claude never runs anything against the live host.
- **Live order**, each step with its own dated entry here: read-only `spike` on live → `run --decide-only` on live → `run` booking one PO per run, watched (the trace check in item 1 on the first) → full hourly runs.
- **Next:** the live-profile task (live config only on the Mac Mini, `config/live*.toml` stays out of the repo; its own keyring names; the wrapper and kill switch for live; item 3's `note_id` drop) is designed with Joey, gets its own entry, and is built with a second-model review.
- Carried in: `SPEC.md` v1.32 (Production; S3), `tasks/plan.md` (Phase P), `tasks/todo.md`.

## 9 Nov 2026 - One error-report path: `RunLog.error`'s test changes (Joey, task 8.2)

- **Why:** task 8.2 (`docs/architecture-review.md` -> Round 2 -> B, settled by Joey 9 Nov 2026) replaces `cli._log_traceback` and the dead `RunLog.error` (no caller in `src/`) with one module-level traceback writer, `runlog.write_traceback`. `tests/test_runlog.py` called `RunLog.error`, so that test now writes the `error` event with `RunLog.event` (as `core/run.py` does) and the traceback is covered by the writer's own tests (Must never #8; 6 Nov 2026).
- **Unchanged:** every ALERT, NOTE and RUN_SUMMARY line, every exit code and the run log's line format. No `SPEC.md` change: nothing the agent does or prints changes.

## 9 Nov 2026 - 5.2 closed; its last booking runs are checked in P5 (Joey)

- **Why:** of 5.2's fixed seam-2 sequence (`tests/seam2/README.md`), runs 1-6 and 12a (`guard.vet()` refuses Discard on a real Note window, D3) passed on 6 Nov (PR 74), and run 9 (W4/W5) passed after the W2 fix (PR 75). Only the full booking runs were left: 10 (`test_run_book`), 11 (fresh copy skips `DUPLICATE_TASK`, non-`/048` untouched) and 12b (Send Email read back unticked after the latest assignee check before every Note-window write). They need about three more resets. Joey has tested a lot already and chose not to run them now.
- **Decision:** 5.2 is closed without runs 10, 11 and 12b. Run 11's skip was already proven on the site in 4.5 (S5).
- **Instead, in P5:** the first scheduled booking run of the P5 week is the first full booking after the W2 fix. Before the week counts, Claude checks that run's safe trace (`SPEC.md` -> Safe trace; allowlisted fields only): every trial Note's `assign_note`, `link_to_project`, `link_select_project` and `mark_solved` has an ok `email_notification_unticked` after both the Note's latest ok `assignee_check` and its previous Note-window write (D7), and every `note_id` in the trace is a trial Note. Any miss, or no booking in that run, stops the P5 week until it is fixed (and the job is unloaded).
- **Loosens?** Yes, a test gate before P5 (not a runtime control): the same checks move from a watched seam-2 run to the first unattended run on the test site. The guard, the assignee check and the Send Email read-back are unchanged and still enforced in code. No `SPEC.md` change: nothing the agent does or prints changes.

## 9 Nov 2026 - Release pinning: the Mac Mini runs the `production` tag (Joey, task 7.4)

- **Why:** the wrapper pulled `main` before every run, so every merge reached the Mac Mini within the hour. On live, a commit should reach it only after it has run on the test site and Joey has chosen it.
- **Decision:** each run, `scripts/macmini-run.sh` runs `git fetch --force --prune --prune-tags origin` (so a moved tag updates and a deleted one disappears), reads `enabled` from `config/test.toml` on `origin/main`, then checks out the `production` tag's commit (detached HEAD), runs `uv sync --locked` and the Playwright install, and runs the agent. `runs.log` gets `wrapper: running production <first 12 characters of the commit>`. No `git pull` any more.
- **Kill switch path (Joey, 9 Nov 2026):** `enabled` is read from `origin/main`, not from the tag, so `enabled = false` merged to `main` still stops the next run without a tag move. Then the wrapper logs `wrapper: enabled = false on main, agent not run`, checks out nothing, opens no alert issue and exits 0 (as the agent's own kill switch does). The agent's own reads of `enabled` (run start and `before_write`) read the checked-out tag's file, so a run goes ahead only when both say `true`; mid-run they never saw a change to `main` anyway, since a run fetched only at its start.
- **Fails closed:** a failed fetch, a missing `production` tag, a failed checkout, or `config/test.toml` on `origin/main` without exactly one `enabled = true` or `enabled = false` line (a trailing comment allowed) runs nothing: `wrapper: setup failed (<step>), agent not run`, the alert issue, exit 2, as a failed pull did. It never falls back to the code already on disk.
- **Who moves the tag:** Joey only, by hand on his laptop (`docs/macmini-setup.md` section 8, "Moving the production tag"). Claude never creates, moves or pushes it, in code, docs or commands; the wrapper calls no `git` tag, push or pull command (a test checks the script).
- **Rollback:** move the tag back to an earlier commit; never to one from before this change, whose wrapper runs `git pull`, which fails on a detached HEAD.
- **Loosens?** No: it tightens what reaches the Mac Mini. `SPEC.md` v1.31: Tech Stack 8, Commands, Project Structure, S6. `docs/workflow.md` Ground rules: merging no longer deploys, except `enabled`.

## 9 Nov 2026 - CMU 06-643 practices: GitHub protections, print ban, CI timeout (Joey)

- **Why:** Joey compared the project with CMU 06-643 (s26) lectures 06-09 (code quality, debugging, GitHub collaboration, GitHub Actions). The repo is public and `main` was not protected, although `docs/workflow.md` (Straight after M1 merges) asked for it.
- **Adopted** (Joey picked all five):
  1. **Branch protection on `main`:** a pull request and the `check` status are required before a merge; no force push, no deletion. No approving review is required (one account can't approve its own PRs). Enforced on admins too (Joey, 9 Nov 2026): Claude works through Joey's admin account, and the Mac Mini pulls `main` until the `production` tag (7.4), so nothing unchecked may reach `main`. If CI itself is broken and a merge can't wait, Joey turns the protection off in Settings, merges, and turns it back on.
  2. **ruff T20 and T10:** `print` is an error under `src/` except `core/output.py`, so CLAUDE.md's "only output.py prints" rule is now checked, not just written; a debugger call (`breakpoint()`, `pdb`) is an error everywhere, since a left-over one would stop an unattended run and print source lines into the run log.
  3. **Secret scanning and push protection** on GitHub: a known secret is refused at push time, before it is public. gitleaks in pre-commit and CI stays.
  4. **Dependabot alerts** (security alerts only, no update PRs): pypdf and pdfplumber read untrusted PDFs, and pinned versions only stay safe if someone hears about their CVEs.
  5. **`timeout-minutes: 30`** on the CI check job (runs take 10-20 minutes; GitHub's default is 6 hours).
- **Not adopted:** mypy (a trial run found 15 errors; the ones checked were false positives from pydantic defaults and narrowing, and fixing them means casts in `guard.py`), coverage gates, OS or Python matrix, caching, badges, `act`, PR and issue templates, ruff docstring rules, CODEOWNERS reviews (one account can't approve its own PRs).
- **Loosens?** No: all five tighten. Items 1, 3 and 4 are GitHub settings, not repo files. No `SPEC.md` change: nothing the agent does or prints changes.

## 9 Nov 2026 - PO number suffix is always exactly /048 (Joey)

- **Why:** the code review audit (`docs/code-review-audit.md`, PR 81) found that `_PDF_PO` in `src/po_agent/b1/reader_rules.py` has no right anchor, so a PDF reading `2609017B/0481` or `2609017B/048X` is read as `2609017B/048` (audit I1, reproduced with fake values).
- **Joey's answer:** a B1 Homes PDF never shows anything after `/048` ("Never", 9 Nov 2026; earlier "/048X will never happen"). So the rule can't misread a real B1 PO.
- **Decision:** audit I1 is accepted and moved to the Nits (N6); no regex change.
- **Revisit:** if a second client or another PO suffix appears.

## 6 Nov 2026 - Faster shipping: fewer waits on Joey (Joey)

- **Why:** Joey asked whether cmux, Claude Code agent teams, git worktrees, QA automation or gstack would ship faster (the Claude Code power-user tips article). The slowest part is waiting for Joey: a task stopping to ask him, a seam-2 run waiting for his reset, his reserved merges. More parallel agents don't shorten that.
- **Not adopted:**
  - cmux: macOS only. Joey builds on Windows, where the Claude Desktop Code tab already runs parallel worktree sessions.
  - Agent teams: experimental, and in-process teammates can't be resumed. The advisor plus linked worktree sessions already covers the work.
  - gstack, for this repo:
    - `/ship` and `/land-and-deploy` merge and deploy (Must never #9; a merge deploys to the Mac Mini).
    - `/qa` and `/browse` click pages (Must never #1).
    - It sends code to another provider for review by default.
    - It installs hooks and needs `.claude/` changes (Joey's).
    - Joey may use it in other projects.
  - Git worktrees are already the build loop.
- **Adopted:**
  1. **Decision batch:** at the start of each phase or week, the advisor asks Joey every foreseeable choice for the next few tasks at once, records them here, and task briefs carry them under "Decided already" (`docs/workflow.md`, Production build loop step 0; `.claude/skills/start-task/SKILL.md`).
  2. **Verify by CI:** CI runs `scripts/check.py` on the PR's head commit. `/verify-pr` takes that instead of re-running the check locally (12-55 minutes), unless the PR touches `scripts/check.py`, `.github/workflows/`, `pyproject.toml` or `uv.lock`. The skill is Joey's file: the advisor hands him the patch.
  3. **Test-site queue:** seam-2 and decide-only runs from several tasks share one reset where their order allows. The advisor keeps the queue and asks Joey for one reset per batch (Production build loop step 10; plan Cross-cutting rules).
  4. **Must never #8, pre-authorised case:** a `test:` commit may change an existing expected result without asking Joey when the PR says it is an intended behaviour change and carries the decisions entry that made it. `/verify-pr` checks both and quotes them. Everything else under #8 stays: never edit a test to make it pass. Joey changes the CLAUDE.md line by hand.
  5. **Answer from the phone:** Remote Control for all sessions, so Joey can answer a waiting session from the Claude mobile app. It is disabled by the organisation's admin today (6 Nov 2026); until it is allowed, desktop banners (the default) are the signal. A desktop setting, no repo change.
- **Who merges (Joey, 6 Nov 2026, later the same day):** Joey stops approving PRs one by one. Only PRs that touch the guard (`guard.py`, `guard_check.py`), the hooks (`.claude/hooks/`, `.claude/settings*.json`) or CI (`.github/workflows/`) stay his to merge. Claude merges every other PR once `/verify-pr` passes, with the same pinned command. That includes PRs touching `scripts/check.py` or the verify-pr skill, and docs that loosen a rule, which still need their decisions entry. Must never #9 and the `/verify-pr` merge condition say so; the skill line is Joey's hand edit, since a hook protects that file.
- **Open, Joey's:** ask the MySys admin for reusable test Notes on the test site, so seam 2 stops consuming the 3 trial POs and needs fewer resets.
- **Loosens?** Yes, three controls: the local re-run of the check before a merge (CI on the same commit still runs it), #8's approval step for intended behaviour changes, and Joey's merge of PRs outside the guard, hooks and CI. Joey told Claude to merge this PR after review (6 Nov 2026).
- Carried in: `docs/workflow.md` (Production build loop steps 0, 7 and 10), `tasks/plan.md` (Cross-cutting rules), `.claude/skills/start-task/SKILL.md`. No `SPEC.md` change: nothing the agent does or prints changes.

## 6 Nov 2026 - Claude on `poagent`, test site only (Joey; loosens a safety control)

- **Found in 1.10:** the S1 spike passed, and Claude Desktop (with computer use and Claude Code) was running inside `poagent`'s own session. Joey uses it there for another project, with his own GitHub account.
- **Joey's choice:** keep it. ADR-002 gate H2 ("no AI session can read the agent's secrets") is **waived for the test site only**. On `poagent`, an AI session can now reach the test-site MySys login and the Mac Mini's `po-agent` GitHub token in the Keychain. The advisor recommended moving Claude to another macOS account instead (Keychains are per account); Joey declined.
- **Why it's acceptable for now:** the test-site account books only test data; the token is fine-grained (this repo only: contents read, issues read and write); no live credential or real PO beyond the 3 trial POs is on the Mac Mini.
- **Conditions while it lasts:**
  - Never open a Claude session (Desktop, Code or computer use) in `~/po-agent` or on the test site, and never let one run `po-agent`, `keyring`, `security` or `macmini-run.sh`, or read `~/Library/Logs/po-agent`.
  - Keep `~/po-agent` unchanged by hand: any local change makes the wrapper's `git pull --ff-only` fail and the agent stop.
  - Don't `gh auth login` another GitHub account in `poagent`: the wrapper uses `gh`'s active account for alerts and the heartbeat. Use a separate credential for the other project (an SSH key, or `GH_CONFIG_DIR` pointing elsewhere).
- **Before go-live (P6), H2 must pass again:** Claude and any other AI tool are removed from `poagent` (or moved to another account) before any live credential reaches the Mac Mini. This is a go-live gate; the CEO's decision 3 assumed H2 passes.
- **Loosens?** Yes: a safety control (ADR-002 H2) is waived on the test site. Joey merges this PR.
- Carried in: `SPEC.md` (v1.30, Trial conditions), `docs/macmini-setup.md` section 3.

## 5 Nov 2026 - Heartbeat: a scheduled GitHub Action (Joey, task 7.1)

- **Choice:** Joey picked a scheduled GitHub Action over healthchecks.io: no new account and no new secret; the Mac Mini's `gh` token already opens alert issues.
- **What changes:** at the end of every run, whatever the exit code, the wrapper replaces the body of the one open `po-agent-heartbeat` issue with the time, the exit code and the `run_id` (no PO data); a failed ping logs `wrapper: heartbeat not sent` and leaves the exit code alone. `.github/workflows/heartbeat.yml` runs `scripts/heartbeat_check.py` every 30 minutes on weekdays with only `GITHUB_TOKEN` (`issues: write`, `contents: read`). It opens one `po-agent-alert` issue, `po-agent heartbeat missed`, when more than 2 hours of today's schedule (07:07-17:30 Perth) have passed since the `last run:` time in the issue's body (not `updatedAt`, which anyone's comment changes; the issue is locked); no second one while an open one was opened after the last ping. Every wrapper `gh` call has a 60-second limit, so a hung `gh` can't make launchd skip runs. Details: `docs/macmini-setup.md` sections 1 and 8.
- **Alert email (Joey, 5 Nov 2026):** the Mac Mini opens `po-agent-alert` issues with Joey's own token, and GitHub doesn't email you about your own actions. `.github/workflows/alert-email.yml` (on `issues` opened or labeled, `issues: write` only, no checkout, only the issue number reaches the shell) has github-actions[bot] post one fixed comment on each such issue it didn't open itself, once per issue, so Joey is emailed as the author. The missed-heartbeat issue is opened by the bot, so GitHub emails Joey about it directly.
- **Run output?** Unchanged: the agent prints nothing new, so `SPEC.md` is unchanged. The new lines are the wrapper's and the workflow's.
- **Loosens?** No: it adds an alert.

## 5 Nov 2026 - Silent-skip alert and more pages (task 7.2, Joey)

- **Found while building 7.2:** both cases it was planned for already stop the run with an ALERT and exit 1, so the wrapper opens the alert issue.
  - A MySys screen change can't make every Note skip quietly: the run stops on its **first** `UNEXPECTED_SCREEN` (the Note is returned, `ALERT UNEXPECTED_SCREEN`, exit 1), and a `Skip(UNEXPECTED_SCREEN)` from the decision engine is raised the same way. One booked Note then one `UNEXPECTED_SCREEN` also alerts. Only business skips (`NOT_B1`, `DUPLICATE_TASK`, ...) let the run go on, and they don't count.
  - M4 Nit #3 was a misread: in `run` and `run --decide-only` a Note Pool second page never waits silently. The stale-Note read (D6; decisions, 3 Nov 2026) lists every Pending Note (All Users, All Pools, Locked/Unlocked All), a superset of the eligible read, so it has a second page whenever the eligible read does, and it already stopped the run (`UNEXPECTED_SCREEN`, exit 1) before any Note was taken. The `INFO` "more pages" line was reachable only in `spike`.
- **Joey's choice:** no `ALL_SKIPPED` alert (it could never fire). A Note Pool second page gets its own ALERT kind, `MORE_PAGES` (fixed detail, no PO data), exit 1, before any Note is taken: from the stale-Note read in the run modes, and from the eligible read (after its counts line) in `spike` and as a backstop in the run modes. The `INFO` "note pool has more pages" template is removed. Page 1 is not processed when there are more pages: changing that would change D6, a larger safety decision.
- **Exit code:** `MorePages` is a kind of `UnexpectedScreen`, exit 1. It stops the run, so no other typed error follows it in the same run.
- **Tests:** offline, two pin the existing stop-on-first-failure (every eligible Note `UNEXPECTED_SCREEN`; one booked then one `UNEXPECTED_SCREEN`); `MORE_PAGES` from the stale read, the eligible read (`run`, `run --decide-only`) and `spike`. Two existing expectations changed with the rule: the stale read's second page was `UNEXPECTED_SCREEN`, spike's was an `INFO` line.
- **Loosens?** No: the same runs stop with the same exit code; the ALERT names the cause, and `spike` now alerts too.
- **Later:** `docs/ops-runbook.md` (7.5) covers `MORE_PAGES` and notes that `UNEXPECTED_SCREEN` is also the silent-skip signal. On live, more than 50 Pending Notes stops every run (as D6 already said): handled before go-live.
- Carried in: `SPEC.md` (v1.28: Production paging, exit codes, Code style, the stdout contract, the stale-Note stop).

## 5 Nov 2026 - M4 security pass: three Nits fixed (Joey)

A read-only security pass over the booker and run loop found no Important issue and five Nits. Joey chose to fix #2, #4 and #5 now; #1 is covered by "one agent at a time" (D7) and #3 goes into task 7.2.

- **#2, Ctrl+C after Submit:** from the Submit click on, a `KeyboardInterrupt` or any other non-`Exception` error is `PARTIAL_WRITE` with its step, like every other error there: the ALERT names the Note, RUN_SUMMARY's `partial` counts it, the Note stays with the agent and the run stops (exit 1). It used to be `ALERT UNEXPECTED_SCREEN` with `partial` 0. Before the click, Ctrl+C is unchanged (no return attempt, `UNEXPECTED_SCREEN` "Note not returned to the pool"). SIGTERM/SIGKILL from the wrapper's 20-minute limit stays out of scope: the wrapper alerts on a non-zero exit and the stale-Note stop holds the next run.
- **#4, a demo line in a real run:** the opening clicks' retry (`booking._open`, reached from `run` via `open_project`) no longer prints `INFO  demo: page blocked, retrying`; it is silent, like the driver's own retry. The line is removed from the INFO templates, so neither `run` nor `demo` prints it.
- **#5, the Note ID check in `book()`:** the run loop now passes the ID of the Note it holds, not the decision's own, so a decision for another Note is `WriteNotStarted` before W1. No change in what a normal run does or prints.
- **Loosens?** No: #2 reports more errors as partial writes, #4 prints less, #5 makes a check real.
- Carried in: `SPEC.md` (v1.27, Run output and the Submit rule).

## 5 Nov 2026 - A lighter build process (Joey)

Joey: the process is heavier than this project needs. He can't judge test code, so stopping for his review slows the work without adding safety. The rule: keep what protects MySys and real data, and what costs Claude but not Joey; drop the steps that cost Joey's time.

- **No review stop for tests.** Every remaining task writes its tests first, commits them as `test:` and carries on. Claude asks Joey only for a behaviour choice that is his (as in 4.5: what the run prints for a stopped Note), in plain words, one question at a time, with a recommendation. The PR's Intent opens with three to five plain-language lines on what changed and what the tests prove. Replaces the review-stop list of 24 Oct 2026 (1.2, 1.4, 2.2-2.5, M3, M4, 5.2).
- **One review round, lighter by risk.** High: one second-model review; the fresh-session `/code-review` is dropped. Medium: `/agent-skills:review`. Low: `check.py` and `/verify-pr` only.
- **By-hand checks only where they belong:** the by-hand tasks (4.6, M6) and the test-site reset. A case an offline or seam-2 test covers isn't checked by hand again (e.g. 4.5's mid-run takeover, S5 before M6).
- **`/goal` is optional** for the code half (offline only; still never against the test site).
- **Less doc ceremony:** a behaviour change needs this log's entry plus the `SPEC.md` lines it changes; `tasks/plan.md` gets no "Built" paragraph per task, only the tick in `tasks/todo.md`.
- **Reports to Joey** are in Traditional Chinese (code and repo text stay English).
- **Kept, unchanged:** Must never 1-9 (the guard, test site only, no secrets or real data out, nothing returned after Submit, the merge rules), `check.py` and CI, `/verify-pr` before every merge, tests first in their own `test:` commit (Claude's cost, and `/verify-pr` uses it for Must never #8), and the test-site rules (one agent at a time, reset first, no retry loops against MySys).
- **Loosens?** Yes, review steps (not a safety control in the code). Joey's to merge, since the matching `CLAUDE.md` TDD line and `.claude/skills/verify-pr/` step 4 change with it and are his to edit.
- Carried in: `docs/workflow.md` (Production build loop), `tasks/plan.md` (Cross-cutting rules, TDD), `.claude/skills/start-task/SKILL.md` (the brief). Joey edits `CLAUDE.md` (TDD) and `.claude/skills/verify-pr/SKILL.md` by hand.

## 5 Nov 2026 - Run mode: book end to end (Joey, task 4.5)

- **What changes:** `po-agent run --site test` no longer refuses (1.6, D1). It is decide-only's loop, but a PROCEED goes to `book()` W1-W5 with `Controls` and the assignee check built for the browser context in use; the Note is then linked and Solved, never returned, and the NOTE line is `"outcome": "booked"` with `po_number`, `pln` and `task_id`. A skip still goes back to the pool. `run --decide-only` is unchanged.
- **Before the Submit click:** `WriteNotStarted` (and any other error) -> one return in a fresh browser, then the run stops (exit 1, `ALERT UNEXPECTED_SCREEN`). `KillSwitch` at W1 or W2 -> the same return, `INFO kill switch on: run stopped`, exit 0. `NoteTaken` at the W1 check -> that browser context is closed, `"outcome": "untouched", "reason": "NOTE_TAKEN"`, no ALERT, and the next Note runs in a fresh browser (Playwright's sync API holds one browser per thread, so the old one closes first).
- **From the Submit click on:** an error is told by type and step together: `PartialWrite`, `AccuracyBreach` or `GuardRefusal` with step W2-W5 (W2's `before_write` errors also say W2 but are a `KillSwitch` or config error). The Note is never returned to the pool, where it would look unbooked: `ALERT PARTIAL_WRITE` (exit 1), `ACCURACY_BREACH` (exit 3) or `GUARD_REFUSAL` (exit 1) names it, and the stale-Note stop (D6) holds every later run until Joey clears it. Any other error naming W3-W5 is raised as `PartialWrite`. A Note someone linked during W1-W3 surfaces at W4 as `GUARD_REFUSAL` and is likewise never returned (4.4 review).
- **Run output (Joey, 5 Nov 2026):** a Note stopped after Submit has no NOTE line (as decide-only's stopped Note, 2 Nov 2026, 3.3); RUN_SUMMARY's `partial` counts it. `"outcome": "partial"` stays in the contract but isn't printed in the MVP.
- **Loosens?** It is the planned first unattended write path (D1 lifted at 4.5 as planned). Every write still goes through the booker's checks, `before_write` and the guard; the Mac Mini job stays unloaded until 4.6.
- Carried in: `SPEC.md` (v1.26, Run output), `tasks/plan.md` (4.5 Built).

## 4 Nov 2026 - W4 and W5: Link to Project and Solved (Joey, task 4.4)

- **What W4 does:** `before_write(note_id, "W4")` runs the assignee check (D7; any failure is `PARTIAL_WRITE`, 3.6 review), then the Note is found again as row 25 maps it (reload, Note ID under All Pools, the row whose ID equals it, opened). That is a second reload after the check's own; it reuses the mapped path instead of the page the check leaves. Send Email Notification is unticked and read back, Link to Project, Choose Project's Search/filter = the pln with Enter, Send Email read back again, then the one cell named exactly the pln, clicked once through `guard.act`. Read back: the Note's only project button reads the pln (another pln -> `ACCURACY_BREACH`), Status still starts Pending.
- **What W5 does:** `before_write(note_id, "W5")` (no assignee check, D7), Send Email read back unticked, Solved once; read back "Solved by <agent>", Solved disabled, one new log line, newest, "Status changed:" from Pending to Solved, then the Note ID search: the Status filter reads Pending, the list is one page and has no row whose ID equals the Note ID.
- **Errors:** every W4/W5 error closes the browser context and carries its step: `PARTIAL_WRITE`, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their type.
- **Guard (Joey, 4 Nov 2026):** `link_select_project` now clicks only an element whose role is cell (`CLICK_TARGETS`), never a row, link or button. Tightens a control; the PR is Joey's to merge (guard.py). The demo's `link_project` uses the same cell-only select: `_link_choice`'s link, button and text fallbacks and its results snapshot are removed (M4 gate).
- **Loosens?** No: W4 and W5 are the planned last writes; the cell pin and the extra read-backs add stops.
- Carried in: `SPEC.md` (W4/W5 Built, Guard additions), `tasks/plan.md` (4.4).

## 4 Nov 2026 - W3: Hold (Joey, task 4.3)

- **What W3 does:** `before_write(note_id, "W3")` (no assignee check, D7; a kill switch or unreadable config here is already `PARTIAL_WRITE`, 3.5), then Hold in the new task's own header row (exact name, never Un-Hold), the dialog headed `Hold Task: <new task>`, the note typed, every check read, the dialog's own Hold pressed once through `guard.act`, and the row read back: Un-Hold, and a Status starting "On-hold" that holds the note. No checkbox is touched, and nothing is saved to disk.
- **The dialog read counts hidden checkboxes too (Joey, 4 Nov 2026):** the read is "exactly one ticked box in the dialog, and it is the reminder", which covers every Related Tasks box, Select-all, Reset turn around time and "at this date"; it now includes hidden boxes, because a Related Tasks row the table hides would still be held with the task. If the test site has a hidden ticked box by design, W3 stops before the confirm and seam 2 shows it.
- **Every related job is read (4.3 review):** the "There are N related jobs" text must be the only one on the page and inside the dialog's read, and its table must hold N row checkboxes plus Select-all; else `PARTIAL_WRITE` before the confirm. A Related Tasks table that is paged, still loading or outside the read can't hide a ticked job. With no such text (row 11 always shows it) the ticked-box count alone applies. The row-11 captures show 58 jobs and 59 boxes, unpaged, inside the dialog block.
- **Errors:** every W3 error closes the browser context (an open dialog is abandoned unconfirmed) and carries `step=W3`: `PARTIAL_WRITE`, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their type. A Status without the note after Hold is `PARTIAL_WRITE`, as in the demo: `docs/specs/spec.md` §6 names a wrong project, PO number or PDF as an accuracy breach.
- **Guard:** no change; `open_hold`, `set_hold_note` and `confirm_hold` already existed.
- **Loosens?** No: W3 is the planned second write, and the hidden-box count adds a stop before it.
- Carried in: `SPEC.md` (W3), `tasks/plan.md` (4.3).

## 4 Nov 2026 - W2: Submit and the read-back on the task detail screen (Joey, task 4.2)

- **What W2 does:** `before_write(note_id, "W2")` (no assignee check, D7; a kill switch or unreadable config here closes the browser context, so the filled form is abandoned and nothing is submitted), then Submit, made once. From the Submit click on, every error is `PARTIAL_WRITE`, except `ACCURACY_BREACH` and `GUARD_REFUSAL`, which keep their type; each carries `step=W2`. The run loop (4.5) tells an error after the click by its type and step together: `PARTIAL_WRITE`, `ACCURACY_BREACH` or `GUARD_REFUSAL` with step W2 (a `KillSwitch` or config error from W2's `before_write` also says W2, but comes before the click).
- **The new task:** the form must close, then the settled task table (the step-10 read) must show exactly one Compaction Test number not in step 10's set, with Status New Project or Inspection Analysis, within 15 s. None, more than one (the accepted residual from 4 Nov, W1 review fixes) or the form still open -> `PARTIAL_WRITE`.
- **Read-back (row 19):** the new task's details row (found from its own header row) must show Lodged By the agent and Task Creator Perth Scheduling; its Task Creator cell opens the detail screen, whose heading must start `TSK_<n> ` and whose section `tsk_<n> [Compaction Test]` must show PO Number, Lodged By and Notes = the email body; the Client section shows Task Creator. Then "-- Select Task --", the project's Documents: the new task's section must hold exactly one row, Type Purchase Order, File starting with the PDF's name; then Tasks. A wrong value (on the details row, the detail screen, or the document: none, two, wrong type or file) -> `ACCURACY_BREACH`; a screen not as mapped (another task's screen, no Documents section) -> `PARTIAL_WRITE`.
- **Guard:** four new read-only actions, each pinned to its one target (Joey, 4 Nov 2026): `open_new_task_detail` (a table cell only), `back_to_project` (the select, only the option "-- Select Task --"), `open_project_documents` and `open_project_tasks` (the button named exactly "Documents" / "Tasks"). Any other target is refused before the page is touched. The unused `search_task` and `open_task_detail` stay as they were.
- **`book()`** now takes `agent` (for Lodged By) and returns the new task number after W2.
- **Seam 2 finding (4 Nov 2026):** the first run stopped with `PARTIAL_WRITE` at the Documents read-back after a real Submit: Create New Task shows on the project's Tasks tab only, so the window found by heading + Create New Task vanished on the Documents tab. A read-only probe (Joey's choice: opening clicks only, counts and fixed errors only) showed the detail screen read-back passing live. The Documents and Tasks steps now find the window by its heading and the Tasks button; the offline fake hides Create New Task on Documents, as live. The stop itself behaved as designed: `PARTIAL_WRITE`, nothing returned to the pool.
- **Loosens?** The guard allows four new actions, all read-only clicks or a select back to the project, and each narrower than an ordinary allowlist entry. W2 itself is the first write, as planned. This PR is Joey's to merge (guard.py).
- Carried in: `SPEC.md` (Guard additions, W2 after Submit), `tasks/plan.md` (4.2).

## 4 Nov 2026 - Production operations: go-live gate 6 (Joey)

- **Why:** a watched demo needed none of this; an unattended hourly job does. Today nobody is told if the job stops running, a skip caused by a MySys screen change opens no alert, the Mac Mini keeps no detail about a failed run, and every merge to `main` deploys within the hour.
- **Planned, not built:** heartbeat (7.1) and the silent-skip alert (7.2) before the P5 week; a trace of allowlisted fields only on the Mac Mini (7.3), the Mac Mini running a `production` tag that only Joey moves (7.4) and `docs/ops-runbook.md` (7.5) before go-live; every alert issue triaged into an expected skip, a new case, a fix or a decision from the P5 week on (7.6); two dev-workflow changes Joey makes by hand in `.claude/` (7.7).
- **Open choices, asked at the task:** the heartbeat service (7.1), the alert's name and exit code (7.2), and where the wrapper reads `enabled` once it runs a tag (7.4). 7.2 and 7.3 change the run output or what is logged, so each gets its own entry when built.
- **Loosens?** No: it adds a go-live gate and changes no behaviour yet.
- Carried in: `SPEC.md` (Production: steps 5 and 6, gate 6), `tasks/plan.md` (Phase P, gate 6, Production operations, the merge-deploys risk), `tasks/todo.md`.

## 4 Nov 2026 - W1 review fixes (Joey, task 4.1 follow-up)

From the post-merge reviews of PR #54 (second-model review and a fresh /code-review):

- **An empty task table counts as no tasks only after the full 15 s wait.** A read-only probe (Joey's choice: a scratch script through the guarded driver, opening clicks only, counts only) showed the rows and the select's options render together with the window, and an empty project shows nothing else (screen map row 10). Two early empty reads could have read a project with a task as having none, and booked a duplicate. Tasks still count once two equal reads match the options. A project with no tasks now costs 15 s at step 10 and again at the W1 reopen.
- **The W1 reopen refuses a task that is live again:** every task found must still be Cancelled (step 10 passed with each Cancelled), so an Undo Cancellation in between is `WRITE_NOT_STARTED`, not a duplicate booking.
- **The Documents read-back fails closed:** the Documents block must be found once and hold no file cell; a header row is not a file row.
- **Closing the context never hides the error:** if the close itself fails, the original error (e.g. a `GuardRefusal`) is raised.
- **Accepted, not changed:** a screen error during the W1 reopen stays `UNEXPECTED_SCREEN` (nothing is filled yet); a re-raised `WRITE_NOT_STARTED` keeps the step it had; a closed context ends the run, so `settled_tasks` retrying it for 15 s is harmless; `po-agent demo` keeps its own duplicate check (Phase P: the demo stays as is). Residual risk: task rows that arrive only after 15 s, at both step 10 and the W1 reopen, still read as no tasks; W2's read-back would then see two new tasks and raise `PARTIAL_WRITE`, after the write.
- **Loosens?** No: each change adds a stop or a wait before Create New Task.
- Carried in: `SPEC.md` (Duplicate check), `docs/screen-map.md` (row 10), `tasks/plan.md` (4.1, Settled task table).

## 3 Nov 2026 - W1: Create New Task filled and read back (Joey, task 4.1)

- **PO Documents or Documents** is a go-live gate (gate 2, the PO admin's live answer), not a 4.1 blocker: the test site uses PO Documents, as the walkthrough did (Joey, 3 Nov 2026). SPEC open question 11 now reads "confirm before go-live".
- **What W1 does:** `book()` takes only a `Proceed` for the Note in hand (else `TypeError` / `WriteNotStarted` before anything), runs `before_write(note_id, "W1")`, reopens the project as step 10 does and stops with `WriteNotStarted` if the search's match isn't the Proceed's pln (checked before the project is opened), Client Internal No. fails the match rule, or the settled Compaction Test tasks differ from step 10's. Then Create New Task is filled by label and read back; any problem once the form is open closes the browser context (nothing is saved: the upload is saved only by Submit) and is `WriteNotStarted`. In 4.1 `book()` accepts only `stop_after="W1"`; nothing calls it outside seam 2 until 4.5.
- **The Documents read-back** is "no file row" (an empty table counts as empty); the test site shows no table at all (row 09). It is what the demo's read-back already checked.
- **Settled task table** built as planned (M4 gate entry); `project_lookup` uses it.
- **Loosens?** No: every new check is a stop before Submit, and nothing new acts in MySys (no guard change).
- Carried in: `SPEC.md` (W1 read-back wording, open question 11), `tasks/plan.md` (4.1 Needs and read-back, P4 row).

## 3 Nov 2026 - M4 gate: doubt review of the booker design (fresh session, before 4.1)

A fresh-context adversarial review of 4.1-4.5 against the screen map, `SPEC.md`, `docs/specs/spec.md` §2 and §6, and the code the booker builds on. The must-fixes, now in `tasks/plan.md` (M4) and `SPEC.md` (MySys screen rules, Deferred table, Trial conditions):

- **The Submit click is the partial-write line**, not "from W3 on": from the click on, every error is `PARTIAL_WRITE` and the Note is never returned to the pool (`docs/specs/spec.md` §6: "a failure at or after W2"). `AccuracyBreach` and `GuardRefusal` after Submit keep their own ALERT and also leave the Note with the agent.
- **An accuracy breach leaves the Note with the agent**, so the stale-Note stop (D6) holds every later run: with no state between runs, that is the MVP's switch-off until Joey unloads the job. A Note linked to another pln at W4 is a wrong project: `ACCURACY_BREACH`.
- **W1 reopens the project after its assignee check** (the check reloads, so the window from step 10 is always gone) and checks heading, Client Internal No. and the Compaction Test task numbers again before Create New Task; a task created meanwhile → `WRITE_NOT_STARTED`.
- **The duplicate check reads a settled task table:** the rows render after the window shows, so an early read can look like "no tasks". Two equal reads in a row, matching the window's "-- Select Task --" options, else `UNEXPECTED_SCREEN`. Applies at step 10 (`project_lookup`) and at the W1 reopen.
- **W2's task detail** is opened from the details row right after the new task's own header row and must show the new task number, else `PARTIAL_WRITE`. Its new allowlist entries are new action names in `guard.py` (Joey merges that PR).
- **Committing clicks are made once**, never through the retrying open helpers. The booker never calls `booking.save_snapshot` (page text on the run machine's disk) or `_link_choice`'s fallbacks (W4's target is the cell only).
- **4.5 routing and tests:** `NoteTaken` at W1 → untouched line, no ALERT, next Note in a fresh context with its own `Controls`; `KillSwitch` at W1/W2 → returned, exit 0, as decide-only. Offline tests for both, and for errors after Submit.
- **Tests:** W-step teardowns return the Note only while it is Pending, unlinked and with the agent (after W4/W5 the reset does it); W5's "gone from Pending" is the Note ID search with no equal row (not `find_note_again`, which raises); the Hold-dialog `guard.vet()` refusal moves to 4.2's test, the last point where the dialog can be opened and left unconfirmed.
- **Accepted, not changed:** the run cap is checked only between Notes (a Note killed by the wrapper mid-booking stays with the agent, and D6 catches it); more than 50 Pending Notes stops every run (already carried; test-site resets and S5 copies should keep the count down); the stale-Note read is Pending-only (3.6 entry).
- **Loosens?** No: every change adds a stop or keeps a Note with the agent. Nothing new acts in MySys beyond what 4.2 already planned.
- Carried in: `tasks/plan.md` (Architecture decisions, M4 intro, 4.1-4.5), `SPEC.md` (Deferred table, MySys screen rules → Duplicate check, W1, W2, W4, W5; Trial conditions).

## 3 Nov 2026 - Assignee check and stale-Note stop (Joey, task 3.6)

- **Assignee check:** `controls.assignee_check` is what `before_write` runs before W1 and W4 (D7): reload `base_url`, the Note Pool under All Pools and All, the Note ID searched (fill, then Refresh), and the one row whose ID cell equals the Note ID must have Assignee `agent_user_name`. Zero or several such rows -> `UnexpectedScreen`. Someone else before W1 raises `NoteTaken`, which like `KillSwitch` is not a `PoAgentError` (no ALERT); someone else before W4 is `PartialWrite`. The check only reads: closing the browser context and printing `"outcome": "untouched", "reason": "NOTE_TAKEN"`, and reopening the window the booker needs (row 25), come with the booker and run mode (4.1, 4.4, 4.5), because nothing calls `before_write` yet (Joey, 3 Nov 2026).
- **Stale-Note stop, changed read:** the test site's Assigned User filter does not list the agent account (10 options, none the agent; seen read-only in 3.6's seam-2 run), so the stop can't filter by Assigned User. It reads the Note Pool under **All Users**, All Pools, Locked/Unlocked All, Status Pending, Search/filter empty (31 rows, one page of 50 on the test site), and stops on any row whose Assignee is `agent_user_name`: `ALERT UNEXPECTED_SCREEN` "a Note is still assigned to the agent from an earlier run" with its `note_id`, exit 1. Only page 1 is read, so **a second page stops the run too** (`UNEXPECTED_SCREEN` "Note Pool has more pages: stale-Note read incomplete"). On live, more than 50 Pending Notes would stop every run; that is handled before go-live (Joey, 3 Nov 2026). No new guard action: `set_user_filter` was proposed and dropped.
- **From the 3.6 review (PR #51):**
  - Before W4 the task exists and is on hold, so **any** failure of the check is `PartialWrite`: someone else, no single equal row, or a failed search or re-login. The Note stays with the agent, so the stale-Note stop holds later runs. It is never returned to the pool, where it would look unbooked. Before W1, no single row stays `UnexpectedScreen`. The run mode (4.5) also handles any other error from W3 on as `PartialWrite`.
  - The stale-Note stop names a Note with the agent on page 1 before stopping on a second page.
  - Routing for 4.1/4.5: the run catches `NoteTaken`, closes that browser context, prints `"outcome": "untouched", "reason": "NOTE_TAKEN"` and goes on with the next Note in a fresh context. The assignee check is built per browser context, because it holds that context's page.
  - Known limit, accepted: the stale-Note read keeps Status at Pending (D6), so a Note left with the agent in another status (e.g. Solved at W5, then a failed read-back) isn't caught there. That Note's own `ALERT PARTIAL_WRITE` reports it.
- **Loosens?** No: both add stops before a write. Nothing new acts in MySys.
- Carried in: `SPEC.md` (Note Pool -> Stale-Note stop; Assignee check), `tasks/plan.md` (3.6, 4.5).

## 3 Nov 2026 - M0b.2: task detail, Link to Project, PO prefill, assignee refresh (Joey; mapped with Claude observing)

- **How:** Joey booked 2609017B by hand in the Playwright window, logged in as the agent, up to Hold and Link to Project (no Solved); Claude only snapshotted. Then Joey reset the test site (cancelled the task, unlinked the Note by hand and returned it to the Agent Pool, and moved an old 2609017B copy that had sat with the agent since 16 Oct to himself).
- **W2 read-back (row 19):** a cell of the new task's details row opens the task detail screen **in the project's own window** (heading `TSK_<n> PLN_<n> ...`). Its `tsk_<n> [Compaction Test]` section shows **PO Number**, **Lodged By** and the **Notes** text; the Client section shows **Task Creator**. The PDF is **not** on the task: it is filed on the **project's Documents tab**, in a section headed by the task number (Type Purchase Order, the file name). Choosing "-- Select Task --" in the window's select goes back to the project. New read-only allowlist entries: the details-row click, that select, and the project's Documents and Tasks buttons. The task screen's Save, Complete and uploads, and the Documents tab's Delete ("close"), Edit and checkboxes, are never touched.
- **W4 (row 20):** Choose Project's results are a table; the agent clicks the **cell** named exactly the pln. The row is never the target, because its accessible name includes the Site Address and a "... Close" street would trip the denylist on every run. Choose Project closes by itself after the click.
- **W1:** PO Number is **not prefilled** (row 24). The PO Documents upload is **saved only by Submit**: an abandoned form leaves no document on the project. The Documents area shows empty by having no table. Every weak field (Creator, Multiple Units, PO Number, PO Contact, Sale Office, Delivery Office, Note, both file inputs) sits in its own label block, so it is found by its exact label inside the `Create New Task` window, never by `nth` or a generated id. The Hold confirm is the "Hold" beside the heading `Hold Task: <task no>`, in one small block.
- **Row 23:** an open Note window does **not** refresh its Assignee, log or the Note Pool row behind it when someone else reassigns the Note (tested twice). The assignee check (3.6) already reads a fresh Note Pool after a reload, so nothing changes there.
- **Mapping lesson:** while Playwright CLI is attached, each click on "Choose File" queues a file chooser that survives a reload and swallows `playwright-cli upload`. Dragging the PDF from Explorer onto the upload area works instead.
- **Loosens?** No: the new allowlist entries only open or read screens, and each write target is narrower (a cell, not a row).
- Carried in: `docs/screen-map.md` v1.3 (rows 08-11, 13, 19, 20, 23, 24; open items 2, 4, 5, 8, 10), `SPEC.md` v1.21 (MySys screen rules: W1, W2, W3, W4, Assignee check, allowlist; In the MVP; Expected slices), `tasks/plan.md` (M0b.2, 3.6, 4.1, 4.2, 4.4).

## 2 Nov 2026 - Run controls: kill switch, Perth window, run cap (Joey, task 3.5)

- **What:** after the config loads, `enabled = false` ends every mode (`run`, `decide-only`, `spike`, `demo`) with `INFO  kill switch on: run not started` and exit 0, before secrets are read or a browser starts. `run` and `run --decide-only` outside Mon-Fri 07:00-18:00 `run_window.tz` end the same way with `INFO  outside the run window: run not started`; `spike`, `demo` and seam 2 (its clock is pinned inside the window) ignore the window. Before each Note is started, the run stops taking Notes once `max_notes_per_run` Notes were started or `max_run_minutes` have passed since the run began, with `INFO  run cap reached: <n> notes left for the next run`; the Note in progress is finished. `controls.before_write(note_id, step)` re-reads `enabled` before every W step and runs the assignee check (3.6) only before W1 and W4 (D7): switched off before W1 or W2 it raises `KillSwitch`, the run returns the Note in a fresh browser context and ends with `INFO  kill switch on: run stopped`, exit 0; from W3 on it is `PartialWrite`, as is an unreadable config there (before W3, `ConfigError`). New dependency `tzdata` (Joey approved, 2 Nov 2026), because Windows has no time-zone database for `zoneinfo`.
- **Why:** D1 and Open questions 6 and 7. The note cap now prints an INFO line too, because a run that leaves Notes behind should say so in `runs.log`.
- **Loosens?** No: it adds stops before and during a run. Nothing new acts in MySys.
- Carried in: `SPEC.md` (Code style -> run output), `tasks/plan.md` (3.5).

## 2 Nov 2026 - Claude reader dropped; two code readers plus a MySys-fed address check (Joey)

- **What:** the paid Claude reader (task 2.5 as planned) is not built. Instead:
  1. **A second code reader:** pypdf reads the PDF's text again. Its issuer (first non-empty line), COMPACTION, PO number and Job Address label line (normalised) must equal pdfplumber's, else `READERS_DISAGREE`. If pypdf reads no text, `PDF_UNREADABLE`.
  2. **The address check is fed by MySys:** the project's address gives the lot and street-and-suburb *R*, and the 30 Oct block rule checks that the PDF's Job Address block holds them. It runs on both readers' text, and if the two results differ, `READERS_DISAGREE`. `ADDRESS_UNVERIFIABLE` when something can't be parsed (the project address, no single label, a label line not starting `Lot <lot>` with a one-word lot, or a lone lot with nothing under it); otherwise a failure is `ADDRESS_MISMATCH`. So an address split across the PDF is now `ADDRESS_MISMATCH`, and a PDF or project lot like `12-A` or `12/13` is `ADDRESS_UNVERIFIABLE`. Tightened after the fresh-context reviews: on pypdf's text the line under a lone lot must be exactly *R* plus the tail (pdfplumber's shares the Supplier column, so it keeps the ends-with rule, and both must pass); *R* of fewer than two words, a second label in any spelling, or a non-ASCII letter in the project address or the block is `ADDRESS_UNVERIFIABLE`.
  3. `decide()` is code only: no reader mode, no Claude call. Its order: steps 2a-4, the second reader, the project lookup, the address check, the duplicate check, PROCEED. A PO that passes every check now PROCEEDs, where deterministic-only mode always skipped `ADDRESS_UNVERIFIABLE`. `CLAUDE_UNAVAILABLE` and `CLAUDE_INVALID_OUTPUT` leave the skip reasons.
- **Why:** the agent must cost nothing per PO: no Anthropic API, API key, model ID or prices. It reads B1 Homes POs only, and their layout is fixed, so code can read them. pypdf reads the PDF independently of pdfplumber: it splits the columns differently (it reads the Supplier column apart from the address), so the two texts are not copies. On the 3 trial PDFs (checked on the laptop, booleans only) the readers agree, and both texts pass the address check against the trial projects.
- **What is lost:** Claude could have read a PO in a new layout. Mitigation: any mismatch skips, so a layout change sends the Note back to the pool, never to a wrong booking.
- **Loosens?** The second reader is no longer a different kind of reader (AI against code), but two code readers must still agree, and the address values now come from MySys instead of a reader, which removes the extraction step the 30 Oct review had to tighten. Nothing that acts in MySys changes. Run output is unchanged: skip reasons only, and pypdf's warnings are kept out of it.
- **CEO:** decision 1 approved the two-reader design with Claude as one reader. Joey informs the CEO of this change.
- **Done by PR #44 (task 2.5b):** the Claude settings left in config, CLI and secrets (`reader_mode`, `claude_model_id`, `aud_per_usd`, `claude_price_usd_per_mtok`, the `anthropic_api_key` secret, decide-only asking for it) are removed, and `docs/macmini-setup.md` no longer names the key. Still left: `CLAUDE.md` (Joey's) names the key and the live-Claude seam, and the unused `live_claude` marker stays while `scripts/check.py` (Joey's) deselects it.
- Carried in: `SPEC.md`, `docs/specs/spec.md` §2-§4 and §7, ADR-001 (a dated note), `tasks/plan.md` 2.5 and 2.6, `tasks/todo.md`.

## 2 Nov 2026 - Decide-only: how each Note is opened, and the stopped Note's output (Joey, task 3.3)

- **What:** the decide-only run opens every Note it works on by "Finding a Note again" (reload, All Pools, the exact Note ID), which is also its reload between Notes. Before taking a Note it reads "Assignee:": anything but `pool_name` means a person has it, so it gets `"outcome": "untouched", "reason": "NOTE_TAKEN"` and is never taken. Before it goes back, every Note is found again and its Assignee must read the agent; otherwise a person took it mid-run, so it is `NOTE_TAKEN` and left with them (second review: the open window can be minutes old). On an error while the agent holds a Note, the browser closes and one return runs in a fresh browser context, then the run stops (exit 1, or the error's own code, e.g. 2 for a failed login); on Ctrl+C there is no return attempt. The stopped Note prints no `NOTE` line: its `ALERT` carries the `note_id`, and the detail says "Note not returned to the pool" if that return failed. NOTE lines and RUN_SUMMARY keep `tokens_in`, `tokens_out` and `cost_aud` at 0.
- **Why:** the run list is read once at the start, so a person can take a listed Note before the agent reaches it; an Assign then would take it from them. Opening every Note the same way keeps one path that works whether or not the agent holds it. A NOTE line for a stopped Note would claim an outcome the run didn't reach.
- **Loosens?** No: it adds a check before the first write on each Note. The full assignee check (3.6) and the stale-Note stop still come before any booking.
- Carried in: `SPEC.md` (MySys screen rules -> Note Pool), `tasks/plan.md` (3.3).

## 2 Nov 2026 - Claude merges verified PRs and edits skills (Joey)

- **Why:** Joey wants routine steps automated: merging a PR he has OK'd, and keeping the task skills (`start-task`, `verify-pr`) in step with `docs/workflow.md`, were the last hand steps in the build loop.
- **What:** `guard_bash` allows exactly `gh pr merge <n> --merge` (one PR by number, a merge commit) and blocks every other form: squash, rebase, `--admin`, `--auto`, `--delete-branch`, no number, no method. The old text rule that blocked any command naming `gh pr merge` is gone, so a commit message may mention it. `protect_paths` allows writes inside `.claude/skills/` except `skills/verify-pr/` (it decides what Claude may merge); `.claude/hooks/`, `.claude/settings*.json` and everything else in `.claude/` stay blocked, including a `.claude/` folder nested in a skill. The allowed merge must be the whole command: any other text naming `pr merge` (shell constructs, `xargs`, backticks, another language, a commit message) and any `gh alias` stay blocked, after the PR's own review found those bypasses. Claude merges only after `/verify-pr` passes with no Important finding and CI is green on the latest commit; a PR that touches `.claude/hooks/`, `.claude/settings*.json`, `.claude/skills/verify-pr/`, `.github/workflows/`, the guard (`src/po_agent/mysys/guard.py`, `scripts/guard_check.py`) or `scripts/check.py`, or loosens a safety control, stays Joey's to merge. Tests in `tests/test_hooks.py`.
- **Loosens:** Must never #9 (Claude may now merge) and the `.claude/` rule (Claude may edit skills). It doesn't loosen pushes to `main`, force-push, the hooks, settings, the guard, CI or the repo-data check: Claude still can't switch off its own guardrails. No change to the agent's behaviour in MySys or its run output.
- Carried in: `.claude/hooks/guard_bash.py` and `.claude/hooks/protect_paths.py` (Joey, by hand), `CLAUDE.md` (Must never #9, Conventions), `SPEC.md` (Must never list), `tasks/plan.md` (1.2), `docs/workflow.md`.

## 30 Oct 2026 - protect_paths inside Claude Code worktrees (Joey)

- **Why:** from task 2.3 each task session runs in its own Claude Code worktree (`docs/workflow.md` v5.19), which the app puts at `.claude/worktrees/<name>/`. `protect_paths` read every path there as `.claude/` and blocked all writes, so the 2.3 session copied files in with `cp`, going around the hook.
- **What:** a path inside `.claude/worktrees/<name>/` (one level only) is checked with the same repo rules, measured from that worktree's root. Its own `.claude/`, `.env*`, `config/live*.toml`, `secrets/` and `state/` stay blocked; `.github/workflows/`, the Mac Mini files and existing seam-1 fixtures still ask; a nested worktree, a loose file in `.claude/worktrees/` and a `../` escape into `.claude/` are blocked. Tests in `tests/test_hooks.py`.
- **Loosens:** writes become possible in ordinary files of a worktree, the same files a session may already write in the main checkout. Nothing else changes. No change to the agent's behaviour in MySys or its run output.
- Carried in: `.claude/hooks/protect_paths.py` (Joey, by hand), `SPEC.md` (repo layout), `tasks/plan.md` (1.2).

## 30 Oct 2026 - Task 2.4: a tighter Job Address block rule (Joey)

- **What:** the address check (§4 step 1) no longer accepts Claude's lot, street and suburb as whole words anywhere in the Job Address block. Now the label line must start `Lot <lot>` (Claude's lot). If more follows on that line, the rest must be exactly `<street> <suburb>` plus an optional tail; if nothing follows, the line under it must end with `<street> <suburb>` plus an optional tail. The tail is nothing, a state, a 4-digit postcode, or both in either order. Compared on normalised text; exactly one `Job Address:` label. Else `ADDRESS_UNVERIFIABLE`, before the project compare (`ADDRESS_MISMATCH`), as before.
- **Why:** the 2.4 code review found two holes in the looser rule: a PDF lot `12-A`, `12 A` or `12/13` passed as Claude's lot `12`; and the line under the label also holds the Supplier column, so a supplier street and suburb could pass. The real layout (the 3 trial PDFs, checked as masked shapes) is the two-line form: the label line ends `Job Address: Lot <lot>`, the next line is Supplier text, then `<street> <suburb> <state>` at its end. The one-line form keeps SPEC's must-pass example passing.
- **Effect:** stricter only; nothing is loosened. A `(#n)` group anywhere but right after the project's lot stays in *R*, so it skips `ADDRESS_MISMATCH`.
- Carried in: `SPEC.md` -> Project address, `docs/specs/spec.md` §4, `tasks/plan.md` 2.4.

## 29 Oct 2026 - Task 2.2: one reader, SkipReason names in the demo (Joey)

- **What:** the deterministic reader (`b1/reader_rules.read_pdf`) is shared by the decision engine and `po-agent demo`. The issuer is the PDF's first non-empty line and must read exactly `B1 Homes Pty Ltd` (before: "B1 Homes" anywhere in the text); checked on the 3 trial PDFs, booleans only. A `.pdf` not named `<internal no>_048[_n].pdf` skips `PO_MISMATCH`; any second attachment skips `MULTIPLE_PDFS`; a live-style title's PO number is read on both title rules; a PO for another internal number than step 0's skips `PO_MISMATCH`.
- **Run output:** the demo's reason names follow `SkipReason` (`docs/specs/spec.md` §3): `NOT_B1_HOMES` becomes `NOT_B1`, and `PO_NUMBER_MISMATCH` and `INTERNAL_NO_MISMATCH` become `PO_MISMATCH`. The demo prints a different reason only when a PDF check fails. Nothing is loosened: the issuer rule is stricter.
- Carried in: no `SPEC.md` or `tasks/plan.md` line names the old reasons, so neither changes.

## 29 Oct 2026 - Go-live gate 1: MySys allows automation, no API (Joey)

- **What:** Alltraders (the MySys vendor) allows the agent to automate the PO workflow on the MySys website. We won't use an API: Alltraders would charge for one. The agent keeps working through the website, as built (ADR-001).
- **Effect:** go-live gate 1 is met. Gates 2-5 still stand. Nothing changes in the code, the agent's behaviour or its run output, and Must never #3 (test site only) is unchanged.
- Carried in: `SPEC.md` -> Production (gate 1), `tasks/plan.md` -> Phase P (gate 1).

## 29 Oct 2026 - Switch to production (Joey)

- **What:** the MVP demo was shown on 28 Oct 2026. From 29 Oct Joey builds production: the agent runs by itself, hourly, on the office Mac Mini (CEO decision 3), with no Enter prompts; first unattended on the test site, then on live MySys once the go-live gates pass. `SPEC.md` -> Production and `tasks/plan.md` -> Phase P carry it.
- **Order (code):** docs catch-up; decide (2.1-2.6); run controls and decide-only (3.1-3.6); real booker (4.1-4.5), built from the demo's proven steps in `src/po_agent/mysys/booking.py`, taking only a `Proceed` and reading back after every write, after a doubt-driven design review; unattended on the test site (1.9, 1.10, 4.6, 5.1, 5.2); then go-live tasks, written once the answers are in. Task numbers and acceptance criteria are unchanged. M6 as written (the unattended demo) is superseded; its checks (S1-S8) move to the unattended-on-test step.
- **Out:** no schedule change (Monday-Friday, hourly 07:07-17:07 Australia/Perth); no Grok Bot; no fake-PDF generator unless a 2.1 case needs one (decided at 2.1). `po-agent demo` stays for supervised demos and isn't extended.
- **Go-live gates** (all before any contact with live, read-only included): (1) MySys confirms automation is allowed (and whether there's an API), else production stops; (2) the PO admin's live answers (PO Documents or Documents, Resolve or Solved, live's Client Ref No. column, agent password expiry); (3) the CEO's go-live sign-off and the backlog cut-off date; (4) accounts: the Anthropic `po-agent-trial` key, a named backup admin for the Mac Mini, the Mac Mini's GitHub token and the `po-agent-alert` label; (5) a week of hourly test-site runs on the Mac Mini with zero wrong bookings. Then live: read-only `spike`, then `run --decide-only`, then `run` booking one PO per run, watched, then full hourly runs, each step with its own dated entry here.
- **Nothing loosened now:** the code stays test site only and CLAUDE.md Must never #3 is unchanged. Joey changes it by hand, with the CEO's sign-off, as the first go-live task; that change gets its own entry. This entry changes no agent behaviour and no run output.
- Carried in: `SPEC.md` v1.17 (Production; the Projects search line now says Enter, PRs #26/#27), `tasks/plan.md` (Phase P; demo notes on the Overview, M0b.2, M4 and M6), `tasks/todo.md`, `docs/workflow.md` v5.18, `README.md`.

## 28 Oct 2026 - A guarded pointer move ends "page blocked" (Joey)

- **Root cause, reproduced offline:** after a guarded click in the header's Project menu, Playwright's pointer stays in the header. While the header is hovered, MySys covers the body, so no click below the header lands ("<body> intercepts pointer events"). Clicking "Welcome Agent" (the old `leave_project_menu`) kept the pointer in the header, so the block stayed until a real mouse moved. `tests/test_booking.py` reproduces both with CSS only.
- **Decision (Joey, in the demo session):** the guard may move the pointer. A new kind `move` has one action, `move_pointer_off_menu`, which moves the pointer onto a list's status line below the header (the footer "Page N of N (N Items)" or "No record (could be) found."). Its role must be plain text (generic, listitem, paragraph, text), and it must be found exactly once and visible. No click, no key, no value. It uses `hover(force=True)`, because a plain hover runs the same "receives events" check the cover fails (https://playwright.dev/python/docs/actionability#forcing-actions). `scripts/guard_check.py` allows `hover` inside `guard.act()` only.
- **Headless only when read-only:** the demo honours `--headed` again, since the block that forced it headed was the parked pointer. A demo that asks for writes (anything but `--until-check` or `--probe-link`) refuses to start without `--headed` (exit 2): Joey approves each write at a prompt and must see the page (PR #29 review).
- **Accepted risk (PR #29 review):** the move is `hover(force=True)`, so the mouseover goes to whatever is on top at the status line's centre, and leaving the header fires mouseout on the menu. MySys hover handlers aren't known to write anything; that can't be checked without `evaluate` (banned); the live runs (plan step 3) are the check. The target must be plain text with no link or button inside it.
- **Removed:** `leave_project_menu`. `leave_menu` now uses the move. The opening clicks keep their retries, and the message is now "page blocked, retrying"; no human mouse is asked for.
- **To prove live** (plan step 3, Joey, hands off the mouse): 5 headed and 5 headless `--until-check` runs, all reaching `demo: read-only checks done` without "page blocked". If any blocks, revert this and keep the human mouse.

## 28 Oct 2026 - Enter runs the two project searches; the guard may press Enter there only (Joey)

- **Decision (Joey, in the demo session):** after filling the project number, the demo runs the search by pressing **Enter** in the search box, in the Projects panel (step 5) and in Choose Project (step 8). This loosens the guard, which pressed no key until now.
- **Kept narrow:** a new guard kind `press` allows only the key `Enter`, and only for two actions on one target each: `submit_project_search` on the Projects panel's textbox "Search..." and `submit_link_search` on Choose Project's textbox "Search/filter". Any other key is refused (`VALUE_MISMATCH`); Enter on any other element, or through any other action, is refused (`WRONG_ELEMENT` / `VALUE_MISMATCH`). The exactly-one, visible, in-scope and denylist checks apply as to every action. `scripts/guard_check.py` allows `press` inside `guard.act()` only.
- **Removed:** the clicks that ran these searches by moving focus, `run_project_search` (27 Oct) and `link_run_search` (28 Oct), leave the allowlist.
- **Step 5 made reliable in the same change** (read-only): the Projects filters must be at their defaults before searching (else `UNEXPECTED_SCREEN`); the search waits up to 60 s; a stale "No record found." or the old list doesn't count as the result; a loading row or a re-render mid-read is read again; any settled list counts (two equal reads in a row), so a hit on a field the list doesn't show no longer times out; the same row listed twice counts as one project.
- Carried in: `SPEC.md` (MySys screen rules: no key presses except these two; Guard additions), `src/po_agent/mysys/guard.py`, `scripts/guard_check.py`, `src/po_agent/mysys/booking.py`.

## 27 Oct 2026 - Supervised demo mode: one PO, Joey's Enter before every write (Joey)

- **What:** `uv run po-agent demo --site test --headed` books the one trial PO 2609017B -> pln_66935 the way Joey does it by hand, for the CEO demo on 28 Oct: take the Note (Send Email unticked), download and check the PDF, find and check the project, Create New Task (Perth Scheduling, - Compaction Test, PO Number, the PDF to PO Documents from memory, Note = the email body), Hold ("ON HOLD UNTIL CALL UP", no checkbox in the dialog touched), Link to Project, Solved. It prints `NEXT  <step> [Enter / n]` and waits before every write; only a bare Enter goes on ("n", anything else or end of input stops). On a failed check, an error or "n" it saves the page's ARIA snapshot to `private/captures/test/demo-<step>.yml` and, if the Note was taken, asks to return it to the pool (one Assign, row 15b), then stops with its ALERT.
- **In-scope checks for this mode** (instead of `SPEC.md` -> In the MVP): the Note is the one eligible 2609017B Note in the Agent Pool (step 0); not linked yet; exactly one PDF link; the PDF names B1 Homes and COMPACTION, its PO number equals the file name's and its internal number the Note's; exactly one B1 Homes project whose Client Ref No. is the internal number, and it is pln_66935, with the same Client Internal No.; no Compaction Test task on it that isn't Cancelled. Every write is read back as in `SPEC.md` -> MySys screen rules.
- **Not in it:** the Claude reader and the two-reader agreement, the address check, the assignee re-check (§8), the stale-Note stop and the run controls (kill switch, Perth window, run cap). Joey's Enter and his presence at the screen stand in for them. `run` still refuses until 4.5; nothing here changes `run` or `decide-only`.
- **`--until-check`** runs the read-only steps (login to the duplicate check) without taking the Note and without any prompt: opening a Note and downloading change nothing (rows 02, 05). Claude may run only this; the first full write run is Joey's, in his own terminal.
- **Not mapped:** the Link to Project search screens (screen-map open item 5). The demo snapshots the page right after the Link to Project click (`demo-S8-link-opened.yml`) and guesses the search box and result; a wrong guess is a guard refusal or a timeout, then the demo stops and Joey links by hand.
- **Guard allowlist additions (loosening, Joey's demo):** `leave_project_menu` (click the inert header text "Welcome Agent" so the Project hover menu closes) and `run_project_search` (click the Projects panel's plain "Search" label so the search runs; SPEC.md -> Project search planned this). Both change nothing in MySys. Opening clicks (open a Note, open a project, Note Pool Refresh, run the Projects search) are tried up to 4 times; Playwright never clicks a covered element, so a retry can't act twice.
- **Found on the test site (27 Oct, read-only runs):** (1) after a choice in the Project hover menu, Playwright's mouse stays on it and the page takes no click below the header ("body intercepts pointer events") until a real mouse moves over the window; headless, it never clears (likely 1.8's section-tab problem too). The demo therefore always runs headed and prints `INFO  demo: page blocked - move the mouse over the browser window` while it waits. A guarded mouse move (a `hover` kind in the guard) would fix it without Joey; that loosens guard_check, so it waits for Joey. (2) `fill` alone did not run the Projects search. (3) The Note body is a `<pre>`; the file name beside the link is now a `<span>` with text.
- **28 Oct 2026, Link to Project seen live (S8):** it opens a floating window "Choose Project" with textboxes "Search/filter", "After..." and "Before..." and no results until a search runs. The demo fills Search/filter with the pln, then clicks the window's heading so focus leaves the box (as the Note Pool search needs) - new allowlist entry `link_run_search`, a click that changes nothing in MySys - then selects the one result naming the pln and snapshots the results (`demo-S8-link-results.yml`) for mapping. After linking, Status reads "Pending by <agent>", so the read-back checks it starts "Pending".
- **28 Oct 2026, 12:09 run:** the Choose Project heading showed at once but its Search/filter only after the 15 s wait had given up, so the picker and its results get 60 s. **`--probe-link`** (Joey): S1, open the Note without taking it, Link to Project, search the pln, snapshot the window and its results to `private/captures/test/demo-probe-link-results.yml`, stop without selecting (the browser closes; no close button is pressed). No write, so a try costs no test-site reset. Snapshots now include child frames.
- **28 Oct 2026, 12:28 probe:** it printed "link probe done" though the results snapshot held no Choose Project window. The window was found as "heading + a Search/filter box", and while its content loads that matched an ancestor holding the Note Pool's own Search/filter. It is now anchored on its own "After..." box. Each sub-step checks the window is still open, and the probe snapshots each one (`demo-probe-link-1-opened`, `-2-filled`, `-3-searched`, `-results`) and fails if the pln isn't listed.
- New dependency: `pdfplumber` (Joey approved). Output: `NEXT` prompt lines and fixed `demo: ...` INFO lines; the final NOTE line has only identifiers.

## 25 Oct 2026 - M0b.1 maps only what 1.8 and 3.1-3.3 need; its findings (Joey; mapped with Claude observing)

- **Scope (Joey):** for the MVP, M0b.1 maps only the cases task 1.8 and tasks 3.1-3.3 need. No new Notes were made for it.
- **Rows 21-22 dropped.** The attachment rule stands without them: the Note window must have exactly one "Download document" link whose URL `file_name` ends `.pdf` (any case). None → `NO_PDF`, more than one → `MULTIPLE_PDFS`, anything not recognised → `NO_PDF`. Every one is a skip back to the pool. The link's name is only "Download document"; the file name is in its URL (row 26).
- **Row 23 (a)-(c) moved to M0b.2**, before 3.6 (which comes after the Milestone A demo): does an open Note window refresh its Assignee after someone else reassigns it. The assignee check never relies on it (a fresh Note Pool read). Row 23 (d), the Note Pool search by Note ID under All Pools, is mapped in row 27.
- **Anchors (row 26):** the Note Pool filters by their fixed `name` attributes; the Note window's user and pool lists as the selects containing `--Select User--` / `--Select Pool--`; the Note Pool and Projects panels by the controls they hold (neither has a heading, and their container ids are generated). The login page's controls all have names.
- **Searching the Note Pool (row 27):** `fill` alone doesn't run the search; it runs when focus leaves the box. The agent fills, then clicks the panel's **Refresh** (added to the allowlist, a new guarded click). Refresh plus the focus change once showed the same Note twice while the footer said 1 item, so the row count must equal the footer's count, after one more Refresh at most, else `UNEXPECTED_SCREEN`. A filter-select change reloads the list by itself.
- **What persists (row 27):** a reload keeps every filter and the Search/filter text, closes every window, lands on Dashboard and hides the module tabs until Project is clicked. A fresh login resets every filter. So the run-start list read sees defaults; within a run the driver sets and reads back what it needs.
- **Moving between windows (rows 25, 28):** an open Note window stays on top of the Projects panel and covers its results. The agent doesn't minimise it or use the taskbar: it reloads after the Note-window steps, searches and reads the project, then reloads and reopens the Note from the Note Pool. A project that is already open doesn't open twice.
- **Returning a Note (row 15b):** one Assign with `--Select User--` + the pool works from a freshly opened Note window. The walkthrough's two Assigns aren't needed.
- **Not mapped:** whether `fill` alone runs the **Projects** search. Task 3.2 checks it first; if not, it clicks the panel's "Search" label to move focus (with its own decisions entry); if that fails, Joey decides (the guard bans key presses).
- Carried in: `docs/screen-map.md` v1.2, `SPEC.md` v1.16 (MySys screen rules, Expected slices), `tasks/plan.md` (M0b.1, M0b.2, 1.8, 3.1, 3.2, 3.6, gate for M3), `tasks/todo.md`, `docs/workflow.md`.

## 25 Oct 2026 - Decision 2, Milestone A first, the repo is public (Joey)

- **Decision 2:** the CEO delegated it to Joey; Joey decides yes, on the terms in `SPEC.md` → Trial conditions. The CEO approved D2 (the trial PDF on the Mac Mini's disk from its download until it's read into memory). Task F.5 is done. 3.4's Mac Mini run is no longer waiting on the CEO.
- **Milestone A comes first:** a decide-only demo to the CEO. The Mac Mini runs the agent by itself against the test site: it logs in, takes each eligible Note, downloads and reads the PDF, decides PROCEED or SKIP, and returns the Note to the pool, writing nothing. Scope: 1.4, 1.6, 1.7, M0b.1, 1.8, 1.9, 1.10; M2 (2.1–2.6); M3's 3.1, 3.2, 3.3, 3.5, then 3.4. For the demo the launchd job may be loaded in decide-only mode (hourly, no writes); plain `run` still refuses until 4.5.
- **3.6 moves after the Milestone A demo.** The assignee check and the stale-Note stop guard writes, and Milestone A has none. 3.6 is still built and merged before any booking code (D1 holds): it joins the gate for M4. M0b.2, M4, M5 and M6 are unchanged and follow Milestone A.
- **The repo is public** (Joey, 24 Oct 2026), so the CEO can read it in a browser. It holds no credentials, PDFs, addresses or client names (the repo-data check, pre-commit and gitleaks in CI guard that), only the 3 trial POs' identifiers, which Must never #6 already allows in committed files. This replaces "private GitHub repo" in `SPEC.md`.
- Carried in: `SPEC.md` v1.15 (assumption 8, open question 4, Expected slices), `tasks/plan.md` (3.6, gate for M4), `tasks/todo.md`, `docs/workflow.md` v5.16.

## 24 Oct 2026 - protect_paths allows three folders outside the repo (Joey; plan task 1.2)

- Plan task 1.2 said `protect_paths.py` blocks every path outside the repo. That would also block plan mode's plan file, Claude Code's memory and Claude's scratchpad, and "plan mode first" is how every step task starts.
- So exactly three folders outside the repo may be written: `~/.claude/plans/`, this project's memory folder (`~/.claude/projects/<project path, every non-alphanumeric as "-">/memory/`) and `<temp>/claude/`. Everything else outside the repo stays blocked, including `~/.claude/settings.json`, `~/.claude/settings.local.json` and `~/.claude/hooks/`.
- Paths are resolved first (absolute, `..` collapsed, symlinks followed) and matched by whole folders, never as a string prefix, so `~/.claude/plans-evil/` doesn't match and `plans/../settings.json` is blocked. The tests cover both sides.
- `tasks/plan.md` 1.2 and `docs/workflow.md` v5.15 (Appendix A) and `SPEC.md` v1.14 (Project Structure) carry the change.

## 24 Oct 2026 — A lighter process for the MVP (Joey)

The MVP's goal is to show the agent runs by itself on the office Mac Mini against the test site. Task 1.1, a check script, took several days: three review rounds, mutation probes, and the same four documents re-edited for each small rule change. The safety core stays as it is; the process around it gets lighter.

- **Review stop only where it matters.** Every task still writes its failing test first and shows it failing. Claude stops for Joey's review before writing code only on 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2: the guard, the hooks, the decision engine and readers, and anything that acts in MySys. On the other tasks it commits the test and carries on. Test changes still go in their own `test:` commit.
- **The freeze rule covers the agent, not the tooling.** A dated entry here plus `SPEC.md` and `tasks/plan.md` is needed for a change to what the agent does in MySys or prints in its run output, or for anything that loosens a safety control (the guard, the hooks, the repo-data check, CI, a Must-never rule). Tightening a dev-tooling rule needs only a clear commit message.
- **No extra work.** No mutation probes, no second review round unless the fixes were large, and no doc edits a task doesn't need.
- **Also in `CLAUDE.md`:** new text uses a plain dash, not the em dash; `uv.lock` and other generated files are changed only through their tool; an unrelated failure is reported, not fixed in the current task; the agent-skills commands are listed by their full names.
- Unchanged: the guard, the two readers and their agreement rule, skip on doubt, test site only, the Must-never rules, check + CI, Joey merges.
- Carried in: `CLAUDE.md`, `SPEC.md` v1.13 (Code style), `tasks/plan.md` (Cross-cutting rules), `docs/workflow.md` v5.14 (Stage 5 step 4, ground rules).

## 19 Oct 2026 — The repo-data check is stricter (Joey; plan task 1.1; widened 21 Oct 2026 after the task's code review and security review)

- The banned folders match **at any depth**, as `.gitignore` does, and the list adds `.state/` and `traces/`, both already git-ignored: `private/`, `logs/`, `state/`, `.state/`, `traces/`, `.playwright-cli/`.
- Trace files match `*trace*.zip` (was `trace*.zip`), so `.gitignore`'s `*.trace.zip` is caught too.
- **Widened 21 Oct 2026:**
  - **Any case.** Folder names and extensions match in any case (`Private/`, `shot.PNG`); this laptop's file system ignores case.
  - **Secret files.** `.env` and `.env.*` files (no `.env.example` exception), `.env/` and `secrets/` folders, and `config/live*.toml` are banned at any depth (`.env/` folders added 24 Oct, after the second code review: `.gitignore`'s `.env` matches a folder too). They were only git-ignored, which `git add -f` gets past, and gitleaks can't recognise a MySys password by its pattern.
  - **Images.** `*.png`, `*.jpg`, `*.jpeg`, `*.webp` and `*.gif` are banned anywhere, because test-site screen captures are real data (Must never #6). `.yml` stays allowed (CI and pre-commit need it), so a copied-out accessibility snapshot isn't caught by the rule; review still has to.
  - **Fixture PDFs.** The rule can't tell a real PDF in `tests/seam1/fixtures/pdfs/` from a fake, so plan task 2.1 now requires every committed fixture PDF to match the generator's output byte for byte.
- ruff skips `*.md`: ruff 0.17 also formats Python blocks in Markdown, and the docs' snippets are illustrative, not code.
- `SPEC.md` v1.12 (Commands), `tasks/plan.md` 1.1 and `docs/workflow.md` v5.12 (Appendix A) carry the change.

## 16 Oct 2026 — MVP plan frozen: decisions D1–D7 (Joey; proposed by Claude after two doubt-driven reviews of `tasks/plan.md`)

`tasks/plan.md` and `tasks/todo.md` are approved. This is the freeze point: from now on a behaviour change needs a dated entry here plus `SPEC.md` and `tasks/plan.md`, in the same commit. `SPEC.md` v1.11, `docs/specs/spec.md` v1.7, `docs/workflow.md` v5.10 and `docs/macmini-setup.md` v1.2 carry the changes.

- **D1 — run controls before booking.** The kill switch, Perth window, run cap and assignee check are built in M3, before any booking code; M5 keeps the alerts and the safety cases. After the S1 spike the Mac Mini job is unloaded, and it is loaded only for the first bookings (plan task 4.6) and from M6. Until then, plain `run` refuses (exit 2). Why: the wrapper pulls `main` every run, so a merge would otherwise deploy booking code to a loaded job with no controls.
- **D2 — the trial PDF briefly on disk.** Chromium writes every download to disk, so "in memory only" isn't possible. The browser is launched with `downloads_path` set to a run-scoped temp folder. The file is read into memory and deleted at once, the folder is removed in a `finally` block, and leftovers are removed at every run start. W1 uploads from the bytes. FileVault is on. **CEO decision 2 was asked on "in memory only", so Joey tells the CEO before it's confirmed.** `CLAUDE.md` Must never #6 needs Joey's wording change.
- **D3 — real-page refusal tests can't press anything.** The guard is split into `vet()` (resolve, allow or refuse; no action code) and `act()` (calls `vet()`, then acts on the element `vet()` resolved). Tests on the real site that prove a refusal (Discard, a Hold-dialog checkbox) call only `vet()`; `act()` refusing is tested on local HTML. Recorded as not "targeting" under Must never #2 (Joey adds the wording to `CLAUDE.md`).
- **D4 — where forbidden strings may appear.** The live host only in `guard_bash.py`'s deny regex (`(?<!test-)prompt\.mysys\.com\.au`) and its test; `ANTHROPIC_API_KEY` only in the secrets test that proves it's ignored; a fake `sk-ant-` string only in the hook test, allowlisted for gitleaks by path. `CLAUDE.md` Must never #3 and Secrets need Joey's wording, #3 before plan task 1.2.
- **D5 — the denylist on a `<select>`** checks the select's own name plus the label of the option being chosen, never every option's text.
- **D6 — the stale-Note stop.** At the start of `run` and `run --decide-only`, after login, a Pending Note still assigned to the agent (left by an earlier partial write or failed return) stops the run with an `ALERT` before any Note is taken. This **reverses** SPEC v1.10's "Note left assigned to the agent (so later runs ignore it)": with no state between runs, one systematic bug could otherwise leave a half-booked Note every hour. MySys is the state, so nothing is stored.
- **D7 — assignee check before W1 and W4 only** (`SPEC.md` §8 and `docs/specs/spec.md` §8 said before every write). Each check leaves the current window for the Note Pool; before W2 that meant leaving a filled, unsubmitted Create New Task form that no screen-map row covers, and then submitting it unchecked. W1 → W2 → W3 now stay in the project window, and `enabled` is still re-read before every step. Cost: a person taking the Note during W1–W3 is caught at W4 as `PARTIAL_WRITE`, which is what the every-write rule gave from W3 on anyway. Option B (keep every write, map the form's round trip, repeat W1's read-back before Submit) was rejected.
- **One agent at a time** (follows from D7 and the shared agent account): no laptop test-site run while the Mac Mini job is loaded, and no manual Mac Mini run while a laptop run is going.
- **Plan open questions answered as recommended:**
  - (2) The dependencies are `playwright`, `pdfplumber`, `anthropic`, `pydantic` and `keyring`; the dev dependencies are `pytest`, `ruff`, `pre-commit`, plus `reportlab` for the fake-PDF generator. Anything else still gets asked.
  - (3) The allowlist adds login (username, password, "Log in") and the module navigation (Project top tab, Note Pool, Projects sub-tab).
  - (4) Two new NOTE values for run output only: `"outcome": "skipped", "reason": "DECIDE_ONLY"` and `"outcome": "untouched", "reason": "NOTE_TAKEN"`.
  - (5) CI installs Chromium for the guard's tests.
  - (6) `enabled` is re-read before every write step.
  - (7) The run cap is checked before each new Note, and a Note in progress is finished. Kill-switch and window exits are code 0.
  - (8) The booker has a test-only `stop_after` parameter; `run` never passes it.
- **Also fixed in the plan:**
  - **Guard:** the build check bans the `request` attribute rather than HTTP verb names (which would have caught `download.delete()`). Locator names are matched exactly.
  - **`Proceed`:** it's frozen and names its `note_id`, internal number and pln.
  - **Email box:** Send Email Notification is unticked after `before_write`, right before the committing click.
  - **Test output:** seam-2 and real-PO failure reports are cut to the exception type, so no real data reaches test output. Selecting `-m testsite` explicitly turns a missing secret into an error.
  - **Spike:** it needs M0b.1 (panel anchors) first.
  - **Accepted for the MVP:** a short list in `tasks/plan.md` → Risks.
- **M0b grows:**
  - M0b.1 adds rows 25–28 (moving between windows, anchors for unlabelled controls, the Note Pool after a filter change, reload or login, and reopening an open project).
  - M0b.1 also asks whether `fill` alone runs a search, and whether returning a Note to the pool takes one Assign or two.
  - M0b.2 closes screen-map open item 8 in full and checks whether the upload is saved before Submit.
  - M0b.1 is now needed before plan task 1.8, the spike.

## 16 Oct 2026 — The 3 trial POs are real; SPEC fixed against the screen map (Joey; defaults proposed by Claude, accepted by Joey)

- **Found:** the 3 trial POs on the test site (2609017B, 2609034B, 2610002B) are **real B1 POs**, with real site addresses and client names. The test site's 2609017B PDF is byte-identical to the live one in `private/pdfs/`.
- **Decision (Joey): keep them as the trial POs and change the rules.** Their internal numbers, PO numbers and test-site plns may appear in committed files and run output (they already do). Their PDFs, addresses, client names and other PDF content stay in MySys and `private/`; test-site captures and screenshots now count as real data. The Mac Mini reads them from the test site in memory and sends them to Claude, as on live, so **the CEO must confirm decision 2 before the first Mac Mini run that downloads one** (M3). Seam 1's committed fixtures become 3 **generated fake** POs (M2; the generator's dependency needs Joey's OK). The 3 trial POs join the laptop-only real-PO seam. `docs/specs/spec.md`'s address examples were replaced with fake ones, in case they were real (ADR-001 line 125 still has the old example; ADRs are left as recorded, Joey to decide). A check of the tracked files found no address or name from the 3 PDFs.
- **Live Projects search (Joey):** 3–4 projects come back per internal number, and only one ends with `/048`; the others are ignored. Rule: exactly one row with Company B1 Homes and Client Ref No. `<internal no>/048` (on test, where Client Ref No. is the bare number, `<internal no>`). SPEC assumes the column is Client Ref No.; confirm in Stage 3B.
- **Defaults proposed by Claude on Joey's "fix them", all accepted by Joey on 16 Oct 2026** (all in `SPEC.md` v1.10 → MySys screen rules):
  - **Duplicate check, MVP:** any non-Cancelled Compaction Test task on the project → `DUPLICATE_TASK`, whatever its PO number (the task table doesn't show PO numbers). v1 compares PO numbers from the task detail screen.
  - **New skip reason `NOTE_ALREADY_LINKED`** (step 2a), plus step 0 needs the Note Pool's Project cell to read `---`. Otherwise a pre-linked Note would pass every check and fail at W4 after the task exists.
  - **"close" is denylisted** (it removes the attached PDF and clears Task Client). The agent never clicks a window Close: it reloads `base_url` between Notes.
  - **Upload to PO Documents** (as in the walkthrough), not Documents; **task Note = the Note's body**, not its title (the captures show a one-line body).
  - **Send Email Notification** is unticked and read back before every write on the Note window (Assign, Link, Solved), not only before Assign.
  - **Assign to pool:** user list `--Select User--` + pool list Agent Pool, because the user list pre-selects the agent.
  - **Assignee check:** a fresh Note Pool search by Note ID, not the open Note window.
  - **W2:** the new task is the one Compaction Test number that wasn't there before Submit; PO number, document and Note are read back on the task detail screen.
  - **W3:** before confirming Hold, also check Reset unticked, reminder ticked with 0, the heading names the new task (check 3.1).
  - **Attachments** are counted before any click (two links → `MULTIPLE_PDFS`, not a guard refusal). **Note Pool:** oldest first, page 1 only.
  - **"Changes nothing" on a rerun** means no task, link, Solved or final-assignee change; the Assign log lines from re-checking a skipped Note are expected.
- **New slice M0b** (Joey clicks, Claude observes): task detail screen, Link to Project search/select, Notes with 0 and 2 attachments, Note-window refresh and Note Pool search by ID, PO Number prefill. M3 needs the attachment and assignee parts; M4 needs task detail and Link.
- **Corrections:** the Compaction Test sub-form has no Creator (the one Creator is in the Client section); test Notes come in both title styles (below). `CLAUDE.md` Must never #2 and #6 updated. `SPEC.md` v1.10, `docs/specs/spec.md` v1.6, `docs/screen-map.md` v1.1.

## 16 Oct 2026 — Screen map written; the denylist grows (Joey)

- **`docs/screen-map.md` v1.0** maps Stage 3A rows 01–16 on the test site, with fake values only. The checks below come from it.
- **The denylist adds four buttons** found in the walkthrough: **Pending** on the Note (reopens a Solved Note), **Undo Cancellation**, **Un-Hold** and **Change Project**. Names are matched as substrings, case-insensitive ("Undo Cancellation" contains "Cancel"). The Note Pool's Status filter lists a Discard option, so the agent never sets that filter. `docs/specs/spec.md` v1.5 §5 and `SPEC.md` v1.9 (Never, open questions 1, 3, 8 and 9). `CLAUDE.md` Must never #2 still lists only the original buttons: Joey to update it.

## 16 Oct 2026 — Check 3.1 (C1): the Hold dialog's related-task checkboxes are unticked by default (Stage 3A, row 11)

- **Found:** in the Hold Task dialog every Related Tasks checkbox (58 jobs on the walkthrough project) and the Select-all box were **unticked**. "Reset turn around time" and "Send me a reminder email at this date" were unticked. "Send me a reminder email every **0** days" was **ticked**, and 0 means no reminders.
- **Decision:** C1 doesn't block Hold on the test site, so no CEO decision is needed before M4. The agent still touches no checkbox in the dialog (Must never #2). Before pressing Hold it reads every one: any related-task or reset box ticked, or the reminder not 0, → close the browser context, `PARTIAL_WRITE` alert (the task already exists).
- **Live:** not seen (opening Hold on live would be a write). Confirm on the first live booking under supervision. `docs/screen-map.md` row 11.

## 16 Oct 2026 — Check 3.2 (C3): a Note goes back to the pool with Assign, no Unassign (Stage 3A, row 15)

- **Found:** on the Note window, choosing **Agent Pool** in the pool list and pressing **Assign** moved a Note from Agent 1 (MySys Only) to Agent Pool. Log: "User Assigned: … From Agent 1 (MySys Only) to Agent Pool"; Assignee reads Agent Pool; status stays Pending. No Unassign or Unlink was needed.
- **Decision:** C3 is answered "yes"; the skip path ("Note back to the pool") uses Assign with the pool list, and no CEO decision is needed before M3. Unlink unassigns *without* putting the Note in a pool (seen at row 04), which is one more reason it stays denied.
- **Live:** the pool there is PO Allocation Pool; not tried (view-only). `docs/screen-map.md` row 15.

## 16 Oct 2026 — Check 3.3: Send Email Notification is only on the Note window (Stage 3A, rows 02–15)

- **Found:** the checkbox appears **only** in the Note window's Assign controls, and it is **ticked every time a Note window opens**. It isn't on Create New Task, the Hold Task dialog (which has its own reminder-email checkbox, see check 3.1) or with Solved. An untick holds through Assign while the window stays open.
- **Decision:** the agent unticks it and reads it back as unticked before **every** Assign, including the skip path. Joey's view (16 Oct 2026) is that a ticked box doesn't matter; CLAUDE.md Must never #4 and `SPEC.md` keep the untick until Joey changes them.
- Not known: whether an email went out when the walkthrough assigned with the box ticked (row 03). `docs/screen-map.md` rows 02–04.

## 16 Oct 2026 — Check 3.4: no MFA seen on the agent account; password expiry unknown

- **Found:** the test-site login page has Username, Password and "Log in" (plus a "Microsoft account login" link the agent doesn't use). Joey logged in as the agent account four times on 16 Oct 2026 with no second step.
- **Decision:** MFA doesn't block M1 on the test site. **Still open:** whether the agent account's password expires, and the live login. Joey to ask the MySys admin before the Mac Mini runs unattended; a failed login already stops the run (`LOGIN_FAILED` alert).

## 16 Oct 2026 — Check 3.5: opening a Note or downloading its PDF changes nothing visible (Stage 3A, rows 02, 05)

- **Found:** on three Notes, opening the Note window and downloading the PDF added **no log line** and left assignee and status unchanged. The download link carries a `user_note_id` that differs from the Note ID. Clicking the file row also opens a preview window.
- **Decision:** Stage 3B may open live Notes and download their PDFs (still no Assign or any other button). Caveat: the Note window doesn't show lock state, so whether opening a Note locks it can't be seen; the Locked filter changed between captures, probably by hand.

## 16 Oct 2026 — Check 3.6: how a cancelled task looks; an On Hold task offers Cancel (Stage 3A, rows 09–14)

- **Found:** a cancelled task's row reads "(tsk_N) | Compaction Test" with an **Undo Cancellation** button and Status **Cancelled**. An On Hold task's row shows **Cancel** next to **Un-Hold**, so it can be cancelled directly (offered; the walkthrough didn't press it). A new task shows Cancel and Hold.
- **Decision:** the test profile's duplicate check (ignore Cancelled, 15 Oct entry) recognises a cancelled task by its Status cell **Cancelled** (or the Undo Cancellation button). The reset (Stage 6.1) can cancel an On Hold task without releasing it first. The project table doesn't show the PO number, so the duplicate check must open each Compaction Test task to compare PO numbers (`docs/screen-map.md` open item 2). The agent never presses Cancel, Undo Cancellation or Un-Hold.

## 16 Oct 2026 — 3 real POs for the MVP's real-PO seam (Joey)

- **The real-PO decision seam (`-m real_data`) uses the 3 most recent real B1 `/048` POs** for the MVP, not 10–20 (14 Oct entry below). Joey saved them to `private/pdfs/`, with their cases in `private/fixtures/cases.toml`, on the laptop only.
- **What it proves is narrower:** 0 false PROCEED on 3 POs is weak evidence, and coverage can't be judged against 80% with 3. So S3 reports coverage without the 80% line, and any skip of a clean real PO is reviewed before M3.
- **Before go-live, the set grows to 10–20** (mostly `/048`, plus other suffixes and odd ones), and the 80% coverage line applies then. The CEO's go-live sign-off uses that larger set.
- `SPEC.md` v1.8 (testing strategy, M0, S3), `docs/workflow.md` v5.8 (Stage 3B), `README.md`, `docs/specs/roadmap.md`.

## 16 Oct 2026 — The last step is Solved; the test site has no Resolve button (Joey)

- **Found in the Stage 3A walkthrough** (2609017B and 2610002B): after Link to Project, the Note's Status buttons are **Pending, Solved and Discard**. There is no Resolve button. This replaces SOP step 15's "Solved and Resolve are equivalent; use Resolve" and `docs/specs/spec.md` story 28's "using Resolve, not Solved".
- **W5 = press Solved on the Note.** Read-back: the status reads "Solved by" the agent, a log line "Status changed … From Pending to Solved" appears, and the Note leaves the Pending list. Once a Note is Solved, **Pending** reopens it, so the agent never presses Pending.
- **Live is still to check** in Stage 3B: if live has a Resolve button, decide then which one the live profile uses.
- **Stage 3A gets new rows** for the screens off the happy path: 15 (send a Note back to Agent Pool with Assign, the skip path), 16 (Projects search with no match, moved out of row 06), 17 (optional: a Create New Task error) and 18 (a cancelled task, was row 07b).
- `SPEC.md` v1.7, `docs/specs/spec.md` v1.4, `docs/workflow.md` v5.7, and the wording in `CLAUDE.md`, `docs/intent.md`, `docs/project-context.md`, `docs/demo-runbook.md`, `docs/macmini-setup.md`, `docs/specs/mission.md`, `README.md` and `roadmap.md`. ADR-001 is left as recorded.

## 15 Oct 2026 — CEO decision 3: the office Mac Mini runs the trial and production (CEO; setup choices by Joey)

- **Host = the office Mac Mini** (ADR-002 Option D, now **Accepted**), for the MVP trial **and** production. It replaces the Anthropic cloud routine for the trial (Option C, 14 Oct entry below) and the expected Sydney cloud VM for production. ADR-002's 14 Oct scores (A 4.60, B 4.20, D 2.80) are kept as the record; the CEO chose D because the Mac Mini was already bought. Maintainer: Joey, with a named backup admin.
- **The trial waiver is withdrawn.** On the Mac Mini, gate H2 passes (secrets in the agent user's Keychain; no AI session on the machine) and H5 passes (company-owned; Joey's and a backup admin account). `SPEC.md` → Trial waiver becomes **Trial conditions**: test-site credentials only, a dedicated low-limit Anthropic key, no real client data on the Mac Mini during the MVP.
- **A separate standard macOS user `poagent`** runs the agent; Joey and the backup have admin accounts. Claude Code is never installed for `poagent`.
- **FileVault on, no automatic login** (Joey, 15 Oct 2026). macOS allows one or the other. The Mac Mini will hold the live MySys password and handle real POs in production, and a missed run only delays POs (they stay in the pool), while a stolen unencrypted Mac gives up the agent's Keychain. Cost: after an unplanned restart (e.g. power failure) the Mac powers back on but waits at the FileVault screen until someone logs in as `poagent`. Revisit if this costs too many runs.
- **Schedule:** a launchd LaunchAgent in `poagent`'s session at **7 minutes past each hour, 07:07–17:07, Monday–Friday**, Mac clock set to **Australia/Perth**. A LaunchAgent (not a LaunchDaemon) because keyring needs `poagent`'s login Keychain, which is unlocked only while that user is logged in. launchd never starts the job while it is still running.
- **The Mac Mini stays up:** no sleep, starts up automatically after a power failure, macOS updates download automatically but are installed by hand **outside 07:00–18:00** (weekday evenings or weekends).
- **Secrets:** in `poagent`'s login Keychain through `keyring` (service `po-agent`, the same names). No `PO_AGENT_*` variables on the Mac Mini; env vars remain for CI and tests.
- **What the routine's Claude session did moves to a small script**, `scripts/macmini-run.sh` (M1): pull `main` (so `enabled = false` on `main` still stops the next run), `uv sync --locked`, run the agent with a 20-minute limit, append the short run output to `~/Library/Logs/po-agent/runs.log`, and on any `ALERT` line or non-zero exit open a GitHub issue labelled `po-agent-alert`. The Mac Mini's GitHub access is one fine-grained token for this repo only (contents read, issues write), kept in the Keychain by `gh`.
- **The MVP still keeps no state between runs** (Joey's 14 Oct choice, now for scope, not because of the host). `runs.log` is a record for Joey, not state the agent reads. v1's skip list, logs and `STOP` file go on the Mac Mini's disk.
- **First step on the Mac Mini:** a MySys test-site login by hand from it, before anything else is installed (`docs/macmini-setup.md` section 2).
- Setup steps: `docs/macmini-setup.md` (replaces `docs/routine-setup.md`). `SPEC.md` v1.6; `docs/specs/spec.md`, `tech-stack.md` and `roadmap.md` v1.3.

## 15 Oct 2026 — Repeatable demo (Joey)

- **The demo must be repeatable, at least 3 times** (to Joey's boss and the CEO). After each demo Joey resets the test site with his own account: cancel the 3 trial tasks, place fresh copies of the 3 Notes (`docs/demo-runbook.md`). The test profile's duplicate check ignores Cancelled tasks, so the agent books the same POs again. New success criterion `SPEC.md` S8; `SPEC.md` v1.5.
- Demos can be shown from the laptop (`--headed --slow-mo 500`, the browser visible) or from the routine (**Run now**). *(The routine is replaced by the Mac Mini: CEO decision 3, entry above.)*

## 15 Oct 2026 — MVP spec approved (Joey)

- **`SPEC.md` approved** (v1.4). Next: M0 screen mapping, then `/plan` in Claude Code.
- **Test-site reset:** Joey's own account can **cancel** tasks on the test site; that's how the test site is reset (`docs/workflow.md` Stage 6.1). The agent itself still never presses Cancel.
- **Duplicate check, test profile only:** ignores Compaction Test tasks whose status is Cancelled (`duplicate_ignores_cancelled = true` in `config/test.toml`). On live every existing task counts. Seam 1 tests both settings.
- **Joey's Claude plan is Pro:** the routine's environment isn't shared; routine runs use Pro usage; *(routine parts superseded by CEO decision 3)* the claude.ai model-training setting must be off before Claude Code reads real data.
- **Node.js can be installed** on Joey's laptop, so Playwright CLI is used for screen mapping.

## 15 Oct 2026 — Screens mapped with Playwright CLI; all 3 trial POs at every stage (Joey)

- **Screen mapping uses Playwright CLI** (`@playwright/cli`), observe-only: Joey does every click and every typed value, including the login; Claude Code only runs `snapshot`, `screenshot`, `find` and `generate-locator`, and writes `docs/screen-map.md` from the accessibility trees. `.claude/settings.json` denies every acting, state or network command; from M1 the `guard_bash.py` hook allows only the observe commands. `.playwright/cli.config.json` blocks the live origin. Its bundled skills aren't installed. The custom `po-agent capture` command is dropped. Fallback without Node.js: the classic `playwright codegen` recorder plus screenshots.
- **The 3 trial POs at every stage:** walkthrough = full SOP for 2609017B, read-only screens for 2609034B and 2610002B; M4 books all three in turn; seam 2 and the S4 trial book all three; the S5 skip case is a fresh copy of 2609034B.
- **`improve-codebase-architecture` vs Addy's skills:** it doesn't replace them. It's the better tool for one job (surveying the code to shape the shared MySys package), so it's used after the MVP and before automation #2 only.

## 14 Oct 2026 — Only the 3 trial POs; Addy's skills plus one Pocock skill (Joey)

- **No 4th fake PO.** The walkthrough, the build and the MVP demo use only the 3 trial POs (2609017B, 2609034B, 2610002B). The walkthrough books 2609017B by hand, so the test site is **reset** by Joey (own account) before M3, after each booking test and before the demo. The skip case in the demo is a fresh copy of a booked trial Note (`DUPLICATE_TASK`); address and other mutations are tested offline in seam 1. Open: can Joey's own account remove a task on the test site?
- **Skills:** Addy Osmani's agent-skills is the main workflow (following its greenfield tutorial). Matt Pocock's `improve-codebase-architecture` (with `codebase-design`, `grilling`, `domain-modeling`) is installed only for an architecture review after the MVP and before automation #2, then removed. The full Pocock plugin isn't installed. Details: `docs/workflow.md` → The skills plan.

## 14 Oct 2026 — The agent may read real client data (Joey; CEO to confirm)

- **Rule change:** the agent may see real client data. Claude (the reader) may read real B1 PO PDFs and Note text; Claude Code may read real PDFs and live-screen captures on Joey's laptop to understand the pages. Joey's call; it answers CEO decision 2 once the CEO confirms. Decision 2 stays open in the CEO decision brief until then.
- **The agent has its own MySys account** on live (as on the test site).
- **Bookings stay on the test site.** The MVP's code never logs into live; go-live still needs the CEO's sign-off after the trial (decision 1).
- **Real data stays on Joey's laptop:** the git-ignored `private/` folder (real PDFs, live screenshots, captures, `cases.toml`). Never in GitHub, a PR, an issue, run output or the cloud routine. A commit hook and the check command block it.
- **Live is view-only during capture:** no Assign, no edits, no bookings with the agent account.
- **New MVP evidence:** a real-PO decision-seam run on the laptop (`-m real_data`, 10–20 real POs): 0 false PROCEED, with per-field agreement, coverage and cost per PO.
- **Before Claude Code reads real data:** on a Pro/Max plan, the claude.ai model-training setting must be off.
- C4 (rules-only address reader) becomes unlikely to be needed; it stays deferred until the CEO confirms decision 2.

## 14 Oct 2026 — MVP first, on an Anthropic cloud routine (Joey)

*The hosting parts of this entry (trial host, waiver, routine alerts, secrets on the routine, production host) are superseded by CEO decision 3, 15 Oct 2026 (above). The MVP scope stands.*

- **Build an MVP first** to prove the agent works end to end on the test site, before the full v1 hardening. Scope chosen by Joey: **happy path + core safety** (`SPEC.md` → Objective): the full ADR-001 design (two readers, verify-not-extract, agreement), all checks before any write, action guard, read-back, skip → pool through Assign, `enabled` kill switch, Perth window, deterministic-only switch, test site only. Deferred to v1: skip list and 24 h retry, partial-write auto-resume (MVP: alert, Note left assigned to the agent, Joey finishes by hand), agent-written `STOP` file (MVP: exit code 3 + alert; Joey turns the routine off), circuit breaker (MVP: first failure stops the run), start-of-run sweep, single-run lock, daily logs with retention, live profile, sender-domain check, email/Teams alerts.
- **Trial host = ADR-002 Option C: an Anthropic cloud routine running the script.** The script still does every click and Claude (the reader) still only reads; the routine's own Claude session only runs three fixed commands and reports.
- **ADR-002 gates H2 (secrets unreadable by the AI session) and H5 (company-owned) are waived for the trial only.** Scope: the test-site agent account, a dedicated Anthropic key with a low spend limit, fake data only. Mitigations in `SPEC.md` → Trial waiver. The waiver never covers live credentials or real POs.
- **No state between routine runs for the MVP** (Joey, 14 Oct 2026). MySys is the state: resolved Notes are done, the duplicate check stops double bookings, skipped Notes are checked again each run. The run transcript is the log. (A git state branch was considered and not chosen.) The skip list, logs and `STOP` file come back in v1 on a host with a disk.
- **MVP alerts:** `ALERT` lines in the run output; the routine opens a GitHub issue labelled `po-agent-alert`, so GitHub emails Joey.
- **Secrets naming:** environment variables `PO_AGENT_*` first (routine; later the VM's root-only env file), keyring fallback (laptop). Not `ANTHROPIC_API_KEY`, so Claude Code itself can't pick it up.
- **GitHub is now required** (routines clone from GitHub). The "no GitHub" fallback is dropped. CEO/IT OK still to get.
- **Production host:** most likely a **Sydney cloud VM** (ADR-002 Option B). Not decided: CEO decision 3 is pending. ADR-002 stays *Proposed* for production.
- **Skills:** the build uses **Addy Osmani's agent-skills** (`/spec` → `/plan` → `/build` → `/review`), replacing Matt Pocock's skills. MVP spec at `SPEC.md`; plan at `tasks/plan.md` and `tasks/todo.md`.
- **Docs moved into the repo:** `claude/intent.md` → `docs/intent.md`, `claude/po-agent-decisions.md` → `docs/decisions.md`, `claude/hosting-research.md` → `docs/hosting-research.md`, `claude/claude-code-workflow.md` → `docs/workflow.md`, `specs/*` → `docs/specs/*`. The repo is the source of truth from now on; the claude.ai project keeps copies.

## Scope

- B1 Homes only. Compaction Test task booking, always a pre-booking → always put on hold. PO = purchase order.
- Live: only notes with subject "[B1 Homes] Order XXXXXXXX/048" (/048 = compaction). PDF must contain "COMPACTION".
- Other suffixes (e.g. /023, /025) are other task types — out of scope, left untouched.

## Architecture (ADR-001 — Accepted; approved by the CEO through decision 1, recorded 13 Oct 2026)

- **Hybrid (Option B).** Deterministic Playwright script does every click through an allowlist; deterministic reader (pdfplumber + patterns + address normaliser/verifier) and Claude (no tools, schema-bound JSON) both read; proceed only if both agree and match MySys. Claude never clicks.
- Scores (weights C1 accuracy 30, C2 messy POs 20, C3 UI change 15, C4 cost 5, C5 effort 15, C6 audit/reuse 15 — set by Claude on Joey's behalf): B 3.95 · A (no-AI script) 3.70 · C (Claude fallback only) 3.45 · D (Claude drives browser) dropped on gates G2/G3. Internal-request replay excluded by G1.
- Flip: A wins if weight(C5)+weight(C4) > weight(C1)+weight(C6), or if a single deterministic address reader is judged as safe as two.
- **Data (G7):** Claude may read real client PO PDFs and note text (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real data stays on Joey's laptop; bookings stay on the test site until go-live.

### ADR-001 action items (approved with decision 1)

1. **ADR accepted.** Status set to Accepted.
2. **Address check = verify, not extract.** Claude extracts lot, street and suburb; the deterministic side verifies each appears in the PDF text (together, in one address block) and matches the MySys project after normalisation. `docs/specs/spec.md` §4.
3. **Decision-seam tests.** Run the full fixture set through both readers; measure agreement on the 3 trial PDFs and the mutated copies. Any false PROCEED is a blocker.
4. **Token cost.** Record Claude token cost per PO during the trial for the CEO.
5. **Option A fallback.** `reader_mode = deterministic-only` must always work. The rules-only address reader is deferred: until it's built, that mode returns every PO to the admin. Build it if decision 2 is "no". *(In the MVP: the switch exists and every PO skips `ADDRESS_UNVERIFIABLE`; the rules-only address reader stays deferred.)*

## Safeguards (approved with decision 1)

- **Half-finished bookings:** the agent records the partial write, alerts Joey, and completes its own booking on the next run after re-running every check. Exception to "no exception report" and "duplicate → skip", for the agent's own task only. *(MVP: alert, Note left assigned to the agent, run stops; Joey finishes by hand; auto-resume in v1.)*
- **Stop after any error:** a booking error (wrong project, wrong PO number or missing PDF found on read-back) makes the agent create a `STOP` file and alert Joey. Only a person removes it, after the CEO approves a restart. *(MVP: no `STOP` file; exit code 3 + alert, and Joey unloads the Mac Mini's launchd job and sets `enabled = false`.)*
- **Without Claude:** POs go to the admin as today.
- **Alerts:** to Joey only, never to customers. Channel (email or Teams webhook) still to choose for v1; MVP uses a GitHub issue.

## Implementation simplifications (13 Oct 2026, Joey)

- No database. State is a skip-list JSON file plus daily JSON-lines logs (one line per Note, one summary line per run), kept 90 days. Extra detail and screenshots only on failures.

## Hosting (CEO decision 3 — decided 15 Oct 2026)

- The existing company server is very old; it won't host the agent.
- **Trial and production: the office Mac Mini** (already purchased), ADR-002 Option D, Accepted. Setup: `docs/macmini-setup.md`. Joey as maintainer plus one named backup admin. Test MySys access from the Mac Mini first.
- *History:* the trial was first planned on an Anthropic cloud routine (14 Oct 2026, H2/H5 waived), and production was expected on a Sydney cloud VM. Both superseded by decision 3.
- Full comparison: `docs/hosting-research.md` (research as of 13–14 Oct). The drafted VM request for IT isn't needed.
- **ADR-002 proposed (14 Oct 2026):** `docs/specs/ADR-002-po-agent-hosting.md`. An Anthropic cloud routine running the script was not chosen for production (2.45): it fails the secrets gate, has no state between runs, and belongs to a personal account. Claude-driven options (routine with a browser tool, Cowork + Claude in Chrome) stay rejected under ADR-001 G2/G3. Estimated 3-year cost (hosting + Claude): IT VM about A$40–330; Sydney VM about A$610–1,010.

## Confirmed SOP (live)

1. Login as agent account → Project (top tab).
2. Note Pool → Assigned Pool = PO Allocation Pool, Locked/Unlocked = Locked.
3. Open note "[B1 Homes] Order XXXXXXXX/048".
4. Click Assign → assign note to the agent account (before downloading).
5. Download attached PO PDF; must contain "COMPACTION".
6. Email body contains internal number as file name, e.g. 2610001B_048 (always ends _048).
7. Projects (not Tasks) → search client internal number (e.g. 2610001B) → open pln → Create New Task.
8. Client > Creator = "Perth Scheduling".
9. Tick Compaction Test (right-hand list).
10. PO Number, e.g. 2610001B/048 (see "Answered questions" for sources).
11. Documents → upload the PO PDF.
12. Note = email body only → Submit.
13. Hold → Note "ON HOLD UNTIL CALL UP" → Hold.
14. Back on note: Link to Project → search pln → select.
15. **Solved** (the Note's Status buttons). *16 Oct 2026: the test site has no Resolve button, so the agent uses Solved (entry above). Check in 3B whether live has a Resolve button.*

- "Send Email Notification": leave unticked (it is ticked by default).

## Test-site differences (from note 235957 screenshot, 12 Oct 2026)

- Testing only: Joey plays B1 Homes and places the trial PO requests directly in the **Agent Pool** (not PO Allocation Pool). *16 Oct 2026: the trial POs are real B1 POs (entry above).*
- Note title = email body text, e.g. "Please find attached Purchase Order / Quotation file 2609034B_048_1.pdf" (no "[B1 Homes] Order …/048"). *16 Oct 2026: newer test Notes have the live-style title "[B1 Homes] Order 2609034B/048" with that text as the body; both styles are in the pool (`docs/screen-map.md` row 01).*
- Source shows "Agent 1 (MySys Only)" because Joey creates the notes (no sender email). Agent's user name in the Assign dropdown is "Agent 1 (MySys Only)".
- Everything else follows the live SOP.

## Answered questions

- PO number: from PDF "Purchase Order No", must agree with file name (_048 → /048) and, on live, the title. Disagreement → skip.
- B1 Homes check: PDF issuer "B1 Homes Pty Ltd" on both sites; on live `[B1 Homes]` title also required.
- Locked filter: applied on both sites.
- Backlog at go-live: read as "process existing /048 notes like new ones" — to confirm, incl. any age cut-off.
- The trial PDFs' addresses match their test projects (lot, street, suburb; the project adds a house number, postcode and state). *16 Oct 2026: the trial PDFs are real, not fake.*
- Architecture: approved by the CEO (decision 1, recorded 13 Oct 2026).
- Trial and production host: the office Mac Mini (CEO decision 3, 15 Oct 2026; replaces the cloud routine Joey chose for the trial on 14 Oct).

## Rules

- Address in PO PDF must match the project: lot number + street + suburb; ignore formatting, case, St/Street, missing postcode/state. Any of the three different or missing → skip.
- Skip → assign note back to the pool it came from. No exception report, apart from the approved alerts to Joey.
- Retry: "project not found" skips retried for up to 24 h; other skip reasons never retried. Agent keeps its own skip list. *(MVP: all skips final.)*
- Duplicate check: skip if the project already has a Compaction Test with the same PO number, except the agent's own recorded partial booking (resume it). *(MVP: always skip.)*
- Agent account cannot delete anything; it has all permissions the SOP needs. Never: Discard, Unlink, Cancel, Unassign, remove document, related-task checkboxes in Hold dialog.
- Agent only reads emails via MySys Notes; never deletes, replies, forwards; no Outlook access.
- Credentials never stored in docs or code.
- Config switch reader = deterministic-only must always work (Option A fallback). *(In the MVP.)*
- Any booking error → agent stops itself until the CEO approves a restart. *(MVP: exit 3 + alert; Joey unloads the launchd job.)*

## Schedule

- Hourly, weekdays 07:00–18:00 Perth time. On the Mac Mini: a launchd job at 7 minutes past each hour, 07:07–17:07 Monday–Friday, with the Mac's clock on Australia/Perth (7 minutes past, so a slow start never lands on the hour).

## Problem / volume

- 0–50 B1 Homes compaction POs per week, ~2 min each; pool must be checked every day.

## Success criteria (all four)

- Accuracy (hard line): no task on wrong project, wrong PO number or missing PDF.
- Coverage: ≥80% of /048 POs handled end to end; rest cleanly returned to pool.
- Speed: every /048 PO processed or returned within 1 hour (during run hours).
- Workload: admin only handles skipped POs.

## Trial

- Test site: https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component
- Live: https://prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component
- Before the trial: decision-seam tests on the full fixture set (3 trial PDFs + mutated copies); any false PROCEED blocks.
- Pass = 3 good trial POs (real B1 POs, 16 Oct 2026 entry) processed end to end, every step correct, no human help:
  - 2609017B → pln_66935
  - 2609034B → pln_66938
  - 2610002B → pln_66940
- Record Claude token cost per PO for the CEO.
- Go-live on real POs only after CEO reviews the trial results and signs off.

## Still open

Updated 9 Nov 2026 (go-live plan, entry above); the go-live gates in `SPEC.md` -> Production are the full list.

- **Live answers** (gate 2; from 9 Nov 2026 Joey's own look at live, go-live plan entry, which adds the pool and agent names, the title format and the Pending Note count): PO Documents or Documents (open question 11); Resolve or Solved on live; whether live's Client Ref No. column ends `/048` (open question 10); whether the agent account's password expires (open question 3; MFA not seen).
- ~~CEO go-live sign-off and the backlog cut-off date~~ **Answered 9 Nov 2026:** Joey signs off under the CEO's delegated authority; no backlog cut-off (go-live plan entry).
- **Accounts** (gate 4): a named backup admin for the Mac Mini, before unattended hourly live runs (go-live plan entry). The Mac Mini's GitHub token and the `po-agent-alert` label are in place.
- ~~Heartbeat service~~ **Answered 5 Nov 2026:** a scheduled GitHub Action (entry above).
- ~~CEO decision 2~~ **Answered 25 Oct 2026:** delegated to Joey, who said yes (entry above). Since 2 Nov 2026 no model reads the PDFs.
- ~~CEO/IT OK on the private GitHub repo~~ **Answered 25 Oct 2026:** the repo is public so the CEO can read it; no real client data in it.
- ~~Alert channel for v1~~ **Answered:** a GitHub issue with the `po-agent-alert` label, which emails Joey (`docs/macmini-setup.md`).
- ~~Test-site checks C1 and C3~~ **Answered 16 Oct 2026** (entries above).
