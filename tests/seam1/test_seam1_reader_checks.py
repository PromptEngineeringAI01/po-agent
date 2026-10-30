"""Seam 1, steps 2a-4 (task 2.2): the Note window, the attachment and the
deterministic read, in docs/specs/spec.md section 2 order.

`check_note_and_pdf()` is what `decide()` runs before the project lookup; it
returns a Skip or what the later steps need (the deterministic reading, the
PDF's file name and the email body). Lean fakes (Joey, 29 Oct 2026): a text
case passes its fake text layer; only the corrupt and image-only cases go
through pdfplumber, on bytes built in seam1_cases.
"""

import pytest
from seam1_cases import POOL, Seam1Case, pdf_bytes

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import NoteChecked, check_note_and_pdf, eligible_internal_no
from po_agent.b1.models import DeterministicReading, NoteSnapshot, Skip, SkipReason

STEPS_2A_TO_4 = {
    SkipReason.NOTE_ALREADY_LINKED,
    SkipReason.NO_PDF,
    SkipReason.MULTIPLE_PDFS,
    SkipReason.PDF_UNREADABLE,
    SkipReason.NOT_B1,
    SkipReason.NOT_COMPACTION,
    SkipReason.PO_MISMATCH,
}
ISSUER = "B1 Homes Pty Ltd"

# A clean fake PO (values fake), in the layout of tests/seam1/fixtures.
PDF_TEXT = """B1 Homes Pty Ltd
1 Builder Way
Purchase Order No 2600001B/048
Order Type: COMPACTION TEST Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00"""
FILE_NAME = "2600001B_048_1.pdf"
BODY = f"Please find attached Purchase Order / Quotation file {FILE_NAME}"


def note(**changes: object) -> NoteSnapshot:
    values: dict[str, object] = {
        "note_id": "1001",
        "title": BODY,
        "body": BODY,
        "attachment_names": (FILE_NAME,),
        "project_linked": False,
    }
    values.update(changes)
    return NoteSnapshot.model_validate(values)


def checked(
    snapshot: NoteSnapshot | None = None,
    text: str = PDF_TEXT,
    internal_no: str = "2600001B",
) -> Skip | NoteChecked:
    return check_note_and_pdf(snapshot or note(), internal_no, text)


def skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


def case_text(case: Seam1Case) -> str:
    if case.pdf in ("corrupt", "image-only"):
        return rules.text_layer(pdf_bytes(case.pdf))
    return case.pdf_text


# --- every seam-1 case, both reader modes ---


def test_seam1_case_steps_2a_to_4(seam1_case: Seam1Case) -> None:
    internal_no = eligible_internal_no(
        seam1_case.pool_row, seam1_case.config.title_rule, POOL
    )
    if internal_no is None:  # step 0: untouched, never opened
        assert seam1_case.expect.result == "untouched"
        return
    result = check_note_and_pdf(seam1_case.note, internal_no, case_text(seam1_case))
    for expect in (seam1_case.expect, seam1_case.expect_deterministic_only):
        if expect.reason in STEPS_2A_TO_4:
            assert result == Skip(reason=expect.reason)
        else:  # skips later, or proceeds: steps 2a-4 pass
            assert isinstance(result, NoteChecked)


def test_seam1_reading_agrees_with_claude_on_proceed_cases(
    seam1_case: Seam1Case,
) -> None:
    # The four fields step 7 compares must come out identical on a clean PO.
    if seam1_case.expect.result != "proceed":
        return
    internal_no = eligible_internal_no(
        seam1_case.pool_row, seam1_case.config.title_rule, POOL
    )
    assert internal_no is not None
    result = check_note_and_pdf(seam1_case.note, internal_no, seam1_case.pdf_text)
    assert isinstance(result, NoteChecked)
    fields = ("issuer", "contains_compaction", "po_number", "client_internal_no")
    for field in fields:
        assert getattr(result.reading, field) == getattr(seam1_case.claude, field)


# --- what a passing Note gives the later steps ---


def test_a_clean_po_gives_its_reading_file_name_and_body() -> None:
    result = checked()
    assert result == NoteChecked(
        internal_no="2600001B",
        pdf_file_name=FILE_NAME,
        email_body=BODY,
        reading=DeterministicReading(
            issuer=ISSUER,
            contains_compaction=True,
            po_number="2600001B/048",
            client_internal_no="2600001B",
            po_from_filename="2600001B/048",
            po_from_title=None,
        ),
    )


def test_the_deterministic_reading_leaves_the_address_empty() -> None:
    result = checked()
    assert isinstance(result, NoteChecked)
    assert (result.reading.site_lot, result.reading.site_street) == ("", "")
    assert result.reading.site_suburb == ""


def test_email_body_is_the_note_body_as_shown_never_the_title() -> None:
    body = f"  Please find attached\n file {FILE_NAME}  "
    result = checked(note(title="[B1 Homes] Order 2600001B/048", body=body))
    assert isinstance(result, NoteChecked)
    assert result.email_body == body


def test_a_live_style_title_po_is_read() -> None:
    result = checked(note(title="[B1 Homes] Order 2600001B/048"))
    assert isinstance(result, NoteChecked)
    assert result.reading.po_from_title == "2600001B/048"


