# ruff: noqa: E501 - the fake page HTML reads better unwrapped
"""The hold re-check (decisions, 11 Nov 2026, hold re-check), offline.

On 11 Nov 2026 a live task the agent had put On Hold was later back at
"New Project" with no Un-Hold in any log: MySys released the hold silently.
The agent can't stop that, but it can see it. Every booking writes a
`booked` event to the safe trace with its pln, task number and internal
number. At the start of each `run` and `run --decide-only`, before any Note
is taken, the agent reads the trace files of today and the previous working
day (Perth), takes that site's bookings newest first (test and live share
the Mac Mini's trace folder), at most 10, and re-reads each
task's row on its project, read only: Un-Hold plus a Status starting
"On-hold" is held; Cancelled is a person's choice and not an alert; any
other state, or the task not found, is `ALERT HOLD_LOST` with the booking's
Note ID. The run goes on (exit 0). No trace (the laptop, CI): nothing is
re-checked and nothing is printed.

The run tests use seam 2's fake MySys (tests/seam2/test_run_loop_offline.py)
with `driver.recheck_hold` faked; the page tests use headless Chromium on a
local fake of the project window (screen map rows 07, 10, 12). Values are
fake.
"""

import importlib.util
import json
import tempfile
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent import cli
from po_agent.b1.models import MySysLookup, SearchRow
from po_agent.core import controls, run, trace
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import booking, driver

_spec = importlib.util.spec_from_file_location(
    "seam2_fake_mysys_for_hold_recheck",
    Path(__file__).parent / "seam2" / "test_run_loop_offline.py",
)
fake_mysys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_mysys)
FakeNote = fake_mysys.FakeNote

KEYS = {"run_id", "ts", "note_id", "step", "name", "outcome", "duration_ms"}
MONDAY_10_PERTH = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
MONDAY = date(2026, 11, 2)
FRIDAY = date(2026, 10, 30)
THURSDAY = date(2026, 10, 29)
SEED_RUN = "20261030T010203Z-abcd"
AGENT = "Agent 1 (MySys Only)"


# --- fixtures --------------------------------------------------------------------


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake secrets, temp, logs and config under tmp_path; the trace folder's
    parent exists; the clock at Monday 10:00 Perth."""
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_USERNAME", "fake-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", "fake-password")
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (tmp_path / "po-agent").mkdir()
    lines = (CONFIG_DIR / "test.toml").read_text("utf-8").splitlines()
    toml = "\n".join(x for x in lines if not x.startswith("trace_dir"))
    toml += f'\ntrace_dir = "{trace_dir(tmp_path).as_posix()}"\n'
    (config_dir / "test.toml").write_text(toml, "utf-8")
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(controls, "now", lambda: MONDAY_10_PERTH)
    yield monkeypatch
    keyring.set_keyring(previous)


def trace_dir(tmp_path: Path) -> Path:
    return tmp_path / "po-agent" / "trace"


@pytest.fixture
def mysys(env, tmp_path):
    """Seam 2's fake MySys, plus a fake `driver.recheck_hold` whose answer
    per task number is `states` (default held). Each re-check is a call
    `recheck <task>` and one guard action, as the real one's reads are."""

    def install(notes: dict, states: dict | None = None, **kwargs):
        rows = tuple(fake_mysys.row(n, note.internal_no) for n, note in notes.items())
        fake = fake_mysys.FakeMySys(
            notes=notes,
            rows=rows,
            config_dir=tmp_path / "config",
            logs_dir=tmp_path / "logs",
            **kwargs,
        )
        for name in fake_mysys.DRIVER_NAMES + fake_mysys.BOOKER_DRIVER_NAMES:
            env.setattr(run.driver, name, getattr(fake, name), raising=False)
        for name in fake_mysys.BOOKING_NAMES:
            env.setattr(booking, name, getattr(fake, name))
        answers = states or {}

        def recheck_hold(guard, page, base_url, username, password, booked, site):
            fake.calls.append(f"recheck {booked.task_id}")
            guard.history.append(("search_project", "done"))
            answer = answers.get(booked.task_id, "on_hold")
            if isinstance(answer, BaseException):
                raise answer
            return answer

        env.setattr(run.driver, "recheck_hold", recheck_hold, raising=False)
        return fake

    return install


