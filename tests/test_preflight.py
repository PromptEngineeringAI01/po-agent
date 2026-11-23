"""Tests for the secrets pre-flight (decisions, 20 Nov 2026, secrets
pre-flight; threat model gap 3): `po-agent preflight --site <site>` checks that
the site's MySys secrets are set and well-formed and prints only their names
and a status. Nothing here reads a real secret or touches either MySys site:
the secrets are fake values in an in-memory keyring and the test environment,
and every run uses the test profile's names. The live pair's names are only
looked up as names (`secret_names`), never read.
"""

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, NoKeyringError

from po_agent import cli
from po_agent.core import secrets

NAMES = ("mysys_test_username", "mysys_test_password")
# A value that must never appear in any output, on any path.
FAKE_VALUE = "fake-value-9f3a1c"


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self, entries=None, error=None):
        super().__init__()
        self.entries = dict(entries or {})
        self.error = error

    def get_password(self, service, username):
        if self.error is not None:
            raise self.error
        return self.entries.get((service, username))

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def delete_password(self, service, username):
        del self.entries[(service, username)]


@pytest.fixture
def store(monkeypatch):
    for name in secrets.SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    previous = keyring.get_keyring()

    def install(entries=None, error=None):
        keyring.set_keyring(MemoryKeyring(entries, error))

    install()
    yield install
    keyring.set_keyring(previous)


def both(value=FAKE_VALUE):
    return {("po-agent", name): value for name in NAMES}


# --- secrets.inspect: presence and format only -------------------------------


def test_a_set_well_formed_secret_is_ok(store):
    store(both())

    assert secrets.inspect("mysys_test_username") == "ok"


def test_an_env_var_counts_as_set(store, monkeypatch):
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", FAKE_VALUE)

    assert secrets.inspect("mysys_test_password") == "ok"


def test_a_secret_in_neither_place_is_not_set(store):
    assert secrets.inspect("mysys_test_username") == "not set"


@pytest.mark.parametrize(
    "value",
    [" fake", "fake ", "fake\n", "fa\tke", "fa\x00ke", "   ", "fa\rke"],
)
def test_a_value_with_outer_whitespace_or_control_characters_is_malformed(value, store):
    store(both(value))

    assert secrets.inspect("mysys_test_username") == "malformed"


def test_a_value_with_a_space_inside_is_fine(store):
    store(both("pass word"))

    assert secrets.inspect("mysys_test_password") == "ok"


@pytest.mark.parametrize(
    "error", [NoKeyringError("detail-x"), KeyringError("locked: detail-x")]
)
def test_an_unreadable_store_is_unavailable(error, store):
    store(error=error)

    assert secrets.inspect("mysys_test_username") == "store unavailable"


def test_an_unknown_name_is_refused(store):
    with pytest.raises(ValueError):
        secrets.inspect("mysys_prod_password")


def test_get_still_returns_the_value(store):
    store(both())

    assert secrets.get("mysys_test_username") == FAKE_VALUE


# --- the command ---------------------------------------------------------------


def run_preflight(capsys, site="test"):
    code = cli.main(["preflight", "--site", site])
    out = capsys.readouterr()
    return code, out.out.splitlines(), out.err


def test_all_ok_prints_each_name_and_status_and_exits_0(store, capsys):
    store(both())

    code, lines, err = run_preflight(capsys)

    assert code == 0
    assert lines[:2] == [
        'SECRET {"name": "mysys_test_username", "status": "ok"}',
        'SECRET {"name": "mysys_test_password", "status": "ok"}',
    ]
    assert lines[2] == "INFO  preflight: secrets ok"
    assert lines[-1].startswith('RUN_SUMMARY {"run_id": ')
    assert '"mode": "preflight"' in lines[-1]
    assert '"site": "test"' in lines[-1]
    assert err == ""


def test_a_problem_exits_2_with_a_config_alert_and_names_every_secret(store, capsys):
    store({("po-agent", "mysys_test_password"): " " + FAKE_VALUE})

    code, lines, _ = run_preflight(capsys)

    assert code == 2
    assert lines[0] == 'SECRET {"name": "mysys_test_username", "status": "not set"}'
    assert lines[1] == 'SECRET {"name": "mysys_test_password", "status": "malformed"}'
    assert lines[2] == (
        'ALERT CONFIG {"note_id": null, "step": null, "detail": "secrets not ready"}'
    )
    assert '"exit_code": 2' in lines[-1]


def test_an_unavailable_store_exits_2(store, capsys):
    store(error=KeyringError("locked"))

    code, lines, _ = run_preflight(capsys)

    assert code == 2
    assert lines[0] == (
        'SECRET {"name": "mysys_test_username", "status": "store unavailable"}'
    )


def test_no_value_reaches_any_output(store, capsys, monkeypatch):
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_USERNAME", FAKE_VALUE + "\n")
    store({("po-agent", "mysys_test_password"): FAKE_VALUE})

    _, lines, err = run_preflight(capsys)

    assert FAKE_VALUE not in "\n".join(lines) + err
    assert str(len(FAKE_VALUE)) not in "\n".join(lines[:3])


def test_an_unknown_site_exits_2_without_reading_any_secret(store, capsys):
    store(both())

    code, lines, _ = run_preflight(capsys, site="staging")

    assert code == 2
    assert not any(line.startswith("SECRET") for line in lines)


def test_the_live_pair_is_looked_up_by_name_only():
    assert cli.secret_names("preflight", "live") == (
        "mysys_live_username",
        "mysys_live_password",
    )


def test_the_command_takes_no_other_options(store, capsys):
    store(both())

    code = cli.main(["preflight", "--site", "test", "--headed"])

    assert code == 2
    assert "invalid command line" in capsys.readouterr().out
