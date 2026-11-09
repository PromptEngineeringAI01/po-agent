# PO Agent MVP — task list

Full acceptance criteria, verify steps and files: `tasks/plan.md`. One task per session; branch per task from up-to-date `main`. Pace: **step** = `/agent-skills:build task <N>`, plan mode first · **auto** = `/agent-skills:build auto` (M2 only, after M1 merged) · **by hand** = Joey does it (Claude observes or writes docs only).

Every code task: failing test first → stop for Joey → `test:` commit → code → `uv run scripts/check.py` shows `check: all passed`.

Decisions D1–D7 (16 Oct 2026) are in `tasks/plan.md` → Decisions from the doubt review; they go into `docs/decisions.md` and SPEC at the freeze.

**One agent at a time:** no laptop test-site run (seam-2 tests, `run`, `spike`) while the Mac Mini job is loaded, and no manual Mac Mini run while a laptop run is going (plan → Cross-cutting rules).

## Production order (from 29 Oct 2026; plan -> Phase P, `SPEC.md` -> Production)

The MVP demo was shown on 28 Oct 2026 (Demo, below). Production builds the unticked tasks in this order; numbers and acceptance criteria are unchanged.

- [x] **P1** (done: PR #31) Docs catch-up and the Production sections · Claude writes, Joey merges
- [x] **P2** (done: PRs #33-#45) Decide: 2.1-2.6
- [x] **P3** Run controls and decide-only: 3.1, 3.2, 3.3, 3.5, 3.6, then 3.4
- [x] **P4** Real booker from `mysys/booking.py`: M0b.2, doubt-driven design review, then 4.1-4.5
- [ ] **P5** Unattended on the test site: 1.9, 1.10, 4.6, 5.1, 5.2, 7.1, 7.2, then the hourly job; a week of hourly runs with zero wrong bookings, every alert triaged (7.6)
- [ ] **P6** Go live, after the go-live gates (MySys permission; PO admin's live answers; CEO sign-off and backlog cut-off date; accounts; P5's week; production operations 7.1-7.6): live spike, then decide-only, then one booking per run, watched · tasks written then

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
- [ ] **7.5** `docs/ops-runbook.md`: what to do for each alert · docs · before go-live
- [ ] **7.6** Alert triage loop: every alert issue closed as expected skip, new case, fix or decision · from the P5 week
- [x] **7.7** (done: PR #59) Dev workflow: `.claude/agents/pr-reviewer.md`; `/verify-pr` requires the todo tick · by hand (Joey)

## Architecture (added 9 Nov 2026; `docs/architecture-review.md` -> Round 2)

- [ ] **8.1** One Send Email Notification control for every Note-window write (Round 2, candidate D; its settled design is there) · step · after the P5 week, before P6 go-live
- [x] **8.2** One error-report path: the ALERT kind on each error class, one traceback writer (Round 2, candidate B) · step · now: no test-site run, and the Mac Mini runs the `production` tag
- [ ] **8.3** The two readers as one module, and `decide()` calls the project lookup itself (Round 2, candidate A, with round 1's proposal 6) · step · after 8.1
- [ ] **8.4** One MySys wait module; its retry refuses committing clicks (Round 2, candidate C) · step · after 8.3, before P6 go-live

## Demo - shown 28 Oct 2026 (decisions, 27-28 Oct 2026)

- [x] **D.1** (done: PR #21, 28 Oct 2026) `po-agent demo --site test --headed`: one trial PO, 2609017B -> pln_66935, Enter before every write; `--until-check` read-only · step
- [x] **D.2** (done: PRs #22-#28, 28 Oct 2026) Live fixes: label reads, project window, Link to Project via Choose Project, `--probe-link`, Enter runs both project searches, Projects filter check · step
- [x] **D.3** (done: PRs #29-#30, 28 Oct 2026) "Page blocked" fixed by the guarded pointer move (10 of 10 hands-off runs); the new task row read until whole · step
- [x] **D.4** (done, 28 Oct 2026) Demo shown: full bookings from the laptop and the Mac Mini. `src/po_agent/mysys/booking.py` holds the proven booking steps for M4 · by hand

## M6 — MVP demo

**Superseded by the Demo above:** 6.1-6.4 were written for the unattended run and weren't done as written. Their checks (S1-S8 on the scheduled job) move to P5.

- [ ] **6.1** `/agent-skills:ship` go/no-go; load the job again, then rehearse `enabled = false` and `launchctl bootout` (S6) · by hand
- [ ] **6.2** Demo 1: scheduled run (S4), fresh 2609034B copy (S5), controls (S6), evidence (S7) · by hand
- [ ] **6.3** Demos 2 and 3 with no change between (S8); one from the laptop headed, with the Mac Mini job unloaded for it · by hand
- [ ] **6.4** One-page demo note for the CEO (cost per PO, S3 result, trial conditions, concerns) · by hand

**Checkpoint complete:** S1–S8 met; CEO note sent; next is `docs/workflow.md` Stage 8.
