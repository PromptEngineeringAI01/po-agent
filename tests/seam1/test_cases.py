"""The seam-1 cases themselves (task 2.1): complete, fake and consistent.

The decision engine runs these cases from task 2.2 on; here they are checked
against the spec's table, the fake-value rule and step 0, which exists.
"""

import io
import re

import pdfplumber
import pytest
from seam1_cases import CASES, CASES_FILE, COVERAGE, POOL, Seam1Case, pdf_bytes

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import eligible_internal_no
from po_agent.b1.models import Proceed, SkipReason
from po_agent.core.errors import WriteNotStarted

FAKE_INTERNAL_NO = re.compile(r"26000[0-9]{2}[A-Z]")
TRIAL_VALUES = ("2609017B", "2609034B", "2610002B", "pln_669")


def test_every_seam1_row_is_covered() -> None:
    covered = {key for case in CASES for key in case.covers}
    assert sorted(set(COVERAGE) - covered) == []


def test_cases_cover_only_known_rows() -> None:
    covered = {key for case in CASES for key in case.covers}
    assert sorted(covered - set(COVERAGE)) == []


def test_case_ids_are_unique() -> None:
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids))


def test_no_trial_po_value_in_the_cases() -> None:
    text = CASES_FILE.read_text(encoding="utf-8")
    assert [value for value in TRIAL_VALUES if value in text] == []


def test_every_internal_number_is_fake() -> None:
    text = CASES_FILE.read_text(encoding="utf-8")
    numbers = set(re.findall(r"\b2[0-9]{6}[A-Za-z]\b", text))
    assert numbers and all(FAKE_INTERNAL_NO.fullmatch(n.upper()) for n in numbers)
    assert set(re.findall(r"pln_[0-9]+", text)) <= {
        f"pln_100{n:02}" for n in range(100)
    }


def test_deterministic_only_never_proceeds(seam1_case: Seam1Case) -> None:
    # Concern C4: no deterministic address extractor yet.
    assert seam1_case.expect_deterministic_only.result != "proceed"


def test_deterministic_only_matches_hybrid_before_claude(seam1_case: Seam1Case) -> None:
    hybrid, deterministic = seam1_case.expect, seam1_case.expect_deterministic_only
    if hybrid.result == "untouched":
        assert deterministic.result == "untouched"
    elif hybrid.reason in {
        SkipReason.NOTE_ALREADY_LINKED,
        SkipReason.NO_PDF,
        SkipReason.MULTIPLE_PDFS,
        SkipReason.PDF_UNREADABLE,
        SkipReason.NOT_B1,
        SkipReason.NOT_COMPACTION,
        SkipReason.PO_MISMATCH,
        SkipReason.PROJECT_NOT_FOUND,
        SkipReason.PROJECT_AMBIGUOUS,
        SkipReason.UNEXPECTED_SCREEN,
    }:
        assert deterministic == hybrid
    else:  # steps 6-10 in hybrid: deterministic-only stops at the address
        assert deterministic.reason is SkipReason.ADDRESS_UNVERIFIABLE


def test_step0_eligibility_matches_the_case(seam1_case: Seam1Case) -> None:
    internal_no = eligible_internal_no(
        seam1_case.pool_row, seam1_case.config.title_rule, POOL
    )
    if seam1_case.expect.result == "untouched":
        assert internal_no is None
    else:
        assert internal_no is not None and FAKE_INTERNAL_NO.fullmatch(internal_no)


def test_expected_proceed_is_a_valid_proceed(seam1_case: Seam1Case) -> None:
    expect = seam1_case.expect
    if expect.result != "proceed":
        return
    assert expect.pln in [row.pln for row in seam1_case.lookup.search_rows]
    assert [n for n in seam1_case.note.attachment_names if n.lower().endswith(".pdf")]
    Proceed(
        note_id=seam1_case.note.note_id,
        internal_no=expect.po_number.split("/")[0],
        pln=expect.pln,
        po_number=expect.po_number,
        email_body=seam1_case.note.body,
        pdf_file_name=seam1_case.note.attachment_names[0],
        pdf_bytes=b"%PDF-stand-in",
        existing_task_nos=expect.existing_task_nos,
    )


def test_injected_text_is_in_the_pdf(seam1_case: Seam1Case) -> None:
    for marker in seam1_case.never_in_output:
        assert marker in seam1_case.pdf_text


def test_proceed_cases_have_a_text_pdf_and_one_attachment(
    seam1_case: Seam1Case,
) -> None:
    if seam1_case.expect.result == "proceed":
        assert seam1_case.pdf == "text"
        assert len(seam1_case.note.attachment_names) == 1


# --- the two cases that need PDF bytes (Joey, 29 Oct 2026: no generator) ---


def test_corrupt_pdf_bytes_are_unreadable() -> None:
    with pytest.raises(WriteNotStarted) as raised:
        rules.pdf_text(pdf_bytes("corrupt"))
    assert raised.value.reason == "PDF_UNREADABLE"


def test_image_only_pdf_has_an_image_and_no_text() -> None:
    data = pdf_bytes("image-only")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        assert len(pdf.pages) == 1
        assert len(pdf.pages[0].images) == 1
    assert rules.pdf_text(data).strip() == ""


def test_pdf_bytes_are_the_same_on_every_call() -> None:
    assert pdf_bytes("image-only") == pdf_bytes("image-only")


def test_text_cases_have_no_pdf_bytes() -> None:
    with pytest.raises(ValueError):
        pdf_bytes("text")
