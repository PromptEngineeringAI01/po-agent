"""Seam 2, run mode on the MySys test site (task 4.5; marker testsite).

`po-agent run --site test` through cli.main, as the Mac Mini runs it.

1. From the reset state (docs/workflow.md 6.1: one Pending, unlinked Note
   per trial PO in the Agent Pool, and no non-Cancelled Compaction Test task
   on any trial pln), one run books all 3 trial POs (S4): a `booked` NOTE
   line per trial Note with its PO number, pln and new task number, which
   is then that project's one non-Cancelled Compaction Test task, and the
   Note has left the Agent Pool (linked and Solved). The booker read back
   every value as it wrote it. An immediate rerun changes nothing (SPEC.md
   -> Reruns): no NOTE line for a trial Note, the same tasks, the same pool.
2. After 1, Joey places a fresh copy of the 2609034B Note and a non-`/048`
   Note in the Agent Pool. One run skips the copy as DUPLICATE_TASK and
   returns it to the Agent Pool with no new task (S5); the non-`/048` Note
   is untouched. Without both Notes in place the test skips.

No teardown return: in run mode a Note left with the agent is a partial
write and is never returned (4.5); the stale-Note stop holds the next run
until Joey's reset clears it, with the booked tasks. Assertions use counts,
enum values and the trial identifiers only, never page text.
"""

import json

import pytest

from po_agent import cli
from po_agent.b1 import reader_rules as rules
from po_agent.core import run
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

pytestmark = pytest.mark.testsite

# SPEC.md -> Trial conditions.
TRIAL_PLNS = {"2609017B": "pln_66935", "2609034B": "pln_66938", "2610002B": "pln_66940"}
COPY = "2609034B"  # its fresh copy is the S5 skip case
UNLINKED = "---"
PLACE_NOTES = (
    "needs a fresh copy of the 2609034B Note and a non-/048 Note in the Agent "
    "Pool, placed by Joey after the 3 trial POs are booked"
)


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


def read_site(config, login) -> tuple[driver.NotePoolList, dict[str, tuple]]:
    """In a browser of its own, closed before a run opens one: the Agent
    Pool's page 1 and each trial project's non-Cancelled Compaction Test
    task numbers."""
    guard = ActionGuard()
    with driver.open_browser(headed=False, slow_mo=0) as page:
        driver.reload_home(guard, page, *login)
        panel = driver.open_note_pool(guard, page)
        driver.leave_menu(guard, page)
        driver.set_note_pool_filters(guard, panel, config.pool_name)
        listing = driver.read_note_pool(guard, panel)
        assert listing.pages == 1, "Agent Pool has more than one page"
        tasks = {
            number: tuple(
                t.task_no
                for t in driver.project_lookup(
                    guard, page, *login, number, "test"
                ).tasks
                if t.status.strip() != rules.CANCELLED
            )
            for number in TRIAL_PLNS
        }
    return listing, tasks


def pool_rows(listing: driver.NotePoolList) -> set[tuple[str, str, str]]:
    return {(r.note_id, r.assignee, r.project) for r in listing.rows}


def trial_notes(config, listing: driver.NotePoolList) -> dict[str, list[str]]:
    found = run.eligible_notes(listing.rows, config.title_rule, config.pool_name)
    return {
        number: [n.note_id for n in found if n.internal_no == number]
        for number in TRIAL_PLNS
    }


def run_once(capsys) -> tuple[int, list[dict], dict]:
    code = cli.main(["run", "--site", "test"])
    lines = capsys.readouterr().out.splitlines()
    notes = [
        json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")
    ]
    summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
    alerts = [x.split()[1] for x in lines if x.startswith("ALERT ")]
    assert alerts == [], "the run raised an ALERT"
    return code, notes, summary


def test_run_books_the_three_trial_pos_and_a_rerun_changes_nothing(
    config, login, check_note_pool_reset, capsys
):
    listing, tasks = read_site(config, login)
    check_note_pool_reset(listing)  # one Note per trial PO
    assert all(tasks[n] == () for n in TRIAL_PLNS), "a trial pln has a live task"
    notes_by_po = {n: ids[0] for n, ids in trial_notes(config, listing).items()}

    code, notes, summary = run_once(capsys)

    assert code == 0
    booked = {n["note_id"]: n for n in notes if n["outcome"] == "booked"}
    assert sorted(booked) == sorted(notes_by_po.values())
    after, after_tasks = read_site(config, login)
    for number, note_id in notes_by_po.items():
        line = booked[note_id]
        assert (line["po_number"], line["pln"]) == (f"{number}/048", TRIAL_PLNS[number])
        assert after_tasks[number] == (line["task_id"],)
    # Linked and Solved: no trial Note left in the Agent Pool.
    left = {r.note_id for r in after.rows}
    assert not left & set(notes_by_po.values())
    assert (summary["booked"], summary["partial"], summary["exit_code"]) == (3, 0, 0)

    # An immediate rerun changes nothing.
    code, notes, summary = run_once(capsys)

    assert code == 0
    assert not [n for n in notes if n["note_id"] in notes_by_po.values()]
    assert summary["booked"] == 0
    rerun, rerun_tasks = read_site(config, login)
    assert pool_rows(rerun) == pool_rows(after)
    assert rerun_tasks == after_tasks


def test_a_fresh_copy_of_a_booked_po_is_skipped_and_a_non_048_note_is_untouched(
    config, login, capsys
):
    listing, tasks = read_site(config, login)
    copies = trial_notes(config, listing)[COPY]
    eligible = {
        n.note_id
        for n in run.eligible_notes(listing.rows, config.title_rule, config.pool_name)
    }
    others = {
        r
        for r in pool_rows(listing)
        if r[0] not in eligible and r[1] == config.pool_name
    }
    booked_before = all(tasks[n] for n in TRIAL_PLNS)
    if not booked_before or len(copies) != 1 or not others:
        pytest.skip(PLACE_NOTES)
    copy = copies[0]

    code, notes, summary = run_once(capsys)

    assert code == 0
    by_id = {n["note_id"]: n for n in notes}
    assert (by_id[copy]["outcome"], by_id[copy]["reason"]) == (
        "skipped",
        "DUPLICATE_TASK",
    )
    assert not {r[0] for r in others} & set(by_id)  # no NOTE line: untouched
    assert summary["booked"] == 0
    after, after_tasks = read_site(config, login)
    # The copy back in the Agent Pool, unlinked; the non-/048 Notes as they
    # were; no new task on any trial pln.
    assert (copy, config.pool_name, UNLINKED) in pool_rows(after)
    assert others <= pool_rows(after)
    assert after_tasks == tasks
