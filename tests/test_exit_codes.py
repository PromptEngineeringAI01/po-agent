"""Alerts and exit codes, end to end (task 5.1), offline.

Every path goes through `cli.main` and the real run loop (`core/run.py`),
the real booker and the real guard; only MySys is faked: seam 2's fake
(tests/seam2/test_run_loop_offline.py) stands in for the driver and the
booking steps. Values are fake.

- LoginFailed / ConfigError -> exit 2; UnexpectedScreen / WriteNotStarted /
  PartialWrite / GuardRefusal -> exit 1; AccuracyBreach -> exit 3; each with
  its ALERT line (SPEC.md -> Exit codes, Run output contract).
- A guard refusal raised by the real `act()` aborts the whole run.
- Any other exception -> ALERT UNEXPECTED_SCREEN with a fixed detail, exit 1,
  nothing on stderr; RUN_SUMMARY is always the last line.
- An error message holding PDF text and an address never reaches stdout or
  stderr.
"""

import importlib.util
import json
import tempfile
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.b1.models import Proceed
from po_agent.core import run
from po_agent.core.config import CONFIG_DIR, load_config
from po_agent.core.errors import (
    AccuracyBreach,
    LoginFailed,
    UnexpectedScreen,
    WriteNotStarted,
)
from po_agent.mysys import booking
from po_agent.mysys.guard import ActionGuard

_spec = importlib.util.spec_from_file_location(
    "seam2_fake_mysys_for_exit_codes",
    Path(__file__).parent / "seam2" / "test_run_loop_offline.py",
)
fake_mysys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_mysys)
FakeNote = fake_mysys.FakeNote
POOL = fake_mysys.POOL
AGENT = fake_mysys.AGENT

