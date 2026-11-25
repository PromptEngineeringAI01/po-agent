"""Summit's readers on Joey's real Summit POs (task 9.7; laptop only).

`-m real_data`: reads private/summit/pdfs/ in the main checkout (or under
SEAM1_PRIVATE_DIR), never in CI. On each PDF both readers agree on all three
fields and the PDF's PO equals its file name's (a reader cross-check only:
decide() compares the title's PO, SPEC). The compaction finding must equal
Joey's expected value for every PDF once private/summit/fixtures/cases.toml
exists (S.0); until then that test skips, never passes. The counts print in
the terminal summary; a failure shows the test name and exception type only
(the real_data scrub in tests/seam1/real_pos.py).

The unmarked tests run offline (CI too) on a fake folder: the skip and error
when the folder is missing, and a report with no value in it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from seam1_cases import text_pdf
from summit_real_pos import Counts, evaluate, report_lines

SUMMIT = Path(__file__).resolve().parent

# --- the real PDFs (laptop only) ---


@pytest.mark.real_data
def test_the_real_summit_pdfs_read_alike_on_both_readers(
    summit_real_counts: Counts,
) -> None:
    counts = summit_real_counts
    assert counts.pdfs > 0
    assert all(agree == counts.pdfs for agree in counts.agree.values())
    assert counts.po_as_file == counts.pdfs
    assert set(counts.outcomes) <= {"READING", "NOT_COMPACTION"}


@pytest.mark.real_data
def test_the_real_summit_compaction_findings_are_joeys(
    summit_real_counts: Counts,
) -> None:
    counts = summit_real_counts
    if counts.expected_given is None:
        pytest.skip("no private/summit/fixtures/cases.toml yet (S.0)")
    assert counts.expected_given == counts.pdfs
    assert counts.as_expected == counts.pdfs


# --- the harness, offline ---

FAKE_PO = "123456/020/01"
FAKE_NAME = "FAKE_SENDER-123456_020_01.pdf"


def _fake_private(root: Path, cases: str | None) -> Path:
    pdfs = root / "summit" / "pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / FAKE_NAME).write_bytes(
        text_pdf(
            [
                "Summit Homes Group",
                f"Purchase Order No: {FAKE_PO}",
                "DESCRIPTION Supplier Code Quantity Unit Unit Price Total",
                "COMPACTION TEST 1.000 EA 99.00 99.00",
                "Sub Total: $99.00",
            ]
        )
    )
    if cases is not None:
        (root / "summit" / "fixtures").mkdir()
        (root / "summit" / "fixtures" / "cases.toml").write_text(
            cases, encoding="utf-8"
        )
    return root / "summit"


def test_the_report_holds_counts_and_no_value(tmp_path: Path) -> None:
    folder = _fake_private(
        tmp_path, f'[[case]]\npdf = "{FAKE_NAME}"\nexpect_compaction = true\n'
    )
    counts = evaluate(folder)
    assert (
        counts.pdfs,
        counts.po_as_file,
        counts.expected_given,
        counts.as_expected,
    ) == (
        1,
        1,
        1,
        1,
    )
    report = "\n".join(report_lines(counts))
    for value in (FAKE_PO, "123456", "Summit Homes Group", FAKE_NAME):
        assert value not in report


def test_no_cases_file_is_not_a_compaction_pass(tmp_path: Path) -> None:
    counts = evaluate(_fake_private(tmp_path, None))
    assert counts.expected_given is None
    assert "no cases.toml yet" in "\n".join(report_lines(counts))


def _pytest(env_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SEAM1_PRIVATE_DIR": str(env_dir)}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(SUMMIT / "test_summit_real_pdfs.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_a_missing_folder_skips_and_is_an_error_under_real_data(tmp_path: Path) -> None:
    skipped = _pytest(tmp_path, "-k", "real_summit", "-p", "no:cacheprovider")
    assert "2 skipped" in skipped.stdout
    selected = _pytest(tmp_path, "-m", "real_data", "-p", "no:cacheprovider")
    assert selected.returncode != 0
    assert "FileNotFoundError" in selected.stdout


def test_cases_file_present_requires_every_pdf_expected(tmp_path: Path) -> None:
    _fake_private(
        tmp_path,
        '[[case]]\npdf = "OTHER-654321_030_02.pdf"\nexpect_compaction = true\n',
    )
    run = _pytest(tmp_path, "-m", "real_data", "-p", "no:cacheprovider")
    assert "1 failed, 1 passed" in run.stdout
    assert "Summit real-PDF seam" in run.stdout
