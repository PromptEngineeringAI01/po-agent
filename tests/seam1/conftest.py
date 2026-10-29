"""Seam-1 fixtures: a `seam1_case` argument runs a test once per case."""

import pytest
from seam1_cases import CASES


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "seam1_case" in metafunc.fixturenames:
        metafunc.parametrize("seam1_case", CASES, ids=[case.id for case in CASES])
