"""Summit's real-PDF and real-PO fixtures and their reports after the run
(tasks 9.7, 9.10)."""

from pathlib import Path

import pytest
from real_pos import PRIVATE_DIR_ENV, _selected_explicitly
from summit_real_pos import (
    CASES,
    REPORT,
    SEAM_REPORT,
    Counts,
    SeamRun,
    evaluate_cases,
    find_summit_dir,
    report_lines,
    seam_report_lines,
    tally_folder,
)


def _summit_dir(request: pytest.FixtureRequest) -> Path:
    """private/summit/ with its PDFs; skipped when absent, unless
    `-m real_data` was selected, where it is an error."""
    folder: Path | None = find_summit_dir()
    if folder is None:
        message = (
            f"private/summit/pdfs/ not found (set {PRIVATE_DIR_ENV} or use the laptop)"
        )
        if _selected_explicitly(request.config.option.markexpr or ""):
            raise FileNotFoundError(message)
        pytest.skip(message)
    return folder


@pytest.fixture(scope="session")
def summit_real_counts(request: pytest.FixtureRequest) -> Counts:
    """The counts over private/summit/pdfs/."""
    counts = tally_folder(_summit_dir(request))
    request.config.stash[REPORT] = report_lines(counts)
    return counts


@pytest.fixture(scope="session")
def summit_real_seam(request: pytest.FixtureRequest) -> SeamRun:
    """Every case of private/summit/fixtures/cases.toml decided; skipped
    (never passed) until S.0 writes that file."""
    folder = _summit_dir(request)
    if not (folder / CASES).is_file():
        pytest.skip("no private/summit/fixtures/cases.toml yet (S.0)")
    run = evaluate_cases(folder)
    request.config.stash[SEAM_REPORT] = seam_report_lines(run)
    return run


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the Summit reports once, after the run, without -s."""
    for key, title in (
        (REPORT, "Summit real-PDF seam"),
        (SEAM_REPORT, "Summit real-PO seam"),
    ):
        lines = config.stash.get(key, None)
        if lines:
            terminalreporter.section(title)
            for line in lines:
                terminalreporter.write_line(line)
