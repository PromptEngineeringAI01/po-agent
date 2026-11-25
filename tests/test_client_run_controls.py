"""Per-client run controls (task 9.5; SPEC.md -> Client 2: Summit Home, The
separate run; docs/decisions.md, 23 Nov 2026, separate run).

- Run lock: B1 keeps `state/run-<site>.lock`; Summit takes
  `state/run-<site>-summit.lock`. A B1 run and a Summit run on one site don't
  block each other (different MySys accounts); two Summit runs do. The
  start-of-run sweep of leftover download folders follows the lock: a run
  removes only its own client's folders, never the other client's, which may
  belong to a run going on now (decisions, 21 Nov 2026, run lock).
- Kill switch: a Summit run needs the site's `enabled` and the client file's
  `enabled`, at start and in every `before_write`; B1 reads only the site's.
- Caps: Summit's `max_notes_per_run` counts bookings and `max_peeks_per_run`
  Notes opened (both from the client file); `max_run_minutes` is the site's.
- The run's MySys account: Summit logs in with its own secret pair as
  "Agent 2 (Summit Homes)", so the stale-Note stop's My Notes is Agent 2's.
- RUN_SUMMARY names the client, B1's too; `run_id` stays its first key (the
  Mac Mini wrapper reads it from there).

Summit's modes are still refused before any secret, login or browser (9.3,
9.4); nothing here reads a real secret or contacts MySys. Values are fake;
expected values are written out from SPEC.md and the plan.
"""

import json
import re
import tempfile
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.core import controls, run, runlock, secrets
from po_agent.core.config import CONFIG_DIR, load_config, parse_client
from po_agent.core.errors import ConfigError, PartialWrite

MONDAY_10_PERTH = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
RUN_ID = "20261102T020000Z-abcd"
SUMMIT_RUN = ["run", "--site", "live", "--client", "summit"]
B1_LIVE_RUN = ["run", "--site", "live"]


# --- fixtures and helpers -------------------------------------------------------


@pytest.fixture
def env(monkeypatch, tmp_path):
    """No secret in the environment or keyring, temp, logs and the run lock's
    state folder under tmp_path; the clock at Monday 10:00 Perth."""
    for name in secrets.SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(controls, "now", lambda: MONDAY_10_PERTH)
    yield monkeypatch
    keyring.set_keyring(previous)


@pytest.fixture
def started(monkeypatch):
    calls = []

    def fake_start(*args, **kwargs):
        calls.append(args)
        return 0

    monkeypatch.setattr(cli, "start", fake_start)
    return calls


def with_enabled(text: str, enabled: bool) -> str:
    out = re.sub(r"(?m)^enabled = \w+", f"enabled = {str(enabled).lower()}", text)
    assert out.count("enabled = ") == text.count("enabled = ")
    return out


