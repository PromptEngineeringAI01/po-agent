"""The safe trace (task 7.3): core/trace.py, offline.

Each event has only run_id, ts, note_id, step, name (a check or the guard's
mapped control name), outcome (pass, fail, a skip reason or an error type)
and duration_ms. A value outside its closed type is dropped (None) when the
event is written. One file per day, <trace_dir>/<YYYY-MM-DD>.jsonl (the
date in the run window's time zone); files older than 90 days are deleted at
run start. The trace is on only when `trace_dir` is set in config and its
parent folder exists (the Mac Mini wrapper makes ~/Library/Logs/po-agent);
it never changes the run output.

The driver is seam 2's fake MySys (tests/seam2/test_run_loop_offline.py);
the decision engine and both PDF readers run for real on its fake PDF. The
clock is a fake patched in as `controls.now`. Values are fake.
"""

import importlib.util
import json
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring
from pydantic import ValidationError

from po_agent import cli
from po_agent.core import controls, run, trace
from po_agent.core.config import CONFIG_DIR, load_config
from po_agent.mysys import booking

_spec = importlib.util.spec_from_file_location(
    "seam2_fake_mysys_for_trace",
    Path(__file__).parent / "seam2" / "test_run_loop_offline.py",
)
fake_mysys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_mysys)
FakeNote = fake_mysys.FakeNote
CLEAN = fake_mysys.CLEAN

KEYS = {"run_id", "ts", "note_id", "step", "name", "outcome", "duration_ms"}
MONDAY_10_PERTH = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
TODAY = "2026-11-02"  # Perth date of MONDAY_10_PERTH
ADDRESS = CLEAN.lookup.address
BODY = CLEAN.note.body
# The fake PDF's text lines that aren't a bare identifier.
PDF_LINES = [line for line in CLEAN.pypdf_text.splitlines() if " " in line.strip()]


class LeakyError(Exception):
    """A MySys-side error whose message quotes page values."""

    def __init__(self, _detail: str) -> None:
        super().__init__(f"{ADDRESS} | {BODY} | {PDF_LINES[0]}")


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
    write_config(config_dir, tmp_path / "po-agent" / "trace")
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(controls, "now", lambda: MONDAY_10_PERTH)
    yield monkeypatch
    keyring.set_keyring(previous)


def write_config(config_dir: Path, trace_dir: Path, **changes: str) -> None:
    lines = (CONFIG_DIR / "test.toml").read_text("utf-8").splitlines()
    toml = "\n".join(x for x in lines if not x.startswith("trace_dir"))
    for old, new in changes.items():
        assert old in toml
        toml = toml.replace(old, new)
    toml += f'\ntrace_dir = "{trace_dir.as_posix()}"\n'
    (config_dir / "test.toml").write_text(toml, "utf-8")


@pytest.fixture
def mysys(env, tmp_path):
    def install(notes: dict, **kwargs):
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
        return fake

    return install


