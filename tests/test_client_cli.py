"""Tests for `--client b1|summit` on the po-agent command (task 9.3; SPEC.md
-> Client 2: Summit Home, The separate run).

`--client` defaults to b1 and sits beside `--site` on run, spike and
preflight; demo stays B1's. Summit is live only: `--site test --client
summit` is ALERT CONFIG, exit 2. Every Summit mode is built: the spike
(9.11, tests/test_summit_spike.py), run --decide-only (9.12,
tests/test_summit_decide_only.py) and run (9.14, tests/test_summit_booking.py).

Nothing here opens a browser or reads a real secret: the mode entry point
(`cli.start`) is replaced, secrets are fake values in the test environment
and an in-memory keyring, and the Summit pair is read only by `preflight`
from those fakes (never against real secrets).
"""

import json
import tempfile
from datetime import UTC, datetime

import keyring
import pytest
from keyring.backend import KeyringBackend

from po_agent import cli
from po_agent.core import controls, secrets

SUMMIT_PAIR = ("mysys_live_summit_username", "mysys_live_summit_password")
FAKE_VALUE = "fake-value-7c2e90"
SUMMIT_MODES = [
    ["spike"],
    ["run", "--decide-only"],
    ["run"],
]


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self, entries=None):
        super().__init__()
        self.entries = dict(entries or {})
        self.asked = []

    def get_password(self, service, username):
        self.asked.append((service, username))
        return self.entries.get((service, username))

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def delete_password(self, service, username):
        del self.entries[(service, username)]


@pytest.fixture
def fake_keyring(monkeypatch, tmp_path):
    """No secret in the environment, an empty in-memory keyring, temp, logs
    and the run lock's state folder under tmp_path; the clock at Monday
    10:00 Perth, inside the run window."""
    for name in secrets.SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(controls, "now", lambda: datetime(2026, 11, 2, 2, tzinfo=UTC))
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture
def started(monkeypatch):
    calls = []

    def fake_start(*args):
        calls.append(args)
        return 0

    monkeypatch.setattr(cli, "start", fake_start)
    return calls


def run_cli(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out.splitlines(), out.err


def alert_of(lines):
    alerts = [line for line in lines if line.startswith("ALERT ")]
    assert len(alerts) == 1
    _, kind, body = alerts[0].split(" ", 2)
    return kind, json.loads(body)


def summary_of(lines):
    assert lines[-1].startswith("RUN_SUMMARY {")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


# --- the secret names ------------------------------------------------------------


@pytest.mark.parametrize("mode", ["run", "decide-only", "spike", "preflight"])
def test_summit_uses_its_own_live_pair(mode):
    assert cli.secret_names(mode, "live", "summit") == SUMMIT_PAIR


@pytest.mark.parametrize("site", ["test", "live"])
def test_b1_is_the_default_client_and_keeps_its_pair(site):
    assert cli.secret_names("run", site, "b1") == (
        f"mysys_{site}_username",
        f"mysys_{site}_password",
    )
    assert secrets.mysys_names(site) == secrets.mysys_names(site, "b1")


def test_summit_has_its_own_live_pair_and_no_test_pair():
    assert secrets.mysys_names("live", "summit") == SUMMIT_PAIR
    with pytest.raises(ValueError):
        secrets.mysys_names("test", "summit")


@pytest.mark.parametrize("client", ["acme", "", "SUMMIT", "B1"])
def test_an_unknown_client_has_no_secrets(client):
    with pytest.raises(ValueError):
        secrets.mysys_names("live", client)


def test_the_summit_pair_reads_from_its_own_env_vars(fake_keyring, monkeypatch):
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_USERNAME", "fake-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_PASSWORD", "fake-pass")

    assert secrets.get("mysys_live_summit_username") == "fake-user"
    assert secrets.get("mysys_live_summit_password") == "fake-pass"
    assert fake_keyring.asked == []


# --- --site test --client summit ------------------------------------------------


@pytest.mark.parametrize("mode", [*SUMMIT_MODES, ["preflight"]])
def test_summit_on_the_test_site_is_alert_config_exit_2(
    mode, fake_keyring, started, capsys
):
    code, lines, err = run_cli(capsys, [*mode, "--site", "test", "--client", "summit"])

    assert code == 2
    assert alert_of(lines) == (
        "CONFIG",
        {
            "note_id": None,
            "step": None,
            "detail": "the client does not run on that site",
        },
    )
    assert summary_of(lines)["exit_code"] == 2
    assert not any(line.startswith("SECRET") for line in lines)
    assert started == []
    assert fake_keyring.asked == []
    assert err == ""


def test_a_broken_client_file_is_alert_config_naming_the_field(
    fake_keyring, started, capsys, monkeypatch, tmp_path
):
    (tmp_path / "clients").mkdir()
    (tmp_path / "clients" / "summit.toml").write_text(
        (cli.CONFIG_DIR / "clients" / "summit.toml")
        .read_text("utf-8")
        .replace('sites = ["live"]', 'sites = ["test"]'),
        "utf-8",
    )
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path)

    code, lines, _ = run_cli(capsys, ["spike", "--site", "live", "--client", "summit"])

    assert code == 2
    kind, alert = alert_of(lines)
    assert kind == "CONFIG"
    assert "field=sites" in alert["detail"]
    assert started == []


