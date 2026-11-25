"""The Tasks read for every client (task 9.8; SPEC.md -> Client 2, What is
shared): every task's number, name, status and Task Creator from the
project's Tasks table (screen-map rows 07, 10), and B1's Compaction Test
tasks as the same rows filtered.

Pure functions on fake rows, in the shape `driver.task_rows` returns: a
header row "(tsk_<n>) | <name>" plus its buttons, then a details row Lodged
By, Task Creator, ..., Status. Values are fake.
"""

import pytest
from pydantic import ValidationError

from po_agent.core.errors import PartialWrite, UnexpectedScreen
from po_agent.core.models import CompactionTask, MySysLookup, ProjectTask
from po_agent.mysys import tasks


def details(creator: str, status: str) -> list[str]:
    """A details row: Lodged By, Task Creator, Create, Office, Stage, Owner,
    Turn Around Time, Days to Complete, Due Date, Status (row 07)."""
    return [
        "---",
        creator,
        "06 May 2026",
        "Fake Office Pty Ltd",
        "---",
        "Fake Owner",
        "3 Days",
        "4 Days",
        "12 May 2026",
        status,
    ]


ROWS = [
    ["(tsk_300001) | Site Classification\nCancel\nHold"],
    details("Fake Creator A", "Certification Passed"),
    ["(tsk_300002) | Energy Efficiency\nUndo Cancellation"],
    details("Fake Creator B", "Cancelled"),
    ["(tsk_300003) | Compaction Test\nCancel\nUn-Hold"],
    details("Fake Creator C", "On-hold\nNotes:"),
    [""],
    ["(tsk_300004) | Footing Details\nCancel\nHold"],
    details("", "New Project"),
    ["(tsk_300005) | Stormwater Layout"],
    details("---", "Certification Passed"),
]


def task(task_no: str, name: str, status: str, creator: str) -> ProjectTask:
    return ProjectTask(task_no=task_no, name=name, status=status, task_creator=creator)


def test_every_task_is_read_with_its_name_status_and_task_creator():
    assert tasks.project_tasks(ROWS) == (
        task(
            "tsk_300001",
            "Site Classification",
            "Certification Passed",
            "Fake Creator A",
        ),
        task("tsk_300002", "Energy Efficiency", "Cancelled", "Fake Creator B"),
        task("tsk_300003", "Compaction Test", "On-hold\nNotes:", "Fake Creator C"),
        task("tsk_300004", "Footing Details", "New Project", ""),
        task("tsk_300005", "Stormwater Layout", "Certification Passed", "---"),
    )


def test_buttons_run_on_without_a_break_stay_out_of_the_name():
    rows = [["(tsk_300007) | Compaction TestCancelHold"], details("X", "New Project")]

    assert tasks.project_tasks(rows) == (
        task("tsk_300007", "Compaction Test", "New Project", "X"),
    )


def test_header_buttons_on_their_own_lines_stay_out_of_the_name():
    # Joey's live screenshot of a Summit project (24 Nov 2026): header rows
    # carry buttons beyond the four the test site showed, on lines of their
    # own. The name is the header's first line, whatever buttons follow it
    # (Joey, 25 Nov 2026: such a Compaction Test header counts for the
    # duplicate check, a quiet DUPLICATE_TASK skip).
    rows = [
        ["(tsk_300008) | Compaction Test\nVariation\nUnassign"],
        details("Fake Creator D", "Certification Passed"),
        ["(tsk_300009) | 1.Single Storey Engineering & Footing\nVariation"],
        details("Fake Creator E", "Certification Passed"),
    ]

    assert tasks.project_tasks(rows) == (
        task("tsk_300008", "Compaction Test", "Certification Passed", "Fake Creator D"),
        task(
            "tsk_300009",
            "1.Single Storey Engineering & Footing",
            "Certification Passed",
            "Fake Creator E",
        ),
    )


