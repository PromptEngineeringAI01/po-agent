"""Tests for core/config.py, core/secrets.py and core/errors.py (task 1.5).

Only the test host and made-up hosts appear here; the live host never does
(CLAUDE.md Must never #3; decisions, 16 Oct 2026, D4). This file is the one
place the name ANTHROPIC_API_KEY may appear: it sets it to prove it's ignored
(D4).
"""

import tomllib
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, NoKeyringError
from po_agent.core import secrets
from po_agent.core.config import Config, load_config, parse_config
from po_agent.core.errors import (
    EXIT_CODES,
    AccuracyBreach,
    ConfigError,
    GuardRefusal,
    LoginFailed,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
    WriteNotStarted,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
TEST_TOML = ROOT / "config" / "test.toml"
TEST_HOST = "test-prompt.mysys.com.au"
MADE_UP_HOST = "mysys.example.invalid"
SECRET_NAMES = ("anthropic_api_key", "mysys_test_username", "mysys_test_password")


def repo_config() -> dict:
    return tomllib.loads(TEST_TOML.read_text(encoding="utf-8"))


def with_changes(**changes) -> dict:
    data = repo_config()
    data.update(changes)
    return data


# --- config -----------------------------------------------------------------


def test_repo_config_loads_as_the_test_profile():
    config = load_config("test")

    assert isinstance(config, Config)
    assert config.site == "test"
    assert config.base_url.host == TEST_HOST
    assert config.reader_mode in ("hybrid", "deterministic-only")
    assert isinstance(config.enabled, bool)
    assert config.max_notes_per_run > 0
    assert config.run_window.tz == "Australia/Perth"


def test_config_is_frozen():
    config = load_config("test")

    with pytest.raises(ValidationError):
        config.enabled = False


@pytest.mark.parametrize("key", ["surprise", "state_dir"])
def test_unknown_top_level_key_is_a_config_error(key):
    with pytest.raises(ConfigError) as caught:
        parse_config(with_changes(**{key: 1}))

    assert key in str(caught.value)


def test_unknown_nested_key_is_a_config_error():
    data = repo_config()
    data["run_window"] = {**data["run_window"], "surprise": 1}

    with pytest.raises(ConfigError) as caught:
        parse_config(data)

    assert "run_window.surprise" in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        f"https://{MADE_UP_HOST}/index.php",
        f"https://{TEST_HOST}.example.invalid/index.php",
        f"https://evil-{TEST_HOST}/index.php",
        f"http://{TEST_HOST}/index.php",
        f"https://someone:pw@{TEST_HOST}/index.php",
        "not a url",
    ],
)
def test_base_url_must_be_https_on_exactly_the_test_host(url):
    with pytest.raises(ConfigError) as caught:
        parse_config(with_changes(base_url=url))

    assert "base_url" in str(caught.value)
    # Fixed template plus the field name: never the offending value.
    assert MADE_UP_HOST not in str(caught.value)
    assert "pw" not in str(caught.value)


def test_test_host_in_any_case_is_accepted():
    config = parse_config(with_changes(base_url=f"https://{TEST_HOST.upper()}/x"))

    assert config.base_url.host == TEST_HOST


@pytest.mark.parametrize("site", ["live", "staging", ""])
def test_site_other_than_test_is_a_config_error(site):
    with pytest.raises(ConfigError):
        parse_config(with_changes(site=site))


@pytest.mark.parametrize("site", ["live", "../test", "TEST"])
def test_load_config_refuses_a_site_other_than_test_before_reading(site, tmp_path):
    with pytest.raises(ConfigError):
        load_config(site, config_dir=tmp_path)


def test_missing_config_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config("test", config_dir=tmp_path)