def stdout_of(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


def trace_file(tmp_path) -> Path:
    return tmp_path / "po-agent" / "trace" / f"{TODAY}.jsonl"


def events_of(tmp_path) -> list[dict]:
    text = trace_file(tmp_path).read_text("utf-8")
    return [json.loads(line) for line in text.splitlines()]


def named(events: list[dict]) -> list[tuple]:
    return [(e["note_id"], e["step"], e["name"], e["outcome"]) for e in events]


# --- what an event holds ---------------------------------------------------------


def test_a_run_traces_only_allowlisted_fields_and_no_page_value(
    mysys, capsys, tmp_path
):
    mysys(
        {
            "300001": FakeNote("2600001B"),  # PROCEED -> DECIDE_ONLY
            # The error's message quotes the address, the Note body and PDF
            # text; the Note is taken, so it is returned, then the run stops.
            "300002": FakeNote("2600002B", fail_at="names", fail_with=LeakyError),
        }
    )

    # --detailed-log too: its traceback (which quotes the message) stays
    # out of the trace.
    code = cli.main(["run", "--site", "test", "--decide-only", "--detailed-log"])

    run_id = json.loads(stdout_of(capsys)[-1].removeprefix("RUN_SUMMARY "))["run_id"]
    assert code == 1
    raw = trace_file(tmp_path).read_text("utf-8")
    for value in (ADDRESS, BODY, *PDF_LINES, "fake-user", "fake-password"):
        assert value not in raw
    assert "Traceback" not in raw
    events = events_of(tmp_path)
    assert all(set(e) == KEYS for e in events)
    assert {e["run_id"] for e in events} == {run_id}
    assert all(e["ts"].endswith("+00:00") for e in events)
    assert all(type(e["duration_ms"]) is int and e["duration_ms"] >= 0 for e in events)
    steps = named(events)
    assert ("300001", "2", "assignee_check", "pass") in steps
    assert ("300001", "decide", "decision", "DECIDE_ONLY") in steps
    assert ("300002", None, "error", "LeakyError") in steps
    # The run's last event: how it ended, as reported.
    assert steps[-1] == ("300002", None, "run_end", "UnexpectedScreen")


def test_a_partial_write_is_traced_with_its_step(mysys, capsys, tmp_path):
    mysys(
        {"300001": FakeNote("2600001B", fail_at="confirm_hold", fail_with=RuntimeError)}
    )

    assert cli.main(["run", "--site", "test"]) == 1

    stdout_of(capsys)
    steps = named(events_of(tmp_path))
    assert ("300001", "W3", "error", "PartialWrite") in steps
    assert steps[-1] == ("300001", "W3", "run_end", "PartialWrite")


def test_a_run_that_finishes_ends_with_run_end_pass(mysys, capsys, tmp_path):
    mysys({})

    assert cli.main(["run", "--site", "test", "--decide-only"]) == 0

    stdout_of(capsys)
    assert named(events_of(tmp_path))[-1] == (None, None, "run_end", "pass")


def test_values_outside_the_closed_type_are_dropped_when_written(tmp_path):
    log = trace.Trace("20261102T010203Z-abcd")
    log.start(tmp_path, date(2026, 11, 2))

    log.event(note_id=ADDRESS, step=BODY, name=PDF_LINES[0], outcome=ADDRESS)
    log.event(note_id="300001", step="W3", name="confirm_hold", outcome="fail")

    lines = (tmp_path / "2026-11-02.jsonl").read_text("utf-8").splitlines()
    first, second = (json.loads(line) for line in lines)
    assert (first["note_id"], first["step"], first["name"], first["outcome"]) == (
        None,
        None,
        None,
        None,
    )
    assert (second["note_id"], second["step"], second["name"], second["outcome"]) == (
        "300001",
        "W3",
        "confirm_hold",
        "fail",
    )
    fields = {k: v for k, v in second.items() if k != "ts"}
    with pytest.raises(ValidationError):
        trace.TraceEvent(**fields, ts=second["ts"], detail=ADDRESS)


# --- where it goes, and what it doesn't change -----------------------------------


def test_the_mac_mini_trace_folder_is_in_the_test_config():
    assert load_config("test", CONFIG_DIR).trace_dir == "~/Library/Logs/po-agent/trace"


def test_no_trace_without_the_parent_folder_and_the_run_output_is_the_same(
    mysys, capsys, tmp_path
):
    notes = {"300001": FakeNote("2600001B"), "300002": FakeNote("2600002B", names=())}

    def outputs() -> list[str]:
        mysys({k: FakeNote(v.internal_no, names=v.names) for k, v in notes.items()})
        cli.main(["run", "--site", "test", "--decide-only"])
        lines = stdout_of(capsys)
        summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
        summary.pop("run_id")
        summary.pop("duration_s")
        return [*lines[:-1], json.dumps(summary)]

    traced = outputs()
    assert trace_file(tmp_path).exists()
    # The laptop and CI: the trace folder's parent isn't there.
    missing = tmp_path / "missing" / "trace"
    write_config(tmp_path / "config", missing)
    untraced = outputs()

    assert not (tmp_path / "missing").exists()
    assert traced == untraced


def test_files_older_than_90_days_are_deleted_at_run_start(mysys, capsys, tmp_path):
    folder = tmp_path / "po-agent" / "trace"
    folder.mkdir()
    kept = folder / "2026-08-04.jsonl"  # 90 days before 2026-11-02
    old = folder / "2026-08-03.jsonl"  # 91 days
    other = folder / "notes.txt"  # not a trace file: left alone
    for path in (kept, old, other):
        path.write_text("{}\n", "utf-8")
    mysys({})

    assert cli.main(["run", "--site", "test", "--decide-only"]) == 0

    stdout_of(capsys)
    assert kept.exists() and other.exists()
    assert not old.exists()
    assert trace_file(tmp_path).exists()
