"""Seam 2, the booker's W4 and W5 on the MySys test site (task 4.4; marker
testsite): one full booking.

From the reset state (docs/workflow.md 6.1), one trial PO, 2609017B: the
test finds its Note, takes it, and gets its `Proceed` by running every check
(`run._decide`, as decide-only does). Then `book(..., stop_after="W5")`: W1
to W3 as before, then the W4 assignee check, back to the Note window (row
25), Link to Project -> Choose Project -> the pln cell, clicked once, and
Solved, pressed once, each read back (rows 13, 14, 20). Pending, Discard,
Change Project and Unlink are never targeted: the W4/W5 actions are only
the ones listed below.

Joey cancels the task and reopens the Note afterwards (reset). The
teardown returns the Note to the pool in a fresh context only while it is
Pending, unlinked and with the agent (a failure before W4); once linked or
Solved it is left for the reset (plan, Phase M4). Assertions use counts,
action names and trial identifiers only.
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
RUN_ID = "20261104T000000Z-seam"
UNLINKED = "---"  # the Note Pool's Project cell before W4 (row 13)
W3_W4_W5 = [
    "confirm_hold",
    "open_note",
    "untick_send_email_notification",
    "link_to_project",
    "link_search_project",
    "submit_link_search",
    "link_select_project",
    "mark_solved",
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
    """The Note IDs this test took. One still Pending, unlinked and with the
    agent at the end is returned through the normal path in a fresh browser
    context; a linked or Solved one is left for Joey's reset."""
    note_ids: list[str] = []
    yield note_ids
    agent = config.agent_user_name
    for note_id in note_ids:
        guard = ActionGuard()
        log = runlog.RunLog(RUN_ID, guard, directory=None)
        with driver.open_browser(headed=False, slow_mo=0) as page:
            panel, listing = driver.search_note(guard, page, *login, note_id)
            row = driver.exact_row(listing, note_id)
            if row is None or row.assignee != agent or row.project != UNLINKED:
                continue
            window = driver.open_note(guard, page, panel, note_id)
            if driver.read_assignee(window) == agent:
                driver.return_note(guard, window, agent, config.pool_name, log, note_id)


def test_booker_w4_w5_links_the_pln_marks_solved_and_reads_back(
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
            stop_after="W5",
        )
        done = [action for action, _ in guard.history]
        held = len(done) - done[::-1].index("confirm_hold") - 1
        # After the Hold confirm: only W4's and W5's own actions, plus the
        # opening clicks of the Note Pool searches (W4's check and way back,
        # W5's read-back).
        searching = {
            "open_project_tab",
            "open_note_pool",
            "move_pointer_off_menu",
            "set_pool_filter",
            "set_locked_filter",
            "search_note_pool",
            "refresh_note_pool",
            "login_username",
            "login_password",
            "login_submit",
        }
        # Row 13 saw the box ticked after linking: W5 may untick it again.
        retick = [*W3_W4_W5[:-1], "untick_send_email_notification", "mark_solved"]
        assert [a for a in done[held:] if a not in searching] in (W3_W4_W5, retick)
        assert done.count("link_select_project") == 1
        assert done.count("mark_solved") == 1
        assert task_no not in proceed.existing_task_nos
