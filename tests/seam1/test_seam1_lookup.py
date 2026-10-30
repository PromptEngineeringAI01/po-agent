"""Seam 1, steps 8 and 10 (task 2.3): the project match, the project window
check and the duplicate check, plus `decide()` end to end in
deterministic-only mode.

`match_project()` is the one match rule: `check_project()` (step 8) uses it,
and the driver (3.2) calls it to choose which `pln_...` link to open.
`check_duplicate()` is step 10. Hybrid `decide()` needs the agreement and
address steps (2.4), so here every case's hybrid result is checked on the
lookup steps only, and `decide()` runs every case in deterministic-only mode.
"""

import pytest
from seam1_cases import POOL, Seam1Case, pdf_bytes

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import (
    check_duplicate,
    check_project,
    decide,
    eligible_internal_no,
    match_project,
)
from po_agent.b1.models import (
    CompactionTask,
    MySysLookup,
    NoteSnapshot,
    Proceed,
    SearchRow,
    Skip,
    SkipReason,
)

INTERNAL_NO = "2600001B"
# A clean fake PO (values fake), as in test_seam1_reader_checks.
PDF_TEXT = """B1 Homes Pty Ltd
1 Builder Way
Purchase Order No 2600001B/048
Order Type: COMPACTION TEST Job: Sample Job
COMPACTION Compaction test 1 each $10.00* $10.00"""
FILE_NAME = "2600001B_048_1.pdf"
BODY = f"Please find attached Purchase Order / Quotation file {FILE_NAME}"
NOTE = NoteSnapshot(
    note_id="1001",
    title=BODY,
    body=BODY,
    attachment_names=(FILE_NAME,),
    project_linked=False,
)
PDF_BYTES = b"%PDF-stand-in"


def row(pln: str, ref: str, company: str = "B1 Homes") -> SearchRow:
    return SearchRow(pln=pln, client_ref_no=ref, company=company)


def task(task_no: str, status: str) -> CompactionTask:
    return CompactionTask(task_no=task_no, status=status)


def lookup(**changes: object) -> MySysLookup:
    values: dict[str, object] = {
        "search_rows": (row("pln_10001", INTERNAL_NO),),
        "more_pages": False,
        "project_internal_no": INTERNAL_NO,
        "address": "Lot 123 (#45) Sample Lane Sampleville 6000 WA",
        "tasks": (),
    }
    values.update(changes)
    return MySysLookup.model_validate(values)


def skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


def decide_det_only(
    snapshot: NoteSnapshot = NOTE,
    text: str = PDF_TEXT,
    project: MySysLookup | None = None,
    site: str = "test",
    ignores_cancelled: bool = True,
) -> Skip | Proceed:
    return decide(
        snapshot,
        INTERNAL_NO,
        text,
        PDF_BYTES,
        project or lookup(),
        site=site,
        reader_mode="deterministic-only",
        duplicate_ignores_cancelled=ignores_cancelled,
    )


def case_text(case: Seam1Case) -> str:
    if case.pdf in ("corrupt", "image-only"):
        return rules.text_layer(pdf_bytes(case.pdf))
    return case.pdf_text


# --- every seam-1 case ---


def test_seam1_case_deterministic_only_end_to_end(seam1_case: Seam1Case) -> None:
    # Zero false PROCEED: every case gives exactly its expected result.
    internal_no = eligible_internal_no(
        seam1_case.pool_row, seam1_case.config.title_rule, POOL
    )
    expect = seam1_case.expect_deterministic_only
    if internal_no is None:  # step 0: untouched, never opened
        assert expect.result == "untouched"
        return
    assert expect.reason is not None
    result = decide(
        seam1_case.note,
        internal_no,
        case_text(seam1_case),
        PDF_BYTES,
        seam1_case.lookup,
        site=seam1_case.config.site,
        reader_mode="deterministic-only",
        duplicate_ignores_cancelled=seam1_case.config.duplicate_ignores_cancelled,
    )
    assert result == skip(expect.reason)


def test_seam1_case_lookup_steps_in_hybrid_mode(seam1_case: Seam1Case) -> None:
    # Steps 8 and 10 give the case's hybrid skip when it is a lookup skip;
    # otherwise they pass, with the expected pln and task numbers.
    internal_no = eligible_internal_no(
        seam1_case.pool_row, seam1_case.config.title_rule, POOL
    )
    if internal_no is None:
        return
    config = seam1_case.config
    expect = seam1_case.expect
    project = check_project(seam1_case.lookup, internal_no, config.site)
    if expect.reason in (
        SkipReason.PROJECT_NOT_FOUND,
        SkipReason.PROJECT_AMBIGUOUS,
        SkipReason.UNEXPECTED_SCREEN,
    ):
        assert project == skip(expect.reason)
        return
    assert isinstance(project, str)
    duplicate = check_duplicate(
        seam1_case.lookup.tasks, config.duplicate_ignores_cancelled
    )
    if expect.reason is SkipReason.DUPLICATE_TASK:
        assert duplicate == skip(SkipReason.DUPLICATE_TASK)
        return
    assert isinstance(duplicate, tuple)
    if expect.result == "proceed":
        assert project == expect.pln
        assert duplicate == expect.existing_task_nos


