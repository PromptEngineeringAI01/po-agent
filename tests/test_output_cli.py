"""Tests for core/output.py and the po-agent CLI (task 1.6).

The stdout contract is SPEC.md -> Code style. Nothing here opens a browser:
the CLI's mode entry point (`cli.start`) is replaced where a test gets past
config and secrets. Page text is faked with a made-up street.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring
from pydantic import ValidationError

from po_agent import cli
from po_agent.core import output
from po_agent.core.errors import (
    AccuracyBreach,
    ConfigError,
    GuardRefusal,
    LoginFailed,
    PartialWrite,
    UnexpectedScreen,
    WriteNotStarted,
)

ROOT = Path(__file__).resolve().parent.parent
SECRET_NAMES = ("anthropic_api_key", "mysys_test_username", "mysys_test_password")
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{4}")
PAGE_TEXT = "12 Example Close"  # stands in for an address in a Playwright message
NOTE_FIELDS = {
    "note_id",
    "outcome",
    "reason",
    "field",
    "po_number",
    "pln",
    "task_id",
    "tokens_in",
    "tokens_out",
    "cost_aud",
}
ALERT_FIELDS = {"note_id", "step", "detail"}
SUMMARY_FIELDS = {
    "run_id",
    "site",
    "mode",
    "seen",
    "eligible",
    "booked",
    "skipped",
    "partial",
    "duration_s",
    "tokens_in",
    "tokens_out",
    "cost_aud",
    "exit_code",
}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """No secrets anywhere, temp and logs under tmp_path."""
    for name in SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    yield monkeypatch
    keyring.set_keyring(previous)


def set_secrets(monkeypatch, names=SECRET_NAMES):
    for name in names:
        monkeypatch.setenv(f"PO_AGENT_{name.upper()}", f"fake-{name}")


@pytest.fixture
def started(env):
    """Replaces cli.start; records each call and returns exit code 0."""
    calls = []

    def fake_start(*args):
        calls.append(args)
        return 0

    env.setattr(cli, "start", fake_start)
    return calls


def lines(captured) -> list[str]:
    return captured.out.splitlines()


def summary_of(captured) -> dict:
    last = lines(captured)[-1]
    assert last.startswith("RUN_SUMMARY {")
    return json.loads(last.removeprefix("RUN_SUMMARY "))


def alert_of(captured) -> tuple[str, dict]:
    alerts = [line for line in lines(captured) if line.startswith("ALERT ")]
    assert len(alerts) == 1
    _, kind, body = alerts[0].split(" ", 2)
    return kind, json.loads(body)


# --- output.py: the line formats --------------------------------------------


def test_info_prints_a_fixed_message(capsys):
    output.info("config loaded")

    assert capsys.readouterr().out == "INFO  config loaded\n"


def test_info_refuses_a_message_that_is_not_a_template(capsys):
    with pytest.raises(ValueError):
        output.info(f"reading {PAGE_TEXT}")

    assert capsys.readouterr().out == ""


def test_note_line_matches_the_contract(capsys):
    output.note(
        output.Note(
            note_id="n123",
            outcome="skipped",
            reason="ADDRESS_MISMATCH",
            field="street",
            po_number="2609034B/048",
            pln="pln_66938",
        )
    )

    assert capsys.readouterr().out == (
        'NOTE  {"note_id": "n123", "outcome": "skipped", "reason": "ADDRESS_MISMATCH",'
        ' "field": "street", "po_number": "2609034B/048", "pln": "pln_66938",'
        ' "task_id": null, "tokens_in": 0, "tokens_out": 0, "cost_aud": 0.0}\n'
    )


def test_alert_line_matches_the_contract(capsys):
    output.alert("PARTIAL_WRITE", output.Alert(note_id="n1", step="W3", detail="x"))

    assert capsys.readouterr().out == (
        'ALERT PARTIAL_WRITE {"note_id": "n1", "step": "W3", "detail": "x"}\n'
    )


def test_run_summary_line_has_exactly_the_contract_fields(capsys):
    output.run_summary(output.RunSummary(run_id="20261016T013507Z-3fa2"))

    line = capsys.readouterr().out
    assert line.startswith("RUN_SUMMARY {")
    assert set(json.loads(line.removeprefix("RUN_SUMMARY "))) == SUMMARY_FIELDS


@pytest.mark.parametrize(
    "model, fields",
    [
        (output.Note, NOTE_FIELDS),
        (output.Alert, ALERT_FIELDS),
        (output.RunSummary, SUMMARY_FIELDS),
    ],
)
def test_models_have_exactly_the_contract_fields(model, fields):
    assert set(model.model_fields) == fields


@pytest.mark.parametrize(
    "model, values",
    [
        (output.Note, {"note_id": "n1", "outcome": "booked", "address": "x"}),
        (output.Alert, {"detail": "x", "body": "x"}),
        (output.RunSummary, {"run_id": "r", "note_text": "x"}),
    ],
)
def test_models_refuse_unknown_fields(model, values):
    with pytest.raises(ValidationError):
        model(**values)


def test_note_outcome_must_be_a_contract_value():
    with pytest.raises(ValidationError):
        output.Note(note_id="n1", outcome="done")


def test_note_identifiers_that_are_not_identifiers_are_redacted(capsys):
    output.note(output.Note(note_id="n1", outcome="booked", po_number=PAGE_TEXT))

    out = capsys.readouterr().out
    assert PAGE_TEXT not in out
    assert '"po_number": "<redacted>"' in out


# --- run_id ------------------------------------------------------------------


def test_run_id_is_utc_start_time_plus_4_hex():
    first, second = cli.new_run_id(), cli.new_run_id()

    assert RUN_ID.fullmatch(first)
    assert RUN_ID.fullmatch(second)


# --- exit 2: command line, site, run mode, config, secrets --------------------


def test_spike_without_secrets_prints_alert_config_and_summary(env, started, capsys):
    code = cli.main(["spike", "--site", "test"])

    captured = capsys.readouterr()
    assert code == 2
    assert len(lines(captured)) == 2
    kind, alert = alert_of(captured)
    assert kind == "CONFIG"
    assert "mysys_test_username" in alert["detail"]
    summary = summary_of(captured)
    assert summary["exit_code"] == 2
    assert summary["mode"] == "spike"
    assert summary["site"] == "test"
    assert RUN_ID.fullmatch(summary["run_id"])
    assert captured.err == ""
    assert started == []


def test_decide_only_also_needs_the_claude_key(env, started, capsys):
    set_secrets(env, ("mysys_test_username", "mysys_test_password"))

    code = cli.main(["run", "--site", "test", "--decide-only"])

    captured = capsys.readouterr()
    assert code == 2
    assert "anthropic_api_key" in alert_of(captured)[1]["detail"]
    assert started == []


def test_spike_does_not_need_the_claude_key(env, started, capsys):
    set_secrets(env, ("mysys_test_username", "mysys_test_password"))

    assert cli.main(["spike", "--site", "test"]) == 0
    assert len(started) == 1


def test_run_without_decide_only_refuses_until_4_5(env, started, capsys):
    set_secrets(env)

    code = cli.main(["run", "--site", "test"])

    captured = capsys.readouterr()
    assert code == 2
    kind, alert = alert_of(captured)
    assert kind == "CONFIG"
    assert alert["detail"] == "run mode not built yet"
    assert summary_of(captured)["mode"] == "run"
    assert started == []


def test_a_site_other_than_test_exits_2(env, started, capsys):
    set_secrets(env)

    code = cli.main(["spike", "--site", "live"])

    captured = capsys.readouterr()
    assert code == 2
    assert alert_of(captured)[0] == "CONFIG"
    assert summary_of(captured)["site"] is None
    assert started == []


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["book", "--site", "test"],
        ["spike"],
        ["spike", "--site", "test", "--slow-mo", "abc"],
        ["spike", "--site", "test", "--decide-only"],
        ["spike", "--site", "test", "--help"],
        ["spike", "--site", "test", "--sit", "x"],
    ],
)
def test_a_bad_command_line_exits_2_with_nothing_on_stderr(env, started, capsys, argv):
    code = cli.main(argv)

    captured = capsys.readouterr()
    assert code == 2
    assert alert_of(captured)[0] == "CONFIG"
    assert summary_of(captured)["exit_code"] == 2
    assert captured.err == ""
    assert started == []


def test_a_bad_config_file_exits_2(env, started, capsys, tmp_path):
    set_secrets(env)
    env.setattr(cli, "CONFIG_DIR", tmp_path / "missing")

    code = cli.main(["spike", "--site", "test"])

    assert code == 2
    assert alert_of(capsys.readouterr())[0] == "CONFIG"
    assert started == []


# --- the happy path ------------------------------------------------------------


def test_options_reach_the_mode_and_summary_is_last(env, started, capsys):
    set_secrets(env)

    code = cli.main(
        ["run", "--site", "test", "--decide-only", "--headed", "--slow-mo", "500"]
    )

    captured = capsys.readouterr()
    assert code == 0
    (mode, config, credentials, options, summary), *_ = started
    assert mode == "decide-only"
    assert config.site == "test"
    assert set(credentials) == set(SECRET_NAMES)
    assert options.headed is True
    assert options.slow_mo == 500
    assert options.detailed_log is False
    assert summary.mode == "decide-only"
    summary = summary_of(captured)
    assert summary["exit_code"] == 0
    assert summary["mode"] == "decide-only"
    for name in SECRET_NAMES:
        assert f"fake-{name}" not in captured.out


def test_decide_only_not_built_yet_says_so_and_exits_0(env, capsys):
    set_secrets(env)
    message = "INFO  decide-only not built yet"

    code = cli.main(["run", "--site", "test", "--decide-only"])

    captured = capsys.readouterr()
    assert code == 0
    assert message in lines(captured)
    assert summary_of(captured)["exit_code"] == 0


# --- typed errors and the catch-all ----------------------------------------------


@pytest.mark.parametrize(
    "error, kind, code",
    [
        (PartialWrite("read-back failed", step="W3", note_id="n1"), "PARTIAL_WRITE", 1),
        (AccuracyBreach("wrong value written", note_id="n1"), "ACCURACY_BREACH", 3),
        (GuardRefusal("control not allowlisted", action="x"), "GUARD_REFUSAL", 1),
        (UnexpectedScreen("window not found"), "UNEXPECTED_SCREEN", 1),
        (WriteNotStarted("read-back failed", step="W1"), "UNEXPECTED_SCREEN", 1),
        (LoginFailed("login refused"), "LOGIN_FAILED", 2),
        (ConfigError("config file not readable"), "CONFIG", 2),
    ],
)
def test_typed_errors_map_to_their_alert_and_exit_code(env, capsys, error, kind, code):
    set_secrets(env)

    def fail(*args):
        raise error

    env.setattr(cli, "start", fail)

    assert cli.main(["spike", "--site", "test"]) == code
    captured = capsys.readouterr()
    alert_kind, alert = alert_of(captured)
    assert alert_kind == kind
    assert alert["note_id"] == error.note_id
    assert alert["step"] == error.step
    assert alert["detail"].startswith(error.detail)
    assert summary_of(captured)["exit_code"] == code
    assert captured.err == ""


def raise_page_text(*args):
    raise RuntimeError(f"Timeout waiting for {PAGE_TEXT}")


def test_an_unmapped_exception_is_unexpected_screen_with_a_fixed_detail(
    env, capsys, tmp_path
):
    set_secrets(env)
    env.setattr(cli, "start", raise_page_text)

    code = cli.main(["spike", "--site", "test"])

    captured = capsys.readouterr()
    assert code == 1
    kind, alert = alert_of(captured)
    assert kind == "UNEXPECTED_SCREEN"
    assert PAGE_TEXT not in captured.out
    assert captured.err == ""
    assert summary_of(captured)["exit_code"] == 1
    assert not (tmp_path / "logs").exists()


def test_detailed_log_writes_the_traceback_to_logs(env, capsys, tmp_path):
    set_secrets(env)
    env.setattr(cli, "start", raise_page_text)

    code = cli.main(["spike", "--site", "test", "--detailed-log"])

    captured = capsys.readouterr()
    assert code == 1
    run_id = summary_of(captured)["run_id"]
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert [event["event"] for event in events] == ["traceback"]
    assert events[0]["run_id"] == run_id
    assert "RuntimeError" in events[0]["traceback"]
    assert PAGE_TEXT not in captured.out
    assert captured.err == ""


def test_detailed_log_keeps_a_hidden_playwright_message_hidden(env, capsys, tmp_path):
    # The guard raises its typed error `from None` so the Playwright message
    # (which can quote page text) stays out of every traceback.
    set_secrets(env)

    def guard_failure(*args):
        try:
            raise RuntimeError(f"locator resolved to {PAGE_TEXT}")
        except RuntimeError:
            raise UnexpectedScreen("guard action failed", action="tick") from None

    env.setattr(cli, "start", guard_failure)

    assert cli.main(["spike", "--site", "test", "--detailed-log"]) == 1
    run_id = summary_of(capsys.readouterr())["run_id"]
    log = (tmp_path / "logs" / f"{run_id}.jsonl").read_text("utf-8")
    assert "UnexpectedScreen" in log
    assert PAGE_TEXT not in log


# --- download-dir sweep (D2) ----------------------------------------------------


def test_leftover_download_dirs_are_removed_before_the_mode_starts(env, capsys):
    set_secrets(env)
    temp = Path(tempfile.gettempdir())
    leftover = temp / "po-agent-dl-20261016T013507Z-3fa2"
    leftover.mkdir()
    (leftover / "trial.pdf").write_bytes(b"%PDF-fake")
    other = temp / "po-agent-other"
    other.mkdir()
    seen = []
    env.setattr(cli, "start", lambda *args: seen.append(leftover.exists()) or 0)

    assert cli.main(["spike", "--site", "test"]) == 0
    assert seen == [False]
    assert other.exists()


def test_leftover_download_dirs_are_removed_even_on_a_config_error(env, capsys):
    leftover = Path(tempfile.gettempdir()) / "po-agent-dl-old"
    leftover.mkdir()

    assert cli.main(["spike", "--site", "test"]) == 2
    assert not leftover.exists()


# --- the installed command, as the Mac Mini runs it --------------------------------


def test_the_command_with_no_secrets_exits_2_and_prints_two_lines(tmp_path):
    child_env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PO_AGENT_")
    }
    # No keyring entries (https://keyring.readthedocs.io/en/latest/,
    # "Configuring"); temp files under tmp_path.
    child_env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    for name in ("TMPDIR", "TEMP", "TMP"):
        child_env[name] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "po_agent.cli", "spike", "--site", "test"],
        capture_output=True,
        text=True,
        env=child_env,
        cwd=ROOT,
    )

    assert result.returncode == 2
    out = result.stdout.splitlines()
    assert len(out) == 2
    assert out[0].startswith("ALERT CONFIG {")
    assert out[1].startswith("RUN_SUMMARY {")
    assert json.loads(out[1].removeprefix("RUN_SUMMARY "))["exit_code"] == 2
    assert result.stderr == ""
