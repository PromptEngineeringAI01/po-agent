"""Tests for the seam-1 models (task 2.1; docs/specs/spec.md section 3) and
the shared models with the Creator in the `Proceed` (task 9.1; ADR-003
decisions 2-3).

Values are fake (`2600001B`, `pln_10001`, `Sample Lane`), never a trial PO's.
"""

import ast
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from po_agent.b1.models import B1Proceed, DeterministicReading, Reading
from po_agent.core.models import (
    CompactionTask,
    MySysLookup,
    NoteSnapshot,
    Proceed,
    SearchRow,
    Skip,
    SkipReason,
)

BODY = "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf"


def proceed(**overrides: object) -> B1Proceed:
    values: dict[str, object] = {
        "note_id": "1001",
        "internal_no": "2600001B",
        "pln": "pln_10001",
        "po_number": "2600001B/048",
        "email_body": BODY,
        "pdf_file_name": "2600001B_048_1.pdf",
        "pdf_bytes": b"%PDF-fake",
        "existing_task_nos": ("tsk_200001",),
        "creator": "Perth Scheduling",
    }
    values.update(overrides)
    return B1Proceed(**values)  # type: ignore[arg-type]


# --- SkipReason: docs/specs/spec.md section 3 and SPEC.md -> Client 2 ---


def test_skip_reasons_are_exactly_the_spec_table() -> None:
    assert {reason.value for reason in SkipReason} == {
        "PROJECT_NOT_FOUND",
        "NO_PDF",
        "MULTIPLE_PDFS",
        "PDF_UNREADABLE",
        "NOT_B1",
        "NOT_COMPACTION",
        "PO_MISMATCH",
        "READERS_DISAGREE",
        "PROJECT_AMBIGUOUS",
        "NOTE_ALREADY_LINKED",
        "ADDRESS_MISMATCH",
        "ADDRESS_UNVERIFIABLE",
        "DUPLICATE_TASK",
        "UNEXPECTED_SCREEN",
        "PARTIAL_WRITE",
        # Summit's three (SPEC.md -> Client 2, Decision checks; task 9.9).
        "COMPANY_UNKNOWN",
        "COMPANY_MISMATCH",
        "CREATOR_UNKNOWN",
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


def test_reading_has_no_address_fields() -> None:
    # Decisions, 2 Nov 2026: no reader extracts the address; MySys gives it.
    assert not {"site_lot", "site_street", "site_suburb"} & set(Reading.model_fields)


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
        reading.po_number = "2600009B/048"  # type: ignore[misc]


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
        {"pdf_file_name": "2600001B_023_1.pdf"},  # not the /048 file
        {"creator": ""},
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


def test_note_snapshot_needs_a_note_id() -> None:
    with pytest.raises(ValidationError):
        NoteSnapshot(
            note_id="",
            title=BODY,
            body=BODY,
            attachment_names=(),
            project_linked=False,
        )


# --- Task 9.1: the Creator travels in the Proceed (ADR-003 decision 3) ---


@pytest.mark.parametrize("model", [Proceed, B1Proceed])
def test_a_proceed_has_no_default_creator(model: type[Proceed]) -> None:
    values = proceed().model_dump()
    del values["creator"]
    with pytest.raises(ValidationError):
        model(**values)


def test_a_b1_proceed_is_a_shared_proceed() -> None:
    # The booker takes the shared model; B1's adds its /048 rules.
    assert isinstance(proceed(), Proceed)


SRC = Path(__file__).resolve().parents[1] / "src" / "po_agent"
# A client's decision engine: src/po_agent/<client>/decision.py, never a
# shared package's (ADR-003 decision 2).
DECISION_ENGINE = re.compile(r"(?!core/|mysys/)[a-z0-9_]+/decision\.py")


def builds_a_proceed(tree: ast.AST) -> bool:
    """A call of a class named ...Proceed, or of a pydantic model_* method on
    one or on a value named ...proceed (model_validate, model_construct,
    model_copy); and, on any value, model_construct or model_copy(update=...),
    which skip validation (no src code uses them)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id.endswith("Proceed"):
            return True
        if isinstance(func, ast.Attribute):
            if func.attr.endswith("Proceed"):
                return True
            if func.attr == "model_construct" or (
                func.attr == "model_copy"
                and any(keyword.arg == "update" for keyword in node.keywords)
            ):
                return True
            owner = func.value
            if (
                func.attr.startswith("model_")
                and isinstance(owner, ast.Name)
                and owner.id.lower().endswith("proceed")
            ):
                return True
    return False


def test_only_a_client_decision_engine_constructs_a_proceed() -> None:
    builders = sorted(
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        if builds_a_proceed(ast.parse(path.read_text(encoding="utf-8")))
    )
    assert "b1/decision.py" in builders
    assert [p for p in builders if not DECISION_ENGINE.fullmatch(p)] == []


@pytest.mark.parametrize(
    ("source", "builds"),
    [
        ("Proceed(note_id='1')", True),
        ("models.B1Proceed(note_id='1')", True),
        ("B1Proceed.model_validate({})", True),
        ("proceed.model_copy(update={'creator': 'x'})", True),
        # A Proceed under another name (run.py's `decision`): no validation.
        ("decision.model_copy(update={'po_number': '1/023'})", True),
        ("decision.model_construct(note_id='1')", True),
        ("lookup.model_copy()", False),
        ("isinstance(decision, Proceed)", False),
        ("Skip(reason=reason)", False),
    ],
)
def test_the_proceed_scan_sees_every_way_to_build_one(
    source: str, builds: bool
) -> None:
    assert builds_a_proceed(ast.parse(source)) is builds


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("b1/decision.py", True),
        ("summit/decision.py", True),
        ("b1/booker.py", False),
        ("core/decision.py", False),
        ("mysys/decision.py", False),
        ("decision.py", False),
    ],
)
def test_only_a_client_package_s_decision_py_may_build_one(
    path: str, allowed: bool
) -> None:
    assert bool(DECISION_ENGINE.fullmatch(path)) is allowed
