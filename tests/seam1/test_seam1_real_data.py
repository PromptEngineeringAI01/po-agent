"""The real-PO seam (task 2.6, S3): real B1 POs through both code readers and
decide(), laptop only.

`-m real_data` reads private/fixtures/cases.toml and private/pdfs/ (the main
checkout's private/, or SEAM1_PRIVATE_DIR). The report is field names,
agree/disagree counts, coverage, a skip reason per case id and
`false PROCEED: N`: never a value from a PDF, a Note or MySys. Case ids are
the trial POs' internal numbers and real-1, real-2, ... for the rest.

The unmarked tests below run offline (in CI too): the skip and error when
private/ is absent, the failure-report scrub, and the whole report on a fake
private/ folder.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from real_pos import (
    TRIAL_INTERNAL_NOS,
    evaluate,
    false_proceeds,
    report_lines,
)
from seam1_cases import CASES, text_pdf

from po_agent.b1.models import Proceed

SEAM1 = Path(__file__).resolve().parent

# --- the real POs (laptop only) ---


@pytest.mark.real_data
def test_no_false_proceed_on_the_real_pos(real_po_results) -> None:
    assert false_proceeds(real_po_results) == 0


@pytest.mark.real_data
def test_every_real_case_has_a_mysys_lookup(real_po_results) -> None:
    """SPEC.md -> Testing Strategy: the lookup is what MySys shows (search
    rows, the Address string, the tasks), so decide() runs on every case."""
    old = [r.case_id for r in real_po_results if not r.mysys_shape]
    assert old == []


@pytest.mark.real_data
def test_the_three_trial_pos_proceed(real_po_results) -> None:
    """S3: each trial PO PROCEEDs with its expected pln and its PO number."""
    proceeded = {
        r.case_id
        for r in real_po_results
        if r.case_id in TRIAL_INTERNAL_NOS
        and isinstance(r.result, Proceed)
        and r.result.pln == r.expect_pln
        and r.result.po_number == f"{r.case_id}/048"
    }
    assert sorted(proceeded) == sorted(TRIAL_INTERNAL_NOS)


# --- offline: a fake private/ folder ---

FAKE_ADDRESS = "Lot 123 (#45) Sample Lane Sampleville 6000 WA"
CLEAN = next(case for case in CASES if case.id == "p1-clean")


def fake_private(folder: Path, cases: str) -> Path:
    """A private/ folder: one fake PDF (2600001B, both readers read the same
    lines) and the given cases.toml."""
    (folder / "pdfs").mkdir(parents=True)
    (folder / "fixtures").mkdir()
    lines = [line for line in CLEAN.pypdf_text.splitlines() if "(" not in line]
    (folder / "pdfs" / "2600001B_048_1.pdf").write_bytes(text_pdf(lines))
    (folder / "fixtures" / "cases.toml").write_text(cases, encoding="utf-8")
    return folder


NOTE = """
note_title = "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf"
note_body = "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf"
"""

MYSYS_CASE = f"""
[[case]]
pdf = "2600001B_048_1.pdf"
{NOTE}
expect = "PROCEED"
expect_reason = ""
expect_pln = "pln_10001"
[case.lookup]
more_pages = false
project_internal_no = "2600001B"
address = "{FAKE_ADDRESS}"
tasks = []
[[case.lookup.search_rows]]
pln = "pln_10001"
client_ref_no = "2600001B"
company = "B1 Homes"
"""

# The pre-2.6 shape: hand-split address fields, no MySys Address string.
OLD_CASE = f"""
[[case]]
pdf = "2600001B_048_1.pdf"
{NOTE}
expect = "PROCEED"
expect_reason = ""
[case.lookup]
project_matches = 1
pln = "pln_10001"
lot = "123"
street = "Sample Lane"
suburb = "Sampleville"
existing_compaction_po = []
"""


def test_a_clean_fake_po_proceeds_and_the_report_holds_no_value(tmp_path) -> None:
    folder = fake_private(tmp_path / "private", MYSYS_CASE)
    results = evaluate(folder)
    assert [r.case_id for r in results] == ["real-1"]
    assert isinstance(results[0].result, Proceed)
    assert results[0].result.pln == "pln_10001"
    assert false_proceeds(results) == 0
    report = "\n".join(report_lines(results))
    assert "false PROCEED: 0" in report
    assert "coverage: 1 of 1 clean POs PROCEED" in report
    assert "field issuer: agree 1, disagree 0" in report
    assert "field address check: agree 1, disagree 0" in report
    for value in ("Sample", "Lot 123", "pln_10001", "2600001B", "B1 Homes"):
        assert value not in report


def test_a_proceed_the_case_doesnt_expect_is_a_false_proceed(tmp_path) -> None:
    wrong_pln = MYSYS_CASE.replace('expect_pln = "pln_10001"', 'expect_pln = "pln_1"')
    folder = fake_private(tmp_path / "a", wrong_pln)
    assert false_proceeds(evaluate(folder)) == 1
    skip = MYSYS_CASE.replace(
        'expect = "PROCEED"\nexpect_reason = ""',
        'expect = "SKIP"\nexpect_reason = "ADDRESS_MISMATCH"',
    )
    folder = fake_private(tmp_path / "b", skip)
    results = evaluate(folder)
    assert false_proceeds(results) == 1
    assert "false PROCEED: 1" in report_lines(results)


def test_a_skip_is_reported_with_its_reason_and_case_id_only(tmp_path) -> None:
    moved = MYSYS_CASE.replace(FAKE_ADDRESS, "Lot 124 Sample Lane Sampleville WA")
    results = evaluate(fake_private(tmp_path / "private", moved))
    lines = report_lines(results)
    assert "case real-1: SKIP ADDRESS_MISMATCH (expected PROCEED)" in lines
    assert "coverage: 0 of 1 clean POs PROCEED" in lines
    assert "false PROCEED: 0" in lines


def test_an_old_shape_lookup_is_read_but_not_decided(tmp_path) -> None:
    results = evaluate(fake_private(tmp_path / "private", OLD_CASE))
    assert [r.mysys_shape for r in results] == [False]
    assert results[0].result is None
    lines = report_lines(results)
    assert "case real-1: not decided (lookup not in the MySys shape)" in lines
    assert "decided: 0 of 1" in lines
    assert "field issuer: agree 1, disagree 0" in lines
    assert "field address check: agree 0, disagree 0" in lines


def test_a_trial_po_is_named_by_its_internal_number(tmp_path) -> None:
    trial = TRIAL_INTERNAL_NOS[0]
    folder = fake_private(tmp_path / "private", OLD_CASE.replace("2600001B", trial))
    (folder / "pdfs" / "2600001B_048_1.pdf").rename(
        folder / "pdfs" / f"{trial}_048_1.pdf"
    )
    lines = report_lines(evaluate(folder))
    assert f"case {trial}: not decided (lookup not in the MySys shape)" in lines
    missing = ", ".join(TRIAL_INTERNAL_NOS[1:])
    assert f"cases: 1 (recent real 0 of 3, trial 1 of 3; trial missing: {missing})" in (
        lines
    )


def test_a_missing_pdf_is_an_error(tmp_path) -> None:
    folder = fake_private(tmp_path / "private", MYSYS_CASE)
    (folder / "pdfs" / "2600001B_048_1.pdf").unlink()
    with pytest.raises(FileNotFoundError):
        evaluate(folder)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('expect_reason = ""', 'expect_reason = "Lot 123 Sample Lane"'),
        ('expect = "PROCEED"', 'expect = "Lot 123 Sample Lane"'),
    ],
    ids=["reason", "expect"],
)
def test_an_expectation_that_isnt_an_enum_value_fails_without_printing_it(
    tmp_path, old: str, new: str
) -> None:
    # Review, 2.6: expect and expect_reason reach the printed report.
    folder = fake_private(tmp_path / "private", MYSYS_CASE.replace(old, new))
    with pytest.raises(ValueError) as error:
        evaluate(folder)
    assert str(error.value) == "case real-1: expect or expect_reason not valid"


def test_an_odd_pdf_name_is_decided_not_an_error(tmp_path) -> None:
    # Review, 2.6: a name that isn't <no>_048[_n].pdf skips like any other.
    odd = "2600001B_048_1 copy.pdf"
    folder = fake_private(
        tmp_path / "private",
        MYSYS_CASE.replace('pdf = "2600001B_048_1.pdf"', f'pdf = "{odd}"'),
    )
    (folder / "pdfs" / "2600001B_048_1.pdf").rename(folder / "pdfs" / odd)
    results = evaluate(folder)
    assert [r.case_id for r in results] == ["real-1"]
    assert "case real-1: SKIP PO_MISMATCH (expected PROCEED)" in report_lines(results)
    assert false_proceeds(results) == 0


# --- offline: no private/, and the failure-report scrub ---

LEAKY_TESTS = f"""
import pytest