# --- B1 unchanged ------------------------------------------------------------------


def test_an_explicit_b1_is_the_same_as_the_default(
    fake_keyring, started, capsys, monkeypatch
):
    for name in ("mysys_test_username", "mysys_test_password"):
        monkeypatch.setenv(f"PO_AGENT_{name.upper()}", f"fake-{name}")

    code, _, _ = run_cli(
        capsys, ["run", "--site", "test", "--decide-only", "--client", "b1"]
    )

    assert code == 0
    (mode, config, credentials, options, summary), *_ = started
    assert mode == "decide-only"
    assert config.site == "test"
    assert set(credentials) == {"mysys_test_username", "mysys_test_password"}


def test_b1_preflight_output_is_unchanged_with_an_explicit_client(
    fake_keyring, capsys, monkeypatch
):
    for name in ("mysys_test_username", "mysys_test_password"):
        monkeypatch.setenv(f"PO_AGENT_{name.upper()}", FAKE_VALUE)

    code, lines, _ = run_cli(capsys, ["preflight", "--site", "test", "--client", "b1"])

    assert code == 0
    assert lines[:3] == [
        'SECRET {"name": "mysys_test_username", "status": "ok"}',
        'SECRET {"name": "mysys_test_password", "status": "ok"}',
        "INFO  preflight: secrets ok",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--site", "test", "--client", "acme"],
        ["spike", "--site", "test", "--client"],
        ["preflight", "--site", "test", "--client", "Summit"],
        ["demo", "--site", "test", "--until-check", "--client", "b1"],
    ],
    ids=["unknown-client", "no-value", "wrong-case", "demo-has-no-client"],
)
def test_a_bad_client_option_is_an_invalid_command_line(
    argv, fake_keyring, started, capsys
):
    code, lines, err = run_cli(capsys, argv)

    assert code == 2
    kind, alert = alert_of(lines)
    assert kind == "CONFIG"
    assert alert["detail"] == "invalid command line"
    assert started == []
    assert err == ""


# --- preflight --client summit (fake values only) -----------------------------------


def test_summit_preflight_checks_the_summit_pair(fake_keyring, capsys, monkeypatch):
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_USERNAME", FAKE_VALUE)
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_PASSWORD", FAKE_VALUE)

    code, lines, err = run_cli(
        capsys, ["preflight", "--site", "live", "--client", "summit"]
    )

    assert code == 0
    assert lines[:3] == [
        'SECRET {"name": "mysys_live_summit_username", "status": "ok"}',
        'SECRET {"name": "mysys_live_summit_password", "status": "ok"}',
        "INFO  preflight: secrets ok",
    ]
    assert FAKE_VALUE not in "\n".join(lines) + err
    assert fake_keyring.asked == []  # both from the fake env: no store read


def test_summit_preflight_reports_a_missing_secret_from_the_fake_keyring(
    fake_keyring, capsys, monkeypatch
):
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_USERNAME", FAKE_VALUE)

    code, lines, _ = run_cli(
        capsys, ["preflight", "--site", "live", "--client", "summit"]
    )

    assert code == 2
    assert lines[1] == (
        'SECRET {"name": "mysys_live_summit_password", "status": "not set"}'
    )
    assert fake_keyring.asked == [("po-agent", "mysys_live_summit_password")]
    assert alert_of(lines)[0] == "CONFIG"
