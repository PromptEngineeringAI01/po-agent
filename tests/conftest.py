"""Fixtures shared by the offline tests (the fakes live in tests/fakes/).

- `browser`: one headless Chromium per test module, for the page tests that
  serve a local fake of a MySys screen.
- `env`: fake secrets, temp, logs and config under tmp_path, with
  `max_notes_per_run = 3`. A module that needs another config or clock
  defines its own `env`, which `mysys` then uses.
- `mysys`: `install(notes, rows=None, **kwargs)` builds seam 2's fake MySys
  (tests/fakes/mysys.py) and patches it in for the driver and the booker.
- `short_waits`: every MySys wait shortened, for page tests whose fail paths
  would otherwise sit out the live 15-60 s waits (tests/fakes/browser.py).

The xdist guard (tests/xdist_guard.py) refuses any parallel run that selects
a `testsite` test.

Values are fake.
"""

import tempfile
from collections.abc import Iterator

import keyring
import pytest
from fakes.browser import shorten_waits
from fakes.mysys import FakeMySys, FakeNote, install, row
from keyring.backends.null import Keyring as NullKeyring
from playwright.sync_api import Browser, sync_playwright
from xdist_guard import pytest_collection_modifyitems  # noqa: F401 (a hook)

from po_agent import cli
from po_agent.core.config import CONFIG_DIR


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def short_waits(monkeypatch) -> None:
    """Every MySys wait shortened for a page test on a local fake
    (tests/fakes/browser.py, `shorten_waits`)."""
    shorten_waits(monkeypatch)


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake secrets, temp and logs under tmp_path, max_notes_per_run = 3."""
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
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    assert "max_notes_per_run = 10" in toml
    (config_dir / "test.toml").write_text(
        toml.replace("max_notes_per_run = 10", "max_notes_per_run = 3"), "utf-8"
    )
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    yield monkeypatch
    keyring.set_keyring(previous)


@pytest.fixture
def mysys(env, tmp_path):
    def install_fake(notes: dict[str, FakeNote], rows=None, **kwargs) -> FakeMySys:
        rows = rows or tuple(row(n, note.internal_no) for n, note in notes.items())
        fake = FakeMySys(
            notes=notes,
            rows=tuple(rows),
            config_dir=tmp_path / "config",
            logs_dir=tmp_path / "logs",
            **kwargs,
        )
        return install(env, fake)

    return install_fake
