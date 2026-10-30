"""Section 4, verify not extract (task 2.4): the normaliser, the project
address parse, the PDF's Job Address block and the address check.

Unit tests of the address rules as a development aid (SPEC.md -> Testing
Strategy). Fake values only. Order agreed in 2.1: the Job Address block check
(ADDRESS_UNVERIFIABLE) runs before the project compare (ADDRESS_MISMATCH).
"""

import pytest
from po_agent.b1.address import (
    ProjectAddress,
    job_address_block,
    normalise,
    parse_project_address,
    verify_address,
)

from po_agent.b1.models import Reading, SkipReason

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


def reading(
    lot: str = "123", street: str = "Sample Lane", suburb: str = "Sampleville"
) -> Reading:
    return Reading(
        issuer="B1 Homes Pty Ltd",
        contains_compaction=True,
        po_number="2600001B/048",
        client_internal_no="2600001B",
        site_lot=lot,
        site_street=street,
        site_suburb=suburb,
    )


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


# --- verify_address: block check first, then the project compare ---


def test_the_spec_example_passes() -> None:
    text = "Job Address: Lot 123 / Sample Lane Sampleville WA"
    assert verify_address(reading(), text, PROJECT) is None


def test_a_clean_address_passes() -> None:
    assert verify_address(reading(), PDF_TEXT, PROJECT) is None


@pytest.mark.parametrize(
    ("value", "pdf_old", "pdf_new", "project"),
    [
        ({"street": "Sample Ln"}, "Sample Lane", "Sample Ln", PROJECT),
        (
            {"street": "SAMPLE LANE", "suburb": "SAMPLEVILLE"},
            "Sample Lane Sampleville",
            "SAMPLE LANE SAMPLEVILLE",
            PROJECT,
        ),
        ({"lot": "Lot 123"}, "", "", PROJECT),  # a leading Lot is stripped
        ({"lot": "12a"}, "Lot 123", "Lot 12A", "Lot 12A (#7) Sample Lane Sampleville"),
        ({}, "", "", "Lot 123 Sample Ln Sampleville"),
    ],
)
def test_normalised_values_pass(
    value: dict[str, str], pdf_old: str, pdf_new: str, project: str
) -> None:
    text = PDF_TEXT.replace(pdf_old, pdf_new) if pdf_old else PDF_TEXT
    assert verify_address(reading(**value), text, project) is None


@pytest.mark.parametrize(
    "value",
    [{"lot": ""}, {"street": ""}, {"suburb": ""}, {"lot": "Lot"}, {"lot": "12 A"}],
)
def test_a_missing_value_is_unverifiable(value: dict[str, str]) -> None:
    result = verify_address(reading(**value), PDF_TEXT, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


def test_no_job_address_block_is_unverifiable() -> None:
    text = PDF_TEXT.replace("Job Address:", "Site:")
    result = verify_address(reading(), text, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


@pytest.mark.parametrize("project", ["", "123 Sample Lane Sampleville 6000 WA"])
def test_a_project_address_without_lot_is_unverifiable(project: str) -> None:
    result = verify_address(reading(), PDF_TEXT, project)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


def test_the_address_split_across_the_pdf_is_unverifiable() -> None:
    text = PDF_TEXT.replace(
        "Supplierton WA Sample Lane Sampleville WA", "Supplierton WA"
    ).replace("Total $11.00", "Total $11.00\nSite: Sample Lane Sampleville WA")
    result = verify_address(reading(), text, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


def test_a_lot_found_elsewhere_that_matches_the_project_is_unverifiable() -> None:
    # Concern C15: Claude's lot is in the PDF and on the project, not in the block.
    text = PDF_TEXT.replace("test 1 each", "test as for Lot 77 1 each")
    project = "Lot 77 (#45) Sample Lane Sampleville 6000 WA"
    result = verify_address(reading(lot="77"), text, project)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


@pytest.mark.parametrize("lot", ["1", "2"])
def test_the_lot_must_follow_lot_in_the_block(lot: str) -> None:
    # "Unit 1, 2 Supplier Road" is in the block, but not as "Lot 1" or "Lot 2".
    project = f"Lot {lot} Sample Lane Sampleville"
    result = verify_address(reading(lot=lot), PDF_TEXT, project)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


def test_a_street_or_suburb_not_in_the_block_is_unverifiable() -> None:
    result = verify_address(reading(suburb="Exampleton"), PDF_TEXT, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE
    result = verify_address(reading(street="Sample Road"), PDF_TEXT, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


def test_a_value_must_match_whole_words_in_the_block() -> None:
    result = verify_address(reading(suburb="Sample"), PDF_TEXT, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE
    project = "Lot 12 Sample Lane Sampleville"
    result = verify_address(reading(lot="12"), PDF_TEXT, project)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE


@pytest.mark.parametrize(
    ("value", "pdf_old", "pdf_new"),
    [
        ({"lot": "124"}, "Lot 123", "Lot 124"),
        ({"street": "Sample Road"}, "Sample Lane", "Sample Road"),
        ({"suburb": "Exampleton"}, "Sampleville WA", "Exampleton WA"),
    ],
)
def test_a_block_value_that_differs_from_the_project_is_a_mismatch(
    value: dict[str, str], pdf_old: str, pdf_new: str
) -> None:
    text = PDF_TEXT.replace(pdf_old, pdf_new)
    result = verify_address(reading(**value), text, PROJECT)
    assert result is SkipReason.ADDRESS_MISMATCH


def test_a_different_lot_letter_is_a_mismatch() -> None:
    text = PDF_TEXT.replace("Lot 123", "Lot 12B")
    project = "Lot 12A (#7) Sample Lane Sampleville 6001 WA"
    result = verify_address(reading(lot="12B"), text, project)
    assert result is SkipReason.ADDRESS_MISMATCH


def test_street_and_suburb_must_equal_the_whole_rest() -> None:
    # Claude's street + suburb is only part of the project's text: the agent
    # never guesses where the street ends.
    project = "Lot 123 Sample Lane Sampleville North 6000 WA"
    result = verify_address(reading(), PDF_TEXT, project)
    assert result is SkipReason.ADDRESS_MISMATCH


def test_the_block_check_comes_before_the_project_compare() -> None:
    # Not in the block and not on the project: the block check decides.
    result = verify_address(reading(lot="77"), PDF_TEXT, PROJECT)
    assert result is SkipReason.ADDRESS_UNVERIFIABLE
