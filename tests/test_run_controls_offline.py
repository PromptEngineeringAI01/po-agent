"""The run controls (task 3.5): kill switch, Perth window, run cap and
`before_write`, offline.

Not `testsite`: the driver is seam 2's fake MySys (tests/seam2/
test_run_loop_offline.py), which records every call, so "no browser
launched" and "no MySys contact" mean it recorded nothing. The clock is a
fake patched in as `controls.now`. Values are fake.

- `enabled = false` -> INFO + RUN_SUMMARY, exit 0, no browser launched.
- Outside Mon-Fri 07:00-18:00 Australia/Perth -> exit 0, no MySys contact,
  for `run --decide-only`; `spike` ignores the window.
- The cap (Notes and minutes) is checked before each Note; a Note in
  progress is finished.
- `before_write(note_id, step)` re-reads `enabled` before every W step and
  calls the assignee check only before W1 and W4 (D7). Disabled before W1 or
  W2 -> KillSwitch (the run returns the Note in a fresh context, exit 0);
  from W3 on -> PartialWrite.
"""

import importlib.util
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.core import controls, run
from po_agent.core.config import CONFIG_DIR, load_config
from po_agent.core.errors import ConfigError, PartialWrite

_spec = importlib.util.spec_from_file_location(
    "seam2_fake_mysys_for_controls",
    Path(__file__).parent / "seam2" / "test_run_loop_offline.py",
)
fake_mysys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_mysys)
FakeNote = fake_mysys.FakeNote
POOL = fake_mysys.POOL

