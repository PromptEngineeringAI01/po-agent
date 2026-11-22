"""Playwright helpers shared by the offline page tests."""

import pytest

from po_agent.mysys import wait

# Short MySys waits for the offline page tests (`shorten_waits`). The fakes
# are local HTML whose slowest change lands 300 ms after the click, so 2 s
# is still plenty for every happy path; fail paths stop after 2 s, not 15-60.
SHORT_LOAD_MS = 2000
SHORT_POLL_MS = 100
SHORT_SETTLE_MS = 300


def set_load_timeout(monkeypatch: pytest.MonkeyPatch, ms: int) -> None:
    """Shortens the MySys load wait for a test (one value, in
    `po_agent.mysys.wait`, for the driver and booking alike)."""
    monkeypatch.setattr(wait, "LOAD_TIMEOUT_MS", ms)


def shorten_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every MySys wait a fake page can run into, shortened: the load wait,
    the read-back polls, My Notes' empty-list settle, and the link and search
    waits. A test that sets one of these itself does so after this, and
    wins."""
    set_load_timeout(monkeypatch, SHORT_LOAD_MS)
    monkeypatch.setattr(wait, "POLL_MS", SHORT_POLL_MS)
    monkeypatch.setattr(wait, "EMPTY_SETTLE_MS", SHORT_SETTLE_MS)
    monkeypatch.setattr(wait, "LINK_TIMEOUT_MS", SHORT_LOAD_MS)
    monkeypatch.setattr(wait, "SEARCH_TIMEOUT_MS", SHORT_LOAD_MS)
