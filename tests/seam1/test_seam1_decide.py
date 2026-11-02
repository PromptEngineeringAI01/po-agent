"""Seam 1, the code-only `decide()` (decisions, 2 Nov 2026): every case end to
end with zero false PROCEED, and section 2 order: steps 2a-4, the second
reader's agreement, the project lookup (8), the address check against the
project's address in MySys (9), the duplicate check (10), PROCEED.

`decide()` takes both readers' text layers, pdfplumber's (`pdf_text`) and
pypdf's (`pypdf_text`), each "" when its library reads none. No Claude, no
API key, no reader mode.
"""

import inspect

import pytest
from seam1_cases import CASES, POOL, Seam1Case, pdf_bytes

from po_agent.b1 import decision
from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import decide, eligible_internal_no
from po_agent.b1.models import CompactionTask, MySysLookup, Proceed, Skip, SkipReason

PDF_BYTES = b"%PDF-stand-in"


def texts(case: Seam1Case) -> tuple[str, str]:
    """Both readers' text: the case's fake text layers, or the libraries'
    reading of the bytes for the corrupt and image-only cases."""
    if case.pdf in ("corrupt", "image-only"):
        data = pdf_bytes(case.pdf)
        return rules.text_layer(data), rules.pypdf_text_layer(data)
    return case.pdf_text, case.pypdf_text


def run(
    case: Seam1Case,
    lookup: MySysLookup | None = None,
    pdf_text: str | None = None,
    pypdf_text: str | None = None,
) -> Skip | Proceed | None:
    """decide() on the case; None when step 0 leaves the Note untouched."""
    internal_no = eligible_internal_no(case.pool_row, case.config.title_rule, POOL)
    if internal_no is None:
        return None
    plumber, pypdf = texts(case)
    return decide(
        case.note,
        internal_no,
        plumber if pdf_text is None else pdf_text,
        pypdf if pypdf_text is None else pypdf_text,
        PDF_BYTES,
        case.lookup if lookup is None else lookup,
        site=case.config.site,
        duplicate_ignores_cancelled=case.config.duplicate_ignores_cancelled,
    )


def by_id(case_id: str) -> Seam1Case:
    return next(case for case in CASES if case.id == case_id)


def skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


CLEAN = by_id("p1-clean")


# --- every seam-1 case ---


def test_seam1_case_end_to_end(seam1_case: Seam1Case) -> None:
    result = run(seam1_case)
    expect = seam1_case.expect
    if expect.result == "untouched":
        assert result is None
    elif expect.result == "skip":
        assert expect.reason is not None
        assert result == skip(expect.reason)
    else:
        assert isinstance(result, Proceed)
        note = seam1_case.note
        assert result.note_id == note.note_id
        assert result.pln == expect.pln
        assert result.po_number == expect.po_number
        assert result.internal_no == result.po_number.split("/")[0]
        assert result.email_body == note.body
        assert result.pdf_file_name == note.attachment_names[0]
        assert result.pdf_bytes == PDF_BYTES
        assert result.existing_task_nos == expect.existing_task_nos


def test_seam1_case_never_carries_its_injected_text(seam1_case: Seam1Case) -> None:
    result = run(seam1_case)
    shown = f"{result!r} {result!s}"
    values = result.model_dump() if isinstance(result, Proceed) else {}
    for text in seam1_case.never_in_output:
        assert text not in shown
        assert not any(isinstance(v, str) and text in v for v in values.values())


def test_no_false_proceed() -> None:
    """PROCEEDs a case doesn't expect, or with values it doesn't expect."""
    count = 0
    for case in CASES:
        result = run(case)
        if isinstance(result, Proceed) and (
            case.expect.result != "proceed"
            or result.pln != case.expect.pln
            or result.po_number != case.expect.po_number
        ):
            count += 1
    print(f"false PROCEED: {count}")
    assert count == 0


def test_the_three_fake_pos_proceed() -> None:
    # Today's deterministic-only mode skips them all ADDRESS_UNVERIFIABLE.
    for case_id, pln in (
        ("p1-clean", "pln_10001"),
        ("p2-clean", "pln_10002"),
        ("p3-clean", "pln_10003"),
    ):
        result = run(by_id(case_id))
        assert isinstance(result, Proceed) and result.pln == pln


# --- no Claude ---


def test_decide_takes_both_texts_and_no_reader_or_mode() -> None:
    assert list(inspect.signature(decide).parameters) == [
        "note",
        "internal_no",
        "pdf_text",
        "pypdf_text",
        "pdf_bytes",
        "lookup",
        "site",
        "duplicate_ignores_cancelled",
    ]


def test_the_claude_reader_hooks_are_gone() -> None:
    assert not hasattr(decision, "ClaudeUnavailable")
    assert not hasattr(decision, "ReaderMode")


# --- section 2 order: the first failing step decides ---

NO_PROJECT = CLEAN.lookup.model_copy(
    update={"search_rows": (), "project_internal_no": "", "address": ""}
)
ON_HOLD = (CompactionTask(task_no="tsk_200001", status="On Hold"),)
WITH_TASK = CLEAN.lookup.model_copy(update={"tasks": ON_HOLD})


