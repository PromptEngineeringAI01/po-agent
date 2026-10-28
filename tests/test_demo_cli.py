"""Tests for the supervised demo's prompt and command line (27 Oct 2026).

`output.ask` is the only place the demo waits for Joey: a bare Enter goes on,
anything else (including end of input) stops. `po-agent demo` needs the
MySys secrets only.
"""

import io
import json
import sys
import tempfile

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.core import output

SECRET_NAMES = ("anthropic_api_key", "mysys_test_username", "mysys_test_password")


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


def summary_of(out: str) -> dict:
    last = out.splitlines()[-1]
    assert last.startswith("RUN_SUMMARY {")
    return json.loads(last.removeprefix("RUN_SUMMARY "))


@pytest.mark.parametrize(
    ("typed", "goes_on"),
    [("\n", True), ("\r\n", True), ("n\n", False), ("y\n", False), ("", False)],
)
def test_only_a_bare_enter_goes_on(monkeypatch, capsys, typed, goes_on):
    monkeypatch.setattr(sys, "stdin", io.StringIO(typed))
    assert output.ask("create the Compaction Test task") is goes_on
    assert capsys.readouterr().out == (
        "NEXT  create the Compaction Test task [Enter / n] "
    )


def test_ask_refuses_a_step_that_is_not_a_template(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n"))
    with pytest.raises(ValueError):
        output.ask("delete everything")
    assert capsys.readouterr().out == ""


def test_demo_without_secrets_stops_before_the_browser(env, capsys):
    assert cli.main(["demo", "--site", "test", "--headed"]) == 2
    out = capsys.readouterr().out
    assert "ALERT CONFIG" in out
    assert summary_of(out)["mode"] == "demo"


def test_demo_needs_only_the_mysys_secrets(env, capsys):
    for name in ("mysys_test_username", "mysys_test_password"):
        env.setenv(f"PO_AGENT_{name.upper()}", f"fake-{name}")
    calls = []

    def fake_start(mode, config, credentials, options, summary):
        calls.append((mode, sorted(credentials), options.until_check))
        return 0

    env.setattr(cli, "start", fake_start)
    assert cli.main(["demo", "--site", "test", "--until-check"]) == 0
    assert calls == [("demo", ["mysys_test_password", "mysys_test_username"], True)]
    assert summary_of(capsys.readouterr().out)["mode"] == "demo"


def test_demo_takes_probe_link(env, capsys):
    for name in ("mysys_test_username", "mysys_test_password"):
        env.setenv(f"PO_AGENT_{name.upper()}", f"fake-{name}")
    calls = []

    def fake_start(mode, config, credentials, options, summary):
        calls.append((mode, options.probe_link, options.until_check))
        return 0

    env.setattr(cli, "start", fake_start)
    assert cli.main(["demo", "--site", "test", "--probe-link"]) == 0
    assert calls == [("demo", True, False)]


# 28 Oct 2026: with the pointer move (move_pointer_off_menu) the page no
# longer needs a visible window, so the demo honours --headed again.


class _FakePlaywright:
    def __init__(self, launched: list[dict]) -> None:
        self.launched = launched
        self.chromium = self

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def launch(self, **kwargs):
        self.launched.append(kwargs)
        return self

    def new_context(self, **kwargs):
        return self

    def new_page(self):
        return self

    def set_default_timeout(self, ms: int) -> None:
        return None

    def close(self) -> None:
        return None


@pytest.mark.parametrize(("headed", "headless"), [(True, False), (False, True)])
def test_demo_browser_honours_headed(monkeypatch, tmp_path, headed, headless):
    from po_agent.core import demo

    launched: list[dict] = []
    monkeypatch.setattr(demo, "sync_playwright", lambda: _FakePlaywright(launched))
    with demo._browser(headed=headed, slow_mo=0, downloads=tmp_path):
        pass
    assert launched[0]["headless"] is headless


def _with_mysys_secrets(env) -> list:
    for name in ("mysys_test_username", "mysys_test_password"):
        env.setenv(f"PO_AGENT_{name.upper()}", f"fake-{name}")
    calls: list = []
    env.setattr(cli, "start", lambda *args: calls.append(args) or 0)
    return calls


def test_a_demo_that_asks_for_writes_needs_headed(env, capsys):
    calls = _with_mysys_secrets(env)
    assert cli.main(["demo", "--site", "test"]) == 2
    out = capsys.readouterr().out
    assert "ALERT CONFIG" in out and "needs --headed" in out
    assert calls == []


@pytest.mark.parametrize("flags", [["--until-check"], ["--probe-link"], ["--headed"]])
def test_read_only_demos_may_be_headless_and_headed_ones_may_write(env, capsys, flags):
    calls = _with_mysys_secrets(env)
    assert cli.main(["demo", "--site", "test", *flags]) == 0
    assert len(calls) == 1