# --- step 8: the match rule ---


def test_the_one_b1_row_with_the_bare_internal_no_matches_on_test() -> None:
    rows = (row("pln_10001", INTERNAL_NO),)
    assert match_project(rows, False, INTERNAL_NO, "test") == "pln_10001"


def test_the_one_b1_row_ending_048_matches_on_live() -> None:
    rows = (row("pln_10001", f"{INTERNAL_NO}/048"),)
    assert match_project(rows, False, INTERNAL_NO, "live") == "pln_10001"


@pytest.mark.parametrize("ref", [" 2600001b ", "2600001B\t", "\n2600001B"])
def test_client_ref_is_trimmed_and_any_case(ref: str) -> None:
    rows = (row("pln_10001", ref),)
    assert match_project(rows, False, INTERNAL_NO, "test") == "pln_10001"


def test_client_ref_048_any_case_on_live() -> None:
    rows = (row("pln_10001", " 2600001b/048 "),)
    assert match_project(rows, False, INTERNAL_NO, "live") == "pln_10001"


@pytest.mark.parametrize(
    ("ref", "site"),
    [
        ("2600001B/048", "test"),  # the live form is another suffix on test
        ("2600001B", "live"),  # the bare number is another suffix on live
        ("2600001B/023", "test"),
        ("2600001B/023", "live"),
        ("2600001B/0480", "live"),
        ("2600001BX", "test"),
        ("12600001B", "test"),
        ("2600001B 048", "live"),
        ("2600002B", "test"),
        ("", "test"),
    ],
)
def test_other_client_refs_are_ignored(ref: str, site: str) -> None:
    rows = (row("pln_10001", ref),)
    result = match_project(rows, False, INTERNAL_NO, site)
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


def test_other_suffix_rows_are_ignored_beside_the_one_match() -> None:
    rows = (
        row("pln_10011", "2600001B/023"),
        row("pln_10001", "2600001B/048"),
        row("pln_10012", "2600001B"),
    )
    assert match_project(rows, False, INTERNAL_NO, "live") == "pln_10001"
    assert match_project(rows, False, INTERNAL_NO, "test") == "pln_10012"


@pytest.mark.parametrize("company", ["Sample Builders", "B1 Homes Pty Ltd", ""])
def test_a_matching_row_of_another_company_is_ignored(company: str) -> None:
    rows = (row("pln_10001", INTERNAL_NO, company),)
    result = match_project(rows, False, INTERNAL_NO, "test")
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


def test_company_is_trimmed() -> None:
    rows = (row("pln_10001", INTERNAL_NO, " B1 Homes "),)
    assert match_project(rows, False, INTERNAL_NO, "test") == "pln_10001"


def test_no_rows_is_project_not_found() -> None:
    result = match_project((), False, INTERNAL_NO, "test")
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


def test_two_matching_projects_are_ambiguous() -> None:
    rows = (row("pln_10001", INTERNAL_NO), row("pln_10004", "2600001b "))
    result = match_project(rows, False, INTERNAL_NO, "test")
    assert result == skip(SkipReason.PROJECT_AMBIGUOUS)


def test_the_same_project_shown_twice_is_one_match() -> None:
    # A list can show the same row twice (screen map row 27): count projects.
    rows = (row("pln_10001", INTERNAL_NO), row("pln_10001", INTERNAL_NO))
    assert match_project(rows, False, INTERNAL_NO, "test") == "pln_10001"


@pytest.mark.parametrize(
    "rows",
    [
        (row("pln_10001", INTERNAL_NO),),  # a match on page 1
        (),  # no match on page 1: it could be on page 2
        (row("pln_10011", "2600001B/023"),),
    ],
)
def test_a_second_results_page_is_ambiguous(rows: tuple[SearchRow, ...]) -> None:
    result = match_project(rows, True, INTERNAL_NO, "test")
    assert result == skip(SkipReason.PROJECT_AMBIGUOUS)


@pytest.mark.parametrize("internal_no", ["", "  "])
@pytest.mark.parametrize("site", ["test", "live"])
def test_an_empty_internal_no_matches_nothing(internal_no: str, site: str) -> None:
    rows = (row("pln_10001", ""), row("pln_10002", "/048"))
    result = match_project(rows, False, internal_no, site)
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


def test_an_unknown_site_is_refused() -> None:
    with pytest.raises(ValueError):
        match_project((row("pln_10001", INTERNAL_NO),), False, INTERNAL_NO, "prod")


# --- step 8: the project window ---


def test_check_project_gives_the_matched_pln() -> None:
    assert check_project(lookup(), INTERNAL_NO, "test") == "pln_10001"


@pytest.mark.parametrize(
    ("value", "site"),
    [(" 2600001b ", "test"), ("2600001B/048", "live"), (" 2600001b/048", "live")],
)
def test_the_window_internal_no_follows_the_match_rule(value: str, site: str) -> None:
    project = lookup(search_rows=(row("pln_10001", value),), project_internal_no=value)
    assert check_project(project, INTERNAL_NO, site) == "pln_10001"


