# Mission — PO Agent

**Status:** Approved for build · 13 Oct 2026 (paths updated 14 Oct 2026) · **Author:** Joey Wu (PE AI Champion) · **Decision owner:** CEO
**Sources:** `docs/intent.md`, `docs/decisions.md`, `docs/specs/ADR-001-po-agent-architecture.md` (approved by the CEO through the CEO decision brief, decision 1, recorded 13 Oct 2026). If this file and the decision log disagree, the decision log wins.

## Mission

Take routine B1 Homes compaction pre-bookings off the PO admin's desk, safely. The PO Agent books every clean `/048` compaction PO into MySys exactly as the admin would, and hands anything it isn't sure about straight back to a person.

## The problem today

B1 Homes (Scott Park Group) emails purchase orders (POs) to support@. Each email becomes a MySys **Note** in the **PO Allocation Pool**. For each compaction PO (suffix `/048`), the admin:

1. opens the Note and reads the PDF
2. finds the project
3. creates a **Compaction Test** task and attaches the PO
4. puts the task **on Hold**
5. links the Note to the project and marks it Solved.

Each PO takes about 2 minutes, at 0–50 POs a week, and someone has to check the pool every working day.

## Who it serves

| Who | What changes for them |
|---|---|
| PO admin | Only handles the Notes the agent hands back to the pool. |
| CEO | Approved the design and trial (decision 1). Decided hosting: the office Mac Mini (decision 3, 15 Oct 2026). Still to confirm Joey's call that Claude may read real POs (decision 2). Reviews the trial evidence (3 tasks, cost per PO) and approves go-live. |
| B1 Homes (Scott Park Group) | Nothing. They keep emailing POs as now. |
| Engineer / maintainer | Builds and runs the agent. The production maintainer hasn't been named yet (open question). |

## Success criteria (all four)

1. **Accuracy (hard line).** No task on the wrong project, with the wrong PO number, or without the PO PDF. Any breach switches the agent off until the CEO approves a restart (approved safeguard; in the MVP, Joey unloads the Mac Mini's launchd job).
2. **Coverage.** At least 80% of `/048` POs handled end to end; the rest go back to the pool cleanly.
3. **Speed.** Every `/048` PO is processed or returned within 1 hour during run hours (weekdays 07:00–18:00 Perth time).
4. **Workload.** The admin only touches POs the agent skipped.

## How it works, in one paragraph

**Hybrid (ADR-001).** A deterministic browser script does every click, and only clicks on an allowlist. Each PO is read twice: by deterministic code and by Claude. Claude has no tools; it only reads and returns a fixed-format answer. For the address, Claude extracts lot, street and suburb, and code verifies each one against the PDF text and the MySys project. The script books the PO only when both readings agree with each other and with MySys. Otherwise it skips. A config switch runs the agent without Claude if Claude becomes unavailable or isn't allowed.

## Principles (in priority order)

1. **Accuracy beats coverage.** When in doubt, skip. A skipped PO costs the admin 2 minutes; a wrong booking costs much more.
2. **Never destroy, never undo.** The agent can't delete, and it never presses Discard, Unlink, Cancel, Unassign or remove-document, or touches the related-task checkboxes in the Hold dialog. This is enforced by how the code is built, not by care.
3. **The script clicks; Claude only reads.**
4. **Read-only on email.** Email is seen only as MySys Notes. No replies, forwards, deletes, Outlook access or email notifications.
5. **No secrets in docs or code.** Credentials come from a secret store at run time.
6. **Prove it on the test site first.** An MVP proves the agent end to end on the test site; live use starts only after the CEO signs off the 3-PO trial.
7. **Build for reuse.** This is the first of 5–7 planned MySys automations. The driver, action guard, run log and two-reader pattern should be reusable.

## Boundaries

- **In:** B1 Homes only; `/048` compaction POs only; existing projects only; create task → Hold → Link → Solved.
- **Out:** other suffixes (e.g. `/023`, `/025`) and other clients (left untouched); creating projects; sending emails; Outlook; pricing or certification changes; deleting, discarding or cancelling anything.
