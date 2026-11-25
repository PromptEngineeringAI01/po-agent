"""The Note loop in core/run.py, offline: decide-only (task 3.3) and run
mode, which books (task 4.5).

Not `testsite`: the driver is a fake of MySys (tests/fakes/mysys.py, with
the `env` and `mysys` fixtures in tests/conftest.py), so nothing opens a
browser; the decision engine and both PDF readers run for real on a fake
PDF built by seam 1's `text_pdf` (no committed PDF). The fake keeps each
Note's assignee, so a test can check where every Note ends.

`po-agent run --site test --decide-only` reads the Note Pool once, takes the
eligible Notes newest first by Note ID, up to `max_notes_per_run`, and for
each: find it (reload, exact ID) -> its assignee is the pool -> take -> 2a ->
attachments -> download -> decide -> back to the pool -> one NOTE line.
Nothing is booked. An error while the agent holds a Note -> one return in a
fresh browser context, then the run stops (exit 1). Values are fake.

`po-agent run --site test` (4.5) runs the same loop, but a PROCEED goes to
the real booker (`book()`, W1-W5) instead of back to the pool. Its MySys
steps (`mysys/driver.py`, `mysys/booking.py`) are faked here too; the real
`Controls.before_write` re-reads the kill switch from the test's config file
and runs the real assignee check over the fake Note Pool search. From the
Submit click on, a Note is never returned to the pool.
"""

import json
from collections import Counter

import pytest
from fakes.mysys import (
    AGENT,
    CLEAN,
    PERSON,
    POOL,
    FakeMySys,
    FakeNote,
    row,
)

from po_agent import cli
from po_agent.core import controls, run
from po_agent.core.errors import (
    AccuracyBreach,
    ConfigError,
    GuardRefusal,
    PartialWrite,
    UnexpectedScreen,
    WriteNotStarted,
)
from po_agent.core.models import (
    CompactionTask,
    NotePoolFilters,
    SearchRow,
    Skip,
    SkipReason,
)


def decide_only(*extra: str) -> int:
    return cli.main(["run", "--site", "test", "--decide-only", *extra])


