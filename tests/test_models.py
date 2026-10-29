"""Tests for the seam-1 models (task 2.1; docs/specs/spec.md section 3).

Values are fake (`2600001B`, `pln_10001`, `Sample Lane`), never a trial PO's.
"""

import pytest
from pydantic import ValidationError

from po_agent.b1.models import (
    CompactionTask,
    DeterministicReading,
    MySysLookup,
    NoteSnapshot,
    Proceed,
    Reading,
    SearchRow,
    Skip,
    SkipReason,
)

BODY = "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf"


def proceed(**overrides: object) -> Proceed:
    values: dict[str, object] = {
        "note_id": "1001",
        "internal_no": "2600001B",
        "pln": "pln_10001",
        "po_number": "2600001B/048",
        "email_body": BODY,
        "pdf_file_name": "2600001B_048_1.pdf",
        "pdf_bytes": b"%PDF-fake",
        "existing_task_nos": ("tsk_200001",),
    }
    values.update(overrides)
    return Proceed(**values)  # type: ignore[arg-type]


# --- SkipReason: exactly docs/specs/spec.md section 3 ---


def test_skip_reasons_are_exactly_the_spec_table() -> None:
    assert {reason.value for reason in SkipReason} == {
        "PROJECT_NOT_FOUND",
        "NO_PDF",
        "MULTIPLE_PDFS",
        "PDF_UNREADABLE",
        "NOT_B1",
        "NOT_COMPACTION",
        "PO_MISMATCH",
        "CLAUDE_UNAVAILABLE",
        "CLAUDE_INVALID_OUTPUT",
        "READERS_DISAGREE",
        "PROJECT_AMBIGUOUS",
        "NOTE_ALREADY_LINKED",
        "ADDRESS_MISMATCH",
        "ADDRESS_UNVERIFIABLE",
        "DUPLICATE_TASK",
        "UNEXPECTED_SCREEN",
        "PARTIAL_WRITE",
    }


@pytest.mark.parametrize("reason", list(SkipReason))
def test_only_project_not_found_is_retryable(reason: SkipReason) -> None:
    assert Skip(reason=reason).retryable is (reason is SkipReason.PROJECT_NOT_FOUND)


def test_skip_rejects_an_unknown_reason() -> None:
    with pytest.raises(ValidationError):
        Skip(reason="NOT_B1_HOMES")  # type: ignore[arg-type]


# --- Reading ---


def test_reading_defaults_to_empty_fields() -> None:
    reading = Reading(contains_compaction=False)
    assert (reading.issuer, reading.po_number, reading.client_internal_no) == (
        "",
        "",
        "",
    )
    assert (reading.site_lot, reading.site_street, reading.site_suburb) == ("", "", "")


def test_reading_is_strict_and_closed() -> None:
    with pytest.raises(ValidationError):
        Reading(contains_compaction="yes")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Reading(contains_compaction=True, po_from_filename="2600001B/048")  # type: ignore[call-arg]


def test_deterministic_reading_carries_the_file_name_and_title_po() -> None:
    reading = DeterministicReading(
        issuer="B1 Homes Pty Ltd",
        contains_compaction=True,
        po_number="2600001B/048",
        client_internal_no="2600001B",
        po_from_filename="2600001B/048",
    )
    assert isinstance(reading, Reading)
    assert reading.po_from_title is None


def test_readings_are_frozen() -> None:
    reading = Reading(contains_compaction=True)
    with pytest.raises(ValidationError):
        reading.site_lot = "316"  # type: ignore[misc]


# --- NoteSnapshot and MySysLookup ---


def test_note_snapshot_fields() -> None:
    note = NoteSnapshot(
        note_id="1001",
        title=BODY,
        body=BODY,
        attachment_names=("2600001B_048_1.pdf",),
        project_linked=False,
    )
    assert note.attachment_names == ("2600001B_048_1.pdf",)
    with pytest.raises(ValidationError):
        note.project_linked = True  # type: ignore[misc]


def test_lookup_keeps_every_search_row_and_the_raw_address() -> None:
    lookup = MySysLookup(
        search_rows=(
            SearchRow(pln="pln_10001", client_ref_no="2600001B", company="B1 Homes"),
            SearchRow(
                pln="pln_10009", client_ref_no="2600001B/023", company="B1 Homes"
            ),
        ),
        more_pages=True,
        project_internal_no="2600001B",
        address="Lot 101 (#5) Sample Lane Sampleville 6000 WA",
        tasks=(CompactionTask(task_no="tsk_200001", status="Cancelled"),),
    )
    assert [row.pln for row in lookup.search_rows] == ["pln_10001", "pln_10009"]
    assert lookup.more_pages is True
    assert lookup.tasks[0].status == "Cancelled"


def test_lookup_with_no_rows_has_no_project() -> None:
    lookup = MySysLookup(search_rows=(), more_pages=False)
    assert (lookup.project_internal_no, lookup.address, lookup.tasks) == ("", "", ())


# --- Proceed: frozen, every value checked ---


def test_proceed_holds_the_booking_values() -> None:
    result = proceed()
    assert (result.pln, result.po_number, result.email_body) == (
        "pln_10001",
        "2600001B/048",
        BODY,
    )
    assert result.existing_task_nos == ("tsk_200001",)


def test_proceed_is_frozen() -> None:
    result = proceed()
    with pytest.raises(ValidationError):
        result.pln = "pln_10002"  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"note_id": ""},
        {"pln": "10001"},
        {"pln": "pln_10001 "},
        {"po_number": "2600001B/023"},
        {"po_number": "2600002B/048"},  # not this internal number's PO
        {"internal_no": "2600001b"},
        {"email_body": ""},
        {"pdf_file_name": "2600001B_048_1.docx"},
        {"pdf_bytes": b""},
        {"existing_task_nos": ("200001",)},
        {"extra": "value"},
    ],
)
def test_proceed_rejects_a_bad_value(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        proceed(**overrides)


def test_proceed_repr_hides_the_pdf_and_the_note_body() -> None:
    text = repr(proceed())
    assert "%PDF" not in text
    assert "Please find attached" not in text