pytestmark = pytest.mark.real_data
ADDRESS = {FAKE_ADDRESS!r}


def test_needs_private(real_po_dir):
    pass


def test_assert_leak():
    assert ADDRESS == "something else"


def test_raise_leak():
    raise ValueError(ADDRESS)
"""

PYTEST_INI = """[pytest]
markers =
    real_data: reads real POs from private/
"""


def run_pytest(folder: Path, *args: str) -> subprocess.CompletedProcess:
    """pytest in a throwaway folder with seam 1's conftest, private/ absent."""
    for name in ("conftest.py", "seam1_cases.py", "real_pos.py"):
        shutil.copy(SEAM1 / name, folder / name)
    (folder / "fixtures").mkdir(exist_ok=True)
    shutil.copy(SEAM1 / "fixtures" / "cases.toml", folder / "fixtures" / "cases.toml")
    (folder / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    (folder / "test_leaky.py").write_text(LEAKY_TESTS, encoding="utf-8")
    env = dict(os.environ, SEAM1_PRIVATE_DIR=str(folder / "absent"))
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(folder), *args, "-p"]
        + ["no:cacheprovider", "-rA", "-v", "--rootdir", str(folder)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=folder,
        env=env,
        timeout=120,
    )


def test_without_private_a_real_data_test_is_skipped(tmp_path) -> None:
    result = run_pytest(tmp_path, "-k", "needs_private")
    assert "SKIPPED" in result.stdout
    assert "private/ not found" in result.stdout
    assert result.returncode == 0


def test_an_explicit_real_data_run_without_private_is_an_error(tmp_path) -> None:
    result = run_pytest(tmp_path, "-m", "real_data", "-k", "needs_private")
    assert "ERROR test_leaky.py::test_needs_private" in result.stdout
    assert "skipped" not in result.stdout.lower()
    assert "test_leaky.py::test_needs_private: PrivateDirMissing" in result.stdout


def test_real_data_failures_show_only_the_test_name_and_exception_type(
    tmp_path,
) -> None:
    result = run_pytest(tmp_path, "-m", "real_data", "-k", "assert_leak or raise_leak")
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Sample Lane" not in output
    assert "Lot 123" not in output
    assert "test_leaky.py::test_assert_leak: AssertionError" in output
    assert "test_leaky.py::test_raise_leak: ValueError" in output
