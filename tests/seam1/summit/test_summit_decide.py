"""Seam 1, Summit's decision engine (task 9.9; SPEC.md -> Client 2: Summit
Home, Decision checks and skip reasons, Creator table; tasks/plan.md 9.9).

`summit.decision.decide()` takes the Note window as read, its original
assignee, both readers' text of the PDF (B1's `PdfTexts`), the project lookup
as a callable and the creator table from the committed client file. It
applies SPEC's table in order: the Note and PDF checks, the PO against the
title's, the title's and PDF's company in the table, then (one lookup) the
project match and Client Internal No., the three companies on one row, the
duplicate check and the creator. One case per row and per boundary
(decide_cases.toml); fake values only; zero false PROCEED.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from po_agent.b1.readers import PdfTexts
from po_agent.core.config import load_client
from po_agent.core.models import (
    MySysLookup,
    NoteSnapshot,
    ProjectTask,
    SearchRow,
    Skip,
    SkipReason,
)
from po_agent.summit.decision import decide
from po_agent.summit.models import SummitProceed

HERE = Path(__file__).parent
PO = tomllib.loads((HERE / "reader_cases.toml").read_text(encoding="utf-8"))["po"]
_RAW = tomllib.loads((HERE / "decide_cases.toml").read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = _RAW["case"]
COMPANIES = load_client("summit", "live").company
PDF_BYTES = b"%PDF-stand-in"
ORIGINAL_ASSIGNEE = "Fake Admin One"
# SPEC's rows decided before the one project lookup (cheap first).
BEFORE_LOOKUP = {
    SkipReason.NOTE_ALREADY_LINKED,
    SkipReason.NO_PDF,
    SkipReason.MULTIPLE_PDFS,
    SkipReason.PDF_UNREADABLE,
    SkipReason.NOT_COMPACTION,
    SkipReason.READERS_DISAGREE,
    SkipReason.PO_MISMATCH,
    SkipReason.COMPANY_UNKNOWN,
}


def _replaced(text: str, pairs: list[list[str]]) -> str:
    for old, new in pairs:
        assert old in text, f"replace target not in the text: {old!r}"
        text = text.replace(old, new)
    return text


def texts_of(case: dict[str, Any]) -> PdfTexts:
    plumber = _replaced(PO["plumber"], case.get("pdf_replace", []))
    pypdf = _replaced(PO["pypdf"], case.get("pdf_replace", []))
    plumber = _replaced(plumber, case.get("plumber_replace", []))
    pypdf = _replaced(pypdf, case.get("pypdf_replace", []))
    empty = case.get("empty")
    return PdfTexts(
        plumber="" if empty == "plumber" else plumber,
        pypdf="" if empty == "pypdf" else pypdf,
        data=PDF_BYTES,
    )


def note_of(case: dict[str, Any]) -> NoteSnapshot:
    base = _RAW["note"]
    return NoteSnapshot(
        note_id="900001",
        title=case.get("title", base["title"]),
        body=base["body"],
        attachment_names=tuple(case.get("attachments", base["attachments"])),
        project_linked=case.get("linked", base["linked"]),
    )


def lookup_of(case: dict[str, Any]) -> MySysLookup:
    base = _RAW["lookup"]
    return MySysLookup(
        search_rows=tuple(
            SearchRow(**row) for row in case.get("search_rows", base["search_rows"])
        ),
        more_pages=case.get("more_pages", base["more_pages"]),
        project_internal_no=case.get("internal_no", base["internal_no"]),
        project_tasks=tuple(
            ProjectTask(**task)
            for task in case.get("project_tasks", base["project_tasks"])
        ),
    )


class FakeLookup:
    """The project lookup decide() may call: records each call."""

    def __init__(self, found: MySysLookup) -> None:
        self.found = found
        self.calls = 0

    def __call__(self) -> MySysLookup:
        self.calls += 1
        return self.found


def run(case: dict[str, Any]) -> tuple[Skip | SummitProceed, FakeLookup]:
    lookup = FakeLookup(lookup_of(case))
    result = decide(
        note_of(case),
        ORIGINAL_ASSIGNEE,
        texts_of(case),
        lookup,
        companies=COMPANIES,
    )
    return result, lookup


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_summit_decide_case(case: dict[str, Any]) -> None:
    result, _ = run(case)
    if "expect_skip" in case:
        assert result == Skip(reason=SkipReason(case["expect_skip"]))
        return
    assert isinstance(result, SummitProceed)
    assert result.pln == case["expect_pln"]
    assert result.po_number == case["expect_po"]
    assert result.internal_no == case["expect_po"].split("/")[0]
    assert result.creator == case["expect_creator"]
    assert result.existing_task_nos == tuple(case.get("expect_task_nos", []))
    previous = case.get("expect_previous_task")
    assert result.previous_task_no == previous
    assert result.previous_task_creator == (
        case["expect_creator"] if previous else None
    )


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_the_lookup_runs_once_and_only_after_the_note_and_pdf_checks(
    case: dict[str, Any],
) -> None:
    _, lookup = run(case)
    early = "expect_skip" in case and SkipReason(case["expect_skip"]) in BEFORE_LOOKUP
    assert lookup.calls == (0 if early else 1)


def test_proceed_carries_the_note_the_pdf_and_the_original_assignee() -> None:
    case = next(c for c in CASES if c["id"] == "clean")
    result, _ = run(case)
    assert isinstance(result, SummitProceed)
    assert result.note_id == "900001"
    assert result.email_body == _RAW["note"]["body"]
    assert result.pdf_file_name == "fake-123456_020_01.pdf"
    assert result.pdf_bytes == PDF_BYTES
    assert result.original_assignee == ORIGINAL_ASSIGNEE


def test_summit_never_skips_for_a_b1_reason() -> None:
    b1_only = {
        SkipReason.NOT_B1,
        SkipReason.ADDRESS_MISMATCH,
        SkipReason.ADDRESS_UNVERIFIABLE,
    }
    reasons = {
        result.reason for result, _ in map(run, CASES) if isinstance(result, Skip)
    }
    assert not reasons & b1_only


def test_no_false_proceed() -> None:
    """PROCEEDs a case doesn't expect, or with values it doesn't expect."""
    count = 0
    for case in CASES:
        result, _ = run(case)
        if isinstance(result, SummitProceed) and (
            "expect_skip" in case
            or result.pln != case["expect_pln"]
            or result.po_number != case["expect_po"]
            or result.creator != case["expect_creator"]
        ):
            count += 1
    print(f"false PROCEED: {count}")
    assert count == 0


@pytest.mark.parametrize("creator", ["", "  ", "---", " --- "])
def test_a_proceed_naming_no_creator_is_refused(creator: str) -> None:
    """Every value is checked again (core/models.py, Proceed): a creator
    that names nobody can't reach W1, whatever decide() did."""
    result, _ = run(next(c for c in CASES if c["id"] == "clean"))
    assert isinstance(result, SummitProceed)
    with pytest.raises(ValidationError):
        SummitProceed(**{**result.model_dump(), "creator": creator})
