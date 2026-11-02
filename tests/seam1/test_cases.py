"""The seam-1 cases themselves (task 2.1): complete, fake and consistent.

The decision engine runs these cases from task 2.2 on; here they are checked
against the spec's table, the fake-value rule and step 0, which exists.
"""

import io
import re
import tomllib

import pdfplumber
import pytest
from seam1_cases import (
    CASES,
    CASES_FILE,
    COVERAGE,
    POOL,
    Seam1Case,
    _build,
    pdf_bytes,
)

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import eligible_internal_no
from po_agent.b1.models import Proceed
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


def test_proceed_cases_read_in_both_layouts(seam1_case: Seam1Case) -> None:
    # Each reader's own layout (fixtures/cases.toml header): a PROCEED must
    # hold with pypdf's columns read apart, not only on a copy of pdfplumber's.
    if seam1_case.expect.result == "proceed":
        assert seam1_case.pypdf_text != seam1_case.pdf_text
        assert "Job Address:" in seam1_case.pypdf_text


def test_a_replace_text_missing_from_a_reader_fails_the_load() -> None:
    raw = tomllib.loads(CASES_FILE.read_text(encoding="utf-8"))
    case = {
        "id": "x",
        "base": "p1",
        "covers": [],
        "pdf_replace": [["Unit 1, 2 Supplier Road Supplierton WA Sample", "y"]],
        "expect": {"result": "untouched"},
    }
    with pytest.raises(ValueError, match="pdf_replace not in pypdf_text"):
        _build(case, raw["po"])


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


def test_no_pdf_is_committed_in_the_fixture_folder() -> None:
    # The repo-data rule allows any PDF there; with no generator, none belongs.
    folder = CASES_FILE.parent / "pdfs"
    assert [p.name for p in folder.rglob("*") if p.suffix.lower() == ".pdf"] == []
