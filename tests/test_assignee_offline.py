"""The assignee check and the stale-Note stop (task 3.6), offline.

Not `testsite`. The assignee check runs for real inside
`Controls.before_write`; only `driver.search_note` is faked: it returns what
the Note Pool lists for the search (a substring filter, so 300001 also lists
3000012), and the check must pick the row whose ID cell equals the Note ID.
The stale-Note stop runs through cli.main on seam 2's fake MySys (tests/
seam2/test_run_loop_offline.py), which records every call. Values are fake.

- Before W1 and W4: a fresh search (reload, All Pools, the Note ID); the one
  row whose ID equals the Note ID must have Assignee `agent_user_name`.
  Zero or several such rows -> UnexpectedScreen before W1. Someone else
  before W1 -> NoteTaken (nothing written, the run carries on). Before W4
  the task exists: someone else, no single row or a failed search ->
  PartialWrite (3.6 review). W2, W3 and W5 don't search (D7).
- Stale-Note stop (D6): in `run --decide-only`, after login and before the
  eligible list is read, the Pending Notes under All Users, All Pools and
  All (the test site's Assigned User list has no agent; decisions, 3 Nov
  2026): a row with the agent as Assignee -> ALERT UNEXPECTED_SCREEN with
  its note_id, no Note opened, exit 1, even with more pages. A second page
  can't be read, so it stops before any Note too: ALERT MORE_PAGES, exit 1
  (7.2; decisions, 5 Nov 2026). `spike` skips the read.
"""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from po_agent import cli
from po_agent.b1.models import NotePoolRow
from po_agent.core import controls
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import (
    LoginFailed,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
)
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

_spec = importlib.util.spec_from_file_location(
    "seam2_fake_mysys_for_assignee",
    Path(__file__).parent / "seam2" / "test_run_loop_offline.py",
)
fake_mysys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_mysys)
FakeNote = fake_mysys.FakeNote
env = fake_mysys.env
mysys = fake_mysys.mysys

AGENT = fake_mysys.AGENT
POOL = fake_mysys.POOL
PERSON = fake_mysys.PERSON
NOTE_ID = "300001"
LOGIN = ("https://test.invalid/", "fake-user", "fake-password")
STALE_DETAIL = "a Note is still assigned to the agent from an earlier run"
MONDAY_10_PERTH = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def inside_run_window(monkeypatch):
    monkeypatch.setattr(controls, "now", lambda: MONDAY_10_PERTH)


def pool_row(note_id: str, assignee: str) -> NotePoolRow:
    return NotePoolRow(
        note_id=note_id, subject_note="fake", project="---", assignee=assignee
    )


class FakeSearch:
    """`driver.search_note`: the rows the Note Pool lists for the search."""

    def __init__(self, *rows: NotePoolRow) -> None:
        self.rows = rows
        self.calls: list[str] = []

    def __call__(self, guard, page, base_url, username, password, note_id):
        self.calls.append(note_id)
        listing = driver.NotePoolList(rows=self.rows, total=len(self.rows), pages=1)
        return "panel", listing


@pytest.fixture
def gate(monkeypatch):
    """Controls with the real assignee check; `install(*rows)` sets what the
    search lists and returns the fake."""

    def install(*rows: NotePoolRow) -> tuple[controls.Controls, FakeSearch]:
        search = FakeSearch(*rows)
        monkeypatch.setattr(driver, "search_note", search)
        check = controls.assignee_check(ActionGuard(), "page", LOGIN, AGENT)
        return controls.Controls("test", CONFIG_DIR, assignee_check=check), search

    return install


# --- the assignee check before W1 and W4 --------------------------------------------


@pytest.mark.parametrize("step", ["W1", "W4"])
def test_the_note_with_the_agent_passes_even_when_a_longer_id_is_listed(gate, step):
    # 3000012 contains 300001: it is listed too, with a person.
    checks, search = gate(pool_row("3000012", PERSON), pool_row(NOTE_ID, AGENT))

    checks.before_write(NOTE_ID, step)

    assert search.calls == [NOTE_ID]