def test_steps_2a_to_4_come_before_the_second_reader() -> None:
    linked = CLEAN.note.model_copy(update={"project_linked": True})
    case = CLEAN.model_copy(update={"note": linked})
    result = run(case, lookup=NO_PROJECT, pypdf_text="")
    assert result == skip(SkipReason.NOTE_ALREADY_LINKED)
    text = CLEAN.pdf_text.replace("2600001B/048", "2600002B/048")
    result = run(CLEAN, lookup=NO_PROJECT, pdf_text=text, pypdf_text="")
    assert result == skip(SkipReason.PO_MISMATCH)


@pytest.mark.parametrize(
    ("pypdf", "reason"),
    [
        ("", SkipReason.PDF_UNREADABLE),
        (
            CLEAN.pypdf_text.replace("2600001B/048", "2600001B/049"),
            SkipReason.READERS_DISAGREE,
        ),
        (
            CLEAN.pypdf_text.replace("Lot 123", "Lot 128"),
            SkipReason.READERS_DISAGREE,
        ),
    ],
    ids=["unreadable", "po-differs", "lot-differs"],
)
def test_the_second_reader_comes_before_the_project_lookup(
    pypdf: str, reason: SkipReason
) -> None:
    assert run(CLEAN, lookup=NO_PROJECT, pypdf_text=pypdf) == skip(reason)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"search_rows": ()}, SkipReason.PROJECT_NOT_FOUND),
        ({"more_pages": True}, SkipReason.PROJECT_AMBIGUOUS),
        ({"project_internal_no": "2600004B"}, SkipReason.UNEXPECTED_SCREEN),
    ],
)
def test_the_project_lookup_comes_before_the_address_and_duplicate_steps(
    changes: dict[str, object], reason: SkipReason
) -> None:
    lookup = WITH_TASK.model_copy(update={**changes, "address": "no address"})
    assert run(CLEAN, lookup=lookup) == skip(reason)


@pytest.mark.parametrize(
    ("plumber_old", "plumber_new", "pypdf_old", "pypdf_new", "reason"),
    [
        # the same change in both texts: the address check's own reason
        ("Lot 123", "Lot 124", "Lot 123", "Lot 124", SkipReason.ADDRESS_MISMATCH),
        ("Lot 123", "Lot 12-A", "Lot 123", "Lot 12-A", SkipReason.ADDRESS_UNVERIFIABLE),
        # the readers' texts give different results: READERS_DISAGREE
        (
            "Sample Lane Sampleville WA",
            "Sample Road Sampleville WA",
            "",
            "",
            SkipReason.READERS_DISAGREE,
        ),
        (
            "",
            "",
            "Sample Lane Sampleville WA",
            "Sample Road Sampleville WA",
            SkipReason.READERS_DISAGREE,
        ),
        (  # pdfplumber: a blank line under the lone lot
            "Job Address: Lot 123\n",
            "Job Address: Lot 123\n\n",
            "",
            "",
            SkipReason.READERS_DISAGREE,
        ),
    ],
)
def test_the_address_check_runs_on_both_texts_before_the_duplicate_check(
    plumber_old: str,
    plumber_new: str,
    pypdf_old: str,
    pypdf_new: str,
    reason: SkipReason,
) -> None:
    plumber = CLEAN.pdf_text.replace(plumber_old, plumber_new) if plumber_old else None
    pypdf = CLEAN.pypdf_text.replace(pypdf_old, pypdf_new) if pypdf_old else None
    result = run(CLEAN, lookup=WITH_TASK, pdf_text=plumber, pypdf_text=pypdf)
    assert result == skip(reason)


def test_the_project_address_is_read_in_decide() -> None:
    lookup = CLEAN.lookup.model_copy(update={"address": "123 Sample Lane Sampleville"})
    assert run(CLEAN, lookup=lookup) == skip(SkipReason.ADDRESS_UNVERIFIABLE)


def test_the_duplicate_check_runs_last() -> None:
    assert run(CLEAN, lookup=WITH_TASK) == skip(SkipReason.DUPLICATE_TASK)


def test_a_clean_po_proceeds() -> None:
    result = run(CLEAN)
    assert isinstance(result, Proceed)
    assert (result.pln, result.po_number) == ("pln_10001", "2600001B/048")
    assert result.existing_task_nos == ()


def test_the_site_picks_the_match_rule_in_decide() -> None:
    lookup = CLEAN.lookup.model_copy(
        update={
            "search_rows": (
                CLEAN.lookup.search_rows[0].model_copy(
                    update={"client_ref_no": "2600001B/048"}
                ),
            ),
            "project_internal_no": "2600001B/048",
        }
    )
    assert run(CLEAN, lookup=lookup) == skip(SkipReason.PROJECT_NOT_FOUND)
    live = CLEAN.model_copy(
        update={"config": CLEAN.config.model_copy(update={"site": "live"})}
    )
    assert isinstance(run(live, lookup=lookup), Proceed)


@pytest.mark.parametrize(
    "line",
    [
        "North Sample Lane Sampleville WA",
        "Lot 999 Sample Lane Sampleville WA",
        "7 Other St Sample Lane Sampleville WA",
    ],
)
def test_more_before_the_address_under_the_label_never_proceeds(line: str) -> None:
    # Review finding 1 (2.5): pdfplumber's line shares the Supplier column, so
    # it only has to end with the address; pypdf's line must be exactly it.
    plumber = CLEAN.pdf_text.replace("Sample Lane Sampleville WA", line)
    pypdf = CLEAN.pypdf_text.replace("Sample Lane Sampleville WA", line)
    result = run(CLEAN, pdf_text=plumber, pypdf_text=pypdf)
    assert result == skip(SkipReason.READERS_DISAGREE)
