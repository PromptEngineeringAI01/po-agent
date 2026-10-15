# Roadmap — PO Agent

**Status:** Approved for build (CEO decision 1, recorded 13 Oct 2026) · v1.3, 15 Oct 2026 (1.3: CEO decision 3, the MVP, trial and production run on the office Mac Mini, replacing the cloud routine. 1.2: MVP first; v1 hardening becomes its own phase) · **Author:** Joey Wu, drafted with Claude
Phases run in order, and each has an exit check. 🔴 = blocker from `spec.md` → Areas of concern (C-numbers). No calendar dates yet: about **1–2 weeks to the MVP demo**, then about 1–2 weeks of hardening to the 3-PO trial (ADR-001 estimated 3–4 weeks in total). Re-size after MVP slice M1.

## Phase 0 — Set up and check the test site by hand (1–2 days) = MVP slice M0

- Repo on a private GitHub repo (the Mac Mini pulls `main` from it); CEO/IT OK to keep the code there.
- Addy Osmani's agent-skills installed in Claude Code; `SPEC.md` reviewed and approved.
- 🔴 **C1:** open the Hold dialog on a test task. Are any related-task checkboxes ever pre-ticked?
- 🔴 **C3:** can a Note be returned to the Agent Pool through **Assign** (pool as assignee), without Unassign?
- 🔴 **C8:** does the agent account have MFA or password expiry?
- Find every screen that shows "Send Email Notification", and how to untick it and read it back (open question 9).
- Map the SOP screens by accessible role and name: Note Pool filters, Assign, attachment download, Projects search (0/1/many results), Create New Task, Hold, Link to Project, Resolve; and how each result can be read back → `docs/screen-map.md`.
- Create an Anthropic API key for the trial with a spend limit.
- Collect the 3 fake PO PDFs and their project data as fixtures (committed). Record the full SOP walkthrough on the test site; view-only captures of live and 10–20 real PO PDFs with their project data into `private/` (laptop only, never committed). See `docs/workflow.md` Stage 3.

**Exit:** ✅ CEO approved decision 1 (13 Oct 2026); `SPEC.md` approved; C1, C3 and C8 answered (or escalated to the CEO); screen map written.

## Phase 1 — MVP on the office Mac Mini (≈1–2 weeks) = slices M1–M6 in `SPEC.md`