def test_someone_else_at_w1_is_note_taken_not_a_run_stop(gate):
    # The agent holds 3000012, not 300001: only the equal row counts.
    checks, _ = gate(pool_row(NOTE_ID, PERSON), pool_row("3000012", AGENT))

    with pytest.raises(controls.NoteTaken) as raised:
        checks.before_write(NOTE_ID, "W1")

    # Like KillSwitch, not a PoAgentError: the run handles it, no ALERT.
    assert not isinstance(raised.value, PoAgentError)
    assert (raised.value.note_id, raised.value.step) == (NOTE_ID, "W1")


def test_someone_else_at_w4_is_a_partial_write(gate):
    checks, _ = gate(pool_row(NOTE_ID, PERSON))

    with pytest.raises(PartialWrite) as raised:
        checks.before_write(NOTE_ID, "W4")

    assert (raised.value.note_id, raised.value.step) == (NOTE_ID, "W4")


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (pool_row("3000012", AGENT),),  # only a longer ID: not the Note
        (pool_row("1300001", AGENT),),
        (pool_row(NOTE_ID, AGENT), pool_row(NOTE_ID, AGENT)),  # twice: not one
    ],
    ids=["none", "prefix-only", "suffix-only", "twice"],
)
@pytest.mark.parametrize(
    ("step", "error"), [("W1", UnexpectedScreen), ("W4", PartialWrite)]
)
def test_not_exactly_one_equal_row_stops_and_after_w3_is_a_partial_write(
    gate, rows, step, error
):
    checks, _ = gate(*rows)

    with pytest.raises(error) as raised:
        checks.before_write(NOTE_ID, step)

    assert (raised.value.note_id, raised.value.step) == (NOTE_ID, step)


@pytest.mark.parametrize(
    "failure", [UnexpectedScreen("fake"), LoginFailed("fake")], ids=["screen", "login"]
)
def test_a_failed_search_before_w4_is_a_partial_write(monkeypatch, failure):
    # The task exists and is on hold: the run must never return the Note to
    # the pool, where it would look unbooked.
    def search(*args):
        raise failure

    monkeypatch.setattr(driver, "search_note", search)
    check = controls.assignee_check(ActionGuard(), "page", LOGIN, AGENT)
    checks = controls.Controls("test", CONFIG_DIR, assignee_check=check)

    with pytest.raises(PartialWrite) as raised:
        checks.before_write(NOTE_ID, "W4")
    with pytest.raises(type(failure)):
        checks.before_write(NOTE_ID, "W1")

    assert (raised.value.note_id, raised.value.step) == (NOTE_ID, "W4")


def test_w2_w3_and_w5_never_leave_their_window(gate):
    checks, search = gate(pool_row(NOTE_ID, PERSON))

    for step in ("W2", "W3", "W5"):
        checks.before_write(NOTE_ID, step)

    assert search.calls == []


# --- the stale-Note stop at run start ---------------------------------------------


