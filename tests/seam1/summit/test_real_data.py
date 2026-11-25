"""Summit's real-PO seam (task 9.10; SPEC.md -> Summit testing and go-live,
Real-PO seam; Summit real data): Joey's real Summit POs through both code
readers and `summit.decision.decide()`, laptop only.

`-m real_data` reads <private>/summit/pdfs/ and
<private>/summit/fixtures/cases.toml (the main checkout's private/, or
SEAM1_PRIVATE_DIR): one `[[case]]` per PDF, 9.7's schema widened (one
schema, `summit_real_pos.py` says each field). The report is field names,
counts, an outcome per case id (summit-1, summit-2, ...) and
`false PROCEED: N`: never a value from a PDF, a Note or MySys. Without
cases.toml (S.0 not done) the real tests skip, never pass; without the
folder, `-m real_data` is an error.

The unmarked tests run offline (CI too) on a fake private/ folder with fake
values only (SPEC -> Summit real data).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from seam1_cases import text_pdf
from summit_real_pos import SeamRun, evaluate_cases, false_proceeds, seam_report_lines

from po_agent.summit.models import SummitProceed

SUMMIT = Path(__file__).resolve().parent

# --- the real POs (laptop only) ---


@pytest.mark.real_data
def test_no_false_proceed_on_the_real_summit_pos(summit_real_seam: SeamRun) -> None:
    assert summit_real_seam.cases
    assert false_proceeds(summit_real_seam.cases) == 0


@pytest.mark.real_data
def test_every_real_summit_pdf_has_a_case(summit_real_seam: SeamRun) -> None:
    """Plan 9.10: the seam runs on all 11, so no PDF goes unexamined."""
    assert summit_real_seam.pdfs_without_case == 0


# --- offline: a fake private/ folder ---

PO_1, NAME_1 = "123456/020/01", "FAKE_SENDER-123456_020_01.pdf"
# A second PO on the same project (one Client Ref No.): SPEC keeps the
# second skipping DUPLICATE_TASK once the first is booked.
PO_2, NAME_2 = "123456/020/02", "FAKE_SENDER-123456_020_02.pdf"
PO_3, NAME_3 = "654321/030/02", "FAKE_SENDER-654321_030_02.pdf"


def fake_pdf(po: str, item: str = "COMPACTION TEST") -> bytes:
    return text_pdf(
        [
            "Summit Homes Group",
            f"Purchase Order No: {po}",
            "DESCRIPTION Supplier Code Quantity Unit Unit Price Total",
            f"{item} 1.000 EA 99.00 99.00",
            "Sub Total: $99.00",
        ]
    )


PDFS = {
    NAME_1: fake_pdf(PO_1),
    NAME_2: fake_pdf(PO_2),
    NAME_3: fake_pdf(PO_3, item="SITE CLEAN"),
}


def fake_private(root: Path, cases: str, names: tuple[str, ...]) -> Path:
    """<root>/summit with the named fake PDFs and the given cases.toml."""
    folder = root / "summit"
    (folder / "pdfs").mkdir(parents=True)
    for name in names:
        (folder / "pdfs" / name).write_bytes(PDFS[name])
    (folder / "fixtures").mkdir()
    (folder / "fixtures" / "cases.toml").write_text(cases, encoding="utf-8")
    return folder


def note(name: str, po: str) -> str:
    return f"""
[[case]]
pdf = "{name}"
expect_compaction = true
note_title = "Summit Homes Group - Lot 1 Fake Street Fakeville - PO: {po} - READY"
note_body = "Fake order table line\\nFake Disclaimer"
original_assignee = "Fake Admin One"
"""


LOOKUP = """
[case.lookup]
more_pages = false
project_internal_no = "123456"
[[case.lookup.search_rows]]
pln = "pln_20001"
client_ref_no = "123456"
company = "Summit Homes Group"
[[case.lookup.project_tasks]]
task_no = "tsk_300001"
name = "Site Start"
status = "Complete"
task_creator = "Fake Staff One"
"""

EXPECT_PROCEED = """expect = "PROCEED"
expect_reason = ""
expect_pln = "pln_20001"
expect_creator = "Compactions"
"""
CLEAN = note(NAME_1, PO_1) + EXPECT_PROCEED + LOOKUP

# The same project once the first PO is booked: its Compaction Test task
# shows, not Cancelled.
BOOKED_TASK = """[[case.lookup.project_tasks]]
task_no = "tsk_300002"
name = "Compaction Test"
status = "On Hold"
task_creator = "Compactions"
"""
SECOND = (
    note(NAME_2, PO_2)
    + """expect = "SKIP"
expect_reason = "DUPLICATE_TASK"
"""
    + LOOKUP
    + BOOKED_TASK
)

# Not a compaction PO: decided before the project lookup, so it needs none.
NOT_COMPACTION = note(NAME_3, PO_3).replace(
    "expect_compaction = true", "expect_compaction = false"
) + (
    """expect = "SKIP"
