"""The seam-2 conftest keeps real data out of failure reports (task 1.8).

Runs pytest in a subprocess on a throwaway test folder that uses
tests/seam2/conftest.py, with a fake address in every failure, and checks the
output holds only the test name and exception type. Also checks that an
explicitly selected `testsite` test with no secret is an error, not a skip.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parent / "seam2" / "conftest.py"
ADDRESS = "Lot 123 (#45) Sample Lane Sampleville 6000 WA"

LEAKY_TESTS = f"""
import pytest

pytestmark = pytest.mark.testsite
ADDRESS = {ADDRESS!r}


def test_assert_leak():
    assert ADDRESS == "something else"


def test_raise_leak():
    raise ValueError(ADDRESS)


def test_print_leak():
    print(ADDRESS)
    raise RuntimeError("failed")


@pytest.fixture
def broken():
    raise KeyError(ADDRESS)


def test_setup_leak(broken):
    pass


def test_needs_secrets(credentials):
    pass
"""

PYTEST_INI = """[pytest]
markers =
    testsite: drives the MySys test site
"""


def run_pytest(folder: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PO_AGENT_")}
    env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(folder), "-m", "testsite", "-p"]
        + ["no:cacheprovider", "-rA", "-v", "--rootdir", str(folder)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=folder,
        env=env,
        timeout=120,
    )


def test_testsite_failures_show_only_the_test_name_and_exception_type(tmp_path):
    shutil.copy(CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    (tmp_path / "test_leaky.py").write_text(LEAKY_TESTS, encoding="utf-8")

    result = run_pytest(tmp_path)

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Sample Lane" not in output
    assert "Lot 123" not in output
    for kind in ("AssertionError", "ValueError", "RuntimeError", "KeyError"):
        assert kind in output
    assert "test_leaky.py::test_raise_leak: ValueError" in output


def test_an_explicit_testsite_run_without_secrets_is_an_error(tmp_path):
    shutil.copy(CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    (tmp_path / "test_leaky.py").write_text(LEAKY_TESTS, encoding="utf-8")

    result = run_pytest(tmp_path)

    assert "ERROR test_leaky.py::test_needs_secrets" in result.stdout
    assert "skipped" not in result.stdout.lower()
    assert "test_leaky.py::test_needs_secrets: ConfigError" in result.stdout
