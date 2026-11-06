"""Seam 2, the safety cases on the MySys test site (task 5.2; marker testsite).

From the reset state (docs/workflow.md 6.1), in this order:

1. A trial Note window is opened from the Note Pool (not taken) and
   `guard.vet()` (never `act()`) is called on its Discard button: refused as
   DENYLISTED (D3). Found again afterwards, the Note has no new log line and
   its assignee and status are unchanged.
2. One `po-agent run --site test --detailed-log` books the 3 trial POs. In
   its detailed log, before every Note-window write (Assign, the Choose
   Project select, Solved) there is an `email_notification_unticked` event
   after the most recent `assignee_check` of that Note; for W4's select and
   W5's Solved that check is W4's (D7). Every Note in the log is a trial
   Note: a non-`/048` Note in the Agent Pool is never assigned or opened,
   and is still in the pool as it was.

Joey resets the test site afterwards (the 3 bookings). The detailed log is
written under pytest's tmp_path, never logs/ or the repo. Assertions use
counts, enum values, action and event names and the trial identifiers only,
never page text.
"""

import json

import pytest

from po_agent import cli
from po_agent.core import run
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard, Refusal, Refused

pytestmark = pytest.mark.testsite

TRIAL_INTERNAL_NOS = ("2609017B", "2609034B", "2610002B")
DISCARD_NOTE = "2609034B"  # the Note row 15b was mapped on
# The guard actions that write in a Note window (SPEC.md -> MySys screen
# rules); each needs Send Email read back unticked first (Must never #4).
NOTE_WINDOW_WRITES = ("assign_note", "link_select_project", "mark_solved")
CHANGES = (
    "select_note_user",
    "select_note_pool",
    "untick_send_email_notification",
    "link_to_project",
    *NOTE_WINDOW_WRITES,
)


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


def read_pool(config, login) -> driver.NotePoolList:
    """The Agent Pool's page 1, in a browser of its own, closed before a run
    opens one."""
    guard = ActionGuard()
    with driver.open_browser(headed=False, slow_mo=0) as page:
        driver.reload_home(guard, page, *login)
        panel = driver.open_note_pool(guard, page)
        driver.leave_menu(guard, page)
        driver.set_note_pool_filters(guard, panel, config.pool_name)
        listing = driver.read_note_pool(guard, panel)
    assert listing.pages == 1, "Agent Pool has more than one page"
    return listing


def unticked_before_each_write(events: list[dict]) -> list[tuple[str, str, str]]:
    """(note_id, action, step of the latest assignee_check) for each
    Note-window write; step is "none" when no unticked event follows that
    check before the write, or there is no check."""
    found = []
    for i, event in enumerate(events):
        if event["event"] != "guard_action":
            continue
        if event.get("action") not in NOTE_WINDOW_WRITES:
            continue
        note_id = event["note_id"]
        mine = [(j, e) for j, e in enumerate(events[:i]) if e["note_id"] == note_id]
        checks = [(j, e) for j, e in mine if e["event"] == "assignee_check"]
        step = "none"
        if checks and checks[-1][1]["ok"]:
            last = checks[-1][0]
            if any(
                e["event"] == "email_notification_unticked" and e["ok"] and j > last
                for j, e in mine
            ):
                step = checks[-1][1]["step"]
        found.append((note_id, event["action"], step))
    return found


def test_vet_refuses_discard_in_an_open_trial_note_window_and_nothing_changes(
    page, guard, config, login, check_note_pool_reset
):
    pool = config.pool_name
    driver.reload_home(guard, page, *login)
    panel = driver.open_note_pool(guard, page)
    driver.leave_menu(guard, page)
    driver.set_note_pool_filters(guard, panel, pool)
    listing = driver.read_note_pool(guard, panel)
    check_note_pool_reset(listing)
    (note,) = [
        n
        for n in run.eligible_notes(listing.rows, config.title_rule, pool)
        if n.internal_no == DISCARD_NOTE
    ]
    window = driver.open_note(guard, page, panel, note.note_id)
    lines_before = driver.log_line_count(window)
    status_before = driver.read_status(window)
    assert driver.read_assignee(window) == pool
    # A reopened Note reads "Pending by <user>" (Joey, 6 Nov 2026).
    assert status_before.startswith("Pending")

    # D3: vet() only, never act(); a status-button click is what Discard is.
    discard = window.get_by_role("button", name="Discard", exact=True)
    verdict = guard.vet("mark_solved", window, discard)

    assert verdict == Refused(Refusal.DENYLISTED)
    window = driver.find_note_again(guard, page, *login, note.note_id)
    assert driver.log_line_count(window) == lines_before
    assert driver.read_assignee(window) == pool
    assert driver.read_status(window) == status_before
    done = {action for action, _ in guard.history}
    assert not done & set(CHANGES)


def test_full_run_unticks_send_email_after_the_latest_check_before_note_window_writes(
    config, login, check_note_pool_reset, capsys, tmp_path, monkeypatch
):
    before = read_pool(config, login)
    check_note_pool_reset(before)  # one Note per trial PO
    trial = {
        n.note_id
        for n in run.eligible_notes(before.rows, config.title_rule, config.pool_name)
        if n.internal_no in TRIAL_INTERNAL_NOS
    }
    others = {
        (r.note_id, r.assignee, r.project)
        for r in before.rows
        if r.note_id not in trial
    }
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")

    code = cli.main(["run", "--site", "test", "--detailed-log"])

    lines = capsys.readouterr().out.splitlines()
    summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
    assert [x.split()[1] for x in lines if x.startswith("ALERT ")] == []
    assert (code, summary["booked"], summary["partial"]) == (0, 3, 0)
    path = tmp_path / "logs" / f"{summary['run_id']}.jsonl"
    events = [json.loads(x) for x in path.read_text("utf-8").splitlines()]

    writes = unticked_before_each_write(events)
    by_action = {
        action: sorted(note_id for note_id, a, _ in writes if a == action)
        for action in NOTE_WINDOW_WRITES
    }
    # One take, one link and one Solved per trial Note; no return (booked).
    assert by_action == {action: sorted(trial) for action in NOTE_WINDOW_WRITES}
    steps = {(action, step) for _, action, step in writes}
    assert steps == {
        ("assign_note", "2"),
        ("link_select_project", "W4"),
        ("mark_solved", "W4"),
    }
    for note_id in trial:
        checks = [
            e["step"]
            for e in events
            if e["event"] == "assignee_check" and e["note_id"] == note_id
        ]
        assert checks == ["2", "W1", "W4"]
    # Non-/048 (and any other) Notes: never opened or assigned.
    assert {e["note_id"] for e in events if e["note_id"] is not None} <= trial
    after = read_pool(config, login)
    assert others <= {(r.note_id, r.assignee, r.project) for r in after.rows}
