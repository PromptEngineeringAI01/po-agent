"""Seam 2, the assignee check and the stale-Note read on the MySys test site
(task 3.6; marker testsite).

One trial Note, from the reset state (docs/workflow.md 6.1): with it in the
Agent Pool, the stale-Note read (All Users, All Pools, All, Pending) lists
no Note with the agent. The test takes the Note, then the stale-Note read
lists exactly that Note, and the assignee check before W1 and before W4 (a fresh
reload and Note Pool search) passes: the row whose ID equals the Note ID
reads the agent. The teardown returns the Note to the pool in a fresh
browser context. Assertions use counts, enum values and the trial
identifiers only, never page text.
"""

from collections.abc import Iterator

import pytest

from po_agent.core import controls, run, runlog
from po_agent.core.config import CONFIG_DIR
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

pytestmark = pytest.mark.testsite

TRIAL_INTERNAL_NO = "2610002B"
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
    returned through the normal path in a fresh browser context."""
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


def stale_ids(guard, page, login, agent) -> list[str]:
    driver.reload_home(guard, page, *login)
    panel = driver.open_note_pool(guard, page)
    driver.leave_menu(guard, page)
    listing = driver.read_agent_notes(guard, panel, agent)
    return [row.note_id for row in listing.rows if row.assignee == agent]


def test_the_assignee_check_reads_the_agent_for_a_taken_trial_note(
    page, guard, config, login, taken
):
    agent, pool = config.agent_user_name, config.pool_name
    log = runlog.RunLog(RUN_ID, guard, directory=None)

    # Precondition: no Note with the agent, and one eligible trial Note.
    assert stale_ids(guard, page, login, agent) == []
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

    assert stale_ids(guard, page, login, agent) == [note.note_id]
    check = controls.assignee_check(guard, page, login, agent)
    gate = controls.Controls("test", CONFIG_DIR, assignee_check=check)
    gate.before_write(note.note_id, "W1")  # raises unless it reads the agent
    gate.before_write(note.note_id, "W4")
