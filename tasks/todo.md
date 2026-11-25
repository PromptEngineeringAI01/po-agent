# PO Agent MVP — task list

Full acceptance criteria, verify steps and files: `tasks/plan.md`. One task per session; branch per task from up-to-date `main`. Pace: **step** = `/agent-skills:build task <N>`, plan mode first · **auto** = `/agent-skills:build auto` (M2 only, after M1 merged) · **by hand** = Joey does it (Claude observes or writes docs only).

Every code task: failing test first → `test:` commit (no review stop since 5 Nov 2026) → code → `uv run scripts/check.py` shows `check: all passed`.

Decisions D1–D7 (16 Oct 2026) are in `tasks/plan.md` → Decisions from the doubt review; they go into `docs/decisions.md` and SPEC at the freeze.

**One agent at a time:** one laptop test-site run at a time (seam-2 tests, `run`, `spike`): the cross-worktree lock keeps seam-2 pytest runs apart, and no laptop `run` or `spike` starts while another test-site run is going (the lock doesn't cover them); no manual Mac Mini test-site run while a laptop run is going. The Mac Mini's live job keeps running: it uses another site, account and secrets (Joey, 20 Nov 2026; decisions, 20 Nov 2026, one Send Email control).

## Phase S - Summit Home, client 2 (added 24 Nov 2026; plan -> Phase S, `SPEC.md` -> Client 2: Summit Home)

Build tasks 9.1-9.15 in this order, one PR each; Joey's live steps S.0-S.5 as SPEC names them. B1 behaviour stays unchanged; any `mysys/` change runs B1's seam 2 on the test site (the advisor may batch resets). High risk = one second-model review. Open questions for the decision batch: plan -> Phase S.

**Before 9.1 (admin)**
- [x] **A.1** (done 24 Nov 2026) Joey approves Phase S (freeze point for this phase) · by hand
- [ ] **A.2** PR 165's hand edits merged (CLAUDE.md first line and Must never #6, `docs/workflow.md` phases) · Joey
- [x] **A.3** `/start-task` brief no longer says "B1 Homes only" or "in the order of Phase P" (`.claude/skills/start-task/SKILL.md`, Claude-editable: the advisor or a small task, or Joey by hand)
- [ ] **A.4** `production` tag moves during the build as Joey picks (plan -> Phase S, open question 2), each followed by one watched B1 hourly run · by hand

**S-A Seam, B1 unchanged**
- [x] **9.1** Shared models (`core/models.py`); the Creator travels in the `Proceed`, no `CREATOR` constant in `mysys/` · step · refactor · high
- [x] **9.2** `mysys/` imports no client package and holds no client constant; the booker moves to `mysys/booker.py` (PRs 177, 178); B1 seam 2 green at Checkpoint S-A (runs 1-10a) · step · refactor · high
- [x] **9.3** `--client b1|summit`; `config/clients/summit.toml` (Summit Renovations; Summit Project = Summit Developments only; `enabled = false`); Summit secret names; `preflight --client summit`; `--site test --client summit` refused · step · high
- [x] **9.4** Client interface (`core/client.py`) in the run loop; `core/` imports no client package (except `demo.py`) · step · refactor · high
- [x] **9.5** Per-client run lock, kill switch (site and client), caps (bookings, peeks), Agent 2 stale read, hold re-check by client; `"client"` in `RUN_SUMMARY` and the `booked` event · step · high
- [x] **9.6** Guard: `set_source_filter` on the Note Pool Source select, tests on local HTML · step · high · **Joey merges**

**Checkpoint S-A:** check green; import test green; B1 seam 2 green (done 25 Nov: Joey ran runs 1-10a only, all passed on a00cfb7; runs 11 and 12 skipped, since 9.1-9.5 didn't change their code; decisions, 25 Nov 2026); 9.6 merged; friction log's "Proposed" rows decided (`docs/factory-handbook.md` §11; done 25 Nov, PR 186); release summary read before the tag moves (`docs/macmini-setup.md`); first B1 hourly run watched after any tag move past here.

**S-B Decide, offline**
- [x] **9.7** Summit readers: company line, `Purchase Order No:`, COMPACTION TEST under Description; seam-1 fake cases; the 11 real PDFs move to `private/summit/pdfs/` and agree on both readers (S.0 expected compaction values pending: the real-PDF check skips until `cases.toml` gives them) · step · **review stop** · high
- [x] **9.8** Tasks read: every task's number, name, status and Task Creator in `MySysLookup`; B1's duplicate check unchanged on mapped headers (unmapped header buttons: quiet `DUPLICATE_TASK`, Joey 25 Nov 2026) · step · high
- [x] **9.9** Summit decision engine: SPEC's decision table in order, three-way company match with aliases, Client Internal No., strict duplicate, previous-task creator; `COMPANY_UNKNOWN`, `COMPANY_MISMATCH`, `CREATOR_UNKNOWN`; seam 1 `false PROCEED: 0` · step · high
- [ ] **9.10** Summit real-PO seam on the 11 POs with `private/summit/fixtures/cases.toml` (needs S.0) · step · pauses: laptop runs

**Checkpoint S-B:** Summit seam 1 `false PROCEED: 0` in CI; friction log's "Proposed" rows decided; real-PO `false PROCEED: 0` on the laptop, clean-PO skips reviewed with Joey.

**S-C Run, offline**
- [ ] **9.11** Note Pool for Summit: Source and Unlocked filters read back, Source column read, list eligibility (sender, `---`, not an agent, title shape); `spike --client summit`; from 9.4: `NotePoolRow` gains the Source cell, `NotePoolFilters` gains `source` and its `pool` becomes optional, `SummitClient.filters`/`eligible` filled · step · high
- [ ] **9.12** The peek (read-only open, iframe body rule, download, readers, lookup, decide) and `run --decide-only --client summit`; guard history read-only for untouched Notes · step · high
- [ ] **9.13** Take (assignee re-check, `NOTE_TAKEN`) and return to the original assignee (user, pool, `---` -> `---` once S.0 confirms it, else ALERT); from 9.4: `Client.return_target()` takes the original assignee read in the peek · step · high
- [ ] **9.14** Summit booking W1-W5: decided Creator (missing option -> `WRITE_NOT_STARTED`), full PO, body, previous-task recheck at W1, Documents name per S.0; `run --client summit` books (needs S.0 screens) · step · high
- [ ] **9.15** Mac Mini: `macmini-run.sh <mode> live summit`, second plist at :30 (07:30-17:30 Mon-Fri Perth; Joey, 24 Nov 2026), Healthchecks `healthchecks_ping_url_summit`, alert issues `po-agent alert summit <run_id>`, `docs/macmini-setup.md` and `docs/ops-runbook.md`; plus the 9.5 list in decisions, 25 Nov 2026, per-client run controls (wrapper reads the client's `enabled`, `stop_group` browser kill, runbook lock path and `rm -rf` step, Summit leftovers when only Summit is stopped) · step · medium · ask-first files

**Checkpoint S-C:** SPEC's offline Summit tests green; friction log's "Proposed" rows decided; B1 seam 2 booking cases green; the client file still `enabled = false`.

**S-D Live (Joey, Mac Mini; each step its own dated decisions entry first; Claude never runs anything on live)**
- [ ] **S.0** (from now, beside the build) By-hand live screenshots into `private/summit/` (Creator options, a Summit Documents row, Locked/Unlocked and My Notes after one by-hand Assign, assigned back before S.1, Note Pool count); `cases.toml` and expected compaction per PDF; the MySys admin's answer on Agent 2's password expiry and MFA; Claude writes the screens into `docs/screen-map.md` redacted · by hand
- [ ] **S.1** (after 9.15; `production` tag on a commit with 9.1-9.15) Agent 2's secrets in `poagent`'s Keychain; `preflight --site live --client summit` exit 0; Agent 2's My Notes empty; Joey tells the team: no by-hand assigns to Agent 2 · by hand
- [ ] **S.2** Kill-switch PR (client `enabled`), `production` tag moved, `spike live summit`: exit 0, `"client": "summit"`, no `MORE_PAGES` · by hand
- [ ] **S.3** `decide-only live summit`: NOTE lines read against the Notes; a peeked Note's log unchanged; its duration sets `max_peeks_per_run` · by hand
- [ ] **S.4** Admins told the agent may take and return their Summit Notes; `run live summit`, cap 1, watched; 5.2's trace check on the first · by hand
- [ ] **S.5** Healthchecks check `po-agent summit` (cron `30 7-17 * * 1-5`, Perth, 40 min grace); cap raised by its own PR; Summit launchd job loaded (:30); first hourly run watched · by hand
- [ ] **After phase 1** (Joey, 25 Nov 2026; decisions, Summit PDF patterns): open question 3's address fallback. A PDF whose PO differs between pages is decided by the site address (suburb + street name, street number ignored), exactly one project, else skip. It needs the PDF address read on both readers, a Projects search by address (a `mysys/` read, B1 seam 2) and the decide branch. The PO written is the page PO equal to the Note title's whose part before the first `/` equals the found project's Client Ref No. and Client Internal No.; none or both -> skip `PO_MISMATCH`. Phase 1 skips it `PO_MISMATCH` · step · high

## Production order (from 29 Oct 2026; plan -> Phase P, `SPEC.md` -> Production)

The MVP demo was shown on 28 Oct 2026 (Demo, below). Production builds the unticked tasks in this order; numbers and acceptance criteria are unchanged.

- [x] **P1** (done: PR #31) Docs catch-up and the Production sections · Claude writes, Joey merges
- [x] **P2** (done: PRs #33-#45) Decide: 2.1-2.6
- [x] **P3** Run controls and decide-only: 3.1, 3.2, 3.3, 3.5, 3.6, then 3.4
- [x] **P4** Real booker from `mysys/booking.py`: M0b.2, doubt-driven design review, then 4.1-4.5
- [x] **P5** (tasks built; the hourly week skipped, decisions 9 Nov 2026, go-live plan) Unattended on the test site: 1.9, 1.10, 4.6, 5.1, 5.2, 7.1, 7.2
- [x] **P6** (done: live hourly since 12 Nov 2026; G.8 ticked 19 Nov 2026) Go live (decisions, 9 Nov 2026, go-live plan): the G tasks below, in order. Code frozen until G.8: only fixes for what go-live finds

## Go live (added 9 Nov 2026; `SPEC.md` -> Production)

Each live step (G.5-G.8) gets its own dated `docs/decisions.md` entry first. Claude never runs anything against the live host.

- [x] **G.1** (done 10 Nov 2026) Joey's look at live with the agent's account, nothing saved (gate 2): PO Documents or Documents; Resolve or Solved; Client Ref No. `<internal no>/048`; password expiry; pool and agent names; `/048` title format; Pending Note count for the stale-Note read (more than 50 is a code change) · by hand
- [x] **G.2** (done 10 Nov 2026: 5 of 5 decided, false PROCEED 0) Real-PO seam on the 3-5 real POs (`uv run pytest tests/seam1 -m real_data`, laptop): `false PROCEED: 0` · Joey puts the POs in `private/`, Claude runs it
- [x] **G.3** Live profile: committed `config/live.toml` (starts disabled, one PO per run), its own keyring names, the wrapper and kill switch for live, the live answers from G.1 (bare-number match, stale read by the agent, Client Documents), alert issues without `note_id` (audit N4) · step · high risk, second-model review · decisions, 10 Nov 2026, live profile
- [x] **G.4** (done 10 Nov 2026) Joey's by-hand steps: Must never #3, the `guard_bash.py` live-host deny and `.claude/` changes for live; Claude and every AI tool removed from `poagent` (H2); live secrets into `poagent`'s Keychain; live config on the Mac Mini; the `production` tag moved to the go-live commit · by hand
- [x] **G.5** (done 10 Nov 2026: spike exit 0, 10 eligible) The one-line PR flipping `enabled = true` in `config/live.toml` (advisor verifies and merges after Joey's go-ahead), then Joey moves the `production` tag to that merge commit (the agent reads `enabled` from the tagged commit too), then the live read-only `spike` from the Mac Mini · by hand (Joey runs, pastes `runs.log` lines)
- [x] **G.6** (done 11 Nov 2026: runs 20261111T014436Z-dd9a and 20261111T014801Z-e75a, exit 0) Live `run --decide-only`; Joey reads its NOTE lines against the Notes · by hand. First try stopped with `set_user_filter` OPTION_NOT_FOUND (nothing written); the stale read now uses My Notes (decisions, 10 Nov 2026, My Notes): merge, move the tag, rerun
- [x] **G.7** (done 11 Nov 2026: five watched runs booked one PO each, exit 0; all five tasks still On Hold at Joey's 16:30 check; the 5.2 trace check passed on the first; their PDF went to PO Documents, not the task's Client Documents: fixed 12 Nov, PR 107, and proven by a live booking) Live `run`, one PO per run, watched; the 5.2 trace check on the first (Joey pastes the `grep <run_id>` trace lines, Claude checks) · by hand · decisions, 11 Nov 2026, G.7
- [x] **G.8** (done: hourly live runs since 12 Nov 2026; after the 18-19 Nov outage the scheduled runs at 12:07, 13:07 and 14:07 on 19 Nov ran on their own, exit 0; decisions, 19 Nov 2026, Mac Mini outage) Backup admin named (gate 4), `gh workflow enable heartbeat`, the `production` tag moved to the G.8 PR's merge commit (cap 10), then the plist copied again to `~/Library/LaunchAgents/` (it now runs `run live`; the old copy's bare `run` is refused) and the hourly job loaded on live; Joey watches the first hourly run · by hand · decisions, 12 Nov 2026, G.8
- [x] **H.1** (done 19 Nov 2026: `production` at e1b1c4f, the check went up at 15:08 Perth and pinged again at 16:08; `runs.log` has no `wrapper: healthchecks ping` line) Healthchecks.io heartbeat: Joey creates the check and stores its ping URL as `poagent` (`docs/macmini-setup.md` sections 1 and 7), then moves the `production` tag to a commit with the wrapper change; healthy when `runs.log` has no `wrapper: healthchecks ping` line and the check shows up · by hand · decisions, 19 Nov 2026, Healthchecks.io heartbeat

## Freeze — before any build

- [x] **F.1** Joey approves `tasks/plan.md` (workflow Stage 4.4); Open questions 2–8 answered as recommended (16 Oct 2026) · by hand
- [x] **F.2** (done: PR #6, 16 Oct 2026) Freeze commit on `plan-mvp`: `tasks/`, the dated D1–D7 entry in `docs/decisions.md`, and the SPEC / `docs/specs/spec.md` / `docs/workflow.md` / `docs/macmini-setup.md` changes in plan → Doc drift; PR; Joey merges · Claude writes, Joey merges
- [x] **F.3** (done: PR #7, 16 Oct 2026) Joey's CLAUDE.md edits by hand (plan → Doc drift: Must never #2, #3, #6 and Secrets); #3 must be merged before 1.2 · by hand
- [x] **F.4** (done, 16 Oct 2026) Local git: fast-forward `main` to `origin/main`; delete or reset the stale `m1-walking-skeleton` branch · by hand
- [x] **F.5** (done, 25 Oct 2026: the CEO approved D2 and delegated decision 2 to Joey, who decided yes) Tell the CEO that D2 puts the trial PDF briefly on the Mac Mini's disk · by hand

## M0b — screens still to map (Stage 3E)

- [x] **M0b.1** (done, 25 Oct 2026; rows 21–22 dropped, row 23 moved to M0b.2) Moving between windows, anchors for unlabelled controls and panels, Note Pool filter reload and search (`fill` + Refresh), reopening an open project (rows 25–28); one Assign returns a Note (15b); Claude writes them up · by hand · **blocks 1.8** and M3
- [x] **M0b.2** (done, 3 Nov 2026; Choose Project, row 20, partly seen live in the demo, 28 Oct 2026) Task detail, Link to Project search/select (and its target's name), PO Number prefill, empty Documents area (rows 19, 20, 24); does an open Note window refresh its Assignee (row 23, needed before 3.6); anchors for every remaining weak locator (open item 8 closed); upload saved before Submit?; reset; Claude writes them up · by hand · blocks M4

**Checkpoint M0b:** rows 19–28 captured; no M0b item left in SPEC or the screen map; both PRs merged; test site reset.

## M1 — walking skeleton + Mac Mini spike

- [x] **1.1** uv project and `scripts/check.py` (ruff, repo-data rule incl. `logs/`, `state/`, traces, any-case `.pdf`; pytest markers) · step
- [x] **1.2** Claude Code hooks + tests (live-host regex anchored so the test host passes); `.claude/settings.json` as the last edit · step · needs F.3 (#3)
- [x] **1.3** Pre-commit (gitleaks + repo-data rule; `.gitleaks.toml` for the hook test's fake key) and CI `check.yml` (+ Chromium) · step
- [x] **1.5** Config (`config/test.toml`, test host only), secrets (env → keyring), typed errors · step
- [x] **1.4** Action guard (`vet()` / `act()` with `value`; `act()` on the element `vet()` resolved; `exact=True`; allowlist, scope, exactly-one, denylist on element, select = chosen option) + widened `guard_check.py` (bans the `request` attribute, not verb names) · step
- [x] **1.6** Output contract, `run_id`, `po-agent` CLI (exit 2 on config/secrets; plain `run` refuses until 4.5; catch-all; nothing on stderr; download-dir sweep) · step
- [x] **1.7** Eligibility, step 0 (test + live title rules, Project `---`, Assignee = pool) · step
- [x] **1.8** Spike: guarded login, Note Pool filters read back (Search empty), list read once, RUN_SUMMARY (seam-2 `spike`); seam-2 failure reports scrubbed to the exception type; explicit `-m testsite` errors on missing secrets · step · needs M0b.1 merged
- [x] **1.9** `scripts/macmini-run.sh` (mode mapping, stop on failed pull, process-group kill, stderr dropped) + launchd plist, with stub-command tests · step
- [x] **1.10** (done: 6 Nov 2026; S1 spike run 20261106T045123Z-19d7; ADR-002 H2 waiver PR #72) Laptop secrets, guardrail prompts, Mac Mini setup, spike as `poagent` (S1), then **unload the job** · by hand

**Checkpoint M1:** check green, CI green on `main` (S2); guardrails behave; laptop spike eligible = 3; Mac Mini S1; job unloaded; review + security review; Joey OK.

## M2 — decision seam (S3)

- [x] **2.1** Seam-1 models (`more_pages`; frozen `Proceed` with `note_id`, internal no., pln, PDF name + bytes, existing task numbers) + 3 fake POs as text + all mutations (`cases.toml`); no PDF generator (Joey, 29 Oct 2026) · auto
- [x] **2.2** (done: PR #34) Deterministic reader + steps 2a–4 (`NOTE_ALREADY_LINKED`, `NO_PDF`, `MULTIPLE_PDFS`, `PDF_UNREADABLE`, `NOT_B1`, `NOT_COMPACTION`, `PO_MISMATCH`) · auto
- [x] **2.3** (done: PR #36) `match_project()` + strict duplicate check (Cancelled toggle); `Skip(UNEXPECTED_SCREEN)`; deterministic-only → `ADDRESS_UNVERIFIABLE` · auto
- [x] **2.4** (done: PR #39) Address verify-not-extract + agreement, stubbed Claude; `false PROCEED: 0` · auto · pauses: address rules
- [x] **2.5** (done: PR #43) (replaced 2 Nov 2026: no Claude reader) Second code reader (pypdf) + address check fed by MySys; `decide()` code only; `false PROCEED: 0` · step · pauses: failing tests
- [x] **2.5b** (done, 2 Nov 2026) Remove the Claude settings from config, CLI and secrets (`reader_mode`, model ID, prices, `anthropic_api_key`) · step
- [x] **2.6** (done: PR #45) Real-PO seam (`-m real_data`, both code readers); no prices · auto · pauses: laptop runs. The S3 evidence comes after 3.2 (Joey, 2 Nov 2026): trial lookups from 3.2's helper, the 3 recent real POs recorded by Joey

**Checkpoint M2:** check green; seam 1 `false PROCEED: 0`; review. After 3.2: real-PO `false PROCEED: 0`, clean-PO skips reviewed. **Gate for M3:** M0b.1 merged (already needed by 1.8); reset.

## M3 — decide-only + run controls

**Milestone A** (decisions, 25 Oct 2026): 1.4, 1.6, 1.7, M0b.1, 1.8, 1.9, 1.10; M2 (2.1–2.6); M3's 3.1, 3.2, 3.3, 3.5, then 3.4, then the decide-only demo to the CEO. 3.6 comes after the demo, before M4.

- [x] **3.1** (done: PR #46) Take a Note and hand it back (untick + read back, assign to agent, step 2a, assign to pool; anchored lists; runlog format incl. `assignee_check`) · step
- [x] **3.2** (done: PR #47) Attachment count, download (`downloads_path` at launch; file read into memory and deleted at once), project search via `match_project()`, project reads → `MySysLookup`; laptop-only helper writes each trial PO's lookup into `private/fixtures/cases.toml` (never committed) · step
- [x] **3.3** (done: PR #48) `run --decide-only` loop with NOTE lines; offline loop test + seam-2 `decide_only` · step
- [x] **3.5** (done: PR #49) Kill switch (start + `before_write` every step), Perth window, run cap · step
- [x] **3.6** (done: PRs #51-#52) Assignee check (All Pools + exact Note ID) before W1 and W4 only (D7); stale-Note stop at run start (D6) · step · after the Milestone A demo, before M4
- [x] **3.4** (done: 6 Nov 2026; laptop run 20261106T063859Z-1bd8, Mac Mini run 20261106T064611Z-dfd6, 3 of 3 DECIDE_ONLY) Decide-only on the laptop (headed), then on the Mac Mini (decision 2: yes, 25 Oct 2026); for the Milestone A demo, the job may be loaded in decide-only mode · by hand

**Checkpoint Milestone A:** check green; seam-2 decide-only green; Mac Mini decide-only green; demo to the CEO. **Checkpoint M3:** 3.6 merged; seam-2 assignee green; Mac Mini decide-only green; review. **Gate for M4:** M0b.2 merged; doubt-driven review of the booker design (fresh session); reset.

## M4 — first booking

- [x] **4.1** (done: PR #54) W1 (PO Documents on the test site; live is go-live gate 2, decisions 3 Nov 2026): `Proceed` matches this Note and pln; Create New Task fill (upload from bytes) + full pre-Submit read-back (`stop_after=W1`) · step
- [x] **4.2** (done: PR #60) W2: Submit, wait for one new task, task-detail read-back (`PartialWrite` / `AccuracyBreach`) · step
- [x] **4.3** (done: PR #61) W3: Hold with every dialog check read, no checkbox touched; `guard.vet()` refuses a Hold checkbox · step
- [x] **4.4** (done: PR #62) W4 Link to Project + W5 Solved; `before_write` → untick → read back → click, read back again before W4's final select · step
- [x] **4.5** `run` mode end to end; seam 2: 3 trial POs booked (S4), rerun changes nothing, 2609034B copy skips (S5); manual mid-run takeover (stop before W1, or `PARTIAL_WRITE` at W4) · step
- [x] **4.6** (done: 6 Nov 2026; tsk_164306, tsk_164307, tsk_164309, exit 0, no ALERT; job unloaded, test site reset) First bookings from the Mac Mini, one trial PO per run (load job, then unload; no laptop runs meanwhile); then reset · by hand

**Checkpoint M4:** check green; seam-2 booking cases green; Mac Mini bookings correct; review + security review; Joey OK.

## M5 — MVP safety

- [x] **5.1** ALERT lines and exit codes for every typed error, end to end; RUN_SUMMARY always last; nothing on stderr · step
- [x] **5.2** (closed: decisions, 9 Nov 2026; runs 1-6, 9, 12a passed; 10, 11, 12b checked in P5's first booking run) Seam-2 safety cases (`guard.vet()` refuses Discard, non-`/048` untouched, Send Email untick after the latest assignee check, from the log); full seam 2 green as the fixed sequence of runs with resets in `tests/seam2/README.md` · step

**Checkpoint M5:** check green; full seam 2 green; manual mid-run takeover (4.5) done; review + security review; docs drift checked.

## Production operations (added 4 Nov 2026; plan -> Phase P -> Production operations)

- [x] **7.1** Heartbeat: one ping per run, email after 2 hours without one inside the schedule · step · asks first: the service · before the P5 week
- [x] **7.2** Silent-skip alert: every eligible Note `UNEXPECTED_SCREEN` → one ALERT · step · asks first: the rule · before the P5 week
- [x] **7.3** Safe trace on the Mac Mini: allowlisted fields only, 90 days · step · before go-live
- [x] **7.4** Release pinning: the Mac Mini runs the `production` tag; `enabled` still read from `main` · step · before go-live
- [x] **7.5** `docs/ops-runbook.md`: what to do for each alert · docs · before go-live
- [ ] ~~**7.6** Alert triage loop~~ (dropped, decisions 9 Nov 2026, go-live plan: alerts are handled with `docs/ops-runbook.md`)
- [x] **7.7** (done: PR #59) Dev workflow: `.claude/agents/pr-reviewer.md`; `/verify-pr` requires the todo tick · by hand (Joey)

## Architecture (added 9 Nov 2026; `docs/architecture-review.md` -> Round 2)

**Code freeze (decisions, 9 Nov 2026, go-live plan):** 8.1, 8.3 and 8.4 waited until live ran hourly (G.8); G.8 is done (19 Nov 2026), so they can start, in the order 8.1, 8.3, 8.4. 8.2 was merged before the freeze (PR 88).

- [x] **8.1** (done 20 Nov 2026; decisions, 20 Nov 2026, one Send Email control) One Send Email Notification control for every Note-window write (Round 2, candidate D; its settled design is there) · step · after G.8
- [x] **8.2** (done: PR 88, before the freeze) One error-report path: the ALERT kind on each error class, one traceback writer (Round 2, candidate B) · step
- [x] **8.3** The two readers as one module, and `decide()` calls the project lookup itself (Round 2, candidate A, with round 1's proposal 6) · step · after 8.1
- [x] **8.4** (done 21 Nov 2026; decisions, 21 Nov 2026, one wait module) One MySys wait module; its retry refuses committing clicks (Round 2, candidate C) · step · after 8.3 (after G.8)

**Carry-over for 8.1 and 8.4 (Joey, 20 Nov 2026: "之後順便做"):** the first of them that changes `src/po_agent/mysys/guard.py` or `src/po_agent/mysys/booking.py` also adds `po_agent.mysys.guard` and `po_agent.mysys.booking` to the mypy strict list in `pyproject.toml` (`[[tool.mypy.overrides]]`). On 20 Nov 2026 `uv run mypy --strict` on the two files gave 6 errors; e.g. `_hold_window_open(page)` in guard.py has no annotations, so mypy skips its body. No behaviour change; a real bug found this way gets its own `test:` commit first.

## Demo - shown 28 Oct 2026 (decisions, 27-28 Oct 2026)

- [x] **D.1** (done: PR #21, 28 Oct 2026) `po-agent demo --site test --headed`: one trial PO, 2609017B -> pln_66935, Enter before every write; `--until-check` read-only · step
- [x] **D.2** (done: PRs #22-#28, 28 Oct 2026) Live fixes: label reads, project window, Link to Project via Choose Project, `--probe-link`, Enter runs both project searches, Projects filter check · step
- [x] **D.3** (done: PRs #29-#30, 28 Oct 2026) "Page blocked" fixed by the guarded pointer move (10 of 10 hands-off runs); the new task row read until whole · step
- [x] **D.4** (done, 28 Oct 2026) Demo shown: full bookings from the laptop and the Mac Mini. `src/po_agent/mysys/booking.py` holds the proven booking steps for M4 · by hand

## M6 — MVP demo

**Superseded by the Demo above:** 6.1-6.4 were written for the unattended run and weren't done as written. **Dropped (decisions, 9 Nov 2026, go-live plan).**

- [x] **6.1** (dropped, decisions 9 Nov 2026) `/agent-skills:ship` go/no-go; load the job again, then rehearse `enabled = false` and `launchctl bootout` (S6) · by hand
- [x] **6.2** (dropped, decisions 9 Nov 2026) Demo 1: scheduled run (S4), fresh 2609034B copy (S5), controls (S6), evidence (S7) · by hand
- [x] **6.3** (dropped, decisions 9 Nov 2026) Demos 2 and 3 with no change between (S8); one from the laptop headed, with the Mac Mini job unloaded for it · by hand
- [x] **6.4** (dropped, decisions 9 Nov 2026) One-page demo note for the CEO (cost per PO, S3 result, trial conditions, concerns) · by hand

**Checkpoint complete:** S1–S8 met; CEO note sent; next is `docs/workflow.md` Stage 8.
