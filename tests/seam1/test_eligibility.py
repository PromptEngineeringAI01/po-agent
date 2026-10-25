"""Tests for step 0, eligibility from the Note Pool list view (task 1.7).

Pure functions, no browser. Values are fake (`2600001B` style, as in
docs/screen-map.md), never a trial PO's.
"""

import pytest
from po_agent.b1.decision import eligible_internal_no
from po_agent.b1.models import NotePoolRow
from pydantic import ValidationError

POOL = "Agent Pool"
BODY = "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf"
LIVE_TITLE = "[B1 Homes] Order 2600001B/048"


def row(subject_note: str, project: str = "---", assignee: str = POOL) -> NotePoolRow:
    return NotePoolRow(
        note_id="1001", subject_note=subject_note, project=project, assignee=assignee
    )


# --- test rule: the Subject/Note cell contains <internal no>_048[_n].pdf ---


@pytest.mark.parametrize(
    "subject_note",
    [
        BODY,  # older Notes: title = body
        f"{LIVE_TITLE} {BODY}",  # newer Notes: live-style title + body
        "Please find attached Purchase Order / Quotation file 2600001B_048.pdf",
        "Please find attached Purchase Order / Quotation file 2600001B_048_12.pdf",
        f"  {BODY}  ",
    ],
)
def test_test_rule_eligible_returns_internal_no(subject_note: str) -> None:
    assert (
        eligible_internal_no(row(subject_note), "test-body-filename", POOL)
        == "2600001B"
    )


@pytest.mark.parametrize(
    "subject_note",
    [
        "Please find attached Purchase Order / Quotation file 2600001B_023_1.pdf",
        "Please find attached Purchase Order / Quotation file 2600001B_048_1.docx",
        "Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf.exe",
        "Please find attached Purchase Order / Quotation file 2600001B_0480_1.pdf",
        "Please find attached Purchase Order / Quotation file 2600001B_048_.pdf",
        "Please find attached Purchase Order / Quotation file x_2600001B_048_1.pdf",
        "Please find attached Purchase Order / Quotation file 2600001B-048_1.pdf",
        LIVE_TITLE,  # live title alone has no file name
        "Call the office about 2600001B",
        "",
        # two different internal numbers in one cell: ambiguous
        f"{BODY} and 2600002B_048_1.pdf",
    ],
)
def test_test_rule_other_text_not_eligible(subject_note: str) -> None:
    assert eligible_internal_no(row(subject_note), "test-body-filename", POOL) is None


def test_test_rule_same_file_twice_is_eligible() -> None:
    cell = f"{BODY} {BODY}"
    assert eligible_internal_no(row(cell), "test-body-filename", POOL) == "2600001B"


# --- live rule (offline only): title [B1 Homes] Order <internal no>/048 ---


@pytest.mark.parametrize(
    "subject_note",
    [LIVE_TITLE, f"{LIVE_TITLE} {BODY}", f" {LIVE_TITLE} "],
)
def test_live_rule_eligible_returns_internal_no(subject_note: str) -> None:
    assert eligible_internal_no(row(subject_note), "live-b1-title", POOL) == "2600001B"


@pytest.mark.parametrize(
    "subject_note",
    [
        BODY,  # test-style body only: no live title
        "[B1 Homes] Order 2600001B/023",
        "[B1 Homes] Order 2600001B/0480",
        "[B1 Homes] Order 2600001B/048x",
        "[B1 Homes]  Order 2600001B/048",
        "[B1 Home] Order 2600001B/048",
        "Re: [B1 Homes] Order 2600001B/048",
        "FW: [B1 Homes] Order 2600001B/048",
        "[B1 Homes] Order /048",
        "",
    ],
)
def test_live_rule_other_text_not_eligible(subject_note: str) -> None:
    assert eligible_internal_no(row(subject_note), "live-b1-title", POOL) is None


# --- both rules: Project `---` and Assignee = pool_name ---


@pytest.mark.parametrize(
    ("rule", "cell"),
    [("test-body-filename", BODY), ("live-b1-title", LIVE_TITLE)],
)
@pytest.mark.parametrize("project", ["pln_12345", "", "--", "----", "pln_12345 ---"])
def test_linked_note_not_eligible(rule: str, cell: str, project: str) -> None:
    assert eligible_internal_no(row(cell, project=project), rule, POOL) is None


@pytest.mark.parametrize(
    ("rule", "cell"),
    [("test-body-filename", BODY), ("live-b1-title", LIVE_TITLE)],
)
@pytest.mark.parametrize(
    "assignee", ["Jane Citizen", "", "agent pool", "Agent Pool 2", "PO Allocation Pool"]
)
def test_note_not_in_pool_not_eligible(rule: str, cell: str, assignee: str) -> None:
    assert eligible_internal_no(row(cell, assignee=assignee), rule, POOL) is None


def test_project_and_assignee_cells_tolerate_surrounding_whitespace() -> None:
    r = row(BODY, project=" --- ", assignee=f" {POOL} ")
    assert eligible_internal_no(r, "test-body-filename", POOL) == "2600001B"


def test_unknown_rule_refused() -> None:
    with pytest.raises(ValueError):
        eligible_internal_no(row(BODY), "anything", POOL)  # type: ignore[arg-type]


def test_note_pool_row_is_frozen_and_strict() -> None:
    r = row(BODY)
    with pytest.raises(ValidationError):
        r.project = "pln_1"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        NotePoolRow(note_id="1", subject_note=BODY, project="---", assignee=POOL, x=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        NotePoolRow(note_id="", subject_note=BODY, project="---", assignee=POOL)
