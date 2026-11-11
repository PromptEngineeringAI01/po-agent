"""Tests for core/config.py, core/secrets.py and core/errors.py (task 1.5).

The test host and made-up hosts appear here; the live host only as the
`LIVE_HOST` constant, never as text (CLAUDE.md Must never #3; decisions,
10 Nov 2026, hooks for the live profile). Nothing here logs in anywhere.
This file is the one place the name ANTHROPIC_API_KEY may appear: it sets it
to prove it's ignored (D4).
"""

import tomllib
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, NoKeyringError
from pydantic import ValidationError

from po_agent.core import config as config_module
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

ROOT = Path(__file__).resolve().parent.parent
TEST_TOML = ROOT / "config" / "test.toml"
LIVE_TOML = ROOT / "config" / "live.toml"
TEST_HOST = "test-prompt.mysys.com.au"
MADE_UP_HOST = "mysys.example.invalid"
SECRET_NAMES = (
    "mysys_test_username",
    "mysys_test_password",
    "mysys_live_username",
    "mysys_live_password",
)


def repo_config() -> dict:
    return tomllib.loads(TEST_TOML.read_text(encoding="utf-8"))


def with_changes(**changes) -> dict:
    data = repo_config()
    data.update(changes)
    return data


def live_config(**changes) -> dict:
    data = tomllib.loads(LIVE_TOML.read_text(encoding="utf-8"))
    data.update(changes)
    return data


# --- config -----------------------------------------------------------------


def test_repo_config_loads_as_the_test_profile():
    config = load_config("test")

    assert isinstance(config, Config)
    assert config.site == "test"
    assert config.base_url.host == TEST_HOST
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


@pytest.mark.parametrize("site", ["staging", "", "prod"])
def test_an_unknown_site_is_a_config_error(site):
    with pytest.raises(ConfigError):
        parse_config(with_changes(site=site))


@pytest.mark.parametrize("site", ["staging", "../test", "TEST", "LIVE", "live/../test"])
def test_load_config_refuses_an_unknown_site_before_reading(site, tmp_path):
    # tmp_path holds a valid test.toml: a refused site never reaches it.
    (tmp_path / "test.toml").write_text(TEST_TOML.read_text("utf-8"), "utf-8")
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
        {"title_rule": "anything"},
        {"enabled": "false"},
        {"max_notes_per_run": 0},
        {"max_run_minutes": -1},
    ],
)
def test_bad_values_are_config_errors(changes):
    with pytest.raises(ConfigError):
        parse_config(with_changes(**changes))


CLAUDE_KEYS = {
    "reader_mode": "hybrid",
    "claude_model_id": "a-model",
    "aud_per_usd": 1.433,
    "claude_price_usd_per_mtok": {"input": 0.0, "output": 0.0},
}


def test_repo_config_has_no_claude_settings():
    # The Claude reader was dropped (decisions, 2 Nov 2026).
    assert CLAUDE_KEYS.keys().isdisjoint(repo_config())


@pytest.mark.parametrize("key", CLAUDE_KEYS)
def test_a_claude_setting_is_an_unknown_key(key):
    data = {k: v for k, v in repo_config().items() if k not in CLAUDE_KEYS}
    data[key] = CLAUDE_KEYS[key]

    with pytest.raises(ConfigError) as caught:
        parse_config(data)

    assert key in str(caught.value)


# --- the live profile (decisions, 10 Nov 2026, live profile) ------------------


def test_repo_live_config_loads_as_the_live_profile():
    config = load_config("live")

    assert config.site == "live"
    assert config.base_url.host == config_module.LIVE_HOST
    assert config.title_rule == "live-b1-title"
    assert config.duplicate_ignores_cancelled is False
    # Committed disabled, switched on for the G.5 spike (decisions, 10 Nov
    # 2026, G.5), off after G.7's first run stopped at W2, on again with the
    # document Type fix (decisions, 11 Nov 2026, live document Type).
    assert config.enabled is True
    assert config.max_notes_per_run == 1  # the watched runs (G.7)
    assert config.stale_read == "my_notes"  # decisions, 10 Nov 2026, My Notes
    # Live's project Documents tab shows Type Purchase Order, as on test
    # (G.7's first run; decisions, 11 Nov 2026, live document Type).
    assert config.project_document_type == "Purchase Order"


