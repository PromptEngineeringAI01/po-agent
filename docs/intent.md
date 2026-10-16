# Intent: PO Agent — B1 Homes compaction test pre-bookings

Author: Joey Wu (PE AI Champion). **Status: design and trial approved by the CEO** (CEO decision brief, decision 1, recorded 13 Oct 2026), including the safeguards. Decision 3 (hosting) was made on 15 Oct 2026: the office Mac Mini. Decision 2 (Claude reading real client POs) is pending; it blocks go-live, not the build. Date: 15 Oct 2026. Decision owner: CEO.
Decision log: `docs/decisions.md`. Active spec: `SPEC.md` (MVP on the office Mac Mini).

## Problem

B1 Homes sends purchase orders (POs) to support@. Each email becomes a MySys Note in the PO Allocation Pool. For every compaction PO (`/048`), an admin opens the note, reads the PDF, finds the project, creates a Compaction Test task, attaches the PO, puts it on hold, then links the note and marks it Solved. It takes about 2 minutes per PO, at 0–50 POs a week, and someone has to check the pool every day.

## Proposed outcome

An agent with its own MySys account checks the pool every hour (weekdays 07:00–18:00 Perth time). For each valid B1 Homes compaction PO it:

- creates an on-hold Compaction Test task on the correct project
- links the note to the project and marks it Solved.

If it can't complete a PO safely, it sends the note back to the pool for a person. The admin then only handles the POs the agent skipped.

## Scope

- **In:** B1 Homes only; `/048` compaction POs only; existing projects; create task → hold → link → Solved.
- **Out:** other PO suffixes (e.g. `/023`, `/025`), which are other task types and are left untouched; other clients, creating projects, sending emails to anyone except internal alerts to Joey, Outlook, pricing or certification changes, and deleting, discarding or cancelling anything.

## Success criteria

1. **Accuracy (hard line):** no task created on the wrong project, with the wrong PO number, or without the PO PDF.
2. **Coverage:** at least 80% of `/048` POs handled end to end; the rest go back to the pool.
3. **Speed:** every `/048` PO is either processed or returned within 1 hour (during run hours).
4. **Workload:** the admin only touches POs the agent skipped.

## Affected users and systems

- **PO admin:** works the pool today; picks up the POs the agent skips.
- **CEO:** approved the design and trial (decision 1). Decided hosting: the office Mac Mini (decision 3, 15 Oct 2026). Still to confirm Joey's call that Claude may read real client POs (decision 2). Reviews the trial and approves go-live.
- **B1 Homes (Scott Park Group):** sends the POs; nothing changes for them.
- **MySys** (third-party, browser only): Note Pool, Projects, Create New Task, Hold, Link to Project, Solved.
  - Live site: `prompt.mysys.com.au`
  - Test site: `test-prompt.mysys.com.au`
- **Agent account:** "Agent 1 (MySys Only)". It can't delete anything, and it has every permission the workflow needs.

## Constraints

- **Access:** browser/UI only. There is no official MySys API.
- **Address check:** the PO PDF and the project must match on lot number, street and suburb. Formatting, letter case, St/Street and a missing postcode or state don't count as differences. Any difference → skip.
  - **How it's checked:** Claude extracts lot, street and suburb. The deterministic code then **verifies** each one: it must appear in the PDF text and match the MySys project after normalisation. The deterministic side does not extract the address independently.
- **Duplicates:** skip if the project already has a Compaction Test task with the same PO number. Exception: the agent's own half-finished booking, which it completes on the next run (approved safeguard).
- **What a skip does:** the agent assigns the note back to the pool. There is no separate exception report.
- **Safeguards (approved with decision 1; the MVP uses simpler forms, listed in `SPEC.md` → Deferred to v1):**
  - **Half-finished bookings:** if a step fails after the task is created, the agent alerts Joey and completes its own booking on the next run, after re-checking everything.
  - **Stop after any error:** a booking error (wrong project, wrong PO number or missing PDF found on read-back) switches the agent off until the CEO approves a restart.
  - **Without Claude:** if Claude is unavailable, POs go to the admin as they do today. The rules-only address reader is built only if needed.
  - **Alerts** go to Joey only (channel to be chosen), never to customers.
