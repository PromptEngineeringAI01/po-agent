# PO Agent — Specs

Hand-off pack for the engineer building the PO Agent (B1 Homes `/048` compaction pre-bookings in MySys). Version 1.2, 14 Oct 2026.

**Building now: the MVP in `SPEC.md` (repo root, approved 15 Oct 2026)**, run on the test site from the office Mac Mini (CEO decision 3, 15 Oct 2026). This folder is the full v1 design the MVP is cut from; where `SPEC.md` is silent, these files apply.

## Read in this order

| File | What it covers |
|---|---|
| `../../SPEC.md` | **Active MVP spec:** scope cut, success criteria S1–S8, commands, structure, trial waiver, expected slices M0–M6. |
| `mission.md` | Why the agent exists, who it serves, the four success criteria, principles, boundaries. |
| `spec.md` | Full v1 requirements and design: user stories, components, processing order, data shapes, action guard, write sequence, the two test seams, **areas of concern and policy conflicts**, open questions. |
| `tech-stack.md` | Recommended stack with reasons, component map, security baseline, hosting, cost. |
| `roadmap.md` | Phases 0–6 with exit checks (MVP is phase 1), the CEO gate, go-live blockers, rollback triggers. |
| `ADR-001-po-agent-architecture.md` | Why hybrid (two readers, script clicks) was chosen over the alternatives. **Accepted.** |
| `ADR-002-po-agent-hosting.md` | Where the agent runs. **Accepted** (CEO decision 3, 15 Oct 2026): the office Mac Mini, for the trial and production. |

**Source of truth for decisions:** `docs/decisions.md`. **Intent:** `docs/intent.md`. **Build runbook:** `docs/workflow.md`.

## Before you start

- **Blocks the first write:** C1 (Hold dialog checkboxes) and C3 (returning a Note to the pool without Unassign); also MFA/password expiry on the agent account (C8). All are checked by hand on the test site in MVP slice M0.
- **Blocks go-live:** CEO decision 2 (Claude reading real POs, C7; Joey has said yes, CEO to confirm) (Decision 3, hosting and secrets, was made on 15 Oct 2026: the office Mac Mini.)
- **Real client data** may be read, on Joey's laptop only (git-ignored `private/`); see `SPEC.md` → Real client data.
- No company security or coding policy was available when this pack was written. A company IT/security review is still needed before go-live (`spec.md` → Areas of concern).
- **The build is approved.** The CEO approved decision 1 (design, trial and safeguards), recorded 13 Oct 2026. ADR-001 is Accepted.

## Glossary

| Term | Meaning |
|---|---|
| **PO** | Purchase order from B1 Homes. Suffix `/048` = compaction test. |
| **Note** | A MySys record created from each email to support@. |
| **Pool** | Where unassigned Notes wait: **PO Allocation Pool** (live) or **Agent Pool** (test). |
| **Client internal number** | B1's job reference, e.g. `2609034B`. It forms the PO number `2609034B/048` and is used to find the project. |
| **pln** | A MySys project ID, e.g. `pln_66938`. |
| **Compaction Test task** | The task created on the project for each PO; always a pre-booking. |
| **Hold** | Puts the task on hold with "ON HOLD UNTIL CALL UP". |
| **Link / Solved** | Link the Note to the pln, then mark the Note **Solved** (its Status button; MySys has no Resolve button). |
| **Reading** | One reader's structured result for a PO. There are two readers: deterministic and Claude. |
| **Verify, not extract** | Claude extracts the address; code checks it against the PDF text and the project. |
| **PROCEED / SKIP** | The decision for a Note. A skip returns the Note to its pool with a reason. |
| **Final / retryable skip** | Only "project not found" is retried (24 h); every other skip is final. *(MVP: all final.)* |
| **Action guard** | The only code allowed to click. Allowlist + denylist; a refusal aborts the run. |
| **Partial write** | The task was created but a later step (Hold, Link, Solved) failed. It can't be undone by the agent. |
| **Decision seam / run seam** | The two test boundaries: decision (offline) and a full run on the test site. |
| **MVP** | The thin first build in `SPEC.md` that proves the agent works end to end on the test site. |
| **Mac Mini job** | The launchd job on the office Mac Mini that runs `scripts/macmini-run.sh` at 7 minutes past each hour, 07:07–17:07 on weekdays, as the standard user `poagent`. |
| **Run output** | The short `INFO`/`NOTE`/`ALERT`/`RUN_SUMMARY` lines a run prints (no PDF text or addresses). In the MVP the agent keeps no state between runs; the Mac Mini appends this output to `runs.log` as the record. |
