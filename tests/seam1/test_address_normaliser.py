"""Section 4 (tasks 2.4 and 2.5): the normaliser, the project address parse,
the PDF's Job Address block and the address check, fed by the project's
address in MySys (decisions, 2 Nov 2026).

Unit tests of the address rules as a development aid (SPEC.md -> Testing
Strategy). Fake values only.
"""

import pytest

from po_agent.b1.address import (
    ProjectAddress,
    job_address_block,
    job_address_line,
    normalise,
    parse_project_address,
    verify_address,
)
from po_agent.b1.models import SkipReason

PROJECT = "Lot 123 (#45) Sample Lane Sampleville 6000 WA"
# The real B1 layout: the Job Address block shares its lines with the
# Supplier block (decisions, 29 Oct 2026).
PDF_TEXT = """B1 Homes Pty Ltd
Purchase Order No 2600001B/048
Supplier: Example Compaction Pty Ltd Job Address: Lot 123
Unit 1, 2 Supplier Road Supplierton WA Sample Lane Sampleville WA
Supplierton WA 6998
Order Type: COMPACTION TEST Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00
Total $11.00"""
# The same PDF as pypdf reads it: the columns apart (decisions, 2 Nov 2026).
PYPDF_TEXT = """B1 Homes Pty Ltd
Purchase Order No 2600001B/048
Supplier: Example Compaction Pty Ltd
Unit 1, 2 Supplier Road Supplierton WA
Supplierton WA 6998
Job Address: Lot 123
Sample Lane Sampleville WA
Supervisor:
Order Type: COMPACTION TEST
Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00
Total $11.00"""
LOT_12 = "Lot 12 Sample Lane Sampleville 6000 WA"


# --- normalise ---


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sample Lane", "sample lane"),
        ("  SAMPLE   LANE ", "sample lane"),  # case-fold, whitespace collapsed
        ("Sample\tLane\nSampleville", "sample lane sampleville"),
        ("Sample-Lane, Sampleville.", "sample lane sampleville"),  # punctuation
        ("Lot 123 / Sample Lane", "lot 123 sample lane"),
        ("O'Connor Way", "o connor way"),
        ("", ""),
        (" ,./ ", ""),
    ],
)
def test_normalise_case_folds_and_collapses_whitespace_and_punctuation(
    text: str, expected: str
) -> None:
    assert normalise(text) == expected


@pytest.mark.parametrize(
    ("short", "full"),
    [
        ("St", "Street"),
        ("Rd", "Road"),
        ("Ave", "Avenue"),
        ("Dr", "Drive"),
        ("Cres", "Crescent"),
        ("Ct", "Court"),
        ("Pl", "Place"),
        ("Bvd", "Boulevard"),
        ("Pde", "Parade"),
        ("Tce", "Terrace"),
        ("Cl", "Close"),
        ("Hwy", "Highway"),
        ("Ln", "Lane"),
    ],
)
def test_street_type_abbreviations_map_to_one_form(short: str, full: str) -> None:
    assert normalise(f"Example {short}") == normalise(f"Example {full}")
    assert normalise(f"Example {short}.") == normalise(f"EXAMPLE {full.upper()}")


def test_an_abbreviation_maps_only_as_a_whole_word() -> None:
    assert normalise("Stanley Road") == "stanley road"
    assert normalise("Drummond Court") == "drummond court"


def test_only_the_spec_abbreviations_map() -> None:
    # Approved 2.4: no others until the real-PO seam shows a need.
    assert normalise("Example Blvd") != normalise("Example Boulevard")
    assert normalise("Example Wy") != normalise("Example Way")


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("Sample Lane", "Sample Road"),
        ("Sampleville", "Sampleville North"),
        ("Sample Lane", "Sampl Lane"),  # no fuzzy matching
        ("12A", "12B"),
    ],
)
def test_different_names_stay_different(one: str, other: str) -> None:
    assert normalise(one) != normalise(other)


# --- the project address (SPEC.md -> MySys screen rules -> Project address) ---


@pytest.mark.parametrize(
    ("address", "lot", "rest"),
    [
        (PROJECT, "123", "sample lane sampleville"),
        (
            "Lot 12A (#7) Example Street Testdale 6001 WA",
            "12a",
            "example street testdale",
        ),
        ("Lot 303 Demo Road Mockford 6002 WA", "303", "demo road mockford"),
        ("Lot 303 Demo Road Mockford", "303", "demo road mockford"),
        ("Lot 303 Demo Road Mockford 6002", "303", "demo road mockford"),
        ("Lot 303 Demo Road Mockford WA", "303", "demo road mockford"),
        ("Lot 303 Demo Rd Mockford", "303", "demo road mockford"),
        ("  lot 303  (#9)  Demo Road Mockford 6002 wa ", "303", "demo road mockford"),
    ],
)
def test_the_project_address_parses_into_lot_and_rest(
    address: str, lot: str, rest: str
) -> None:
    assert parse_project_address(address) == ProjectAddress(lot=lot, rest=rest)


