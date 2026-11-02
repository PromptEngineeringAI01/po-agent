"""Seam-1 fixtures: a `seam1_case` argument runs a test once per case.

The real-PO seam's fixtures and hooks (real_pos.py) are imported here, so
pytest registers them: `real_po_dir`, `real_po_results`, 1.8's failure-report
scrub for `real_data` tests and the report after the run.
"""

import pytest
from real_pos import (  # noqa: F401
    pytest_runtest_makereport,
    pytest_terminal_summary,
    real_po_dir,
    real_po_results,
)
from seam1_cases import CASES


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "seam1_case" in metafunc.fixturenames:
        metafunc.parametrize("seam1_case", CASES, ids=[case.id for case in CASES])