def lines_of(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


def test_a_note_left_with_the_agent_stops_decide_only_before_any_note(mysys, capsys):
    fake = mysys(
        {"300002": FakeNote("2600002B")},
        agent_rows=(pool_row("300099", AGENT),),
    )

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 1
    # After login, before the eligible list is read; no Note opened or taken.
    assert fake.calls.index("login") < fake.calls.index("agent_notes")
    assert "read" not in fake.calls
    assert not [c for c in fake.calls if c.startswith(("find_again", "take"))]
    assert fake.notes["300002"].taken == 0
    alerts = [x for x in lines if x.startswith("ALERT ")]
    assert len(alerts) == 1
    kind, _, body = alerts[0].removeprefix("ALERT ").partition(" ")
    alert = json.loads(body)
    assert kind == "UNEXPECTED_SCREEN"
    assert alert["note_id"] == "300099"
    assert alert["detail"].startswith(STALE_DETAIL)
    assert not [x for x in lines if x.startswith("NOTE")]
    summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
    assert summary["exit_code"] == 1


def test_a_note_with_the_agent_on_page_1_is_named_even_with_more_pages(mysys, capsys):
    mysys(
        {"300002": FakeNote("2600002B")},
        agent_rows=(pool_row("300099", AGENT),),
        agent_pages=2,
    )

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 1
    (alert,) = [x for x in lines if x.startswith("ALERT ")]
    body = json.loads(alert.removeprefix("ALERT ").partition(" ")[2])
    assert body["note_id"] == "300099"
    assert body["detail"].startswith(STALE_DETAIL)


def test_a_second_page_in_the_stale_note_read_stops_before_any_note(mysys, capsys):
    fake = mysys(
        {"300002": FakeNote("2600002B")},
        agent_rows=(pool_row("300002", POOL),),
        agent_pages=2,
    )

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 1
    assert "read" not in fake.calls
    assert not [c for c in fake.calls if c.startswith(("find_again", "take"))]
    # 7.2 (decisions, 5 Nov 2026): its own ALERT kind, still exit 1.
    assert [x.split()[1] for x in lines if x.startswith("ALERT ")] == ["MORE_PAGES"]


def test_with_no_note_left_with_the_agent_decide_only_goes_on(mysys, capsys):
    fake = mysys({"300002": FakeNote("2600002B", names=())})

    code = cli.main(["run", "--site", "test", "--decide-only"])

    assert code == 0
    assert fake.calls.index("agent_notes") < fake.calls.index("read")
    assert fake.notes["300002"].assignee == POOL


# Live (decisions, 10 Nov 2026, My Notes): the read is the agent's own My
# Notes tab, between two reloads, before the Note Pool is opened. The test
# profile is switched to it here; nothing runs on live.


def my_notes_profile(tmp_path) -> None:
    toml = tmp_path / "config" / "test.toml"
    text = toml.read_text("utf-8")
    assert 'stale_read = "note_pool"' in text
    toml.write_text(
        text.replace('stale_read = "note_pool"', 'stale_read = "my_notes"'), "utf-8"
    )


def test_my_notes_profile_reads_my_notes_between_reloads_then_goes_on(
    mysys, capsys, tmp_path
):
    my_notes_profile(tmp_path)
    fake = mysys({"300002": FakeNote("2600002B", names=())})

    code = cli.main(["run", "--site", "test", "--decide-only"])

    assert code == 0
    calls = fake.calls
    start = calls.index("login")
    assert calls[start : start + 5] == [
        "login",
        "reload_home",
        "open_my_notes",
        "my_notes",
        "reload_home",
    ]
    assert calls[start + 5] == "open_note_pool"
    assert "agent_notes" not in calls
    assert calls.index("my_notes") < calls.index("filters") < calls.index("read")


def test_any_note_in_my_notes_stops_the_run_before_the_note_pool(
    mysys, capsys, tmp_path
):
    my_notes_profile(tmp_path)
    # Any row stops it, whatever its Assignee cell says.
    fake = mysys(
        {"300002": FakeNote("2600002B")},
        my_notes_rows=(pool_row("300099", PERSON),),
    )

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 1
    assert "open_note_pool" not in fake.calls
    assert not [c for c in fake.calls if c.startswith(("find_again", "take"))]
    (alert,) = [x for x in lines if x.startswith("ALERT ")]
    kind, _, body = alert.removeprefix("ALERT ").partition(" ")
    assert kind == "UNEXPECTED_SCREEN"
    assert json.loads(body)["note_id"] == "300099"
    assert json.loads(body)["detail"].startswith(STALE_DETAIL)


def test_a_second_page_of_my_notes_stops_the_run_as_more_pages(mysys, capsys, tmp_path):
    my_notes_profile(tmp_path)
    fake = mysys({"300002": FakeNote("2600002B")}, my_notes_pages=2)

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 1
    assert "open_note_pool" not in fake.calls
    assert [x.split()[1] for x in lines if x.startswith("ALERT ")] == ["MORE_PAGES"]


def test_spike_skips_the_stale_note_read(mysys, capsys):
    fake = mysys(
        {"300002": FakeNote("2600002B")},
        agent_rows=(pool_row("300099", AGENT),),
    )

    code = cli.main(["spike", "--site", "test"])

    assert code == 0
    assert "agent_notes" not in fake.calls