@pytest.mark.parametrize(
    "address",
    [
        "",
        "123 Sample Lane Sampleville 6000 WA",  # no leading Lot
        "(#45) Lot 123 Sample Lane Sampleville",
        "Sample Lane Lot 123 Sampleville",
        "Lot",  # no lot
        "Lot 123",  # no street or suburb
        "Lot 123 (#45) 6000 WA",
        "Lot 12-A Sample Lane Sampleville",  # the lot is one word of letters
        "Lot 12/13 Sample Lane Sampleville",  # and digits, as in the PDF
    ],
)
def test_a_project_address_without_its_shape_is_unparsed(address: str) -> None:
    assert parse_project_address(address) is None


# --- the PDF's Job Address block ---


def test_the_block_is_the_job_address_field_and_the_line_under_it() -> None:
    block = job_address_block(PDF_TEXT)
    assert block is not None
    assert normalise(block) == normalise(
        "Lot 123 Unit 1, 2 Supplier Road Supplierton WA Sample Lane Sampleville WA"
    )


def test_the_block_on_one_line() -> None:
    text = "Job Address: Lot 123 / Sample Lane Sampleville WA\nUnit 1 Supplierton"
    block = job_address_block(text)
    assert block is not None
    assert normalise(block) == normalise(
        "Lot 123 Sample Lane Sampleville WA Unit 1 Supplierton"
    )


def test_the_block_on_the_last_line() -> None:
    block = job_address_block("B1 Homes Pty Ltd\nJob Address: Lot 123 Sample Lane")
    assert block is not None and normalise(block) == "lot 123 sample lane"


@pytest.mark.parametrize(
    "text",
    [
        "",
        PDF_TEXT.replace("Job Address:", "Site:"),
        PDF_TEXT + "\nJob Address: Lot 77 Sample Lane Sampleville",  # two fields
    ],
)
def test_no_single_job_address_field_is_no_block(text: str) -> None:
    assert job_address_block(text) is None


# --- the label line, which both readers must read alike ---


def test_the_label_line_is_the_text_after_the_label() -> None:
    line = job_address_line(PDF_TEXT)
    assert line is not None and normalise(line) == "lot 123"
    assert job_address_line(PYPDF_TEXT) is not None
    assert normalise(job_address_line(PYPDF_TEXT) or "") == "lot 123"


def test_the_label_line_on_one_line_holds_the_whole_address() -> None:
    line = job_address_line("Job Address: Lot 123 / Sample Lane Sampleville WA")
    assert line is not None
    assert normalise(line) == "lot 123 sample lane sampleville wa"


@pytest.mark.parametrize(
    "text",
    [
        "",
        PDF_TEXT.replace("Job Address:", "Site:"),
        PDF_TEXT + "\nJob Address: Lot 77 Sample Lane Sampleville",  # two labels
        "Job Address\n: Lot 123 Sample Lane Sampleville",  # label over a break
    ],
)
def test_no_single_label_on_one_line_is_no_label_line(text: str) -> None:
    assert job_address_line(text) is None


# --- verify_address: the Job Address block against the project's address ---
# Decisions, 2 Nov 2026: MySys's lot and R are the values; no reader extracts
# an address. ADDRESS_UNVERIFIABLE: the project address or the block can't be
# parsed. ADDRESS_MISMATCH: both parse, but the block doesn't hold the
# project's lot, street and suburb where the rule needs them.


def test_a_clean_address_passes() -> None:
    assert verify_address(PDF_TEXT, PROJECT) is None


def test_pypdfs_layout_passes() -> None:
    # pypdf reads the columns apart: the line under the label is the address.
    assert verify_address(PYPDF_TEXT, PROJECT) is None


def test_the_spec_example_passes() -> None:
    text = "Job Address: Lot 123 / Sample Lane Sampleville WA"
    assert verify_address(text, PROJECT) is None


def test_the_spec_example_passes_above_a_supplier_line() -> None:
    # The fixture's one-line layout: the Supplier text is on the next line.
    text = PDF_TEXT.replace(
        "Job Address: Lot 123\nUnit 1, 2 Supplier Road Supplierton WA"
        " Sample Lane Sampleville WA",
        "Job Address: Lot 123 / Sample Lane Sampleville WA\n"
        "Unit 1, 2 Supplier Road Supplierton WA",
    )
    assert text != PDF_TEXT
    assert verify_address(text, PROJECT) is None


