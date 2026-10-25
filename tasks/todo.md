# PO Agent MVP — task list

Full acceptance criteria, verify steps and files: `tasks/plan.md`. One task per session; branch per task from up-to-date `main`. Pace: **step** = `/agent-skills:build task <N>`, plan mode first · **auto** = `/agent-skills:build auto` (M2 only, after M1 merged) · **by hand** = Joey does it (Claude observes or writes docs only).

Every code task: failing test first → stop for Joey → `test:` commit → code → `uv run scripts/check.py` shows `check: all passed`.

Decisions D1–D7 (16 Oct 2026) are in `tasks/plan.md` → Decisions from the doubt review; they go into `docs/decisions.md` and SPEC at the freeze.

**One agent at a time:** no laptop test-site run (seam-2 tests, `run`, `spike`) while the Mac Mini job is loaded, and no manual Mac Mini run while a laptop run is going (plan → Cross-cutting rules).

## Freeze — before any build

- [x] **F.1** Joey approves `tasks/plan.md` (workflow Stage 4.4); Open questions 2–8 answered as recommended (16 Oct 2026) · by hand
- [x] **F.2** (done: PR #6, 16 Oct 2026) Freeze commit on `plan-mvp`: `tasks/`, the dated D1–D7 entry in `docs/decisions.md`, and the SPEC / `docs/specs/spec.md` / `docs/workflow.md` / `docs/macmini-setup.md` changes in plan → Doc drift; PR; Joey merges · Claude writes, Joey merges
- [x] **F.3** (done: PR #7, 16 Oct 2026) Joey's CLAUDE.md edits by hand (plan → Doc drift: Must never #2, #3, #6 and Secrets); #3 must be merged before 1.2 · by hand
- [x] **F.4** (done, 16 Oct 2026) Local git: fast-forward `main` to `origin/main`; delete or reset the stale `m1-walking-skeleton` branch · by hand
- [ ] **F.5** Tell the CEO that D2 puts the trial PDF briefly on the Mac Mini's disk (decision 2 was asked as "in memory only") · by hand

## M0b — screens still to map (Stage 3E)

- [ ] **M0b.1** Note attachments (0 / 2), assignee read (rows 21–23), moving between windows, anchors for unlabelled controls and panels, Note Pool filter reload, reopening an open project (rows 25–28); does `fill` alone run the searches; one Assign or two to return a Note; Claude writes them up · by hand · **blocks 1.8** and M3
- [ ] **M0b.2** Task detail, Link to Project search/select (and its target's name), PO Number prefill, empty Documents area (rows 19, 20, 24); anchors for every remaining weak locator (open item 8 closed); upload saved before Submit?; reset; Claude writes them up · by hand · blocks M4

**Checkpoint M0b:** rows 19–28 captured; no M0b item left in SPEC or the screen map; both PRs merged; test site reset.

## M1 — walking skeleton + Mac Mini spike

- [x] **1.1** uv project and `scripts/check.py` (ruff, repo-data rule incl. `logs/`, `state/`, traces, any-case `.pdf`; pytest markers) · step
- [x] **1.2** Claude Code hooks + tests (live-host regex anchored so the test host passes); `.claude/settings.json` as the last edit · step · needs F.3 (#3)
- [x] **1.3** Pre-commit (gitleaks + repo-data rule; `.gitleaks.toml` for the hook test's fake key) and CI `check.yml` (+ Chromium) · step
- [x] **1.5** Config (`config/test.toml`, test host only), secrets (env → keyring), typed errors · step
- [x] **1.4** Action guard (`vet()` / `act()` with `value`; `act()` on the element `vet()` resolved; `exact=True`; allowlist, scope, exactly-one, denylist on element, select = chosen option) + widened `guard_check.py` (bans the `request` attribute, not verb names) · step
- [ ] **1.6** Output contract, `run_id`, `po-agent` CLI (exit 2 on config/secrets; plain `run` refuses until 4.5; catch-all; nothing on stderr; download-dir sweep) · step
- [ ] **1.7** Eligibility, step 0 (test + live title rules, Project `---`, Assignee = pool) · step
- [ ] **1.8** Spike: guarded login, Note Pool filters read back (Search empty), list read once, RUN_SUMMARY (seam-2 `spike`); seam-2 failure reports scrubbed to the exception type; explicit `-m testsite` errors on missing secrets · step · needs M0b.1 merged
- [ ] **1.9** `scripts/macmini-run.sh` (mode mapping, stop on failed pull, process-group kill, stderr dropped) + launchd plist, with stub-command tests · step
- [ ] **1.10** Laptop secrets, guardrail prompts, Mac Mini setup, spike as `poagent` (S1), then **unload the job** · by hand

**Checkpoint M1:** check green, CI green on `main` (S2); guardrails behave; laptop spike eligible = 3; Mac Mini S1; job unloaded; review + security review; Joey OK.

## M2 — decision seam (S3)

- [ ] **2.1** Seam-1 models (`more_pages`; frozen `Proceed` with `note_id`, internal no., pln, PDF name + bytes, existing task numbers) + fake fixture PO generator (3 fake POs + all mutations) · auto · pauses: generator dependency
- [ ] **2.2** Deterministic reader + steps 2a–4 (`NOTE_ALREADY_LINKED`, `NO_PDF`, `MULTIPLE_PDFS`, `PDF_UNREADABLE`, `NOT_B1`, `NOT_COMPACTION`, `PO_MISMATCH`) · auto
- [ ] **2.3** `match_project()` + strict duplicate check (Cancelled toggle); `Skip(UNEXPECTED_SCREEN)`; deterministic-only → `ADDRESS_UNVERIFIABLE` · auto
- [ ] **2.4** Address verify-not-extract + agreement, stubbed Claude; `false PROCEED: 0` · auto · pauses: address rules
- [ ] **2.5** Claude reader (no tools, structured output, temp 0, 60 s, one retry, cost) + model ID pin + live-Claude seam · auto · pauses: prompt review, model ID
- [ ] **2.6** Prices; real-PO seam (`-m real_data`); live-Claude ×3 · auto · pauses: prices

**Checkpoint M2:** check green; live-Claude ×3, deterministic-only and real-PO all `false PROCEED: 0`; clean-PO skips reviewed; review. **Gate for M3:** M0b.1 merged (already needed by 1.8); reset.

## M3 — decide-only + run controls

Listed in build order: 3.5 and 3.6 need only 3.3, so they come before 3.4, whose Mac Mini part waits for the CEO.

- [ ] **3.1** Take a Note and hand it back (untick + read back, assign to agent, step 2a, assign to pool; anchored lists; runlog format incl. `assignee_check`) · step
- [ ] **3.2** Attachment count, download (`downloads_path` at launch; file read into memory and deleted at once), project search via `match_project()`, project reads → `MySysLookup` · step
- [ ] **3.3** `run --decide-only` loop with NOTE lines; offline loop test + seam-2 `decide_only` · step
- [ ] **3.5** Kill switch (start + `before_write` every step), Perth window, run cap · step
- [ ] **3.6** Assignee check (All Pools + exact Note ID) before W1 and W4 only (D7); stale-Note stop at run start (D6) · step
- [ ] **3.4** Decide-only on the laptop (headed), then on the Mac Mini after **CEO decision 2** on D2's terms (F.5) · by hand

**Checkpoint M3:** check green; seam-2 decide-only and assignee green; Mac Mini decide-only green; review. **Gate for M4:** M0b.2 merged; doubt-driven review of the booker design (fresh session); reset.

## M4 — first booking

- [ ] **4.1** W1 (needs PO Documents confirmed with the PO admin, SPEC open question 11): `Proceed` matches this Note and pln; Create New Task fill (upload from bytes) + full pre-Submit read-back (`stop_after=W1`) · step
- [ ] **4.2** W2: Submit, wait for one new task, task-detail read-back (`PartialWrite` / `AccuracyBreach`) · step
- [ ] **4.3** W3: Hold with every dialog check read, no checkbox touched; `guard.vet()` refuses a Hold checkbox · step
- [ ] **4.4** W4 Link to Project + W5 Solved; `before_write` → untick → read back → click, read back again before W4's final select · step
- [ ] **4.5** `run` mode end to end; seam 2: 3 trial POs booked (S4), rerun changes nothing, 2609034B copy skips (S5); manual mid-run takeover (stop before W1, or `PARTIAL_WRITE` at W4) · step
- [ ] **4.6** First bookings from the Mac Mini, one trial PO per run (load job, then unload; no laptop runs meanwhile); then reset · by hand

**Checkpoint M4:** check green; seam-2 booking cases green; Mac Mini bookings correct; review + security review; Joey OK.

## M5 — MVP safety

- [ ] **5.1** ALERT lines and exit codes for every typed error, end to end; RUN_SUMMARY always last; nothing on stderr · step
- [ ] **5.2** Seam-2 safety cases (`guard.vet()` refuses Discard, non-`/048` untouched, Send Email untick after the latest assignee check, from the log); full seam 2 green as the fixed sequence of runs with resets in `tests/seam2/README.md` · step

**Checkpoint M5:** check green; full seam 2 green; manual mid-run takeover (4.5) done; review + security review; docs drift checked.

## M6 — MVP demo

- [ ] **6.1** `/agent-skills:ship` go/no-go; load the job again, then rehearse `enabled = false` and `launchctl bootout` (S6) · by hand
- [ ] **6.2** Demo 1: scheduled run (S4), fresh 2609034B copy (S5), controls (S6), evidence (S7) · by hand
- [ ] **6.3** Demos 2 and 3 with no change between (S8); one from the laptop headed, with the Mac Mini job unloaded for it · by hand
- [ ] **6.4** One-page demo note for the CEO (cost per PO, S3 result, trial conditions, concerns) · by hand

**Checkpoint complete:** S1–S8 met; CEO note sent; next is `docs/workflow.md` Stage 8.