def test_upper_case_pdf_extension_is_a_pdf() -> None:
    result = checked(note(attachment_names=("2600001B_048_1.PDF",)))
    assert isinstance(result, NoteChecked)
    assert result.reading.po_from_filename == "2600001B/048"


# --- step 2a and step 3 ---


def test_a_linked_note_skips() -> None:
    assert checked(note(project_linked=True)) == skip(SkipReason.NOTE_ALREADY_LINKED)


@pytest.mark.parametrize(
    "names",
    [(), ("2600001B_048_1.docx",), ("2600001B_048_1.pdf.txt",), ("2600001B_048_1",)],
)
def test_no_attachment_or_one_that_is_not_a_pdf_skips_no_pdf(
    names: tuple[str, ...],
) -> None:
    assert checked(note(attachment_names=names)) == skip(SkipReason.NO_PDF)


@pytest.mark.parametrize(
    "names",
    [
        (FILE_NAME, "2600001B_048_2.pdf"),
        (FILE_NAME, "photo.jpg"),  # any second attachment, as the link count
        (FILE_NAME, FILE_NAME),
    ],
)
def test_more_than_one_attachment_skips_multiple_pdfs(names: tuple[str, ...]) -> None:
    assert checked(note(attachment_names=names)) == skip(SkipReason.MULTIPLE_PDFS)


# --- step 4: the deterministic read ---


@pytest.mark.parametrize("kind", ["corrupt", "image-only"])
def test_no_text_layer_skips_pdf_unreadable(kind: str) -> None:
    text = rules.text_layer(pdf_bytes(kind))
    assert text.strip() == ""
    assert checked(text=text) == skip(SkipReason.PDF_UNREADABLE)


def test_whitespace_only_text_skips_pdf_unreadable() -> None:
    assert checked(text=" \n\t\n") == skip(SkipReason.PDF_UNREADABLE)


@pytest.mark.parametrize(
    "text",
    [
        PDF_TEXT.replace(ISSUER, "Sample Builders Pty Ltd"),
        # B1 Homes named, but not as the issuer on the first line
        "Sample Builders Pty Ltd\nfor B1 Homes Pty Ltd\n" + PDF_TEXT,
        PDF_TEXT.replace(ISSUER, "B1 Homes"),
    ],
)
def test_an_issuer_other_than_b1_homes_skips_not_b1(text: str) -> None:
    assert checked(text=text) == skip(SkipReason.NOT_B1)


def test_no_compaction_skips_not_compaction() -> None:
    text = PDF_TEXT.replace("COMPACTION", "SURVEY")
    assert checked(text=text) == skip(SkipReason.NOT_COMPACTION)


@pytest.mark.parametrize(
    "text",
    [
        PDF_TEXT.replace("2600001B/048", "2600002B/048"),  # differs from file name
        PDF_TEXT.replace("2600001B/048", "2600001B/023"),
        PDF_TEXT.replace("Purchase Order No", "Order"),  # no PO number
        PDF_TEXT + "\nPurchase Order No 2600009B/048",  # two different PO numbers
    ],
)
def test_a_pdf_po_that_is_not_the_file_names_skips_po_mismatch(text: str) -> None:
    assert checked(text=text) == skip(SkipReason.PO_MISMATCH)


def test_a_live_style_title_po_that_differs_skips_po_mismatch() -> None:
    snapshot = note(title="[B1 Homes] Order 2600002B/048")
    assert checked(snapshot) == skip(SkipReason.PO_MISMATCH)


@pytest.mark.parametrize("name", ["notes.pdf", "2600001B_049_1.pdf", "x_048_1.pdf"])
def test_a_pdf_whose_name_is_not_a_048_po_skips_po_mismatch(name: str) -> None:
    assert checked(note(attachment_names=(name,))) == skip(SkipReason.PO_MISMATCH)


def test_a_po_of_another_internal_number_than_step_0_skips_po_mismatch() -> None:
    # PDF and file name agree on 2600002B, but step 0 read 2600001B.
    name = "2600002B_048_1.pdf"
    text = PDF_TEXT.replace("2600001B/048", "2600002B/048")
    result = checked(note(attachment_names=(name,)), text=text)
    assert result == skip(SkipReason.PO_MISMATCH)


# --- section 2 order: the first failing step decides ---


@pytest.mark.parametrize(
    ("snapshot", "text", "reason"),
    [
        (note(project_linked=True, attachment_names=()), "", "NOTE_ALREADY_LINKED"),
        (note(attachment_names=()), "", "NO_PDF"),
        (note(attachment_names=(FILE_NAME, FILE_NAME)), "", "MULTIPLE_PDFS"),
        (note(attachment_names=("notes.pdf",)), "", "PDF_UNREADABLE"),
        (note(), "Sample Builders Pty Ltd\nno order here", "NOT_B1"),
        (note(), "B1 Homes Pty Ltd\nPurchase Order No 2600002B/048", "NOT_COMPACTION"),
    ],
)
def test_checks_run_in_section_2_order(
    snapshot: NoteSnapshot, text: str, reason: str
) -> None:
    assert checked(snapshot, text=text) == skip(SkipReason(reason))