def output(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


def alerts_of(lines: list[str]) -> list[tuple[str, dict]]:
    found = []
    for line in lines:
        if line.startswith("ALERT "):
            kind, _, body = line.removeprefix("ALERT ").partition(" ")
            found.append((kind, json.loads(body)))
    return found


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def opened(fake: FakeMySys) -> list[str]:
    """The Note IDs found and opened, in order, each once (a Note is found
    again before it goes back)."""
    found = [c.split()[1] for c in fake.calls if c.startswith("find_again ")]
    return list(dict.fromkeys(found))


# --- the loop ----------------------------------------------------------------


def test_eligible_notes_go_newest_first_up_to_the_cap_from_one_list_read(mysys, capsys):
    # Newest first (decisions, 10 Nov 2026, newest first): an old Note that
    # always skips can't take every run's cap. 99998 is the oldest (a
    # number, not text), so it is past the cap of 3.
    fake = mysys(
        {
            "300010": FakeNote("2600010B", names=()),
            "300002": FakeNote("2600002B", names=()),
            "300001": FakeNote("2600001B", names=()),
            "99998": FakeNote("2600998B", names=()),
        },
        rows=(
            row("99998", "2600998B"),
            row("300001", "2600001B"),
            row("300007", "2600007B", assignee=PERSON),  # not eligible
            row("300002", "2600002B"),
            row("300010", "2600010B"),
        ),
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert fake.reads == 1
    assert opened(fake) == ["300010", "300002", "300001"]
    # Past the cap and not eligible: never opened, never taken.
    assert not [c for c in fake.calls if "99998" in c or "300007" in c]
    assert fake.notes["99998"].taken == 0
    # Each processed Note taken once and back in the pool.
    assert Counter(n for n, v in fake.notes.items() if v.taken) == Counter(
        ["300010", "300002", "300001"]
    )
    assert all(v.taken <= 1 for v in fake.notes.values())
    assert all(v.assignee == POOL for v in fake.notes.values())
    assert [n["note_id"] for n in notes_of(lines)] == ["300010", "300002", "300001"]
    summary = summary_of(lines)
    assert summary["mode"] == "decide-only"
    assert (summary["seen"], summary["eligible"]) == (5, 4)
    assert (summary["skipped"], summary["booked"], summary["exit_code"]) == (3, 0, 0)


def test_the_run_filters_the_profile_s_pool_locked(mysys, capsys):
    # Task 9.2: the filters come from the client (B1: the profile's pool,
    # Locked); the driver holds none.
    fake = mysys({"300001": FakeNote("2600001B")})

    assert decide_only() == 0

    assert fake.filters == [NotePoolFilters(pool=POOL, locked="Locked")]


def test_the_body_read_is_the_one_ending_with_the_pdf_s_file_name(mysys, capsys):
    # Task 9.2: B1's body rule (SPEC.md -> Email body) is the run's choice.
    fake = mysys({"300001": FakeNote("2600001B", names=("2600001B_048_2.pdf",))})

    assert decide_only() == 0

    ((note_id, rule),) = fake.body_rules
    assert note_id == "300001"
    assert rule.search("Please find attached file 2600001B_048_2.pdf \n")
    assert not rule.search("Please find attached file 2600001B_048_1.pdf")
    assert not rule.search("2600001B_048_2.pdf is attached")


def test_one_note_line_per_note_and_nothing_booked(mysys, capsys):
    fake = mysys(
        {
            "300003": FakeNote("2600001B"),
            "300002": FakeNote("2600002B", names=()),
            "300001": FakeNote("2600003B", linked=True),
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    zero = {"field": None, "task_id": None, "tokens_in": 0, "tokens_out": 0}
    assert notes_of(lines) == [
        {
            "note_id": "300003",
            "outcome": "skipped",
            "reason": "DECIDE_ONLY",
            "po_number": "2600001B/048",
            "pln": "pln_10001",
            "cost_aud": 0.0,
            **zero,
        },
        {
            "note_id": "300002",
            "outcome": "skipped",
            "reason": "NO_PDF",
            "po_number": "2600002B/048",
            "pln": None,
            "cost_aud": 0.0,
            **zero,
        },
        {
            "note_id": "300001",
            "outcome": "skipped",
            "reason": "NOTE_ALREADY_LINKED",
            "po_number": "2600003B/048",
            "pln": None,
            "cost_aud": 0.0,
            **zero,
        },
    ]
    # Every Note is found again, its Assignee read, before it goes back (a
    # person may have taken it meanwhile). A Note skipped before the project
    # read has no download or project read it doesn't need.
    per_note = {
        n: [c.split()[0] for c in fake.calls if c.endswith(f" {n}")] for n in fake.notes
    }
    assert per_note == {
        "300003": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "names",
            "download",
            "body",
            "lookup",
            "find_again",
            "assignee",
            "return",
        ],
        "300002": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "names",
            "download",
            "find_again",
            "assignee",
            "return",
        ],
        "300001": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "find_again",
            "assignee",
            "return",
        ],
    }
    assert all(v.assignee == POOL for v in fake.notes.values())
    summary = summary_of(lines)
    assert (summary["skipped"], summary["booked"], summary["partial"]) == (3, 0, 0)
    assert (summary["tokens_in"], summary["tokens_out"], summary["cost_aud"]) == (
        0,
        0,
        0.0,
    )
    # The run's own download folder (D2), gone when the run ends.
    (folder,) = {d for d in fake.downloads}
    assert folder.name == f"po-agent-dl-{summary['run_id']}"
    assert not folder.exists()


def test_a_note_a_person_holds_is_never_taken(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B", assignee=PERSON)})

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert fake.notes["300001"].taken == 0
    assert fake.notes["300001"].assignee == PERSON
    assert not [c for c in fake.calls if c.startswith(("take", "return"))]
    (note,) = notes_of(lines)
    assert (note["outcome"], note["reason"]) == ("untouched", "NOTE_TAKEN")
    assert summary_of(lines)["skipped"] == 0


@pytest.mark.parametrize("during", ["lookup", "2a"])
def test_a_note_a_person_takes_mid_run_is_not_returned(mysys, capsys, during):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", person_takes_at=during),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert "return 300002" not in fake.calls
    assert fake.notes["300002"].assignee == PERSON
    assert fake.notes["300001"].assignee == POOL  # the run goes on
    first, _ = notes_of(lines)
    assert (first["note_id"], first["outcome"], first["reason"]) == (
        "300002",
        "untouched",
        "NOTE_TAKEN",
    )


# --- stop on the first failure ---------------------------------------------------

WRONG_PROJECT = CLEAN.lookup.model_copy(update={"project_internal_no": "2600009B"})


@pytest.mark.parametrize(
    "failing",
    [
        FakeNote("2600001B", fail_at="lookup"),  # UnexpectedScreen
        FakeNote("2600001B", lookup=WRONG_PROJECT),  # Skip(UNEXPECTED_SCREEN)
    ],
    ids=["unexpected-screen", "skip-unexpected-screen"],
)
def test_an_unexpected_screen_returns_the_note_in_a_fresh_context_then_stops(
    mysys, capsys, failing
):
    fake = mysys({"300002": failing, "300001": FakeNote("2600002B", names=())})

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert "300001" not in opened(fake)  # the run stopped
    # The old browser closed, then one return through the normal path.
    after = fake.calls[fake.calls.index("closed") :]
    assert after == [
        "closed",
        "open_browser",
        "find_again 300002",
        "assignee 300002",
        "return 300002",
        "closed",
    ]
    assert fake.notes["300002"].assignee == POOL
    assert notes_of(lines) == []
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300002")
    summary = summary_of(lines)
    assert (summary["exit_code"], summary["booked"]) == (1, 0)


def test_a_failed_return_leaves_the_note_with_the_agent_and_the_alert_says_so(
    mysys, capsys
):
    fake = mysys({"300001": FakeNote("2600001B", fail_at="lookup")}, fail_return=True)

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert [c for c in fake.calls if c.startswith("return")] == ["return 300001"]
    assert fake.notes["300001"].assignee == AGENT
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    assert "not returned to the pool" in alert["detail"]
    assert summary_of(lines)["exit_code"] == 1


def test_an_error_before_the_note_is_taken_stops_without_a_return(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B", fail_at="find_again")})

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.calls.count("open_browser") == 1
    assert fake.notes["300001"].taken == 0
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")


def test_any_other_error_after_the_take_returns_the_note_and_names_it(mysys, capsys):
    fake = mysys(
        {"300001": FakeNote("2600001B", fail_at="download", fail_with=RuntimeError)}
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.notes["300001"].assignee == POOL
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")


def test_ctrl_c_after_the_take_names_the_note_as_not_returned(mysys, capsys):
    # Joey stopping a watched laptop run: no return attempt, but the ALERT
    # says which Note stays with the agent.
    fake = mysys(
        {
            "300001": FakeNote(
                "2600001B", fail_at="download", fail_with=KeyboardInterrupt
            )
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.calls.count("open_browser") == 1
    assert fake.notes["300001"].assignee == AGENT
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    assert "not returned to the pool" in alert["detail"]


# --- the detailed log ------------------------------------------------------------


def test_detailed_log_has_the_skips_and_one_traceback_per_error(
    mysys, capsys, tmp_path
):
    mysys(
        {
            "300002": FakeNote("2600001B", names=()),
            # Fails at the download: the fake PDF is 2600001B's, so this
            # Note would skip PO_MISMATCH before any project lookup.
            "300001": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = decide_only("--detailed-log")

    run_id = summary_of(output(capsys))["run_id"]
    assert code == 1
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    named = [
        (e["event"], e["note_id"], e.get("reason") or e.get("type")) for e in events
    ]
    assert ("skip", "300002", "NO_PDF") in named
    assert ("error", "300001", "UnexpectedScreen") in named
    assert [e["event"] for e in events].count("traceback") == 1


def test_without_detailed_log_nothing_is_written_to_logs(mysys, capsys, tmp_path):
    mysys({"300001": FakeNote("2600001B", fail_at="lookup")})

    assert decide_only() == 1
    output(capsys)
    assert not (tmp_path / "logs").exists()


# --- run mode: book end to end (4.5) ---------------------------------------------

W1_TO_W5 = [
    "check",  # W1's assignee check (D7)
    "reopen",
    "form",
    "fill",
    "submit",  # the partial-write line
    "new_task",
    "task_row",
    "open_detail",
    "detail",
    "back",
    "document",
    "project_window",
    "open_hold",
    "fill_hold",
    "confirm_hold",
    "on_hold",
    "check",  # W4's assignee check (D7)
    "find_again",
    "link",
    "log_count",
    "solved",
    "solved_log",
    "gone",
]


def book_run(*extra: str) -> int:
    return cli.main(["run", "--site", "test", *extra])


def calls_for(fake: FakeMySys, note_id: str) -> list[str]:
    return [c.split()[0] for c in fake.calls if c.endswith(f" {note_id}")]


def test_run_books_a_proceed_w1_to_w5_and_returns_a_skip(mysys, capsys):
    fake = mysys(
        {
            "300002": FakeNote("2600001B"),  # PROCEED
            "300001": FakeNote("2600002B", names=()),  # NO_PDF
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    assert calls_for(fake, "300002") == [
        "find_again",
        "assignee",
        "take",
        "2a",
        "names",
        "download",
        "body",
        "lookup",
        *W1_TO_W5,
    ]
    # Booked: never returned (the Note is linked and Solved, with the agent).
    assert "return 300002" not in fake.calls
    assert fake.notes["300002"].assignee == AGENT
    assert fake.notes["300001"].assignee == POOL
    assert "context_closed" not in fake.calls
    zero = {"field": None, "tokens_in": 0, "tokens_out": 0, "cost_aud": 0.0}
    booked, skipped = notes_of(lines)
    assert booked == {
        "note_id": "300002",
        "outcome": "booked",
        "reason": None,
        "po_number": "2600001B/048",
        "pln": "pln_10001",
        "task_id": "tsk_200002",
        **zero,
    }
    assert (skipped["note_id"], skipped["outcome"], skipped["reason"]) == (
        "300001",
        "skipped",
        "NO_PDF",
    )
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert summary["mode"] == "run"
    assert (summary["booked"], summary["skipped"], summary["partial"]) == (1, 1, 0)
    assert summary["exit_code"] == 0


BOOKER_WRITES = (
    "submit_task",
    "confirm_hold",
    "link_to_project",
    "link_select_project",
    "mark_solved",
)


@pytest.mark.parametrize("at", ["check", "link", "solved"])
def test_a_run_log_that_cant_be_written_mid_booking_doesnt_stop_it(mysys, capsys, at):
    # 5.2 review: the booker's run-log writes (W1/W4 checks, W4/W5 read-back
    # events, step flushes) never turn a booking into a partial write.
    fake = mysys({"300001": FakeNote("2600001B")}, break_log_at=at)

    code = book_run("--detailed-log")

    lines = output(capsys)
    assert "gone 300001" in fake.calls
    (booked,) = notes_of(lines)
    assert (booked["outcome"], booked["task_id"]) == ("booked", "tsk_200002")
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], code) == (1, 0, 0)


def test_the_detailed_log_has_send_email_unticked_after_w4s_check_before_w4_and_w5(
    mysys, capsys, tmp_path
):
    # 5.2, D7: the booker's assignee checks (W1, W4) and its Send Email
    # read-backs (W4's select, W5's Solved) are in the detailed log, in order.
    mysys({"300001": FakeNote("2600001B")})

    assert book_run("--detailed-log") == 0

    run_id = summary_of(output(capsys))["run_id"]
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    named = [
        (e["event"], e["step"], e.get("action"))
        for e in events
        if e["note_id"] == "300001"
        and (
            e["event"] in ("assignee_check", "email_notification_unticked")
            or e.get("action") in BOOKER_WRITES
        )
    ]
    # Each guard action carries its own W step (the safe trace, SPEC.md).
    assert named == [
        ("assignee_check", "2", None),
        ("assignee_check", "W1", None),
        ("guard_action", "W2", "submit_task"),
        ("guard_action", "W3", "confirm_hold"),
        ("assignee_check", "W4", None),
        ("email_notification_unticked", "W4", None),
        ("guard_action", "W4", "link_to_project"),
        ("email_notification_unticked", "W4", None),
        ("guard_action", "W4", "link_select_project"),
        ("email_notification_unticked", "W5", None),
        ("guard_action", "W5", "mark_solved"),
    ]
    assert all(
        e["ok"]
        for e in events
        if e["event"] in ("assignee_check", "email_notification_unticked")
    )


def test_a_note_taken_at_the_w1_check_is_untouched_and_the_next_runs_in_a_new_context(
    mysys, capsys
):
    fake = mysys(
        {
            # A person takes it while the project is read (step 10).
            "300002": FakeNote("2600001B", person_takes_at="lookup"),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    # Nothing written for 300002, and it stays with the person.
    assert calls_for(fake, "300002")[-2:] == ["lookup", "check"]
    assert "return 300002" not in fake.calls
    assert fake.notes["300002"].assignee == PERSON
    # Its browser context closed, then a fresh one for the next Note. The
    # sync API holds one browser per thread, so the old one closes first.
    checked = fake.calls.index("check 300002")
    assert fake.calls[checked + 1 : checked + 4] == [
        "context_closed",
        "closed",
        "open_browser",
    ]
    assert fake.calls.index("find_again 300001") > checked + 3
    assert fake.notes["300001"].assignee == POOL
    first, second = notes_of(lines)
    assert (first["note_id"], first["outcome"], first["reason"]) == (
        "300002",
        "untouched",
        "NOTE_TAKEN",
    )
    assert (second["note_id"], second["reason"]) == ("300001", "NO_PDF")
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["skipped"], summary["exit_code"]) == (0, 1, 0)


@pytest.mark.parametrize(
    ("kill_at", "closed_by_booker"),
    [("lookup", False), ("fill", True)],
    ids=["before-w1", "before-w2"],
)
def test_a_kill_switch_at_w1_or_w2_returns_the_note_in_a_fresh_context_and_exits_0(
    mysys, capsys, kill_at, closed_by_booker
):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", kill_at=kill_at),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    assert "submit 300002" not in fake.calls
    assert ("context_closed" in fake.calls) is closed_by_booker
    after = fake.calls[fake.calls.index("closed") :]
    assert after == [
        "closed",
        "open_browser",
        "find_again 300002",
        "assignee 300002",
        "return 300002",
        "closed",
    ]
    assert fake.notes["300002"].assignee == POOL
    assert "300001" not in opened(fake)
    assert "INFO  kill switch on: run stopped" in lines
    assert alerts_of(lines) == []
    assert notes_of(lines) == []
    assert summary_of(lines)["exit_code"] == 0


def test_write_not_started_returns_the_note_in_a_fresh_context_and_stops(mysys, capsys):
    # The Create New Task form not filled as read back (W1): nothing submitted.
    fake = mysys(
        {
            "300002": FakeNote("2600001B", fail_at="fill"),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert "submit 300002" not in fake.calls
    after = fake.calls[fake.calls.index("context_closed") :]
    assert after == [
        "context_closed",
        "closed",
        "open_browser",
        "find_again 300002",
        "assignee 300002",
        "return 300002",
        "closed",
    ]
    assert fake.notes["300002"].assignee == POOL
    assert "300001" not in opened(fake)
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"], alert["step"]) == (
        "UNEXPECTED_SCREEN",
        "300002",
        "W1",
    )
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], summary["exit_code"]) == (0, 0, 1)


AFTER_SUBMIT = [
    # (FakeNote changes, ALERT kind, step, exit code)
    ({"fail_at": "submit", "fail_with": RuntimeError}, "PARTIAL_WRITE", "W2", 1),
    ({"fail_at": "new_task"}, "PARTIAL_WRITE", "W2", 1),  # UnexpectedScreen
    ({"fail_at": "detail", "fail_with": AccuracyBreach}, "ACCURACY_BREACH", "W2", 3),
    ({"kill_at": "document"}, "PARTIAL_WRITE", "W3", 1),  # the kill switch at W3
    ({"fail_at": "confirm_hold", "fail_with": RuntimeError}, "PARTIAL_WRITE", "W3", 1),
    ({"person_takes_at": "on_hold"}, "PARTIAL_WRITE", "W4", 1),  # taken at W4
    # A Note someone linked meanwhile: no Link to Project to press (4.4).
    ({"fail_at": "link", "fail_with": GuardRefusal}, "GUARD_REFUSAL", "W4", 1),
    ({"fail_at": "gone"}, "PARTIAL_WRITE", "W5", 1),  # UnexpectedScreen
]


@pytest.mark.parametrize(
    ("changes", "kind", "step", "exit_code"),
    AFTER_SUBMIT,
    ids=[
        "submit-click-fails",
        "unexpected-screen-after-submit",
        "accuracy-breach-w2",
        "kill-switch-w3",
        "hold-confirm-fails",
        "note-taken-w4",
        "guard-refusal-w4",
        "not-gone-w5",
    ],
)
def test_from_the_submit_click_on_the_note_is_never_returned_and_the_run_stops(
    mysys, capsys, changes, kind, step, exit_code
):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", **changes),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == exit_code
    assert "submit 300002" in fake.calls
    # No return attempted: no fresh browser, no Assign back to the pool.
    assert fake.calls.count("open_browser") == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.notes["300002"].assignee in (AGENT, PERSON)
    assert "300001" not in opened(fake)  # the run stopped
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["note_id"], alert["step"]) == (kind, "300002", step)
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 1)
    assert summary["exit_code"] == exit_code


# --- run mode: the custody matrix (decisions, 5 Nov 2026, run mode) ----------------
# From the Submit click on (W2-W5) a Note is never returned to the pool: its
# ALERT names it, RUN_SUMMARY counts it as partial, the run stops. Before
# the click (W1, W2's before_write) a stopped Note is returned. Every way
# the booker can stop x every fake call it makes.

# The fake's calls from the Submit click on, by the booker's step. W4's
# assignee check and its find-again are this Note's second call of that
# name (the first: W1's check, step 2's find).
AFTER_CLICK_CALLS = {
    "W2": (
        "submit",
        "new_task",
        "task_row",
        "open_detail",
        "detail",
        "back",
        "document",
    ),
    "W3": ("project_window", "open_hold", "fill_hold", "confirm_hold", "on_hold"),
    "W4": ("check#2", "find_again#2", "link"),
    "W5": ("log_count", "solved", "solved_log", "gone"),
}
# W1's calls, the form never submitted.
BEFORE_CLICK_CALLS = ("check#1", "reopen", "form", "fill")
# A MySys step raising: UnexpectedScreen stands for any PoAgentError the
# booker converts; RuntimeError for a Playwright error; Ctrl+C.
RAISED = (
    UnexpectedScreen,
    AccuracyBreach,
    GuardRefusal,
    RuntimeError,
    KeyboardInterrupt,
)
KILL_SWITCH = "kill-switch"
PERSON_TAKES = "person-takes"
NEXT_STEP = {"W2": "W3", "W3": "W4", "W4": "W5", "W5": None}


def _after_click_expected(trigger, step: str, call: str) -> tuple[str, str, int] | str:
    """By the rule: (ALERT kind, its step, exit code), or why the code can't
    stop there. GuardRefusal and AccuracyBreach keep their kind, every other
    error is PARTIAL_WRITE; exit 3 for an accuracy breach, else 1."""
    if trigger == KILL_SWITCH:
        # Re-read by each step's before_write: it stops the next step.
        if NEXT_STEP[step] is None:
            return "no before_write after W5's: the booking finishes"
        return ("PARTIAL_WRITE", NEXT_STEP[step], 1)
    if trigger == PERSON_TAKES:
        # D7: the assignee is checked before W1 and W4 only.
        if step == "W5" or (step == "W4" and call != "check#2"):
            return "no assignee check after W4's (D7): the booking finishes"
        return ("PARTIAL_WRITE", "W4", 1)
    if call == "check#2":
        # W4's assignee check: any failure is PartialWrite (D7; booker W4).
        return ("PARTIAL_WRITE", "W4", 1)
    if trigger is AccuracyBreach:
        return ("ACCURACY_BREACH", step, 3)
    if trigger is GuardRefusal:
        return ("GUARD_REFUSAL", step, 1)
    return ("PARTIAL_WRITE", step, 1)


def _trigger_changes(trigger, call: str) -> dict:
    if trigger == KILL_SWITCH:
        return {"kill_at": call}
    if trigger == PERSON_TAKES:
        return {"person_takes_at": call}
    return {"fail_at": call, "fail_with": trigger}


def _trigger_id(trigger) -> str:
    return trigger if isinstance(trigger, str) else trigger.__name__


def _after_click_cases() -> list:
    cases = []
    for trigger in (*RAISED, KILL_SWITCH, PERSON_TAKES):
        for step, calls in AFTER_CLICK_CALLS.items():
            for call in calls:
                expected = _after_click_expected(trigger, step, call)
                marks = ()
                if isinstance(expected, str):
                    marks = pytest.mark.skip(reason=expected)
                    expected = (None, None, None)
                cases.append(
                    pytest.param(
                        trigger,
                        call,
                        *expected,
                        id=f"{_trigger_id(trigger)}-{step}-{call}",
                        marks=marks,
                    )
                )
    return cases


@pytest.mark.parametrize(
    ("trigger", "call", "kind", "step", "exit_code"), _after_click_cases()
)
def test_custody_matrix_from_the_submit_click_on_the_note_is_never_returned(
    mysys, capsys, trigger, call, kind, step, exit_code
):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", **_trigger_changes(trigger, call)),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert "submit 300002" in fake.calls
    # No return attempted: no fresh browser, no Assign back to the pool.
    assert fake.calls.count("open_browser") == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    holder = PERSON if trigger == PERSON_TAKES else AGENT
    assert fake.notes["300002"].assignee == holder
    assert "300001" not in opened(fake)  # the run stopped
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["note_id"], alert["step"]) == (kind, "300002", step)
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 1)
    assert (code, summary["exit_code"]) == (exit_code, exit_code)


@pytest.mark.parametrize("call", BEFORE_CLICK_CALLS)
@pytest.mark.parametrize(
    "trigger", [t for t in RAISED if t is not KeyboardInterrupt], ids=_trigger_id
)
def test_custody_matrix_before_the_submit_click_the_note_is_returned(
    mysys, capsys, trigger, call
):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", fail_at=call, fail_with=trigger),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert "submit 300002" not in fake.calls
    # One return, in a fresh browser context.
    assert fake.calls.count("open_browser") == 2
    assert [c for c in fake.calls if c.startswith("return")] == ["return 300002"]
    assert fake.calls.index("return 300002") > fake.calls.index("closed")
    assert fake.notes["300002"].assignee == POOL
    assert "300001" not in opened(fake)  # the run stopped
    ((alert_kind, alert),) = alerts_of(lines)
    assert alert["note_id"] == "300002"
    assert alert_kind != "PARTIAL_WRITE"
    assert "not returned" not in alert["detail"]
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 0)
    expected = 3 if alert_kind == "ACCURACY_BREACH" else 1
    assert (code, summary["exit_code"]) == (expected, expected)


@pytest.mark.parametrize("call", BEFORE_CLICK_CALLS)
def test_custody_matrix_ctrl_c_before_the_submit_click_names_the_note_not_returned(
    mysys, capsys, call
):
    # Ctrl+C skips the return (run.py), and the ALERT says which Note stays
    # with the agent; nothing was submitted, so it is no partial write.
    fake = mysys(
        {
            "300002": FakeNote("2600001B", fail_at=call, fail_with=KeyboardInterrupt),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert "submit 300002" not in fake.calls
    assert fake.calls.count("open_browser") == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.notes["300002"].assignee == AGENT
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300002")
    assert "not returned to the pool" in alert["detail"]
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 0)
    assert (code, summary["exit_code"]) == (1, 1)


# The kill switch read by W1's before_write (set during the project read)
# or W2's (set during any W1 call): before the click.
@pytest.mark.parametrize("call", ["lookup", *BEFORE_CLICK_CALLS])
def test_custody_matrix_a_kill_switch_before_the_submit_click_returns_the_note(
    mysys, capsys, call
):
    fake = mysys(
        {
            "300002": FakeNote("2600001B", kill_at=call),
            "300001": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert "submit 300002" not in fake.calls
    assert fake.calls.count("open_browser") == 2
    assert [c for c in fake.calls if c.startswith("return")] == ["return 300002"]
    assert fake.notes["300002"].assignee == POOL
    assert "300001" not in opened(fake)
    assert "INFO  kill switch on: run stopped" in lines
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 0)
    assert (code, summary["exit_code"]) == (0, 0)


# The run loop's backstop (run._submitted): the booker gives every error
# from the click on one of its three types, so no fake call reaches an
# error of another type that names W3-W5. Pinned here directly.
def _stop(error_type, step):
    if error_type is controls.KillSwitch:
        return controls.KillSwitch(note_id="300001", step=step)
    if error_type is controls.NoteTaken:
        return controls.NoteTaken(note_id="300001", step=step)
    return error_type("fake stop", note_id="300001", step=step)


AFTER_CLICK_TYPES = (PartialWrite, AccuracyBreach, GuardRefusal)
OTHER_TYPES = (
    UnexpectedScreen,
    WriteNotStarted,
    ConfigError,
    controls.KillSwitch,
    controls.NoteTaken,
)


@pytest.mark.parametrize("step", [None, "W1", "W2", "W3", "W4", "W5"])
@pytest.mark.parametrize(
    "error_type", AFTER_CLICK_TYPES + OTHER_TYPES, ids=lambda t: t.__name__
)
def test_custody_matrix_what_counts_as_past_the_submit_click(error_type, step):
    # W3-W5: past the click, whatever the type. W2: only the booker's
    # after-click types (its before_write errors also say W2).
    past = step in ("W3", "W4", "W5") or (
        step == "W2" and error_type in AFTER_CLICK_TYPES
    )
    assert run._submitted(_stop(error_type, step)) is past


def test_custody_matrix_an_error_with_no_step_is_before_the_click():
    assert run._submitted(RuntimeError("fake")) is False
    assert run._submitted(KeyboardInterrupt()) is False


# --- run mode: what the run knows about Submit, not the last exception (4.5 review)


def test_a_run_log_that_fails_after_w5_never_returns_the_booked_note(mysys, capsys):
    # --detailed-log, and the log can't be written once the Note is Solved.
    fake = mysys({"300001": FakeNote("2600001B")}, break_log_at="gone")

    code = book_run("--detailed-log")

    lines = output(capsys)
    assert "gone 300001" in fake.calls
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.calls.count("open_browser") == 1
    (booked,) = notes_of(lines)
    assert (booked["outcome"], booked["task_id"]) == ("booked", "tsk_200002")
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], code) == (1, 0, 0)


def test_a_failed_browser_close_after_submit_keeps_the_partial_write(mysys, capsys):
    # The Hold confirm fails (W3), then closing the browser fails too.
    fake = mysys(
        {
            "300001": FakeNote(
                "2600001B", fail_at="confirm_hold", fail_with=RuntimeError
            )
        },
        close_fails=True,
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.calls.count("open_browser") == 1
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"], alert["step"]) == ("PARTIAL_WRITE", "300001", "W3")
    assert summary_of(lines)["partial"] == 1


# --- 7.2: a silent skip can't happen; more pages alerts (decisions, 5 Nov 2026) ---


def test_when_every_eligible_note_would_be_unexpected_screen_the_first_alerts(
    mysys, capsys
):
    # The run stops on the first UNEXPECTED_SCREEN, so a MySys screen change
    # can't skip every Note quietly: one ALERT, exit 1, the next Note untouched.
    fake = mysys(
        {
            "300002": FakeNote("2600001B", fail_at="download"),
            "300001": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert opened(fake) == ["300002"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "300002")
    ]
    assert summary_of(lines)["exit_code"] == 1


def test_one_booked_then_one_unexpected_screen_still_alerts(mysys, capsys):
    fake = mysys(
        {
            "300002": FakeNote("2600001B"),  # PROCEED: booked
            "300001": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert [n["outcome"] for n in notes_of(lines)] == ["booked"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "300001")
    ]
    assert fake.notes["300001"].assignee == POOL
    summary = summary_of(lines)
    assert (summary["booked"], summary["exit_code"]) == (1, 1)


@pytest.mark.parametrize("command", [book_run, decide_only])
def test_more_pages_in_the_eligible_read_alerts_before_any_note(mysys, capsys, command):
    fake = mysys({"300001": FakeNote("2600001B")}, pool_pages=2)

    code = command()

    lines = output(capsys)
    assert code == 1
    assert opened(fake) == []
    assert not [c for c in fake.calls if c.startswith("take")]
    assert [kind for kind, _ in alerts_of(lines)] == ["MORE_PAGES"]
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["seen"], summary["eligible"], summary["exit_code"]) == (1, 1, 1)


# --- the client's values reach MySys (task 9.4, mutant rows) -----------------

# B1's project rule (SPEC.md -> Project search): the one B1 Homes row whose
# Client Ref No. is the internal number; another builder's row never matches.
B1_ROW = SearchRow(pln="pln_10001", client_ref_no="2600001B", company="B1 Homes")
OTHER_ROW = SearchRow(
    pln="pln_10009", client_ref_no="2600001B", company="Another Builder"
)


def is_b1_rule(rule) -> bool:
    return rule.match((OTHER_ROW, B1_ROW), False, "2600001B") == "pln_10001" and (
        rule.match((OTHER_ROW,), False, "2600001B")
        == Skip(reason=SkipReason.PROJECT_NOT_FOUND)
    )


def set_profile(fake: FakeMySys, old: str, new: str) -> None:
    toml = fake.config_dir / "test.toml"
    text = toml.read_text("utf-8")
    assert old in text
    toml.write_text(text.replace(old, new), "utf-8")


def test_the_project_read_and_w1_s_reopen_use_b1_s_project_rule(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B")})

    assert book_run() == 0

    assert [step for step, _ in fake.rules] == ["lookup", "reopen"]
    assert all(is_b1_rule(rule) for _, rule in fake.rules)


def test_w2_reads_back_the_profile_s_documents_type(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B")})
    set_profile(
        fake,
        'project_document_type = "Client Documents"',
        'project_document_type = "Fake Documents Type"',
    )

    assert book_run() == 0

    assert fake.document_types == ["Fake Documents Type"]


def test_a_profile_counting_cancelled_tasks_skips_a_cancelled_duplicate(mysys, capsys):
    # duplicate_ignores_cancelled = false (live's value): a Cancelled
    # Compaction Test task still counts (SPEC.md -> Duplicate check).
    cancelled = (CompactionTask(task_no="tsk_100001", status="Cancelled"),)
    lookup = CLEAN.lookup.model_copy(update={"tasks": cancelled})
    fake = mysys({"300001": FakeNote("2600001B", lookup=lookup)})
    set_profile(
        fake,
        "duplicate_ignores_cancelled = true",
        "duplicate_ignores_cancelled = false",
    )

    assert decide_only() == 0

    ((note),) = notes_of(output(capsys))
    assert (note["outcome"], note["reason"]) == ("skipped", "DUPLICATE_TASK")


def test_every_read_back_naming_the_agent_gets_the_profile_s_agent(mysys, capsys):
    # Lodged By on the new task row and the detail screen, and "Solved by"
    # name the agent (SPEC.md -> MySys screen rules), never the pool.
    fake = mysys({"300001": FakeNote("2600001B")})

    assert book_run() == 0

    assert fake.agents == [("task_row", AGENT), ("detail", AGENT), ("solved", AGENT)]