def test_bad_toml_is_a_config_error(tmp_path):
    (tmp_path / "test.toml").write_text("site = \n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config("test", config_dir=tmp_path)


def test_config_file_with_a_made_up_host_is_a_config_error(tmp_path):
    text = TEST_TOML.read_text(encoding="utf-8").replace(TEST_HOST, MADE_UP_HOST)
    (tmp_path / "test.toml").write_text(text, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config("test", config_dir=tmp_path)


@pytest.mark.parametrize(
    "changes",
    [
        {"reader_mode": "claude-only"},
        {"title_rule": "anything"},
        {"enabled": "false"},
        {"max_notes_per_run": 0},
        {"max_run_minutes": -1},
        {"aud_per_usd": 0},
    ],
)
def test_bad_values_are_config_errors(changes):
    with pytest.raises(ConfigError):
        parse_config(with_changes(**changes))


def test_missing_key_is_a_config_error():
    data = repo_config()
    del data["pool_name"]

    with pytest.raises(ConfigError) as caught:
        parse_config(data)

    assert "pool_name" in str(caught.value)


# --- secrets ----------------------------------------------------------------


class MemoryKeyring(KeyringBackend):
    """In-memory keyring backend (https://keyring.readthedocs.io/en/latest/,
    "Write your own keyring backend")."""

    priority = 1

    def __init__(self, entries=None, error=None):
        super().__init__()
        self.entries = dict(entries or {})
        self.error = error
        self.asked = []

    def get_password(self, service, username):
        self.asked.append((service, username))
        if self.error is not None:
            raise self.error
        return self.entries.get((service, username))

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def delete_password(self, service, username):
        del self.entries[(service, username)]


@pytest.fixture
def clean_env(monkeypatch):
    for name in SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return monkeypatch


@pytest.fixture
def use_keyring():
    previous = keyring.get_keyring()

    def install(backend):
        keyring.set_keyring(backend)
        return backend

    yield install
    keyring.set_keyring(previous)


def test_env_var_wins_over_keyring(clean_env, use_keyring):
    use_keyring(MemoryKeyring({("po-agent", "mysys_test_username"): "from-keyring"}))
    clean_env.setenv("PO_AGENT_MYSYS_TEST_USERNAME", "from-env")

    assert secrets.get("mysys_test_username") == "from-env"


@pytest.mark.parametrize("name", SECRET_NAMES)
def test_keyring_service_po_agent_when_no_env_var(name, clean_env, use_keyring):
    backend = use_keyring(MemoryKeyring({("po-agent", name): f"kr-{name}"}))

    assert secrets.get(name) == f"kr-{name}"
    assert backend.asked == [("po-agent", name)]


def test_empty_env_var_falls_back_to_keyring(clean_env, use_keyring):
    use_keyring(MemoryKeyring({("po-agent", "mysys_test_password"): "kr-pw"}))
    clean_env.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", "")

    assert secrets.get("mysys_test_password") == "kr-pw"


@pytest.mark.parametrize("name", SECRET_NAMES)
def test_missing_secret_is_a_config_error_naming_it(name, clean_env, use_keyring):
    use_keyring(MemoryKeyring())

    with pytest.raises(ConfigError) as caught:
        secrets.get(name)

    assert name in str(caught.value)
    assert caught.value.exit_code == 2


@pytest.mark.parametrize(
    "error",
    [NoKeyringError("backend says sk-detail"), KeyringError("locked: sk-detail")],
)
def test_keyring_failure_is_a_config_error_without_its_text(
    error, clean_env, use_keyring
):
    use_keyring(MemoryKeyring(error=error))

    with pytest.raises(ConfigError) as caught:
        secrets.get("mysys_test_password")

    assert "mysys_test_password" in str(caught.value)
    assert "sk-detail" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_anthropic_api_key_env_var_is_ignored(clean_env, use_keyring):
    use_keyring(MemoryKeyring())
    clean_env.setenv("ANTHROPIC_API_KEY", "should-be-ignored")

    with pytest.raises(ConfigError) as caught:
        secrets.get("anthropic_api_key")

    assert "should-be-ignored" not in str(caught.value)


def test_anthropic_api_key_env_var_does_not_override_keyring(clean_env, use_keyring):
    use_keyring(MemoryKeyring({("po-agent", "anthropic_api_key"): "kr-key"}))
    clean_env.setenv("ANTHROPIC_API_KEY", "should-be-ignored")

    assert secrets.get("anthropic_api_key") == "kr-key"


@pytest.mark.parametrize("name", ["mysys_live_password", "ANTHROPIC_API_KEY", ""])
def test_unknown_secret_name_is_refused(name, clean_env, use_keyring):
    backend = use_keyring(MemoryKeyring())

    with pytest.raises(ValueError):
        secrets.get(name)
    assert backend.asked == []


# --- errors -----------------------------------------------------------------


def test_exit_code_table():
    assert EXIT_CODES == {
        UnexpectedScreen: 1,
        WriteNotStarted: 1,
        PartialWrite: 1,
        GuardRefusal: 1,
        LoginFailed: 2,
        ConfigError: 2,
        AccuracyBreach: 3,
    }
    for error_type, code in EXIT_CODES.items():
        assert issubclass(error_type, PoAgentError)
        assert error_type("fixed detail").exit_code == code


def test_message_is_the_detail_plus_identifiers():
    error = GuardRefusal(
        "action refused: denylisted",
        action="set_hold",
        step="W3",
        note_id="104233",
        pln="pln_66938",
    )

    assert str(error) == (
        "action refused: denylisted"
        " (action=set_hold, step=W3, note_id=104233, pln=pln_66938)"
    )
    assert error.detail == "action refused: denylisted"
    assert (error.action, error.step, error.note_id) == ("set_hold", "W3", "104233")
    assert error.args == (str(error),)


def test_message_without_identifiers_is_the_detail():
    assert str(UnexpectedScreen("Note window not found")) == "Note window not found"


@pytest.mark.parametrize(
    "field", ["action", "step", "note_id", "pln", "field", "secret"]
)
def test_identifier_holding_page_text_is_redacted(field):
    page_text = "12 Smith Close, Somewhere WA 6000"

    error = PartialWrite("read-back failed", **{field: page_text})

    assert "Smith" not in str(error)
    assert "Smith" not in repr(error.args)
    assert getattr(error, field) == "<redacted>"
    assert f"{field}=<redacted>" in str(error)


def test_po_number_identifier_is_kept():
    error = AccuracyBreach("task value mismatch", step="W2", note_id="2609034B/048")

    assert "note_id=2609034B/048" in str(error)