- **Retries:** "project not found" is retried for up to 24 h. Every other skip reason is final. The agent keeps its own list of skips.
- **Off-limits buttons:** Discard, Unlink, Cancel, Unassign, removing a document, and the related-task checkboxes in the Hold dialog.
- **Email:** read-only, through MySys Notes. No replies, forwards or deletes, and no access to Outlook. "Send Email Notification" stays unticked.
- **Credentials:** never stored in docs or code.
- **Schedule:** hourly, weekdays 07:00–18:00 Perth time.
- **Approach: hybrid (ADR-001, approved by the CEO through decision 1).** A script does every click. Deterministic code and Claude both read the email and PDF, and the script proceeds only if they agree with each other and with MySys. For the address, the deterministic side verifies Claude's extraction (see Address check). Claude never clicks. Rationale and scoring: `docs/specs/ADR-001-po-agent-architecture.md`.
- **Fallback:** a config setting (reader = deterministic-only) runs the agent without Claude (ADR Option A). Until the rules-only address reader is built, that mode returns every PO to the admin.
- **Data:** the agent may read real client data (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real PDFs and live-screen captures are used on Joey's laptop only (git-ignored `private/`), never in GitHub or on the Mac Mini during the MVP. Bookings stay on the test site until go-live.
- **Records:** one log line per note and one summary line per run, in a daily log file kept 90 days, plus a skip list. No database.

## Delivery order (14 Oct 2026)

1. **MVP** (`SPEC.md`): the smallest build that proves the 3 trial POs book end to end on the test site, run hourly on the **office Mac Mini** by a launchd job. Some safeguards are in a simpler form (e.g. a half-finished booking stops the agent and Joey finishes it by hand).
2. **v1 hardening** (`docs/specs/spec.md`, roadmap phase 2): every approved safeguard in full, the fallback mode and the live profile.
3. **Trial and CEO sign-off**, then **production** on the same office Mac Mini (decision 3).

## Trial plan (test site)

URL: `https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component`

**Where it runs:** the office Mac Mini runs the script hourly as a separate standard macOS user, with its secrets in that user's Keychain (ADR-002 Option D, Accepted; `SPEC.md` → Trial conditions; `docs/macmini-setup.md`). Live credentials go there only after the CEO's go-live sign-off.

For testing only, Joey plays B1 Homes and places the trial PO requests (real B1 POs, 16 Oct 2026) directly in the test site's Agent Pool. The workflow is the same as on live, except for these differences:

| | Live | Test site |
|---|---|---|
| Pool to filter | PO Allocation Pool | **Agent Pool** |
| Note title | `[B1 Homes] Order 2609034B/048` | Email body text, e.g. `Please find attached Purchase Order / Quotation file 2609034B_048_1.pdf` |
| Note source | Sender's email (scottparkgroup.com.au) | Agent 1 (MySys Only), because Joey creates the notes |
| "Send Email Notification" | Unticked by agent | Ticked by default; agent unticks |

Test POs and projects:

| Client internal no. | Project |
|---|---|
| 2609017B | pln_66935 |
| 2609034B | pln_66938 |
| 2610002B | pln_66940 |

**Before the trial — decision-seam tests:** run the full fixture set through both readers and measure their agreement on the 3 trial PDFs and the mutated copies. Any false PROCEED is a blocker.

**Evidence for the CEO:** record Claude's token cost per PO during the trial.

**Pass:** all 3 POs processed end to end with every step correct and no human help, and no false PROCEED in the decision-seam tests. The CEO reviews the 3 test tasks and the cost per PO, then approves going live on real POs.

## Answered questions

1. **PO number:** taken from the PDF ("Purchase Order No") and checked against the file name (`_048` → `/048`), and on live also against the title. Any disagreement → skip.
2. **B1 Homes check:** the PDF issuer must be "B1 Homes Pty Ltd" on both sites; on live the `[B1 Homes]` title is also required.
3. **Locked filter:** applied on both sites.
4. **Backlog:** read as "process existing `/048` notes like new ones". *Still to confirm, including whether there's an age cut-off.*
5. **Hosting:** the office Mac Mini (already purchased), for the trial and production (CEO decision 3, 15 Oct 2026). It replaces the cloud routine planned for the trial on 14 Oct. The existing company server is very old and won't be used. See `docs/specs/ADR-002-po-agent-hosting.md` and `docs/hosting-research.md`.
6. **Trial data:** each trial PDF's address matches its test project, so all 3 trial POs should pass the address check. The trial POs are real B1 POs (16 Oct 2026, `docs/decisions.md`).
7. **Architecture:** the CEO approved the design, trial and safeguards (decision 1, recorded 13 Oct 2026). ADR-001 is Accepted.

## Open questions

1. The CEO's confirmation that Claude may read real client POs (decision 2; Joey has said yes). Blocks go-live.
2. ~~Where the agent runs in production, and who maintains it~~ Decided 15 Oct 2026 (CEO decision 3): the office Mac Mini, maintained by Joey with a named backup.
3. Confirm the backlog reading (answered question 4) and any age cut-off.
4. Alert channel for Joey (email or Teams webhook) for v1.