def test_the_test_profile_keeps_its_own_values():
    config = load_config("test")

    assert config.stale_read == "note_pool"
    assert config.project_document_type == "Purchase Order"


def test_load_config_reads_the_sites_own_file(tmp_path):
    (tmp_path / "live.toml").write_text(LIVE_TOML.read_text("utf-8"), "utf-8")

    assert load_config("live", config_dir=tmp_path).site == "live"
    with pytest.raises(ConfigError):
        load_config("test", config_dir=tmp_path)  # no test.toml there


def test_each_site_needs_its_own_host():
    live_url = f"https://{config_module.LIVE_HOST}/index.php"
    with pytest.raises(ConfigError) as caught:
        parse_config(with_changes(base_url=live_url))
    assert "base_url" in str(caught.value)

    with pytest.raises(ConfigError) as caught:
        parse_config(live_config(base_url=f"https://{TEST_HOST}/index.php"))
    assert "base_url" in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://{host}/index.php",
        "https://{host}:8443/index.php",
        "https://someone:pw@{host}/index.php",
        "https://{host}.example.invalid/index.php",
        "https://evil-{host}/index.php",
    ],
)
def test_live_base_url_must_be_https_on_exactly_the_live_host(url):
    with pytest.raises(ConfigError) as caught:
        parse_config(live_config(base_url=url.format(host=config_module.LIVE_HOST)))

    assert "base_url" in str(caught.value)
    assert "pw" not in str(caught.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"title_rule": "test-body-filename"},
        {"duplicate_ignores_cancelled": True},
    ],
)
def test_live_needs_the_live_title_rule_and_counts_cancelled_tasks(changes):
    with pytest.raises(ConfigError):
        parse_config(live_config(**changes))


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


@pytest.mark.parametrize("name", SECRET_NAMES)
def test_anthropic_api_key_env_var_is_ignored(name, clean_env, use_keyring):
    use_keyring(MemoryKeyring())
    clean_env.setenv("ANTHROPIC_API_KEY", "should-be-ignored")

    with pytest.raises(ConfigError) as caught:
        secrets.get(name)

    assert "should-be-ignored" not in str(caught.value)


@pytest.mark.parametrize("name", SECRET_NAMES)
def test_anthropic_api_key_env_var_does_not_override_keyring(
    name, clean_env, use_keyring
):
    use_keyring(MemoryKeyring({("po-agent", name): "kr-value"}))
    clean_env.setenv("ANTHROPIC_API_KEY", "should-be-ignored")

    assert secrets.get(name) == "kr-value"


@pytest.mark.parametrize(
    # anthropic_api_key: no Claude key since 2 Nov 2026 (decisions)
    "name",
    ["mysys_prod_password", "ANTHROPIC_API_KEY", "anthropic_api_key", ""],
)
def test_unknown_secret_name_is_refused(name, clean_env, use_keyring):
    backend = use_keyring(MemoryKeyring())

    with pytest.raises(ValueError):
        secrets.get(name)
    assert backend.asked == []


@pytest.mark.parametrize("site", ["test", "live"])
def test_the_site_picks_its_own_mysys_secret_pair(site):
    assert secrets.mysys_names(site) == (
        f"mysys_{site}_username",
        f"mysys_{site}_password",
    )


@pytest.mark.parametrize("site", ["staging", "", "LIVE"])
def test_an_unknown_site_has_no_secrets(site):
    with pytest.raises(ValueError):
        secrets.mysys_names(site)


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


def test_reason_identifier_is_kept_or_redacted():
    kept = GuardRefusal(
        "guard refused the action", action="assign_note", reason="DENYLISTED"
    )
    redacted = GuardRefusal("guard refused the action", reason="12 Smith Close")

    assert kept.reason == "DENYLISTED"
    assert str(kept) == (
        "guard refused the action (action=assign_note, reason=DENYLISTED)"
    )
    assert redacted.reason == "<redacted>"
    assert "Smith" not in str(redacted)
