# Seam 2 on the test site

Seam 2 drives the MySys test site (marker `testsite`). "Full seam 2 green" is
the one fixed sequence of runs below, each started from the state it needs,
with the output of every run shown (task 5.2).

Before the first run:

- The Mac Mini job is unloaded, and nothing else runs against the test site
  (one agent at a time).
- The test site is reset (`docs/workflow.md` 6.1, Joey, by hand, with his own
  account): no non-cancelled Compaction Test task on the 3 trial plns, exactly
  one Pending, unlinked Note per trial PO in the Agent Pool, nothing assigned
  to the agent account.

A reset follows every W-step or booking run. The read-only and take-and-return
runs leave the reset state as they found it, so they run back to back.

| # | Run | Needs first |
|---|---|---|
| 1 | `uv run pytest tests/seam2 -m testsite -k test_spike` | reset |
| 2 | `uv run pytest tests/seam2 -m testsite -k test_note_window` | - |
| 3 | `uv run pytest tests/seam2 -m testsite -k test_reads` | - |
| 4 | `uv run pytest tests/seam2 -m testsite -k test_decide_only` | - |
| 5 | `uv run pytest tests/seam2 -m testsite -k test_assignee_check` | - |
| 6 | `uv run pytest tests/seam2 -m testsite -k test_booker_w1` | - |
| 7 | `uv run pytest tests/seam2 -m testsite -k test_booker_w2` | reset |
| 8 | `uv run pytest tests/seam2 -m testsite -k test_booker_w3` | reset |
| 9 | `uv run pytest tests/seam2 -m testsite -k test_booker_w4_w5` | reset |
| 10 | `uv run pytest tests/seam2 -m testsite -k test_run_book` | reset |
| 11 | `uv run pytest tests/seam2 -m testsite -k "test_run_book and fresh_copy"` | Joey places a fresh copy of the 2609034B Note and a non-`/048` Note in the Agent Pool |
| 12 | `uv run pytest tests/seam2 -m testsite -k test_safety` | reset |

Reset again after run 12.

Notes:

- `-k` matches test and module names as substrings, so each name keeps its
  `test_` prefix: plain `-k reads` would also pick up tests whose names
  contain "reads" in other files.
- Run 10 books the 3 trial POs and reruns; its second test skips until the
  Notes for run 11 are in place. Run 11 checks the `DUPLICATE_TASK` skip and
  that a non-`/048` Note is untouched (S5).
- Run 12 (`test_safety.py`): `guard.vet()` refuses Discard in an open trial
  Note window (D3), then one booking run with `--detailed-log` must read Send
  Email back unticked after the latest assignee check before every Note-window
  write (W4's check for W4 and W5, D7), and touch no Note but the trial ones.
  Its detailed log goes to pytest's temporary folder, not `logs/`.
- To check what a run selects without logging in, add `--collect-only`.
  Running a seam-2 file by path without `-m "not testsite"` logs in to MySys.
- Failure reports are cut to the test name and the exception type
  (`conftest.py`): page text never reaches the terminal.
