"""The seam-2 safety net: `testsite` tests never run under pytest-xdist.

Seam 2 drives the one MySys test site with one agent account, so its tests
must run one at a time. `scripts/check.py` runs the offline tests with `-n`;
the guard (tests/xdist_guard.py, loaded by tests/conftest.py) fails the run
loudly when a selected test is marked `testsite` and `-n` is set or the run
is an xdist worker.

Every run here is either `--collect-only` in this repo (nothing logs in) or a
dummy test in tmp_path, so no test reaches MySys.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD_MESSAGE = "testsite tests must never run under pytest-xdist"


def run_pytest(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = str(ROOT / "tests")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def test_seam2_collect_only_with_workers_is_refused():
    result = run_pytest(
        "tests/seam2", "-m", "testsite", "--collect-only", "-q", "-n", "2", cwd=ROOT
    )

    assert result.returncode != 0
    assert GUARD_MESSAGE in result.stdout + result.stderr


def test_seam2_collect_only_serial_is_allowed():
    result = run_pytest(
        "tests/seam2", "-m", "testsite", "--collect-only", "-q", cwd=ROOT
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert GUARD_MESSAGE not in result.stdout + result.stderr


def dummy_project(tmp_path: Path) -> Path:
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = --strict-markers\nmarkers =\n    testsite: fake\n",
        encoding="utf-8",
    )
    (tmp_path / "test_dummy.py").write_text(
        "import pytest\n\n\n"
        "@pytest.mark.testsite\n"
        "def test_marked():\n    pass\n\n\n"
        "def test_plain():\n    pass\n",
        encoding="utf-8",
    )
    return tmp_path


def test_a_testsite_test_in_an_xdist_worker_fails_loudly(tmp_path):
    project = dummy_project(tmp_path)

    result = run_pytest("-p", "xdist_guard", "-m", "testsite", "-n", "2", cwd=project)

    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert GUARD_MESSAGE in out
    assert "1 passed" not in out


def test_parallel_run_with_testsite_deselected_passes(tmp_path):
    project = dummy_project(tmp_path)

    result = run_pytest(
        "-p", "xdist_guard", "-m", "not testsite", "-n", "2", cwd=project
    )

    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "1 passed" in out
    assert GUARD_MESSAGE not in out
