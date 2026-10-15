# Demo runbook — PO Agent MVP on the test site

**Version:** 1 · 15 Oct 2026 · **Owner:** Joey Wu · **Spec:** `SPEC.md` → S8
Use this every time you show the agent to your boss or the CEO. The demo can be repeated as often as you like: each demo books the 3 trial POs, and a 10-minute reset makes the test site ready for the next one.

## Why a reset is needed

After a demo, each trial project has an On Hold Compaction Test task and each trial Note is resolved. The agent only picks up unresolved Notes in the Agent Pool, and it skips a PO whose project already has a live task for that PO number. So before the next demo:

- the old tasks are **cancelled** by you (your own account). On the test site the agent ignores Cancelled tasks in its duplicate check, so it can book the same PO again
- fresh copies of the 3 Notes go back in the Agent Pool.

The agent never cancels anything itself. Cancelled tasks pile up on the 3 test projects over time; that's fine on the test site.

## 1. Reset (about 10 minutes, with your own account)

Do this straight after each demo, so you're always ready for the next.

- [ ] **Cancel** the non-cancelled Compaction Test task for each PO:
  - pln_66935: 2609017B/048
  - pln_66938: 2609034B/048
  - pln_66940: 2610002B/048
- [ ] **Agent Pool:** exactly one unresolved, unassigned Note for each of 2609017B, 2609034B and 2610002B, each with its PDF. Create fresh copies for any that were resolved. The leftover 2609034B copy from the skip step (section 3) can stay as the next demo's 2609034B Note.
- [ ] Nothing left assigned to the agent account.
- [ ] `config/test.toml` on `main` has `enabled = true`; the routine is switched on (if you'll use it).

## 2. Show it (pick one)

| Way | How | Good for | Time |
|---|---|---|---|
| **Watch it work** (laptop) | In the VS Code terminal: `uv run po-agent run --site test --headed --slow-mo 500` | A first demo: your boss sees the browser do each step, slowed down | 3–5 min |
| **Unattended from the cloud** | claude.ai/code/routines → `PO Agent MVP (test site)` → **Run now**; open the run's transcript | Showing that nobody's laptop is needed | 3–5 min, plus a minute to start |
| **On the schedule** | Leave the routine on; show the result of the last hourly run (it runs at 7 minutes past each hour, 07:07–17:07 on weekdays) | The real day-to-day picture | — |

Don't press **Run now** while a scheduled run is in progress (two runs at once could both pick up a Note).

## 3. What to show

1. **Before:** the Agent Pool with the 3 trial Notes.
2. **The run:** the browser (laptop) or the transcript (cloud). Point out that it reads each PDF twice and checks the address before it creates anything.
3. **After, on each project** (pln_66935, pln_66938, pln_66940): one Compaction Test task with the PO number, the PDF attached, Creator "Perth Scheduling", the email body as the Note, **On Hold — "ON HOLD UNTIL CALL UP"**, no notification sent. Each Note linked and resolved; the Agent Pool empty of trial Notes.
4. **The skip:** put a fresh copy of the 2609034B Note in the Agent Pool and run once more. The agent skips it as a duplicate and hands it back to the pool, changing nothing else. This shows what happens to anything it isn't sure about.
5. **The cost:** the `RUN_SUMMARY` line's `cost_aud`, divided by 3.
6. **The safety switch:** the routine's on/off switch and `enabled = false`.

## 4. After the demo

- Do the reset (section 1).
- Keep the `RUN_SUMMARY` line of each demo for the CEO note (cost per PO, run time).
- If anything went wrong, don't rerun straight away: read the transcript or the terminal output first, and check `docs/workflow.md` Appendix B.