# Stand-ins for what a page or Playwright message can quote: PDF text and a
# job address. Neither may reach stdout or stderr.
PDF_TEXT = "Compaction test to slab area fake PDF line"
ADDRESS = "12 Fakeview Close, Faketown WA 6999"


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake secrets, temp, logs and config under tmp_path."""
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
    (config_dir / "test.toml").write_text(
        (CONFIG_DIR / "test.toml").read_text("utf-8"), "utf-8"
    )
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    # Inside the Perth run window, whatever day the tests run.
    monkeypatch.setattr(run.controls, "in_window", lambda window, at: True)
    yield monkeypatch
    keyring.set_keyring(previous)


@pytest.fixture
def mysys(env, tmp_path):
    def install(notes: dict[str, "FakeNote"]) -> "fake_mysys.FakeMySys":
        rows = tuple(fake_mysys.row(n, note.internal_no) for n, note in notes.items())
        fake = fake_mysys.FakeMySys(
            notes=notes,
            rows=rows,
            config_dir=tmp_path / "config",
            logs_dir=tmp_path / "logs",
        )
        for name in fake_mysys.DRIVER_NAMES + fake_mysys.BOOKER_DRIVER_NAMES:
            env.setattr(run.driver, name, getattr(fake, name), raising=False)
        for name in fake_mysys.BOOKING_NAMES:
            env.setattr(booking, name, getattr(fake, name))
        return fake

    return install


def two_notes(**changes) -> dict[str, "FakeNote"]:
    """300001 (a PROCEED unless `changes` break it), then 300002."""
    return {
        "300001": FakeNote("2600001B", **changes),
        "300002": FakeNote("2600002B", names=()),
    }


def book_run(*extra: str) -> int:
    return cli.main(["run", "--site", "test", *extra])


def lines_of(capsys) -> list[str]:
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
    assert sum(line.startswith("RUN_SUMMARY ") for line in lines) == 1
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def raised(tmp_path: Path, run_id: str) -> str:
    """The error type cli.py reported, from the --detailed-log traceback."""
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    (traceback,) = [e["traceback"] for e in events if e["event"] == "traceback"]
    return traceback.strip().splitlines()[-1].split(":")[0].rsplit(".", 1)[-1]


# --- every typed error through the real run path ----------------------------------


def _login_refused(guard, page, username, password):
    raise LoginFailed("login did not reach the app")


TYPED = [
    # (error type, how the fake MySys gets there, ALERT kind, step, exit code)
    ("LoginFailed", "login", "LOGIN_FAILED", None, 2),
    ("ConfigError", "no-secret", "CONFIG", None, 2),
    ("UnexpectedScreen", {"fail_at": "download"}, "UNEXPECTED_SCREEN", None, 1),
    # The task form doesn't read back as filled (W1): nothing submitted.
    ("WriteNotStarted", {"fail_at": "fill"}, "UNEXPECTED_SCREEN", "W1", 1),
    (
        "PartialWrite",
        {"fail_at": "confirm_hold", "fail_with": RuntimeError},
        "PARTIAL_WRITE",
        "W3",
        1,
    ),
    (
        "AccuracyBreach",
        {"fail_at": "detail", "fail_with": AccuracyBreach},
        "ACCURACY_BREACH",
        "W2",
        3,
    ),
]


@pytest.mark.parametrize(
    ("error", "how", "kind", "step", "exit_code"),
    TYPED,
    ids=[case[0] for case in TYPED],
)
def test_each_typed_error_ends_the_run_with_its_alert_and_exit_code(
    env, mysys, capsys, tmp_path, error, how, kind, step, exit_code
):
    fake = mysys(two_notes(**how) if isinstance(how, dict) else two_notes())
    if how == "login":
        env.setattr(run.driver, "login", _login_refused)
    if how == "no-secret":
        env.delenv("PO_AGENT_MYSYS_TEST_PASSWORD")

    code = book_run("--detailed-log")

    lines = lines_of(capsys)
    assert code == exit_code
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["step"]) == (kind, step)
    summary = summary_of(lines)
    assert summary["exit_code"] == exit_code
    assert raised(tmp_path, summary["run_id"]) == error
    assert not any(c.endswith(" 300002") for c in fake.calls)  # the run stopped


# --- a guard refusal from the real act() aborts the run -----------------------------


def test_a_guard_refusal_from_act_aborts_the_whole_run(env, mysys, capsys):
    fake = mysys(two_notes())
    take = fake.take_note

    def take_then_press_an_unknown_control(guard, window, agent, log, note_id):
        take(guard, window, agent, log, note_id)
        # Not allowlisted: the real guard refuses before touching the page.
        guard.act("press_discard", None, None)

    env.setattr(run.driver, "take_note", take_then_press_an_unknown_control)

    code = book_run()

    lines = lines_of(capsys)
    assert code == 1
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("GUARD_REFUSAL", "300001")
    assert "reason=UNKNOWN_ACTION" in alert["detail"]
    assert "submit 300001" not in fake.calls
    assert not any(c.endswith(" 300002") for c in fake.calls)
    # Before Submit: back to the pool in a fresh browser context.
    assert fake.notes["300001"].assignee == POOL
    assert summary_of(lines)["exit_code"] == 1


# --- anything else: a fixed detail, nothing quoted ----------------------------------


def _page_text_error(*args, **kwargs):
    raise RuntimeError(f"Timeout waiting for {PDF_TEXT} at {ADDRESS}")


WHERE = [
    # (the fake MySys call that crashes, step on the ALERT)
    ("read_note_pool", None),  # before any Note
    ("download_pdf", None),  # the agent holds the Note
    ("confirm_hold", "W3"),  # after Submit
]


@pytest.mark.parametrize(("where", "step"), WHERE, ids=[w for w, _ in WHERE])
@pytest.mark.parametrize("detailed_log", [False, True], ids=["plain", "detailed-log"])
def test_any_other_exception_is_unexpected_or_partial_with_nothing_quoted(
    env, mysys, capsys, where, step, detailed_log
):
    mysys(two_notes())
    target = booking if where == "confirm_hold" else run.driver
    env.setattr(target, where, _page_text_error)

    code = book_run(*(["--detailed-log"] if detailed_log else []))

    captured = capsys.readouterr()
    assert captured.err == ""
    for quoted in (PDF_TEXT, ADDRESS, "Fakeview", "Timeout"):
        assert quoted not in captured.out
    lines = captured.out.splitlines()
    assert code == 1
    ((kind, alert),) = alerts_of(lines)
    assert kind == ("PARTIAL_WRITE" if step else "UNEXPECTED_SCREEN")
    assert alert["step"] == step
    summary = summary_of(lines)
    assert summary["exit_code"] == 1


def test_an_address_passed_as_an_identifier_is_redacted(env, mysys, capsys):
    fake = mysys(two_notes())

    def lookup_fails(*args):
        raise UnexpectedScreen("project not found", pln=ADDRESS, field=PDF_TEXT)

    env.setattr(run.driver, "project_lookup", lookup_fails)

    assert book_run() == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Fakeview" not in captured.out and "slab" not in captured.out
    ((kind, alert),) = alerts_of(captured.out.splitlines())
    assert kind == "UNEXPECTED_SCREEN"
    assert "pln=<redacted>" in alert["detail"]
    assert fake.notes["300001"].assignee == POOL
    assert summary_of(captured.out.splitlines())["exit_code"] == 1


def test_run_summary_is_last_even_when_the_crash_hits_the_cleanup(env, mysys, capsys):
    # The download crashes, then the return in a fresh context crashes too,
    # then closing the browser crashes: still one ALERT, then RUN_SUMMARY.
    fake = mysys(two_notes(fail_at="download", fail_with=RuntimeError))
    fake.fail_return = True
    fake.close_fails = True

    code = book_run()

    lines = lines_of(capsys)
    assert code == 1
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    assert "not returned to the pool" in alert["detail"]
    assert summary_of(lines)["exit_code"] == 1


# --- M4 security pass Nits (5 Nov 2026) ---------------------------------------------

CTRL_C = [
    # (the fake MySys call Ctrl+C hits, ALERT kind, step, partial)
    ("fill", "UNEXPECTED_SCREEN", None, 0),  # W1: before the Submit click
    ("new_task", "PARTIAL_WRITE", "W2", 1),
    ("confirm_hold", "PARTIAL_WRITE", "W3", 1),
    ("gone", "PARTIAL_WRITE", "W5", 1),
]


@pytest.mark.parametrize(
    ("where", "kind", "step", "partial"), CTRL_C, ids=[c[0] for c in CTRL_C]
)
def test_ctrl_c_from_the_submit_click_on_is_a_partial_write(
    env, mysys, capsys, where, kind, step, partial
):
    # Nit 2: a KeyboardInterrupt (not an Exception) after Submit is reported
    # like any other error there; before Submit it stays a stop with no
    # return attempt.
    fake = mysys(two_notes(fail_at=where, fail_with=KeyboardInterrupt))

    code = book_run()

    lines = lines_of(capsys)
    assert code == 1
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["note_id"], alert["step"]) == (kind, "300001", step)
    summary = summary_of(lines)
    assert (summary["partial"], summary["exit_code"]) == (partial, 1)
    assert fake.notes["300001"].assignee == AGENT  # never returned
    assert not any(c.endswith(" 300002") for c in fake.calls)


def test_book_refuses_a_decision_for_another_note_before_w1(env, mysys, tmp_path):
    # Nit 5: the run loop passes the Note it holds, not the decision's own
    # Note ID, so a decision for another Note never reaches W1.
    fake = mysys(two_notes())
    config_dir = tmp_path / "config"
    other = Proceed(
        note_id="300002",
        internal_no="2600002B",
        pln="pln_10002",
        po_number="2600002B/048",
        email_body="fake body",
        pdf_file_name="2600002B_048_1.pdf",
        pdf_bytes=b"%PDF-fake",
        existing_task_nos=(),
    )

    with pytest.raises(WriteNotStarted) as error:
        run._book(
            ActionGuard(),
            fake_mysys.FakePage(fake.calls),
            load_config("test", config_dir),
            ("https://fake.test", "fake-user", "fake-password"),
            other,
            config_dir,
            note_id="300001",
        )

    assert error.value.step == "W1"
    assert fake.calls == []  # nothing read or written in MySys