def test_an_unmapped_button_run_on_stays_in_the_name():
    # Never read as "Compaction Test": the select then lists a Compaction
    # Test the table doesn't, and the settled read stops (UNEXPECTED_SCREEN).
    rows = [["(tsk_300010) | Compaction TestVariation"], details("X", "New Project")]

    assert tasks.project_tasks(rows) == (
        task("tsk_300010", "Compaction TestVariation", "New Project", "X"),
    )


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param([["(tsk_300003) | Compaction Test\nCancel\nHold"]], id="last"),
        pytest.param(
            [
                ["(tsk_300003) | Compaction Test\nCancel\nHold"],
                ["(tsk_300001) | Site Classification\nCancel\nHold"],
                details("Fake Creator A", "New Project"),
            ],
            id="another-header-next",
        ),
        pytest.param(
            [["(tsk_300003) | Compaction Test\nCancel\nHold"], [""]],
            id="spacer-next",
        ),
    ],
)
def test_a_compaction_header_without_its_details_row_is_an_unexpected_screen(rows):
    with pytest.raises(UnexpectedScreen):
        tasks.project_tasks(rows)


def test_another_tasks_header_without_its_details_row_is_kept_unknown():
    # As B1 before 9.8, such a row never stops a run. Its status and Task
    # Creator read as empty (unknown), so Summit's previous-task rule skips
    # CREATOR_UNKNOWN on it rather than passing over it.
    rows = [
        ["(tsk_300001) | Site Classification\nCancel\nHold"],
        ["(tsk_300003) | Compaction Test\nCancel\nHold"],
        details("Fake Creator C", "New Project"),
        ["(tsk_300004) | Footing Details\nCancel\nHold"],
        [""],
    ]

    assert tasks.project_tasks(rows) == (
        task("tsk_300001", "Site Classification", "", ""),
        task("tsk_300003", "Compaction Test", "New Project", "Fake Creator C"),
        task("tsk_300004", "Footing Details", "", ""),
    )


def test_compaction_tasks_are_the_same_rows_filtered():
    assert tasks.compaction_tasks(ROWS) == {"tsk_300003": "On-hold\nNotes:"}


def test_a_compaction_header_with_other_buttons_counts_for_the_duplicate_check():
    # Joey, 25 Nov 2026: before 9.8 such a header was passed over and the
    # settled read stopped (ALERT UNEXPECTED_SCREEN); now DUPLICATE_TASK.
    rows = [
        ["(tsk_300008) | Compaction Test\nVariation\nUnassign"],
        details("Fake Creator D", "Certification Passed"),
    ]

    assert tasks.compaction_tasks(rows) == {"tsk_300008": "Certification Passed"}


def test_compaction_tasks_need_only_their_own_details_rows():
    # As before 9.8: another task's header without its details row is
    # outside the Compaction Test read (W2, W3, the hold read, demo).
    rows = [
        ["(tsk_300003) | Compaction Test\nCancel\nHold"],
        details("Fake Creator C", "New Project"),
        ["(tsk_300004) | Footing Details\nCancel\nHold"],
    ]

    assert tasks.compaction_tasks(rows) == {"tsk_300003": "New Project"}


def test_compaction_tasks_keep_their_partial_write_for_a_missing_details_row():
    # W2 and W3 read it after Submit: a broken table there is PARTIAL_WRITE.
    with pytest.raises(PartialWrite):
        tasks.compaction_tasks([["(tsk_300003) | Compaction Test\nCancel\nHold"]])


# MySysLookup: B1's duplicate check reads `tasks`, the Compaction Test ones.


def test_a_lookup_of_every_task_holds_its_compaction_tasks():
    lookup = MySysLookup(
        search_rows=(),
        more_pages=False,
        project_tasks=tasks.project_tasks(ROWS),
    )

    assert lookup.tasks == (
        CompactionTask(task_no="tsk_300003", status="On-hold\nNotes:"),
    )


def test_a_lookup_whose_compaction_tasks_disagree_with_every_task_is_refused():
    with pytest.raises(ValidationError):
        MySysLookup(
            search_rows=(),
            more_pages=False,
            project_tasks=tasks.project_tasks(ROWS),
            tasks=(CompactionTask(task_no="tsk_300001", status="New Project"),),
        )


def test_a_project_task_number_must_be_a_task_number():
    with pytest.raises(ValidationError):
        task("300001", "Site Classification", "New Project", "X")