def seed(
    tmp_path: Path, day: date, *bookings: tuple[str, str, str, str], site="test"
) -> None:
    """Writes `booked` events, as an earlier run would, to `day`'s file."""
    trace_dir(tmp_path).parent.mkdir(exist_ok=True)  # as the Mac Mini has it
    log = trace.Trace(SEED_RUN)
    log.start(trace_dir(tmp_path), day)
    for note_id, pln, task_id, internal_no in bookings:
        log.booked(
            note_id=note_id,
            pln=pln,
            task_id=task_id,
            internal_no=internal_no,
            site=site,
        )


def booked(n: int) -> tuple[str, str, str, str]:
    return (f"3000{n:02d}", f"pln_100{n:02d}", f"tsk_2000{n:02d}", f"26000{n:02d}B")


def stdout_of(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


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


def events_of(tmp_path: Path, day: date = MONDAY) -> list[dict]:
    path = trace_dir(tmp_path) / f"{day.isoformat()}.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def rechecked(fake) -> list[str]:
    return [c.split()[1] for c in fake.calls if c.startswith("recheck ")]


def decide_only() -> int:
    return cli.main(["run", "--site", "test", "--decide-only"])


def book_run() -> int:
    return cli.main(["run", "--site", "test"])


# --- the booked event ------------------------------------------------------------


def test_a_booking_writes_a_booked_event_with_its_pln_task_and_internal_no(
    mysys, capsys, tmp_path
):
    mysys({"300002": FakeNote("2600001B")})  # PROCEED -> booked

    assert book_run() == 0

    stdout_of(capsys)
    events = events_of(tmp_path)
    found = [e for e in events if e["name"] == "booked"]
    assert len(found) == 1
    (event,) = found
    assert (event["note_id"], event["step"], event["outcome"]) == (
        "300002",
        "W5",
        "pass",
    )
    assert (event["pln"], event["task_id"], event["internal_no"], event["site"]) == (
        "pln_10001",
        "tsk_200002",
        "2600001B",
        "test",
    )
    assert set(event) == KEYS | {"pln", "task_id", "internal_no", "site"}
    # Every other event keeps exactly the 7.3 fields.
    assert all(set(e) == KEYS for e in events if e["name"] != "booked")


def test_booked_values_outside_their_closed_type_are_dropped(tmp_path):
    log = trace.Trace(SEED_RUN)
    log.start(tmp_path, FRIDAY)

    log.booked(
        note_id="300001",
        pln="Lot 123 Sample Lane",
        task_id="tsk_200001 | Compaction Test",
        internal_no="2600001B/048 Sampleville",
        site="Sampleville",
    )

    (line,) = (tmp_path / f"{FRIDAY.isoformat()}.jsonl").read_text("utf-8").splitlines()
    event = json.loads(line)
    assert event["name"] == "booked"
    assert "Sample" not in line and "Compaction" not in line
    keys = ("pln", "task_id", "internal_no", "site")
    assert all(event.get(key) is None for key in keys)
    # A booking missing a value can't be re-checked: it isn't listed.
    log.start(tmp_path, MONDAY)
    assert log.recent_bookings("test") == ()


# --- which bookings are re-checked -----------------------------------------------


def test_recent_bookings_are_today_and_the_previous_working_day_newest_first(
    tmp_path,
):
    seed(tmp_path, THURSDAY, booked(1))
    seed(tmp_path, FRIDAY, booked(2), booked(3))
    seed(tmp_path, MONDAY, booked(4))
    path = trace_dir(tmp_path) / f"{FRIDAY.isoformat()}.jsonl"
    with open(path, "a", encoding="utf-8") as file:
        file.write("not json\n")
        file.write('{"name": "booked"}\n')

    log = trace.Trace("20261102T020000Z-0001")
    log.start(trace_dir(tmp_path), MONDAY)

    found = log.recent_bookings("test")
    assert [b.task_id for b in found] == ["tsk_200004", "tsk_200003", "tsk_200002"]
    first = found[0]
    assert (first.note_id, first.pln, first.internal_no) == (
        "300004",
        "pln_10004",
        "2600004B",
    )


def test_on_a_tuesday_the_previous_working_day_is_monday(tmp_path):
    seed(tmp_path, FRIDAY, booked(1))
    seed(tmp_path, MONDAY, booked(2))

    log = trace.Trace("20261103T020000Z-0001")
    log.start(trace_dir(tmp_path), date(2026, 11, 3))

    assert [b.task_id for b in log.recent_bookings("test")] == ["tsk_200002"]


def test_a_task_booked_twice_in_the_files_is_listed_once(tmp_path):
    seed(tmp_path, FRIDAY, booked(1))
    seed(tmp_path, MONDAY, booked(1))

    log = trace.Trace("20261102T020000Z-0001")
    log.start(trace_dir(tmp_path), MONDAY)

    assert [b.task_id for b in log.recent_bookings("test")] == ["tsk_200001"]


def test_only_the_runs_own_sites_bookings_are_listed(tmp_path):
    # Review finding 1: test and live share the Mac Mini's trace folder.
    seed(tmp_path, FRIDAY, booked(1), site="live")
    seed(tmp_path, FRIDAY, booked(2), site="test")

    log = trace.Trace("20261102T020000Z-0001")
    log.start(trace_dir(tmp_path), MONDAY)

    assert [b.task_id for b in log.recent_bookings("test")] == ["tsk_200002"]
    assert [b.task_id for b in log.recent_bookings("live")] == ["tsk_200001"]


def test_no_trace_folder_lists_no_bookings(tmp_path):
    log = trace.Trace("20261102T020000Z-0001")
    log.start(tmp_path / "missing" / "trace", MONDAY)

    assert log.recent_bookings("test") == ()


# --- the re-check in a run -------------------------------------------------------


@pytest.mark.parametrize("command", [book_run, decide_only])
def test_a_held_task_is_rechecked_before_any_note_and_the_run_goes_on(
    mysys, capsys, tmp_path, command
):
    seed(tmp_path, FRIDAY, booked(9))
    fake = mysys({"300002": FakeNote("2600001B", names=())})  # NO_PDF

    assert command() == 0

    lines = stdout_of(capsys)
    assert rechecked(fake) == ["tsk_200009"]
    calls = fake.calls
    at = calls.index("recheck tsk_200009")
    assert calls.index("login") < at < calls.index("open_note_pool")
    # A reload between the project read and the Note Pool.
    assert "reload_home" in calls[at : calls.index("open_note_pool")]
    assert "find_again 300002" in calls  # the run went on
    assert "INFO  hold re-check: 1 checked, 0 not on hold" in lines
    assert alerts_of(lines) == []
    assert summary_of(lines)["exit_code"] == 0


@pytest.mark.parametrize(
    ("state", "detail"),
    [
        ("not_on_hold", "booked task not on hold"),
        ("not_found", "booked task not found"),
    ],
)
def test_a_lost_hold_alerts_with_the_bookings_note_and_the_run_goes_on(
    mysys, capsys, tmp_path, state, detail
):
    seed(tmp_path, FRIDAY, booked(9))
    fake = mysys(
        {"300002": FakeNote("2600001B", names=())}, states={"tsk_200009": state}
    )

    assert book_run() == 0

    lines = stdout_of(capsys)
    assert alerts_of(lines) == [
        ("HOLD_LOST", {"note_id": "300009", "step": "hold_check", "detail": detail})
    ]
    assert "INFO  hold re-check: 1 checked, 1 not on hold" in lines
    # Nothing in the line but the Note ID: no pln, task or internal number.
    (line,) = [x for x in lines if x.startswith("ALERT")]
    for value in ("pln_10009", "tsk_200009", "2600009B"):
        assert value not in line
    assert "find_again 300002" in fake.calls
    summary = summary_of(lines)
    assert (summary["exit_code"], summary["skipped"]) == (0, 1)


def test_a_cancelled_task_is_not_an_alert(mysys, capsys, tmp_path):
    seed(tmp_path, FRIDAY, booked(9))
    mysys({}, states={"tsk_200009": "cancelled"})

    assert book_run() == 0

    lines = stdout_of(capsys)
    assert alerts_of(lines) == []
    assert "INFO  hold re-check: 1 checked, 0 not on hold" in lines


def test_at_most_ten_are_rechecked_newest_first(mysys, capsys, tmp_path):
    seed(tmp_path, FRIDAY, *(booked(n) for n in range(1, 13)))
    fake = mysys({})

    assert book_run() == 0

    lines = stdout_of(capsys)
    assert rechecked(fake) == [f"tsk_2000{n:02d}" for n in range(12, 2, -1)]
    assert "INFO  hold re-check: 10 checked, 0 not on hold" in lines
    assert "INFO  hold re-check cap reached: 2 tasks not checked" in lines


def test_a_read_that_fails_stops_the_run_before_any_note(mysys, capsys, tmp_path):
    seed(tmp_path, FRIDAY, booked(9))
    fake = mysys(
        {"300002": FakeNote("2600001B")},
        states={"tsk_200009": UnexpectedScreen("project search did not finish")},
    )

    assert book_run() == 1

    lines = stdout_of(capsys)
    assert [kind for kind, _ in alerts_of(lines)] == ["UNEXPECTED_SCREEN"]
    assert "open_note_pool" not in fake.calls
    assert not [c for c in fake.calls if "300002" in c]


def test_a_test_run_never_rechecks_a_live_booking(mysys, capsys, tmp_path):
    seed(tmp_path, FRIDAY, booked(8), site="live")
    seed(tmp_path, FRIDAY, booked(9))
    fake = mysys({})

    assert book_run() == 0

    lines = stdout_of(capsys)
    assert rechecked(fake) == ["tsk_200009"]
    assert "INFO  hold re-check: 1 checked, 0 not on hold" in lines


def test_no_booking_in_the_trace_rechecks_nothing_and_prints_nothing(
    mysys, capsys, tmp_path
):
    seed(tmp_path, THURSDAY, booked(9))  # too old
    fake = mysys({})

    assert book_run() == 0

    lines = stdout_of(capsys)
    assert rechecked(fake) == []
    assert not [x for x in lines if "hold re-check" in x]
    assert "reload_home" not in fake.calls


def test_the_trace_has_each_recheck_under_its_note_and_the_reads_under_none(
    mysys, capsys, tmp_path
):
    seed(tmp_path, FRIDAY, booked(8), booked(9))
    mysys({}, states={"tsk_200008": "not_on_hold"})

    assert book_run() == 0

    stdout_of(capsys)
    events = events_of(tmp_path)
    checks = [
        (e["note_id"], e["step"], e["outcome"])
        for e in events
        if e["name"] == "hold_check"
    ]
    assert checks == [("300009", "0", "pass"), ("300008", "0", "fail")]
    reads = [e for e in events if e["name"] == "search_project"]
    assert len(reads) == 2
    assert all(e["note_id"] is None and e["step"] == "0" for e in reads)


# --- reading the task's row (screen map rows 07, 10, 12) -------------------------


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


TASKS = [
    # (task, header buttons, Status cell)
    ("tsk_200001", "<button>Undo Cancellation</button>", "Cancelled"),
    (
        "tsk_200002",
        "<button>Cancel</button><button>Un-Hold</button>",
        "On-hold Notes: ON HOLD UNTIL CALL UP",
    ),
    ("tsk_200003", "<button>Cancel</button><button>Hold</button>", "New Project"),
    (
        "tsk_200004",
        "<button>Cancel</button><button>Hold</button>",
        "On-hold Notes: ON HOLD UNTIL CALL UP",
    ),
    (
        "tsk_200005",
        "<button>Cancel</button><button>Un-Hold</button>",
        "On-hold Notes: held by hand",
    ),
    ("tsk_200006", "<button>Cancel</button><button>Un-Hold</button>", "New Project"),
]


def project_page() -> str:
    rows = "".join(
        f"<tr><td><div><span>({task}) | Compaction Test</span><div>{buttons}</div></div></td></tr>"
        f"<tr><td>{AGENT}</td><td>Perth Scheduling</td><td>{status}</td></tr>"
        for task, buttons, status in TASKS
    )
    options = "".join(
        f"<option>({task}) [Compaction Test]</option>" for task, _, _ in TASKS
    )
    return f"""
<div><div>
  <h3>pln_10001 B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <select><option>-- Select Task --</option>{options}</select>
  <button>Create New Task</button>
  <table><tbody>{rows}</tbody></table>
</div><div><span title="Close">close</span></div></div>"""


@pytest.mark.parametrize(
    ("task", "state"),
    [
        ("tsk_200001", "cancelled"),
        ("tsk_200002", "on_hold"),
        ("tsk_200003", "not_on_hold"),  # the 11 Nov live revert: Hold, New Project
        ("tsk_200004", "not_on_hold"),  # On-hold text but no Un-Hold
        ("tsk_200005", "on_hold"),  # re-held by hand with another note
        ("tsk_200006", "not_on_hold"),  # Un-Hold but not On-hold
        ("tsk_200099", "not_found"),
    ],
)
def test_read_hold_reads_the_tasks_own_row(page, task, state):
    page.set_content(project_page())
    project = booking.project_window(page, "pln_10001")

    assert booking.read_hold(project, task) == state


# --- which project the re-check reads (driver.recheck_hold) ----------------------


BOOKED = trace.Booking(
    note_id="300001", pln="pln_10001", task_id="tsk_200001", internal_no="2600001B"
)


def lookup_of(*plns: str, internal_no: str = "2600001B") -> MySysLookup:
    return MySysLookup(
        search_rows=tuple(
            SearchRow(pln=pln, client_ref_no="2600001B", company="B1 Homes")
            for pln in plns
        ),
        more_pages=False,
        project_internal_no=internal_no if plns else "",
    )


@pytest.mark.parametrize(
    ("lookup", "window"),
    [
        (lookup_of("pln_10002"), "project"),  # the match is another project
        (lookup_of(), None),  # no match
        (lookup_of("pln_10001", "pln_10002"), None),  # ambiguous
        (lookup_of("pln_10001", internal_no="2600009B"), "project"),
    ],
)
def test_a_project_that_isnt_the_booked_one_is_not_found(monkeypatch, lookup, window):
    # Review finding 2. Step 8's reads (`_lookup_and_window`) are seam 2's;
    # here only what recheck_hold makes of their answer.
    monkeypatch.setattr(driver, "_lookup_and_window", lambda *a, **k: (lookup, window))
    read = []
    monkeypatch.setattr(booking, "read_hold", lambda *a: read.append(a) or "on_hold")

    state = driver.recheck_hold(None, None, "url", "user", "pw", BOOKED, "test")

    assert (state, read) == ("not_found", [])


def test_the_booked_project_is_read_for_the_task(monkeypatch):
    monkeypatch.setattr(
        driver,
        "_lookup_and_window",
        lambda *a, **k: (lookup_of("pln_10001"), "project"),
    )
    monkeypatch.setattr(booking, "read_hold", lambda project, task: f"{project} {task}")

    state = driver.recheck_hold(None, None, "url", "user", "pw", BOOKED, "test")

    assert state == "project tsk_200001"
