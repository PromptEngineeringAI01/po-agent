"""Seam-2 fixtures (marker testsite) and the failure-report scrub (task 1.8).

In a default run (`-m "not testsite ..."`) these tests are deselected and no
fixture runs. When `-m testsite` is selected explicitly, a missing secret or
a failed precondition is an error, never a skip, so "green with nothing run"
can't count as done.

Failure reports of `testsite` and `real_data` tests are cut to the test name
and the exception type (Must never #6): Playwright call logs, strict-mode and
timeout text, assertion diffs and captured output can all quote page text.
"""

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Page

from po_agent.core import secrets
from po_agent.core.config import Config, load_config
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

SCRUBBED_MARKERS = ("testsite", "real_data")
# The 3 trial POs (SPEC.md -> Trial conditions): internal numbers only.
TRIAL_INTERNAL_NOS = ("2609017B", "2609034B", "2610002B")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    # https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport
    report = yield
    if report.failed and any(item.get_closest_marker(m) for m in SCRUBBED_MARKERS):
        kind = call.excinfo.typename if call.excinfo else "Failure"
        # A plain string: the terminal prints it as is, and the short summary
        # finds no crash message to quote.
        report.longrepr = f"{item.nodeid}: {kind}"
        report.sections = []
    return report


@pytest.fixture(scope="session")
def config() -> Config:
    return load_config("test")


@pytest.fixture(scope="session")
def credentials() -> dict[str, str]:
    """The test-site login; ConfigError (an error, not a skip) if unset."""
    return {
        name: secrets.get(name)
        for name in ("mysys_test_username", "mysys_test_password")
    }


@pytest.fixture
def page() -> Iterator[Page]:
    with driver.open_browser(headed=False, slow_mo=0) as page:
        yield page


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


class ResetStateError(Exception):
    """The test site isn't in the reset state (docs/workflow.md 6.1)."""


@pytest.fixture
def check_note_pool_reset(config) -> Callable[[driver.NotePoolList], None]:
    """Note Pool part of the reset-state precondition (3.2 adds the project part).

    Under Agent Pool + Locked, Status Pending: exactly one eligible, unlinked
    Note per trial PO. The error names counts and trial numbers only.
    """
    from po_agent.core.run import eligible_notes

    def check(listing: driver.NotePoolList) -> None:
        found = eligible_notes(listing.rows, config.title_rule, config.pool_name)
        counts = {
            number: sum(note.internal_no == number for note in found)
            for number in TRIAL_INTERNAL_NOS
        }
        if listing.pages != 1 or any(count != 1 for count in counts.values()):
            raise ResetStateError(
                f"not in the reset state: rows={len(listing.rows)}, "
                f"eligible={len(found)}, per trial PO={counts}"
            )

    return check
