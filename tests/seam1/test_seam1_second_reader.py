"""The second code reader (decisions, 2 Nov 2026): pypdf reads the PDF's text
again, and its reading must equal pdfplumber's.

`reader_rules.pypdf_text_layer()` is pypdf's text, "" when pypdf can't read
the bytes. `check_second_reader()` compares the two texts: issuer (the first
non-empty line), COMPACTION, the one PO number and the Job Address label line
(normalised) must be equal, else READERS_DISAGREE; no pypdf text is
PDF_UNREADABLE. The line under the label is left to the address check, which
runs on both texts: pypdf reads the Supplier column apart from it.
"""

import pytest
from seam1_cases import pdf_bytes, text_pdf

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import check_second_reader
from po_agent.b1.models import Skip, SkipReason

# pdfplumber's layout: the Job Address block shares its lines with Supplier.
PLUMBER = """B1 Homes Pty Ltd
1 Builder Way
Purchase Order No 2600001B/048
Supplier: Example Compaction Pty Ltd Job Address: Lot 123
Unit 1, 2 Supplier Road Supplierton WA Sample Lane Sampleville WA
Order Type: COMPACTION TEST Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00"""
# pypdf's layout of the same PDF: the columns apart.
PYPDF = """B1 Homes Pty Ltd
1 Builder Way
Purchase Order No 2600001B/048
Supplier: Example Compaction Pty Ltd
Unit 1, 2 Supplier Road Supplierton WA
Job Address: Lot 123
Sample Lane Sampleville WA
Order Type: COMPACTION TEST
Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00"""
LINES = [
    "B1 Homes Pty Ltd",
    "Purchase Order No 2600001B/048",
    "Job Address: Lot 123",
    "Sample Lane Sampleville WA",
    "Order Type: COMPACTION TEST",
]


def skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


# --- pypdf's text ---


def test_pypdf_reads_a_text_pdf() -> None:
    text = rules.pypdf_text_layer(text_pdf(LINES))
    assert [line.strip() for line in text.splitlines() if line.strip()] == LINES


def test_both_libraries_read_a_text_pdf_alike() -> None:
    data = text_pdf(LINES)
    assert (
        check_second_reader(rules.text_layer(data), rules.pypdf_text_layer(data))
        is None
    )


@pytest.mark.parametrize("kind", ["corrupt", "image-only"])
def test_no_text_layer_reads_as_empty(kind: str) -> None:
    assert rules.pypdf_text_layer(pdf_bytes(kind)).strip() == ""


@pytest.mark.parametrize("data", [b"", b"not a pdf", b"%PDF-1.4\n%%EOF\n"])
def test_bytes_pypdf_cannot_read_are_empty_never_an_error(data: bytes) -> None:
    assert rules.pypdf_text_layer(data) == ""


def test_pypdf_prints_nothing_on_a_broken_pdf(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # pypdf logs warnings ("EOF marker not found"); only output.py prints.
    rules.pypdf_text_layer(pdf_bytes("corrupt"))
    rules.pypdf_text_layer(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n")
    assert capsys.readouterr() == ("", "")


# --- the agreement ---


def test_the_two_layouts_of_one_pdf_agree() -> None:
    assert check_second_reader(PLUMBER, PYPDF) is None


def test_identical_texts_agree() -> None:
    assert check_second_reader(PLUMBER, PLUMBER) is None


@pytest.mark.parametrize("pypdf", ["", " \n\t\n"])
def test_no_pypdf_text_is_pdf_unreadable(pypdf: str) -> None:
    assert check_second_reader(PLUMBER, pypdf) == skip(SkipReason.PDF_UNREADABLE)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        # issuer: the first non-empty line, exactly
        ("B1 Homes Pty Ltd", "B1 HOMES PTY LTD"),
        ("B1 Homes Pty Ltd", "B1 Homes Pty. Ltd"),
        ("B1 Homes Pty Ltd\n1 Builder Way", "B1 Homes Pty Ltd 1 Builder Way"),
        ("B1 Homes Pty Ltd\n", "Sample Builders Pty Ltd\nB1 Homes Pty Ltd\n"),
        # COMPACTION
        ("COMPACTION", "C0MPACTION"),
        # the one PO number
        ("2600001B/048", "2600001B/049"),
        ("2600001B/048", "2600001b/048"),
        ("Purchase Order No 2600001B/048", "Order 2600001B/048"),
        ("1 Builder Way", "1 Builder Way\nPurchase Order No 2600009B/048"),
        # the Job Address label line
        ("Job Address: Lot 123", "Job Address: Lot 128"),
        ("Job Address: Lot 123", "Job Address: Lot 123 Sample Lane"),
        ("Job Address: Lot 123", "Job Address: Lot 12-3"),
        ("Job Address: Lot 123", "Site: Lot 123"),
        ("Job Address: Lot 123", "Job Address: Lot 123\nJob Address: Lot 123"),
    ],
)
def test_any_difference_in_pypdfs_reading_is_readers_disagree(
    old: str, new: str
) -> None:
    pypdf = PYPDF.replace(old, new)
    assert pypdf != PYPDF
    assert check_second_reader(PLUMBER, pypdf) == skip(SkipReason.READERS_DISAGREE)


def test_the_comparison_is_symmetric() -> None:
    plumber = PLUMBER.replace("Lot 123", "Lot 128")
    assert check_second_reader(plumber, PYPDF) == skip(SkipReason.READERS_DISAGREE)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Job Address: Lot 123", "Job Address:  LOT 123 "),  # case, spaces
        ("Job Address: Lot 123", "Job Address: Lot 123."),  # punctuation
        ("B1 Homes Pty Ltd", "  B1 Homes Pty Ltd  "),  # the line is trimmed
        ("B1 Homes Pty Ltd", "\n\nB1 Homes Pty Ltd"),  # blank lines first
    ],
)
def test_case_space_and_punctuation_in_layout_alone_agree(old: str, new: str) -> None:
    assert check_second_reader(PLUMBER, PYPDF.replace(old, new, 1)) is None


def test_the_line_under_the_label_is_not_compared() -> None:
    # pypdf leaves the Supplier column out of it; the address check reads it.
    pypdf = PYPDF.replace("Sample Lane Sampleville WA", "Sample Road Sampleville WA")
    assert check_second_reader(PLUMBER, pypdf) is None


def test_no_label_in_either_text_agrees() -> None:
    # Then the address check skips ADDRESS_UNVERIFIABLE on both texts.
    plumber = PLUMBER.replace("Job Address:", "Site:")
    pypdf = PYPDF.replace("Job Address:", "Site:")
    assert check_second_reader(plumber, pypdf) is None
