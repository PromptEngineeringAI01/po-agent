"""Seam 2, the booker's W1 on the MySys test site (task 4.1; marker testsite).

From the reset state (docs/workflow.md 6.1), one trial PO, 2609017B: the
test finds its Note, takes it, and gets its `Proceed` by running every check
(`run._decide`, as decide-only does). Then `book(..., stop_after="W1")`: the
W1 check, the project reopened and checked, Create New Task filled and read
back, never submitted; the browser context then closes, abandoning the form.
A fresh context's project read shows the same Compaction Test tasks as step
10 (no new task). The PDF upload is saved only by Submit (M0b.2), so no new
document is left either; Joey checks the project's Documents tab by hand
(its button is allowlisted only in 4.2). The teardown returns the Note to
the pool in a fresh context while it is Pending, unlinked and with the agent.
Assertions use counts, action names and trial identifiers only.
"""

from collections.abc import Iterator

import pytest

from po_agent.b1 import booker
from po_agent.b1.models import Proceed
from po_agent.core import controls, run, runlog
from po_agent.core.config import CONFIG_DIR
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

pytestmark = pytest.mark.testsite

TRIAL_INTERNAL_NO = "2609017B"
TRIAL_PLN = "pln_66935"  # SPEC.md -> Trial conditions
RUN_ID = "20261103T000000Z-seam"


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
    returned through the normal path in a fresh browser context (after W1
    nothing is linked or submitted)."""
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


def test_booker_w1_fills_create_new_task_reads_it_back_and_leaves_nothing(
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
        booker.book(
            proceed,
            note_id=note.note_id,
            guard=guard,
            page=page,
            login=login,
            controls=gate,
            stop_after="W1",
        )
        done = [action for action, _ in guard.history]
        assert done[-1] == "set_task_note"
        assert "submit_task" not in done
    # The context is closed: the filled form is abandoned. A fresh read.
    with driver.open_browser(headed=False, slow_mo=0) as fresh:
        lookup = driver.project_lookup(
            ActionGuard(), fresh, *login, TRIAL_INTERNAL_NO, "test"
        )
    after = {task.task_no for task in lookup.tasks}
    assert after == set(proceed.existing_task_nos)