expect_reason = "NOT_COMPACTION"
"""
)


def test_the_cases_are_decided_and_the_report_holds_no_value(tmp_path) -> None:
    folder = fake_private(
        tmp_path, CLEAN + SECOND + NOT_COMPACTION, (NAME_1, NAME_2, NAME_3)
    )
    run = evaluate_cases(folder)
    assert isinstance(run.cases[0].result, SummitProceed)
    assert seam_report_lines(run) == [
        "summit cases: 3, PDFs without a case: 0",
        "field company: agree 3, disagree 0",
        "field po number: agree 3, disagree 0",
        "field compaction: agree 3, disagree 0",
        "case summit-1: PROCEED (expected PROCEED)",
        "case summit-2: SKIP DUPLICATE_TASK (expected SKIP DUPLICATE_TASK)",
        "case summit-3: SKIP NOT_COMPACTION (expected SKIP NOT_COMPACTION)",
        "as expected: 3 of 3",
        "coverage: 1 of 1 clean POs PROCEED",
        "false PROCEED: 0",
    ]
    report = "\n".join(seam_report_lines(run))
    for value in ("123456", "654321", "pln_", "tsk_", "Fake", "Summit Homes", "FAKE"):
        assert value not in report


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            'expect = "PROCEED"\nexpect_reason = ""',
            'expect = "SKIP"\nexpect_reason = "DUPLICATE_TASK"',
        ),
        ('expect_pln = "pln_20001"', 'expect_pln = "pln_20009"'),
        ('expect_creator = "Compactions"', 'expect_creator = "NH Sub Floor"'),
    ],
    ids=["expected-skip", "other-pln", "other-creator"],
)
def test_a_proceed_the_case_doesnt_expect_is_a_false_proceed(
    tmp_path, old: str, new: str
) -> None:
    assert old in CLEAN
    run = evaluate_cases(fake_private(tmp_path, CLEAN.replace(old, new), (NAME_1,)))
    assert false_proceeds(run.cases) == 1
    lines = seam_report_lines(run)
    assert "false PROCEED: 1" in lines
    assert "as expected: 0 of 1" in lines


def test_a_proceed_with_another_po_than_the_file_names_is_a_false_proceed(
    tmp_path,
) -> None:
    # The PDF and the title agree on PO_1; Joey's saved file is named for
    # another PO of the project, so the PO written would not be the file's.
    other = "FAKE_SENDER-123456_020_09.pdf"
    folder = fake_private(tmp_path, CLEAN.replace(NAME_1, other), ())
    (folder / "pdfs" / other).write_bytes(PDFS[NAME_1])
    run = evaluate_cases(folder)
    assert false_proceeds(run.cases) == 1


def test_a_skip_the_case_doesnt_expect_is_reported_not_judged(tmp_path) -> None:
    other_company = CLEAN.replace(
        'company = "Summit Homes Group"', 'company = "Fake Builders"'
    )
    run = evaluate_cases(fake_private(tmp_path, other_company, (NAME_1,)))
    lines = seam_report_lines(run)
    assert "case summit-1: SKIP PROJECT_NOT_FOUND (expected PROCEED)" in lines
    assert "as expected: 0 of 1" in lines
    assert "coverage: 0 of 1 clean POs PROCEED" in lines
    assert "false PROCEED: 0" in lines


def test_two_cases_expecting_proceed_on_one_project_is_an_error(tmp_path) -> None:
    """SPEC: the second PO of a project skips DUPLICATE_TASK once the first
    is booked, so expected results can't book one project twice."""
    both = CLEAN + note(NAME_2, PO_2) + EXPECT_PROCEED + LOOKUP
    folder = fake_private(tmp_path, both, (NAME_1, NAME_2))
    with pytest.raises(ValueError) as error:
        evaluate_cases(folder)
    assert str(error.value) == (
        "cases summit-1 and summit-2: both expect PROCEED on one project"
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('expect_reason = ""', 'expect_reason = "Lot 1 Fake Street"'),
        ('expect = "PROCEED"', 'expect = "Lot 1 Fake Street"'),
        ('expect_creator = "Compactions"\n', ""),
        ('expect_pln = "pln_20001"\n', ""),
    ],
    ids=["reason", "expect", "no-creator", "no-pln"],
)
def test_an_expectation_that_isnt_valid_fails_without_printing_it(
    tmp_path, old: str, new: str
) -> None:
    assert old in CLEAN
    folder = fake_private(tmp_path, CLEAN.replace(old, new), (NAME_1,))
    with pytest.raises(ValueError) as error:
        evaluate_cases(folder)
    assert str(error.value) == "case summit-1: expected result not valid"


def test_a_case_whose_decision_needs_a_lookup_without_one_is_an_error(
    tmp_path,
) -> None:
    no_lookup = CLEAN.split("[case.lookup]", 1)[0]
    folder = fake_private(tmp_path, no_lookup, (NAME_1,))
    with pytest.raises(ValueError) as error:
        evaluate_cases(folder)
    assert str(error.value) == "case summit-1: decide() needs its [case.lookup]"


def test_a_pdf_without_a_case_is_counted(tmp_path) -> None:
    run = evaluate_cases(fake_private(tmp_path, CLEAN, (NAME_1, NAME_3)))
    assert run.pdfs_without_case == 1
    assert "summit cases: 1, PDFs without a case: 1" in seam_report_lines(run)


def test_a_case_whose_pdf_is_missing_is_an_error(tmp_path) -> None:
    folder = fake_private(tmp_path, CLEAN, ())
    with pytest.raises(FileNotFoundError):
        evaluate_cases(folder)


# --- offline: no cases.toml yet, no folder ---


def _pytest(env_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SEAM1_PRIVATE_DIR": str(env_dir)}
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(SUMMIT / "test_real_data.py")]
        + ["-m", "real_data", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_without_cases_it_skips_and_without_the_folder_it_is_an_error(
    tmp_path,
) -> None:
    pdfs = tmp_path / "with-pdfs" / "summit" / "pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / NAME_1).write_bytes(PDFS[NAME_1])
    no_cases = _pytest(tmp_path / "with-pdfs")
    assert "2 skipped" in no_cases.stdout
    assert "passed" not in no_cases.stdout
    no_folder = _pytest(tmp_path / "absent")
    assert no_folder.returncode != 0
    assert "FileNotFoundError" in no_folder.stdout
