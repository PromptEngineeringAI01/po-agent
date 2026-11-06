"""Seam 2, taking a Note and handing it back on the MySys test site (task 3.1;
marker testsite).

One trial Note, from the reset state (docs/workflow.md 6.1): open it from the
Note Pool, take it, read step 2a, reload, find it again (All Pools, exact ID)
and return it to the pool with one Assign. It must end in the Agent Pool,
Pending, with exactly two new log lines, and the detailed log must show Send
Email Notification read back unticked before each Assign. If the test stops
with the Note still with the agent, the teardown returns it in a fresh
browser context. Assertions use counts, enum values, action and event names
and the trial identifiers only, never page text.
"""

import json
from collections.abc import Iterator

import pytest

from po_agent.core import run, runlog
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

pytestmark = pytest.mark.testsite

TRIAL_INTERNAL_NO = "2609034B"  # the Note row 15b was mapped on
RUN_ID = "20261102T000000Z-seam"


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


def test_note_window_takes_a_note_and_hands_it_back(
    page, guard, config, login, taken, tmp_path
):
    agent, pool = config.agent_user_name, config.pool_name
    log = runlog.RunLog(RUN_ID, guard, directory=tmp_path)

    driver.reload_home(guard, page, *login)
    panel = driver.open_note_pool(guard, page)
    driver.leave_menu(guard, page)
    driver.set_note_pool_filters(guard, panel, pool)
    listing = driver.read_note_pool(guard, panel)
    # Precondition: exactly one Pending, unlinked, eligible 2609034B Note in
    # the Agent Pool. Only the Note this test uses (Joey, 2 Nov 2026:
    # 2610002B's Note is Solved on the test site); the shared 1.8 check
    # stays for the other seam-2 tests.
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
    lines_before = driver.log_line_count(window)
    taken.append(note.note_id)
    driver.take_note(guard, window, agent, log, note.note_id)
    assert driver.is_unlinked(window, log, note.note_id) is True

    window = driver.find_note_again(guard, page, *login, note.note_id)
    driver.return_note(guard, window, agent, pool, log, note.note_id)
    log.flush(note_id=note.note_id, step="return")
    taken.remove(note.note_id)

    assert driver.read_assignee(window) == pool
    # A reopened Note reads "Pending by <user>" (Joey, 6 Nov 2026).
    assert driver.read_status(window).startswith("Pending")
    assert driver.log_line_count(window) - lines_before == 2

    # Every action done; a covered-page click may fail first and be retried
    # (opening and refreshing clicks only, driver._open_retried).
    retried = {"open_note", "refresh_note_pool"}
    assert all(
        outcome == "done" or (outcome == "failed" and action in retried)
        for action, outcome in guard.history
    )
    path = tmp_path / f"{RUN_ID}.jsonl"
    events = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    named = [e.get("action") or e["event"] for e in events]
    assigns = [i for i, name in enumerate(named) if name == "assign_note"]
    assert len(assigns) == 2
    for i in assigns:
        changes = [
            j
            for j, name in enumerate(named[:i])
            if name in ("select_note_user", "select_note_pool")
        ]
        unticked = [
            j
            for j, name in enumerate(named[:i])
            if name == "email_notification_unticked"
        ]
        assert unticked and unticked[-1] > changes[-1]