- **M1 Walking skeleton:** scaffold, config, secrets module, action guard + build check, check command, hooks, CI; `po-agent spike`; `scripts/macmini-run.sh` and the launchd plist; the Mac Mini set up (`docs/macmini-setup.md`), starting with a test-site login by hand from it, and one spike run there as `poagent`. Proves MySys accepts logins from the office address (ADR-002 action item 2).
- **M2 Decision seam:** `reader_mode` switch (hybrid | deterministic-only), deterministic reader, address normaliser and verifier ("verify, not extract"), Claude reader (no tools, schema-bound), agreement rules, log line, skip reasons; fixture set (3 trial PDFs + mutated copies, minus the live-title rows); stubbed-Claude tests in CI; live-Claude run with token cost.
- **M3 Decide-only on the Mac Mini:** `run --decide-only` with the stdout contract, on the Mac Mini; no state between runs.
- **M4 First booking:** booker W1–W5 with read-back; one PO booked from a manual run on the Mac Mini (`launchctl kickstart`).
- **M5 Safety (MVP form):** `enabled` kill switch, Perth window, run cap, assignee check; the first failure stops the run; partial write → alert, Note left assigned to the agent; accuracy breach → alert + exit 3 (Joey unloads the launchd job); guard-refusal tests; `ALERT` → GitHub issue (opened by the Mac Mini's run script).
- **M6 MVP demo:** test site reset; launchd job loaded; the 3 trial POs only, then a fresh copy of one trial Note as the skip case (`DUPLICATE_TASK`); reset and repeat at least 3 times (`docs/demo-runbook.md`); cost per PO; a one-page demo note for the CEO.

**Exit:** `SPEC.md` success criteria S1–S8 all met; **zero false PROCEED** in seam 1 (ADR action item 3).

## Phase 2 — Harden to v1 (≈1–2 weeks)

Build the items the MVP deferred, as approved in `spec.md`:

- 24 h retry for `PROJECT_NOT_FOUND`; skip list with retry deadlines.
- Partial-write record and **auto-resume** on the next run (approved safeguard), with the duplicate check accepting only the agent's own task.
- Circuit breaker (3 unexpected screens / partial writes), start-of-run sweep, single-run lock (launchd won't overlap scheduled runs, but a manual run can).
- Live profile (PO Allocation Pool, `[B1 Homes]` title rule, live URL) behind the environment guard and go-live flag; seam 1 re-run with live-style titles; C6 sender-domain check.
- Alert channel to Joey chosen and tested (C2): email or a Teams webhook.
- Full seam 2 table on the test site: partial write and resume, overlap, a person taking the Note, and the rest.

**Exit:** all seam 1 and seam 2 tests in `spec.md` pass on the test site.

## Phase 3 — Trial (CEO gate)

- Run on the hourly schedule on the test site for a few days with fresh fake POs, unattended. Host: the office Mac Mini (CEO decision 3).
- Clean test-site state; Joey places the 3 fake POs (`2609017B`, `2609034B`, `2610002B`) in the Agent Pool; scheduled runs process them with no human help.
- **CEO review pack:**
  - the 3 tasks
  - the logs for the trial runs
  - the seam 1 agreement report (zero false PROCEED)
  - token cost per PO (AUD)
  - where the trial ran (the office Mac Mini) and the trial conditions
  - the open concerns and how each was settled.

**Exit:** CEO sign-off recorded (name, date). Only then can the go-live flag be set.

## Phase 4 — Go-live preparation (blocks live)

- ✅ **CEO decision 3** (15 Oct 2026): production runs on the **office Mac Mini** that ran the trial (ADR-002 Option D, Accepted). Maintainer: Joey, with a named backup admin.
- Production on the Mac Mini: a MySys **live** login by hand from it first (view-only); live credentials into `poagent`'s Keychain; `state_dir` on its disk (skip list, logs, `STOP`); alert channel tested from it. **The trial's test credentials are deleted from the Keychain and the trial API key revoked.**
- 🔴 **CEO decision 2:** confirm Joey's "yes" that Claude may read real client POs (C7). If the CEO says no, build the deterministic address extractor (C4) first.
- Confirm the live agent account exists with the same rights; remove Discard/Unlink/Cancel/Unassign rights if possible (C9).
- C6 sender-domain check confirmed; C5, C10, C11 decided; C17 MySys terms checked.
- Backlog decision and any age cut-off (open question 1).
- *Not planned (C14):* a decide-only shadow week on live. The attended first live week covers this.
- **Deploy checklist** (`/ship` in Claude Code, plus `engineering:deploy-checklist` in Cowork):
  - seams 1 and 2 green on the release build
  - the model ID pinned and recorded
  - kill switch tested on the production host
  - rollback steps written (below)
  - PO admin briefed on what agent-made tasks and returned Notes look like.

**Exit:** every 🔴 above closed; deploy checklist signed by Joey.

## Phase 5 — Live, attended first week

- Set the go-live flag. Joey and the PO admin watch the first live run.
- First week: the admin checks every agent-made task against its PDF.
- Daily review of the run summary lines; check that any `PARTIAL_WRITE` was finished by the agent on its next run.

**Exit:** a week with zero accuracy breaches; the admin confirms the workload change.

## Phase 6 — Steady state and measurement

- Weekly summary for the CEO: POs seen, processed, skipped by reason, coverage %, any breach, Claude cost.
- Track against the four success criteria. If coverage is below 80%, look at the skip reasons (ADR revisit trigger).
- Changes go through seam 1 first; change the model only on purpose.
- Extract the shared package (driver, guard, run controller, state, log format) for the next automation.

## Rollback triggers (decided now, per the deploy checklist)

- **Any accuracy breach** (wrong project, wrong PO number, missing PDF) → the agent switches itself off (`STOP` file in v1; in the MVP, exit 3 + alert and Joey unloads the launchd job); review the logs; fix it with a new seam 1 fixture first; re-enable only with CEO agreement.
- **Any guard refusal or circuit-breaker stop on live** → kill switch off until a developer has checked the screen map.
- **More than 2 `PARTIAL_WRITE` in a week** → kill switch off; review.

**How to roll back:** set `enabled = false`, create the `STOP` file in the state directory (v1 hosts), or unload the Mac Mini's launchd job (`launchctl bootout`). Notes stay in the pool for the admin as before. Nothing has to be undone, apart from finishing any recorded partial write by hand if the agent is stopped.