@pytest.mark.parametrize(
    ("pdf_old", "pdf_new", "project"),
    [
        ("Sample Lane", "Sample Ln", PROJECT),
        ("Sample Lane Sampleville", "SAMPLE LANE SAMPLEVILLE", PROJECT),
        ("Lot 123", "LOT 123", PROJECT),
        ("Lot 123", "Lot 12A", "Lot 12a (#7) Sample Lane Sampleville"),
        ("", "", "Lot 123 Sample Ln Sampleville"),
        ("", "", "lot 123 sample lane sampleville"),
    ],
)
def test_normalised_values_pass(pdf_old: str, pdf_new: str, project: str) -> None:
    text = PDF_TEXT.replace(pdf_old, pdf_new) if pdf_old else PDF_TEXT
    assert verify_address(text, project) is None


@pytest.mark.parametrize(
    "tail", ["", " WA", " WA 6000", " 6000", " 6000 WA", ", WA.", " wa 6000"]
)
def test_street_and_suburb_end_the_line_under_the_label(tail: str) -> None:
    text = PDF_TEXT.replace(
        "Sample Lane Sampleville WA", f"Sample Lane Sampleville{tail}"
    )
    assert verify_address(text, PROJECT) is None


# --- ADDRESS_UNVERIFIABLE: something can't be parsed ---


@pytest.mark.parametrize(
    "project",
    [
        "",
        "123 Sample Lane Sampleville 6000 WA",  # no leading Lot
        "Lot 123",  # no street or suburb
        "Lot 12-A Sample Lane Sampleville",  # a lot that isn't one word
        "Lot 12/13 Sample Lane Sampleville",
    ],
)
def test_a_project_address_without_its_shape_is_unverifiable(project: str) -> None:
    assert verify_address(PDF_TEXT, project) is SkipReason.ADDRESS_UNVERIFIABLE


def test_an_unparsed_project_address_is_unverifiable_whatever_the_block() -> None:
    text = PDF_TEXT.replace("Lot 123", "Lot 124")  # would be a mismatch
    project = "123 Sample Lane Sampleville 6000 WA"
    assert verify_address(text, project) is SkipReason.ADDRESS_UNVERIFIABLE


@pytest.mark.parametrize(
    "text",
    [
        "",
        PDF_TEXT.replace("Job Address:", "Site:"),
        PDF_TEXT + "\nJob Address: Lot 123 Sample Lane Sampleville",  # two labels
        "Job Address\n: Lot 123 Sample Lane Sampleville",  # label over a break
        PDF_TEXT.replace("Job Address: Lot 123", "Job Address: Site Lot 123"),
        PDF_TEXT.replace("Job Address: Lot 123", "Job Address:\nLot 123"),
        PDF_TEXT.replace("Job Address: Lot 123", "Job Address: Lot"),
        "B1 Homes Pty Ltd\nJob Address: Lot 123",  # a lone lot, no line under
        "Job Address: Lot 123\n\nSample Lane Sampleville WA",  # blank line under
    ],
)
def test_a_block_without_its_shape_is_unverifiable(text: str) -> None:
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_UNVERIFIABLE


@pytest.mark.parametrize("pdf_lot", ["Lot 12-A", "Lot 12/13", "Lot 12.5", "Lot #12"])
def test_a_pdf_lot_that_is_not_one_word_is_unverifiable(pdf_lot: str) -> None:
    # Finding 1 (30 Oct): "12-A" or "12/13" never passes as lot 12.
    two_lines = PDF_TEXT.replace("Lot 123", pdf_lot)
    one_line = f"Job Address: {pdf_lot} Sample Lane Sampleville WA"
    for text in (two_lines, one_line):
        result = verify_address(text, LOT_12)
        assert result is SkipReason.ADDRESS_UNVERIFIABLE


# --- ADDRESS_MISMATCH: both parse, and differ ---


@pytest.mark.parametrize(
    ("pdf_old", "pdf_new"),
    [
        ("Lot 123", "Lot 124"),
        ("Sample Lane Sampleville WA", "Sample Road Sampleville WA"),
        ("Sample Lane Sampleville WA", "Sample Lane Exampleton WA"),
    ],
)
def test_a_block_value_that_differs_from_the_project_is_a_mismatch(
    pdf_old: str, pdf_new: str
) -> None:
    text = PDF_TEXT.replace(pdf_old, pdf_new)
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_MISMATCH


