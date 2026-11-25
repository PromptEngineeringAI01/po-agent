"""Summit's real-PDF fixture and its report after the run (task 9.7)."""

from pathlib import Path

import pytest
from real_pos import PRIVATE_DIR_ENV, _selected_explicitly
from summit_real_pos import REPORT, Counts, find_summit_dir, report_lines, tally_folder


@pytest.fixture(scope="session")
def summit_real_counts(request: pytest.FixtureRequest) -> Counts:
    """The counts over private/summit/pdfs/; skipped when absent, unless
    `-m real_data` was selected, where it is an error."""
    folder: Path | None = find_summit_dir()
    if folder is None:
        message = (
            f"private/summit/pdfs/ not found (set {PRIVATE_DIR_ENV} or use the laptop)"
        )
        if _selected_explicitly(request.config.option.markexpr or ""):
            raise FileNotFoundError(message)
        pytest.skip(message)
    counts = tally_folder(folder)
    request.config.stash[REPORT] = report_lines(counts)
    return counts


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the Summit counts once, after the run, without -s."""
    lines = config.stash.get(REPORT, None)
    if lines:
        terminalreporter.section("Summit real-PDF seam")
        for line in lines:
            terminalreporter.write_line(line)
