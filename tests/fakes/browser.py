"""Playwright helpers shared by the offline page tests."""

import pytest

from po_agent.mysys import booking, driver

# Short MySys waits for the offline page tests (`shorten_waits`). The fakes
# are local HTML whose slowest change lands 300 ms after the click, so 2 s
# is still plenty for every happy path; fail paths stop after 2 s, not 15-60.
SHORT_LOAD_MS = 2000
SHORT_POLL_MS = 100
SHORT_SETTLE_MS = 300


def set_load_timeout(monkeypatch: pytest.MonkeyPatch, ms: int) -> None:
    """Shortens the MySys load wait for a test. `booking.LOAD_TIMEOUT_MS`
    copies `driver.LOAD_TIMEOUT_MS` at import, so a test that drives both
    modules sets both here, to one value."""
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", ms)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", ms)


def shorten_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every MySys wait a fake page can run into, shortened: the load wait
    (both copies), the read-back polls (both copies), My Notes' empty-list
    settle, and booking's link and search waits. A test that sets one of
    these itself does so after this, and wins."""
    set_load_timeout(monkeypatch, SHORT_LOAD_MS)
    monkeypatch.setattr(driver, "POLL_MS", SHORT_POLL_MS)
    monkeypatch.setattr(booking, "POLL_MS", SHORT_POLL_MS)
    monkeypatch.setattr(driver, "EMPTY_SETTLE_MS", SHORT_SETTLE_MS)
    monkeypatch.setattr(booking, "LINK_TIMEOUT_MS", SHORT_LOAD_MS)
    monkeypatch.setattr(booking, "SEARCH_TIMEOUT_MS", SHORT_LOAD_MS)