@pytest.mark.parametrize(
    ("value", "site"),
    [
        ("2600004B", "test"),
        ("", "test"),
        ("2600001B/048", "test"),
        ("2600001B", "live"),
        ("2600001B/023", "live"),
    ],
)
def test_a_window_internal_no_that_does_not_match_is_unexpected_screen(
    value: str, site: str
) -> None:
    ref = INTERNAL_NO if site == "test" else f"{INTERNAL_NO}/048"
    project = lookup(search_rows=(row("pln_10001", ref),), project_internal_no=value)
    result = check_project(project, INTERNAL_NO, site)
    assert result == skip(SkipReason.UNEXPECTED_SCREEN)


def test_a_failed_match_skips_before_the_window_is_read() -> None:
    project = lookup(search_rows=(), project_internal_no="2600004B")
    result = check_project(project, INTERNAL_NO, "test")
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


# --- step 10: duplicate check ---


@pytest.mark.parametrize("ignores_cancelled", [True, False])
def test_no_compaction_test_task_passes_with_no_task_numbers(
    ignores_cancelled: bool,
) -> None:
    assert check_duplicate((), ignores_cancelled) == ()


@pytest.mark.parametrize(
    "status", ["On Hold", "Completed", "Open", "In Progress", "", "cancelled"]
)
@pytest.mark.parametrize("ignores_cancelled", [True, False])
def test_any_task_not_cancelled_is_a_duplicate(
    status: str, ignores_cancelled: bool
) -> None:
    result = check_duplicate((task("tsk_200001", status),), ignores_cancelled)
    assert result == skip(SkipReason.DUPLICATE_TASK)


@pytest.mark.parametrize("status", ["Cancelled", " Cancelled "])
def test_a_cancelled_task_is_ignored_only_when_configured(status: str) -> None:
    tasks = (task("tsk_200001", status),)
    assert check_duplicate(tasks, True) == ("tsk_200001",)
    assert check_duplicate(tasks, False) == skip(SkipReason.DUPLICATE_TASK)


def test_one_live_task_among_cancelled_ones_is_a_duplicate() -> None:
    tasks = (
        task("tsk_200001", "Cancelled"),
        task("tsk_200002", "On Hold"),
        task("tsk_200003", "Cancelled"),
    )
    assert check_duplicate(tasks, True) == skip(SkipReason.DUPLICATE_TASK)


def test_every_existing_task_number_is_kept_for_w2() -> None:
    tasks = (task("tsk_200003", "Cancelled"), task("tsk_200001", "Cancelled"))
    assert check_duplicate(tasks, True) == ("tsk_200003", "tsk_200001")


# --- decide(), deterministic-only: section 2 order ---


def test_a_clean_po_skips_address_unverifiable() -> None:
    assert decide_det_only() == skip(SkipReason.ADDRESS_UNVERIFIABLE)


def test_steps_2a_to_4_come_before_the_project_lookup() -> None:
    no_project = lookup(search_rows=(), project_internal_no="")
    linked = NOTE.model_copy(update={"project_linked": True})
    text = PDF_TEXT.replace("2600001B/048", "2600002B/048")
    result = decide_det_only(linked, project=no_project)
    assert result == skip(SkipReason.NOTE_ALREADY_LINKED)
    result = decide_det_only(text=text, project=no_project)
    assert result == skip(SkipReason.PO_MISMATCH)


ON_HOLD = (task("tsk_200001", "On Hold"),)


@pytest.mark.parametrize(
    ("project", "reason"),
    [
        (lookup(search_rows=(), tasks=ON_HOLD), "PROJECT_NOT_FOUND"),
        (lookup(more_pages=True, tasks=ON_HOLD), "PROJECT_AMBIGUOUS"),
        (lookup(project_internal_no="2600004B", tasks=ON_HOLD), "UNEXPECTED_SCREEN"),
    ],
)
def test_the_project_lookup_comes_before_the_address_and_duplicate_steps(
    project: MySysLookup, reason: str
) -> None:
    assert decide_det_only(project=project) == skip(SkipReason(reason))


@pytest.mark.parametrize("ignores_cancelled", [True, False])
def test_the_address_step_comes_before_the_duplicate_check(
    ignores_cancelled: bool,
) -> None:
    # Deterministic-only skips at step 9, whatever tasks the project has.
    result = decide_det_only(
        project=lookup(tasks=ON_HOLD), ignores_cancelled=ignores_cancelled
    )
    assert result == skip(SkipReason.ADDRESS_UNVERIFIABLE)


def test_the_site_picks_the_match_rule_in_decide() -> None:
    project = lookup(
        search_rows=(row("pln_10001", f"{INTERNAL_NO}/048"),),
        project_internal_no=f"{INTERNAL_NO}/048",
    )
    result = decide_det_only(project=project, site="live")
    assert result == skip(SkipReason.ADDRESS_UNVERIFIABLE)
    result = decide_det_only(project=project, site="test")
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)
