"""Tests for core/runlog.py: the detailed JSON-lines log (task 3.1).

Written only with --detailed-log: one JSON object per line in
logs/<run_id>.jsonl, keys {"ts", "run_id", "note_id", "step", "event", "ok"}
plus one name key for some events (the action, field, error type or skip
reason). Never a value: no page text, no typed value. 5.2 asserts on the
order of these events, so guard actions are written before the next event.
"""

import json

import pytest

from po_agent.core import runlog
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys.guard import ActionGuard

RUN_ID = "20261102T010203Z-abcd"
NOTE_ID = "300001"
BASE_KEYS = {"ts", "run_id", "note_id", "step", "event", "ok"}
PAGE_TEXT = "12 Sample Lane, Sampleville WA 6000"


def events_in(directory) -> list[dict]:
    path = directory / f"{RUN_ID}.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_without_a_directory_nothing_is_written(tmp_path):
    guard = ActionGuard()
    log = runlog.RunLog(RUN_ID, guard, directory=None)
    guard.history.append(("assign_note", "done"))
    log.event("read_back", note_id=NOTE_ID, step="2", ok=True, field="assignee")
    log.flush(note_id=NOTE_ID, step="2")
    assert list(tmp_path.iterdir()) == []


def test_an_event_is_one_json_line_with_the_contract_keys(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    log.event("read_back", note_id=NOTE_ID, step="2", ok=True, field="assignee")
    log.event("email_notification_unticked", note_id=NOTE_ID, step="2", ok=True)

    first, second = events_in(tmp_path)
    assert set(first) == BASE_KEYS | {"field"}
    assert first["run_id"] == RUN_ID
    assert (first["note_id"], first["step"], first["event"], first["ok"]) == (
        NOTE_ID,
        "2",
        "read_back",
        True,
    )
    assert first["field"] == "assignee"
    assert first["ts"].endswith("+00:00")  # UTC, ISO 8601
    assert set(second) == BASE_KEYS


def test_guard_actions_go_out_by_name_before_the_next_event(tmp_path):
    guard = ActionGuard()
    log = runlog.RunLog(RUN_ID, guard, directory=tmp_path)
    guard.history += [
        ("untick_send_email_notification", "done"),
        ("select_note_user", "done"),
    ]
    log.event("email_notification_unticked", note_id=NOTE_ID, step="2", ok=True)
    guard.history.append(("assign_note", "TARGET_NOT_FOUND"))
    log.flush(note_id=NOTE_ID, step="2")
    log.flush(note_id=NOTE_ID, step="2")  # nothing new: nothing written

    events = events_in(tmp_path)
    assert [(e["event"], e.get("action"), e["ok"]) for e in events] == [
        ("guard_action", "untick_send_email_notification", True),
        ("guard_action", "select_note_user", True),
        ("email_notification_unticked", None, True),
        ("guard_action", "assign_note", False),
    ]
    guard_events = [e for e in events if e["event"] == "guard_action"]
    assert all(set(e) == BASE_KEYS | {"action"} for e in guard_events)


def test_an_error_is_its_type_name_then_a_separate_traceback(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    try:
        raise RuntimeError(PAGE_TEXT)
    except RuntimeError as error:
        log.error(error, note_id=NOTE_ID, step="2")

    error_event, traceback_event = events_in(tmp_path)
    assert set(error_event) == BASE_KEYS | {"type"}
    assert (error_event["event"], error_event["type"], error_event["ok"]) == (
        "error",
        "RuntimeError",
        False,
    )
    assert PAGE_TEXT not in json.dumps(error_event)
    assert traceback_event["event"] == "traceback"
    assert "RuntimeError" in traceback_event["traceback"]


def test_a_skip_names_its_reason(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    log.event("skip", note_id=NOTE_ID, step="2a", ok=True, reason="NOTE_ALREADY_LINKED")
    (event,) = events_in(tmp_path)
    assert set(event) == BASE_KEYS | {"reason"}
    assert event["reason"] == "NOTE_ALREADY_LINKED"


def test_an_event_outside_the_contract_is_refused(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    with pytest.raises(ValueError):
        log.event("note_body", note_id=NOTE_ID, step="2", ok=True)
    assert not (tmp_path / f"{RUN_ID}.jsonl").exists()


def test_a_name_that_is_not_an_identifier_is_redacted(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    log.event("read_back", note_id=NOTE_ID, step="2", ok=False, field=PAGE_TEXT)
    (event,) = events_in(tmp_path)
    assert event["field"] == "<redacted>"


# --- the one traceback writer (task 8.2) ------------------------------------


class _PageTextIds(Exception):
    """Duck-typed note_id and step, as KillSwitch and NoteTaken carry."""

    note_id = PAGE_TEXT
    step = "W 2"


def test_write_traceback_appends_one_line_in_the_run_log_format(tmp_path):
    log = runlog.RunLog(RUN_ID, ActionGuard(), directory=tmp_path)
    log.event("error", note_id=NOTE_ID, step="W2", ok=False, type="UnexpectedScreen")
    try:
        raise UnexpectedScreen("task not found", note_id=NOTE_ID, step="W2")
    except UnexpectedScreen as error:
        runlog.write_traceback(tmp_path, RUN_ID, error)

    error_event, traceback_event = events_in(tmp_path)
    assert error_event["event"] == "error"
    assert set(traceback_event) == BASE_KEYS | {"traceback"}
    assert {k: traceback_event[k] for k in ("run_id", "note_id", "step")} == {
        "run_id": RUN_ID,
        "note_id": NOTE_ID,
        "step": "W2",
    }
    assert (traceback_event["event"], traceback_event["ok"]) == ("traceback", False)
    assert "UnexpectedScreen" in traceback_event["traceback"]


def test_write_traceback_needs_no_run_log_and_hides_what_it_must(tmp_path):
    # A config error is reported before any RunLog exists.
    try:
        try:
            raise RuntimeError(f"locator resolved to {PAGE_TEXT}")
        except RuntimeError:
            raise _PageTextIds() from None
    except _PageTextIds as error:
        runlog.write_traceback(tmp_path / "logs", RUN_ID, error)

    (event,) = events_in(tmp_path / "logs")
    assert (event["note_id"], event["step"]) == ("<redacted>", "<redacted>")
    assert "_PageTextIds" in event["traceback"]
    assert PAGE_TEXT not in json.dumps(event)


def test_write_traceback_swallows_a_file_error(tmp_path):
    blocked = tmp_path / "logs"
    blocked.write_text("a file where the folder should be", "utf-8")
    runlog.write_traceback(blocked, RUN_ID, RuntimeError("fixed"))
    assert blocked.read_text("utf-8") == "a file where the folder should be"
