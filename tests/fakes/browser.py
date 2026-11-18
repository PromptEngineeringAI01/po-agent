"""Playwright helpers shared by the offline page tests."""

import pytest

from po_agent.mysys import booking, driver


def set_load_timeout(monkeypatch: pytest.MonkeyPatch, ms: int) -> None:
    """Shortens the MySys load wait for a test. `booking.LOAD_TIMEOUT_MS`
    copies `driver.LOAD_TIMEOUT_MS` at import, so a test that drives both
    modules sets both here, to one value."""
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", ms)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", ms)
