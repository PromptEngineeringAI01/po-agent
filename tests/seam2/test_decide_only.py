"""Seam 2, the decide-only run on the MySys test site (task 3.3; marker
testsite).

From the reset state (docs/workflow.md 6.1: one Pending, unlinked Note per
trial PO in the Agent Pool), `po-agent run --site test --decide-only` runs
once through cli.main. It must print one NOTE line per trial Note, leave all
3 Notes in the Agent Pool and create no task: each trial project's Compaction
Test task numbers are the same before and after. The teardown returns any
Note still with the agent in a fresh browser context. Assertions use counts,
enum values and the trial identifiers only, never page text.
"""

import json

import pytest

from po_agent import cli
from po_agent.core import run, runlog
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

pytestmark = pytest.mark.testsite

RUN_ID = "20261102T000000Z-seam"
# SPEC.md -> Trial conditions (as conftest.py; `import conftest` is ambiguous).
TRIAL_INTERNAL_NOS = ("2609017B", "2609034B", "2610002B")


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


def trial_notes(page, guard, config, login, check) -> dict[str, str]:
    """The reset check, then each trial PO's Note ID."""
    driver.reload_home(guard, page, *login)
    panel = driver.open_note_pool(guard, page)
    driver.leave_menu(guard, page)
    driver.set_note_pool_filters(guard, panel, config.pool_name)
    listing = driver.read_note_pool(guard, panel)
    check(listing)
    found = run.eligible_notes(listing.rows, config.title_rule, config.pool_name)
    return {
        n.internal_no: n.note_id for n in found if n.internal_no in TRIAL_INTERNAL_NOS
    }


def task_nos(page, guard, login) -> dict[str, tuple[str, ...]]:
    lookups = {
        number: driver.project_lookup(guard, page, *login, number, "test")
        for number in TRIAL_INTERNAL_NOS
    }
    return {n: tuple(t.task_no for t in lookup.tasks) for n, lookup in lookups.items()}


@pytest.fixture
def before(page, guard, config, login, check_note_pool_reset):
    notes = trial_notes(page, guard, config, login, check_note_pool_reset)
    tasks = task_nos(page, guard, login)
    yield notes, tasks
    # Teardown: any trial Note left with the agent goes back to the pool.
    for note_id in notes.values():
        guard = ActionGuard()
        log = runlog.RunLog(RUN_ID, guard, directory=None)
        with driver.open_browser(headed=False, slow_mo=0) as fresh:
            window = driver.find_note_again(guard, fresh, *login, note_id)
            if driver.read_assignee(window) == config.agent_user_name:
                driver.return_note(
                    guard,
                    window,
                    config.agent_user_name,
                    config.pool_name,
                    log,
                    note_id,
                )


def test_decide_only_run_returns_every_trial_note_and_books_nothing(
    before, page, guard, config, login, capsys
):
    notes, tasks = before

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = capsys.readouterr().out.splitlines()
    summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
    note_lines = [
        json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")
    ]
    assert code == 0
    assert (summary["mode"], summary["booked"], summary["exit_code"]) == (
        "decide-only",
        0,
        0,
    )
    assert sorted(n["note_id"] for n in note_lines) == sorted(notes.values())
    assert all(n["outcome"] == "skipped" for n in note_lines)
    # All 3 back in the Agent Pool, and no task created.
    after = trial_notes(page, guard, config, login, lambda listing: None)
    assert after == notes
    assert task_nos(page, guard, login) == tasks