def test_a_different_lot_letter_is_a_mismatch() -> None:
    text = PDF_TEXT.replace("Lot 123", "Lot 12B")
    project = "Lot 12A (#7) Sample Lane Sampleville 6001 WA"
    assert verify_address(text, project) is SkipReason.ADDRESS_MISMATCH


@pytest.mark.parametrize("lot", ["1", "2", "12"])
def test_the_lot_is_the_whole_word_after_lot_in_the_block(lot: str) -> None:
    # "Unit 1, 2 Supplier Road" is in the block, and 12 starts 123: neither
    # is the block's lot.
    project = f"Lot {lot} Sample Lane Sampleville"
    assert verify_address(PDF_TEXT, project) is SkipReason.ADDRESS_MISMATCH


def test_the_lot_with_a_word_after_it_on_one_line_is_a_mismatch() -> None:
    text = "Job Address: Lot 12 A Sample Lane Sampleville WA"
    assert verify_address(text, LOT_12) is SkipReason.ADDRESS_MISMATCH


def test_a_lot_found_elsewhere_that_matches_the_project_is_a_mismatch() -> None:
    # Concern C15: the project's lot is in the PDF, but not in the block.
    text = PDF_TEXT.replace("test 1 each", "test as for Lot 77 1 each")
    project = "Lot 77 (#45) Sample Lane Sampleville 6000 WA"
    assert verify_address(text, project) is SkipReason.ADDRESS_MISMATCH


def test_the_supplier_street_and_suburb_are_a_mismatch() -> None:
    # Finding 2 (30 Oct): the line under the label also holds the Supplier
    # column in pdfplumber's text.
    project = "Lot 123 Supplier Road Supplierton 6998 WA"
    for text in (PDF_TEXT, PYPDF_TEXT):
        assert verify_address(text, project) is SkipReason.ADDRESS_MISMATCH


def test_street_and_suburb_must_equal_the_whole_rest() -> None:
    # The project's R is longer than what ends the line: no guessing.
    project = "Lot 123 Sample Lane Sampleville North 6000 WA"
    assert verify_address(PDF_TEXT, project) is SkipReason.ADDRESS_MISMATCH


def test_the_address_split_across_the_pdf_is_a_mismatch() -> None:
    text = PDF_TEXT.replace(
        "Supplierton WA Sample Lane Sampleville WA", "Supplierton WA"
    ).replace("Total $11.00", "Total $11.00\nSite: Sample Lane Sampleville WA")
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_MISMATCH


@pytest.mark.parametrize(
    "tail", [" WA Australia", " WA 6000 WA 6000", " 600", " Supplierton WA", " WA X"]
)
def test_anything_else_after_the_suburb_is_a_mismatch(tail: str) -> None:
    text = PDF_TEXT.replace(
        "Sample Lane Sampleville WA", f"Sample Lane Sampleville{tail}"
    )
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_MISMATCH


@pytest.mark.parametrize(
    "line",
    [
        "Job Address: Lot 123 Unit 4 Sample Lane Sampleville WA",  # words between
        "Job Address: Lot 123 Sample Lane Sampleville WA Supplierton",
        "Job Address: Lot 123 Sampleville",
    ],
)
def test_a_one_line_address_must_be_lot_street_suburb(line: str) -> None:
    assert verify_address(line, PROJECT) is SkipReason.ADDRESS_MISMATCH


@pytest.mark.parametrize(
    "project",
    [
        "Lot 123 Sample Lane (#45) Sampleville 6000 WA",
        "Lot 123 Sample Lane Sampleville (#45) 6000 WA",
        "Lot 123 Sample Lane Sampleville 6000 WA (#45)",
    ],
)
def test_a_house_number_not_right_after_the_lot_is_a_mismatch(project: str) -> None:
    # Review nit 1 (2.4): only "Lot <lot> (#n)" is dropped; anywhere else the
    # number stays in R, so the compare fails safe.
    assert verify_address(PDF_TEXT, project) is SkipReason.ADDRESS_MISMATCH


# --- review findings, 2.5 (2 Nov 2026) ---
# 1. pypdf reads the Supplier column apart, so on its text the line under a
#    lone lot must be exactly R plus the tail (exact_line_under=True);
#    pdfplumber's line keeps the suffix rule, and decide() needs both.


def test_pypdfs_line_under_the_label_is_exactly_the_address() -> None:
    assert verify_address(PYPDF_TEXT, PROJECT, exact_line_under=True) is None


