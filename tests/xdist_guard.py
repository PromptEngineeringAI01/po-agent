"""Seam 2 never runs in parallel (decisions, 19 Nov 2026, pytest-xdist).

`testsite` tests drive the one MySys test site with one agent account, one
test at a time. `scripts/check.py` runs the offline tests with pytest-xdist
(`-n`), so these hooks stop any run that still selects a `testsite` test when
`-n` is set or inside an xdist worker:

- in the main process (xdist switches itself off under `--collect-only`, so
  the `-n` option is checked, not only the worker flag): a usage error once
  collection and `-m` are done;
- in a worker (where a collection error is lost in xdist's crash report):
  every selected `testsite` test fails in setup, before any fixture runs, so
  nothing logs in.

Loaded by tests/conftest.py; tests/test_xdist_guard.py loads it with
`-p xdist_guard`.
"""

import pytest

MESSAGE = (
    "testsite tests must never run under pytest-xdist (-n): seam 2 drives the "
    "one test site, one test at a time. Run it without -n."
)


def _worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items) -> None:
    # trylast: after `-m` has deselected, so only selected tests count.
    if _worker(config) or not config.getoption("numprocesses", default=None):
        return
    marked = [item for item in items if item.get_closest_marker("testsite")]
    if marked:
        raise pytest.UsageError(f"{MESSAGE} Selected: {len(marked)} testsite tests.")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    if _worker(item.config) and item.get_closest_marker("testsite"):
        pytest.fail(MESSAGE, pytrace=False)
