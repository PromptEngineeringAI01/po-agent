"""Seam 2, the booker's W2 on the MySys test site (task 4.2; marker testsite).

From the reset state (docs/workflow.md 6.1), one trial PO, 2609017B: the
test finds its Note, takes it, and gets its `Proceed` by running every check
(`run._decide`, as decide-only does). Then `book(..., stop_after="W2")`: W1,
then Submit (the first write), the one new Compaction Test task, its detail
screen read back (PO Number, Lodged By, Notes, Task Creator), back to the
project, its Documents section (the PDF) and the Tasks button.

Then the D3 check, which only this test can make (once a task is on hold its
row shows Un-Hold): the new task's Hold dialog is opened (it changes
nothing), `guard.vet()` (never `act()`) on a Related Tasks checkbox must
refuse, the checkbox still reads unticked, and the browser context closes
without confirming. Joey cancels the task afterwards (reset). The teardown
returns the Note to the pool in a fresh context while it is Pending,
unlinked and with the agent (nothing is linked after W2). Assertions use
counts, action names and trial identifiers only.
"""

from collections.abc import Iterator

import pytest

from po_agent.b1 import booker
from po_agent.b1.models import Proceed
from po_agent.core import controls, run, runlog
from po_agent.core.config import CONFIG_DIR
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard, Refusal, Refused

pytestmark = pytest.mark.testsite

TRIAL_INTERNAL_NO = "2609017B"
TRIAL_PLN = "pln_66935"  # SPEC.md -> Trial conditions
RUN_ID = "20261104T000000Z-seam"
W2 = [
    "submit_task",
    "open_new_task_detail",
    "back_to_project",
    "open_project_documents",
    "open_project_tasks",
]


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


@pytest.fixture
def taken(config, login) -> Iterator[list[str]]:
    """The Note IDs this test took; any still with the agent at the end are
    returned through the normal path in a fresh browser context (after W2
    the Note is still Pending and unlinked)."""
    note_ids: list[str] = []
    yield note_ids
    for note_id in note_ids:
        guard = ActionGuard()
        log = runlog.RunLog(RUN_ID, guard, directory=None)
        with driver.open_browser(headed=False, slow_mo=0) as page:
            window = driver.find_note_again(guard, page, *login, note_id)
            if driver.read_assignee(window) == config.agent_user_name:
                driver.return_note(
                    guard,
                    window,
                    config.agent_user_name,
                    config.pool_name,
                    log,
                    note_id,
                )


def test_booker_w2_submits_reads_the_new_task_back_and_the_hold_checkbox_is_refused(
    taken, config, login, tmp_path
):
    agent, pool = config.agent_user_name, config.pool_name
    guard = ActionGuard()
    log = runlog.RunLog(RUN_ID, guard, directory=None)
    with driver.open_browser(headed=False, slow_mo=0, downloads=tmp_path) as page:
        driver.reload_home(guard, page, *login)
        panel = driver.open_note_pool(guard, page)
        driver.leave_menu(guard, page)
        driver.set_note_pool_filters(guard, panel, pool)
        listing = driver.read_note_pool(guard, panel)
        found = [
            n
            for n in run.eligible_notes(listing.rows, config.title_rule, pool)
            if n.internal_no == TRIAL_INTERNAL_NO
        ]
        if listing.pages != 1 or len(found) != 1:
            pytest.fail(
                f"not in the reset state: {TRIAL_INTERNAL_NO} eligible={len(found)}"
            )
        (note,) = found
        window = driver.open_note(guard, page, panel, note.note_id)
        taken.append(note.note_id)
        driver.take_note(guard, window, agent, log, note.note_id)
        with driver.note_downloads(page, tmp_path):
            proceed = run._decide(guard, page, config, login, log, note, window)
        assert isinstance(proceed, Proceed)
        assert proceed.pln == TRIAL_PLN

        check = controls.assignee_check(guard, page, login, agent)
        gate = controls.Controls("test", CONFIG_DIR, assignee_check=check)
        task_no = booker.book(
            proceed,
            note_id=note.note_id,
            guard=guard,
            page=page,
            login=login,
            controls=gate,
            agent=agent,
            stop_after="W2",
        )
        done = [action for action, _ in guard.history]
        assert done[-len(W2) :] == W2
        assert done.count("submit_task") == 1
        assert task_no not in proceed.existing_task_nos

        # D3: the Hold dialog's checkboxes are refused; vet() only, no act().
        project = booking.project_window(page, proceed.pln)
        dialog = booking.open_hold(guard, page, project, task_no)
        related = dialog.get_by_role("table").get_by_role("checkbox").first
        verdict = guard.vet("untick_send_email_notification", dialog, related)
        assert verdict == Refused(Refusal.HOLD_CHECKBOX)
        assert not related.is_checked()
        assert "confirm_hold" not in [action for action, _ in guard.history]
    # The context is closed with the dialog unconfirmed: nothing is held.