# Australia/Perth is UTC+8 all year (no daylight saving).
MONDAY_10_PERTH = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
SATURDAY_10_PERTH = datetime(2026, 11, 7, 2, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def _write_config(config_dir: Path, **changes: str) -> None:
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    for old, new in changes.items():
        assert old in toml
        toml = toml.replace(old, new)
    (config_dir / "test.toml").write_text(toml, "utf-8")


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake secrets, temp, logs and config under tmp_path; the clock at
    Monday 10:00 Perth unless a test moves it."""
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
    _write_config(config_dir)
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    clock = FakeClock(MONDAY_10_PERTH)
    monkeypatch.setattr(controls, "now", clock.now)
    yield monkeypatch, config_dir, clock
    keyring.set_keyring(previous)


@pytest.fixture
def mysys(env):
    monkeypatch, _, _ = env

    def install(notes: dict[str, FakeNote]) -> "fake_mysys.FakeMySys":
        rows = tuple(fake_mysys.row(n, note.internal_no) for n, note in notes.items())
        fake = fake_mysys.FakeMySys(notes=notes, rows=rows)
        for name in fake_mysys.DRIVER_NAMES:
            monkeypatch.setattr(run.driver, name, getattr(fake, name), raising=False)
        return fake

    return install


def lines_of(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


# --- kill switch at run start ---------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--site", "test", "--decide-only"],
        ["spike", "--site", "test"],
        ["demo", "--site", "test", "--until-check"],
    ],
    ids=["decide-only", "spike", "demo"],
)
def test_kill_switch_off_exits_0_before_any_browser(env, mysys, capsys, argv):
    _, config_dir, _ = env
    _write_config(config_dir, **{"enabled = true": "enabled = false"})
    fake = mysys({"300001": FakeNote("2600001B")})

    code = cli.main(argv)

    lines = lines_of(capsys)
    assert code == 0
    assert fake.calls == []  # no browser launched, no login
    assert "INFO  kill switch on: run not started" in lines
    assert not [x for x in lines if x.startswith("ALERT")]
    assert summary_of(lines)["exit_code"] == 0


# --- Perth window ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("at", "inside"),
    [
        (datetime(2026, 11, 1, 22, 59, tzinfo=UTC), False),  # Mon 06:59 Perth
        (datetime(2026, 11, 1, 23, 0, tzinfo=UTC), True),  # Mon 07:00 Perth
        (datetime(2026, 11, 6, 9, 59, tzinfo=UTC), True),  # Fri 17:59 Perth
        (datetime(2026, 11, 6, 10, 0, tzinfo=UTC), False),  # Fri 18:00 Perth
        (SATURDAY_10_PERTH, False),
    ],
    ids=["mon-0659", "mon-0700", "fri-1759", "fri-1800", "sat-1000"],
)
def test_the_run_window_is_mon_to_fri_7_to_18_perth(at, inside):
    window = load_config("test").run_window

    assert controls.in_window(window, at) is inside


def test_decide_only_outside_the_window_exits_0_without_contacting_mysys(
    env, mysys, capsys
):
    _, _, clock = env
    clock.at = SATURDAY_10_PERTH
    fake = mysys({"300001": FakeNote("2600001B")})

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 0
    assert fake.calls == []
    assert "INFO  outside the run window: run not started" in lines
    assert summary_of(lines)["exit_code"] == 0


def test_spike_ignores_the_window(env, mysys, capsys):
    _, _, clock = env
    clock.at = SATURDAY_10_PERTH
    fake = mysys({"300001": FakeNote("2600001B")})

    code = cli.main(["spike", "--site", "test"])

    assert code == 0
    assert "login" in fake.calls


# --- run cap ----------------------------------------------------------------------


def test_the_time_cap_stops_before_a_new_note_and_finishes_the_one_in_progress(
    env, mysys, capsys
):
    # max_run_minutes = 12; each Note takes 5 minutes. Notes start at 0, 5
    # and 10 minutes; the third ends at 15, past the cap, and is finished.
    # The fourth would start at 15: never opened.
    monkeypatch, _, clock = env
    fake = mysys({f"30000{i}": FakeNote(f"260000{i}B", names=()) for i in range(1, 5)})
    take = fake.take_note

    def slow_take(*args):
        clock.at += timedelta(minutes=5)
        take(*args)

    monkeypatch.setattr(run.driver, "take_note", slow_take)

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 0
    assert [n["note_id"] for n in notes_of(lines)] == ["300001", "300002", "300003"]
    assert not [c for c in fake.calls if "300004" in c]
    assert all(v.assignee == POOL for v in fake.notes.values())
    assert "INFO  run cap reached: 1 notes left for the next run" in lines
    assert summary_of(lines)["exit_code"] == 0


def test_the_note_cap_leaves_the_rest_for_the_next_run(env, mysys, capsys):
    _, config_dir, _ = env
    _write_config(config_dir, **{"max_notes_per_run = 10": "max_notes_per_run = 2"})
    fake = mysys({f"30000{i}": FakeNote(f"260000{i}B", names=()) for i in range(1, 5)})

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 0
    assert [n["note_id"] for n in notes_of(lines)] == ["300001", "300002"]
    assert not [c for c in fake.calls if "300003" in c or "300004" in c]
    assert "INFO  run cap reached: 2 notes left for the next run" in lines


# --- kill switch mid-run ------------------------------------------------------------


def test_a_kill_switch_mid_note_returns_it_in_a_fresh_context_and_exits_0(
    env, mysys, capsys
):
    # The booker's before_write raises KillSwitch before W1 or W2; here the
    # fake MySys raises it mid-Note in its place.
    fake = mysys(
        {
            "300001": FakeNote(
                "2600001B", fail_at="download", fail_with=controls.KillSwitch
            ),
            "300002": FakeNote("2600002B"),
        }
    )

    code = cli.main(["run", "--site", "test", "--decide-only"])

    lines = lines_of(capsys)
    assert code == 0
    after = fake.calls[fake.calls.index("closed") :]
    assert after == [
        "closed",
        "open_browser",
        "find_again 300001",
        "assignee 300001",
        "return 300001",
        "closed",
    ]
    assert fake.notes["300001"].assignee == POOL
    assert not [c for c in fake.calls if "300002" in c]
    assert "INFO  kill switch on: run stopped" in lines
    assert not [x for x in lines if x.startswith("ALERT")]
    assert summary_of(lines)["exit_code"] == 0


# --- before_write --------------------------------------------------------------------

STEPS = ("W1", "W2", "W3", "W4", "W5")


@pytest.fixture
def checks(env):
    _, config_dir, _ = env
    calls: list[tuple[str, str]] = []
    gate = controls.Controls(
        "test", config_dir, assignee_check=lambda n, s: calls.append((n, s))
    )
    return gate, calls, config_dir


def test_before_write_checks_the_assignee_only_before_w1_and_w4(checks):
    gate, calls, _ = checks

    for step in STEPS:
        gate.before_write("300001", step)

    assert calls == [("300001", "W1"), ("300001", "W4")]


@pytest.mark.parametrize("step", ["W1", "W2"])
def test_before_write_kill_switch_before_anything_is_submitted(checks, step):
    gate, calls, config_dir = checks
    gate.before_write("300001", "W1")  # read while enabled
    _write_config(config_dir, **{"enabled = true": "enabled = false"})

    with pytest.raises(controls.KillSwitch):
        gate.before_write("300001", step)


@pytest.mark.parametrize("step", ["W3", "W4", "W5"])
def test_before_write_kill_switch_after_a_submit_is_a_partial_write(checks, step):
    gate, calls, config_dir = checks
    gate.before_write("300001", "W1")
    _write_config(config_dir, **{"enabled = true": "enabled = false"})

    with pytest.raises(PartialWrite) as raised:
        gate.before_write("300001", step)

    assert (raised.value.note_id, raised.value.step) == ("300001", step)
    assert calls == [("300001", "W1")]  # the switch is read first: no W4 check


@pytest.mark.parametrize(("step", "error"), [("W1", ConfigError), ("W3", PartialWrite)])
def test_before_write_with_an_unreadable_config_stops(checks, step, error):
    gate, _, config_dir = checks
    (config_dir / "test.toml").write_text("enabled = ", "utf-8")

    with pytest.raises(error):
        gate.before_write("300001", step)