@pytest.mark.parametrize(
    "tail", ["", " WA", " WA 6000", " 6000", " 6000 WA", ", WA.", " wa 6000"]
)
def test_the_exact_line_under_takes_the_same_tails(tail: str) -> None:
    text = PYPDF_TEXT.replace(
        "Sample Lane Sampleville WA", f"Sample Lane Sampleville{tail}"
    )
    assert verify_address(text, PROJECT, exact_line_under=True) is None


@pytest.mark.parametrize(
    "line",
    [
        "North Sample Lane Sampleville WA",  # a longer street
        "Lot 999 Sample Lane Sampleville WA",  # another lot before it
        "7 Other St Sample Lane Sampleville WA",  # another street before it
        "Unit 1, 2 Supplier Road Supplierton WA Sample Lane Sampleville WA",
    ],
)
def test_anything_before_the_address_on_the_exact_line_is_a_mismatch(
    line: str,
) -> None:
    text = PYPDF_TEXT.replace("Sample Lane Sampleville WA", line)
    result = verify_address(text, PROJECT, exact_line_under=True)
    assert result is SkipReason.ADDRESS_MISMATCH


def test_a_supplier_street_ending_in_the_projects_street_is_a_mismatch() -> None:
    text = "Job Address: Lot 5\nACME Pty 23 North Main St Perth WA 6000"
    project = "Lot 5 Main Street Perth WA 6000"
    result = verify_address(text, project, exact_line_under=True)
    assert result is SkipReason.ADDRESS_MISMATCH


def test_the_one_line_form_is_exact_in_both_modes() -> None:
    text = "Job Address: Lot 123 / Sample Lane Sampleville WA"
    assert verify_address(text, PROJECT, exact_line_under=True) is None
    longer = "Job Address: Lot 123 North Sample Lane Sampleville WA"
    result = verify_address(longer, PROJECT, exact_line_under=True)
    assert result is SkipReason.ADDRESS_MISMATCH


# 2. R of one word (a suburb alone) would pass any street in it.


@pytest.mark.parametrize(
    "project",
    ["Lot 1 Baldivis", "Lot 1 (#3) Baldivis 6171 WA", "Lot 1 Baldivis WA"],
)
def test_a_project_address_of_one_word_after_the_lot_is_unparsed(
    project: str,
) -> None:
    assert parse_project_address(project) is None
    text = "Job Address: Lot 1\nSample Lane Baldivis WA"
    assert verify_address(text, project) is SkipReason.ADDRESS_UNVERIFIABLE


# 3. Any spelling of the label counts: a second one is never missed.


@pytest.mark.parametrize(
    "extra",
    [
        "Job  Address: Lot 316 Sample Lane Sampleville",  # two spaces
        "Job Address: Lot 316 Sample Lane Sampleville",  # no-break space
        "JobAddress: Lot 316 Sample Lane Sampleville",
        "Job Address - Lot 316 Sample Lane Sampleville",
        "JOB ADDRESS Lot 316 Sample Lane Sampleville",
        "Job_Address: Lot 316 Sample Lane Sampleville",
        "Job\nAddress: Lot 316 Sample Lane Sampleville",
    ],
)
def test_a_second_label_in_any_spelling_is_unverifiable(extra: str) -> None:
    text = f"{PDF_TEXT}\n{extra}"
    assert job_address_line(text) is None
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_UNVERIFIABLE


def test_a_lone_label_in_another_spelling_is_unverifiable() -> None:
    text = PDF_TEXT.replace("Job Address:", "Job  Address:")
    assert verify_address(text, PROJECT) is SkipReason.ADDRESS_UNVERIFIABLE


# 4. Non-ASCII letters would fold into word breaks, so two different names
#    could compare equal.


@pytest.mark.parametrize(
    ("pdf_suburb", "project_suburb"),
    [
        ("Samplèville", "Sampléville"),
        ("Samplèville", "Samplèville"),
        ("Sampleville", "Sampléville"),
        ("Samplèville", "Sampleville"),
    ],
)
def test_a_non_ascii_letter_on_either_side_is_unverifiable(
    pdf_suburb: str, project_suburb: str
) -> None:
    text = PDF_TEXT.replace("Sampleville WA", f"{pdf_suburb} WA")
    project = f"Lot 123 Sample Lane {project_suburb}"
    assert verify_address(text, project) is SkipReason.ADDRESS_UNVERIFIABLE


def test_non_ascii_punctuation_alone_still_passes() -> None:
    text = PDF_TEXT.replace("Unit 1, 2", "Unit 1 – 2")
    assert verify_address(text, PROJECT) is None