def config_dir(tmp_path: Path, *, site_on: bool, summit_on: bool) -> Path:
    """config/live.toml and config/clients/summit.toml as committed, with
    each `enabled` set; test.toml as committed."""
    folder = tmp_path / "config"
    (folder / "clients").mkdir(parents=True, exist_ok=True)
    for name in ("test.toml",):
        (folder / name).write_text((CONFIG_DIR / name).read_text("utf-8"), "utf-8")
    live = (CONFIG_DIR / "live.toml").read_text("utf-8")
    (folder / "live.toml").write_text(with_enabled(live, site_on), "utf-8")
    summit = (CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8")
    (folder / "clients" / "summit.toml").write_text(
        with_enabled(summit, summit_on), "utf-8"
    )
    return folder


def summit_profile(**changes):
    with open(CONFIG_DIR / "clients" / "summit.toml", "rb") as file:
        data = tomllib.load(file)
    data.update(changes)
    return parse_client(data)


def live_config(**changes):
    return load_config("live", CONFIG_DIR).model_copy(update=changes)


def run_cli(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    assert out.err == ""
    return code, out.out.splitlines()


def summary_of(lines):
    assert lines[-1].startswith("RUN_SUMMARY {")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def hold(tmp_path: Path, name: str) -> runlock.RunLock:
    return runlock.acquire(tmp_path / "state" / name)


LOCK_HELD = "INFO  run lock held: run not started"
NOT_BUILT = "mode not built for this client yet"


# --- the run lock ---------------------------------------------------------------


def test_two_summit_runs_on_one_site_block_each_other(env, started, capsys, tmp_path):
    other = hold(tmp_path, "run-live-summit.lock")
    try:
        code, lines = run_cli(capsys, SUMMIT_RUN)
    finally:
        other.release()

    assert code == 0
    assert LOCK_HELD in lines
    assert summary_of(lines)["exit_code"] == 0
    assert started == []


def test_a_b1_run_does_not_block_a_summit_run(env, started, capsys, tmp_path):
    b1 = hold(tmp_path, "run-live.lock")
    try:
        code, lines = run_cli(capsys, SUMMIT_RUN)
    finally:
        b1.release()

    # Past the lock: the run meets Summit's refusal (until 9.11-9.14).
    assert LOCK_HELD not in lines
    assert code == 2
    assert any(NOT_BUILT in line for line in lines if line.startswith("ALERT CONFIG"))
    assert started == []


def test_a_summit_run_does_not_block_a_b1_run(env, started, capsys, tmp_path):
    env.setattr(cli, "CONFIG_DIR", config_dir(tmp_path, site_on=False, summit_on=True))
    summit = hold(tmp_path, "run-live-summit.lock")
    try:
        code, lines = run_cli(capsys, B1_LIVE_RUN)
    finally:
        summit.release()

    # Past the lock: B1's live run stops at its kill switch.
    assert LOCK_HELD not in lines
    assert "INFO  kill switch on: run not started" in lines
    assert code == 0


def test_b1_keeps_its_lock_file(env, started, capsys, tmp_path):
    b1 = hold(tmp_path, "run-live.lock")
    try:
        code, lines = run_cli(capsys, B1_LIVE_RUN)
    finally:
        b1.release()

    assert code == 0
    assert LOCK_HELD in lines


# --- the download-folder sweep follows the lock ---------------------------------


def download_folders(tmp_path: Path) -> tuple[Path, Path]:
    b1 = tmp_path / "temp" / f"po-agent-dl-{RUN_ID}"
    summit = tmp_path / "temp" / f"po-agent-dl-summit-{RUN_ID}"
    b1.mkdir()
    summit.mkdir()
    return b1, summit


def test_each_client_s_download_folder_has_its_own_name():
    assert cli.download_dir("b1", RUN_ID).name == f"po-agent-dl-{RUN_ID}"
    assert cli.download_dir("summit", RUN_ID).name == f"po-agent-dl-summit-{RUN_ID}"


def test_a_b1_run_removes_b1_s_leftover_folder_and_leaves_summit_s(
    env, started, capsys, tmp_path
):
    env.setattr(cli, "CONFIG_DIR", config_dir(tmp_path, site_on=False, summit_on=True))
    b1, summit = download_folders(tmp_path)

    code, _ = run_cli(capsys, B1_LIVE_RUN)

    assert code == 0
    assert not b1.exists()
    assert summit.is_dir()


def test_summit_s_sweep_removes_only_summit_s_folders(env, tmp_path):
    b1, summit = download_folders(tmp_path)

    cli.sweep_download_dirs("summit")

    assert b1.is_dir()
    assert not summit.exists()


# --- the kill switch ------------------------------------------------------------


@pytest.mark.parametrize(
    ("site_on", "summit_on", "expected"),
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_a_summit_run_needs_both_switches_at_start(site_on, summit_on, expected):
    config = live_config(enabled=site_on)

    assert controls.run_enabled(config, summit_profile(enabled=summit_on)) is expected


@pytest.mark.parametrize("site_on", [True, False])
def test_a_b1_run_needs_only_the_site_switch_at_start(site_on):
    assert controls.run_enabled(live_config(enabled=site_on), None) is site_on


def summit_gate(folder: Path, client: str = "summit"):
    checked = []
    gate = controls.Controls(
        "live",
        folder,
        lambda note_id, step: checked.append((note_id, step)),
        client=client,
    )
    return gate, checked


@pytest.mark.parametrize(("site_on", "summit_on"), [(True, False), (False, True)])
def test_either_switch_off_stops_summit_before_w1(tmp_path, site_on, summit_on):
    gate, checked = summit_gate(
        config_dir(tmp_path, site_on=site_on, summit_on=summit_on)
    )

    with pytest.raises(controls.KillSwitch):
        gate.before_write("300001", "W1")

    assert checked == []


def test_both_switches_on_let_summit_reach_its_assignee_check(tmp_path):
    gate, checked = summit_gate(config_dir(tmp_path, site_on=True, summit_on=True))

    gate.before_write("300001", "W1")

    assert checked == [("300001", "W1")]


def test_summit_s_switch_off_after_submit_is_a_partial_write(tmp_path):
    gate, _ = summit_gate(config_dir(tmp_path, site_on=True, summit_on=False))

    with pytest.raises(PartialWrite):
        gate.before_write("300001", "W3")


@pytest.mark.parametrize(("step", "error"), [("W1", ConfigError), ("W4", PartialWrite)])
def test_an_unreadable_client_file_stops_summit_closed(tmp_path, step, error):
    folder = config_dir(tmp_path, site_on=True, summit_on=True)
    (folder / "clients" / "summit.toml").unlink()
    gate, checked = summit_gate(folder)

    with pytest.raises(error):
        gate.before_write("300001", step)

    assert checked == []


def test_b1_s_before_write_ignores_summit_s_switch(tmp_path):
    gate, checked = summit_gate(
        config_dir(tmp_path, site_on=True, summit_on=False), client="b1"
    )

    gate.before_write("300001", "W1")

    assert checked == [("300001", "W1")]


# --- the caps -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("opened", "booked", "expected"),
    [
        (11, 1, False),  # past the site's max_notes_per_run (10): not Summit's cap
        (12, 0, True),  # max_peeks_per_run: Notes opened
        (3, 2, True),  # max_notes_per_run: bookings
        (3, 1, False),
    ],
)
def test_summit_s_caps_come_from_its_client_file(env, opened, booked, expected):
    profile = summit_profile(max_notes_per_run=2, max_peeks_per_run=12)

    reached = controls.cap_reached(
        live_config(), MONDAY_10_PERTH, opened, profile=profile, booked=booked
    )

    assert reached is expected


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [(timedelta(minutes=11, seconds=59), False), (timedelta(minutes=12), True)],
)
def test_summit_s_time_cap_is_the_site_s_max_run_minutes(env, elapsed, expected):
    # config/live.toml: max_run_minutes = 12.
    started = MONDAY_10_PERTH - elapsed

    reached = controls.cap_reached(
        live_config(), started, 0, profile=summit_profile(), booked=0
    )

    assert reached is expected


# --- the run's MySys account -----------------------------------------------------


def test_summit_logs_in_as_agent_2_with_its_own_pair():
    assert run.account(live_config(), summit_profile()) == (
        "Agent 2 (Summit Homes)",
        "mysys_live_summit_username",
        "mysys_live_summit_password",
    )


def test_b1_keeps_agent_1_and_its_pair():
    assert run.account(live_config(), None) == (
        "Agent 1 (MySys Only)",
        "mysys_live_username",
        "mysys_live_password",
    )


# --- RUN_SUMMARY names the client ------------------------------------------------


def test_a_b1_run_s_summary_names_b1_and_starts_with_run_id(
    env, started, capsys, tmp_path
):
    env.setattr(cli, "CONFIG_DIR", config_dir(tmp_path, site_on=False, summit_on=True))

    _, lines = run_cli(capsys, B1_LIVE_RUN)

    assert lines[-1].startswith('RUN_SUMMARY {"run_id": ')
    assert summary_of(lines)["client"] == "b1"


def test_a_summit_run_s_summary_names_summit(env, started, capsys):
    _, lines = run_cli(capsys, SUMMIT_RUN)

    assert lines[-1].startswith('RUN_SUMMARY {"run_id": ')
    assert summary_of(lines)["client"] == "summit"


def test_the_demo_s_summary_names_b1(env, started, capsys):
    env.setenv("PO_AGENT_MYSYS_TEST_USERNAME", "fake-user")
    env.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", "fake-password")

    _, lines = run_cli(capsys, ["demo", "--site", "test", "--until-check"])

    assert summary_of(lines)["client"] == "b1"


def test_a_bad_command_line_s_summary_names_no_client(env, capsys):
    code, lines = run_cli(capsys, ["run", "--site", "live", "--client", "other"])

    assert code == 2
    assert summary_of(lines)["client"] is None
