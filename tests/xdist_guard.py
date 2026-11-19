"""Seam 2 never runs in parallel (decisions, 19 Nov 2026, pytest-xdist).

`testsite` tests drive the one MySys test site with one agent account, one
test at a time. `scripts/check.py` runs the offline tests with pytest-xdist
(`-n`), so two hooks keep `testsite` tests out of any parallel run:

- in a worker (any xdist worker, however started: `-n`, `--tx`,
  PYTEST_ADDOPTS): every selected `testsite` test fails in setup, before any
  fixture runs, so nothing logs in. A collection error there would be lost
  in xdist's crash report, hence the setup-time failure.
- in the main process with `-n` or `--tx` set (xdist switches itself off
  under `--collect-only`, where the main process collects): a usage error
  once collection and `-m` are done.

Registered by tests/conftest.py (`pytest_plugins`); tests/test_xdist_guard.py
checks that and loads it with `-p xdist_guard` in its dummy projects.
"""

import pytest

MESSAGE = (
    "testsite tests must never run under pytest-xdist (-n): seam 2 drives the "
    "one test site, one test at a time. Run it without -n."
)


def _worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def _parallel_requested(config: pytest.Config) -> bool:
    return bool(
        config.getoption("numprocesses", default=None)
        or config.getoption("tx", default=None)
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items) -> None:
    # trylast: after `-m` has deselected, so only selected tests count.
    if _worker(config) or not _parallel_requested(config):
        return
    marked = [item for item in items if item.get_closest_marker("testsite")]
    if marked:
        raise pytest.UsageError(f"{MESSAGE} Selected: {len(marked)} testsite tests.")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    if _worker(item.config) and item.get_closest_marker("testsite"):
        pytest.fail(MESSAGE, pytrace=False)
