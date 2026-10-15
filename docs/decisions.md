# PO Agent — decision log (updated 15 Oct 2026)

Source of truth for decisions behind `docs/intent.md`, `SPEC.md` (MVP) and `docs/specs/` (v1 spec pack v1.2, ADR-001, ADR-002). If any spec disagrees with this log, this log wins. Author: Joey Wu.

After `tasks/plan.md` is approved (the freeze point), add a dated entry here for every behaviour change, in the same commit as the `SPEC.md` and `tasks/plan.md` changes.

## Status

- **13 Oct 2026: the CEO approved decision 1** of the CEO decision brief: the two-reader design, its safeguards, and a trial on the test site with 3 fake POs. The build can start.
- **15 Oct 2026: the CEO made decision 3:** the agent runs on the **office Mac Mini** (already purchased), for the MVP trial and for production (entry below).
- **Pending (blocks go-live only):** decision 2 (Claude reading real client POs). Joey has decided it as "yes" for now, **CEO to confirm** (entry below).

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
15. Resolve (Solved and Resolve are equivalent; use Resolve).

- "Send Email Notification": leave unticked (it is ticked by default).

## Test-site differences (from note 235957 screenshot, 12 Oct 2026)

- Testing only: Joey plays B1 Homes and places fake PO requests directly in the **Agent Pool** (not PO Allocation Pool).
- Note title = email body text, e.g. "Please find attached Purchase Order / Quotation file 2609034B_048_1.pdf" (no "[B1 Homes] Order …/048").
- Source shows "Agent 1 (MySys Only)" because Joey creates the notes (no sender email). Agent's user name in the Assign dropdown is "Agent 1 (MySys Only)".
- Everything else follows the live SOP.

## Answered questions

- PO number: from PDF "Purchase Order No", must agree with file name (_048 → /048) and, on live, the title. Disagreement → skip.
- B1 Homes check: PDF issuer "B1 Homes Pty Ltd" on both sites; on live `[B1 Homes]` title also required.
- Locked filter: applied on both sites.
- Backlog at go-live: read as "process existing /048 notes like new ones" — to confirm, incl. any age cut-off.
- Fake PDF addresses match their test projects exactly.
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
- Pass = 3 good fake POs processed end to end, every step correct, no human help:
  - 2609017B → pln_66935
  - 2609034B → pln_66938
  - 2610002B → pln_66940
- Record Claude token cost per PO for the CEO.
- Go-live on real POs only after CEO reviews the trial results and signs off.

## Still open

- **CEO decision 2:** confirm Joey's "yes" (Claude may read real client data). Blocks go-live. (Decision 3 was made on 15 Oct 2026: the office Mac Mini.)
- Test-site checks before the first write: C1 (Hold dialog checkboxes pre-ticked?), C3 (return a Note to the pool without Unassign) and MFA/password expiry on the agent account — `SPEC.md` open questions 1–3.
- CEO/IT OK on the private GitHub repo (the Mac Mini pulls the code from it).
- Backlog reading confirmation (and age cut-off).
- Alert channel for Joey for v1 (email or Teams webhook).
