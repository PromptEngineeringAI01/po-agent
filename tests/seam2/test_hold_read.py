"""Seam 2, the hold re-check's read on the MySys test site (decisions, 11
Nov 2026, hold re-check; marker testsite).

Read only, from any state of the test site (no reset needed): for each trial
PO, the project's Compaction Test tasks are read as step 10 reads them, then
`driver.recheck_hold` re-reads each one through the Projects search, as a
run does at its start. A Cancelled task reads "cancelled"; any other reads
"on_hold" exactly when its Status starts "On-hold" (after run 10 of the
seam-2 sequence the 3 bookings are held); a task number the project hasn't
got reads "not_found". Only reading actions are done: nothing is held,
released or changed. Assertions use the trial identifiers, task numbers and
states only, never an address or page text.
"""

import pytest

from po_agent.b1 import reader_rules as rules
from po_agent.core.trace import Booking
from po_agent.mysys import driver

pytestmark = pytest.mark.testsite

# SPEC.md -> Trial conditions.
TRIAL_PLNS = {"2609017B": "pln_66935", "2609034B": "pln_66938", "2610002B": "pln_66940"}
READING = {
    "login_username",
    "login_password",
    "login_submit",
    "open_project_tab",
    "open_projects_subtab",
    "move_pointer_off_menu",
    "search_project",
    "submit_project_search",
    "open_project",
}
RETRIED = {"open_project"}  # an opening click a covered page may fail
NO_SUCH_TASK = "tsk_999999999"


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


def only_reading(guard) -> bool:
    return {action for action, _ in guard.history} <= READING and all(
        outcome == "done" or (outcome == "failed" and action in RETRIED)
        for action, outcome in guard.history
    )


@pytest.mark.parametrize("internal_no", list(TRIAL_PLNS))
def test_hold_read_agrees_with_each_trial_tasks_status(
    config, login, guard, internal_no
):
    pln = TRIAL_PLNS[internal_no]
    with driver.open_browser(headed=False, slow_mo=0) as page:
        lookup = driver.project_lookup(guard, page, *login, internal_no, config.site)
        states = {}
        for task_no in [task.task_no for task in lookup.tasks] + [NO_SUCH_TASK]:
            booked = Booking(
                note_id="1", pln=pln, task_id=task_no, internal_no=internal_no
            )
            states[task_no] = driver.recheck_hold(
                guard, page, *login, booked, config.site
            )

    assert states.pop(NO_SUCH_TASK) == "not_found"
    for task in lookup.tasks:
        if task.status == rules.CANCELLED:
            wanted = "cancelled"
        elif task.status.startswith("On-hold"):
            wanted = "on_hold"
        else:
            wanted = "not_on_hold"
        assert states[task.task_no] == wanted, task.task_no
    assert only_reading(guard)
