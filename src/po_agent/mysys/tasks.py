"""The project's Tasks table as MySys shows it (screen-map rows 07, 10):
shared parsing for every client, no browser code (task 9.2, moved from
`b1/reader_rules.py`). Cell text is untrusted: it never goes into an error.
"""

import re
from collections.abc import Iterator, Mapping, Sequence

from po_agent.core.errors import PartialWrite, UnexpectedScreen
from po_agent.core.models import COMPACTION_TEST, ProjectTask

# A task's header cell: "(tsk_200001) | Compaction Test" plus the row's
# button texts, which inner text can run on without a break. The pattern is
# B1's Compaction Test header (before 9.8) with the name captured, so a name
# is "Compaction Test" exactly when B1 read the header as one. A button
# label not listed here stays in the name, as shown (live shows more than
# the test site): such a header is never a Compaction Test task.
_TASK_HEADER = re.compile(
    r"\((tsk_[0-9]+)\) \| (.+?)"
    r"(?:\s*(?:Undo Cancellation|Cancel|Un-Hold|Hold))*\s*",
    re.DOTALL,
)
CANCELLED = "Cancelled"


def _headers(rows: Sequence[Sequence[str]]) -> Iterator[tuple[int, str, str]]:
    """(row index, task number, name) of every task header row."""
    for index, cells in enumerate(rows):
        match = _TASK_HEADER.fullmatch(cells[0].strip()) if cells else None
        if match is not None:
            yield index, match.group(1), match.group(2)


def _details(rows: Sequence[Sequence[str]], index: int) -> Sequence[str] | None:
    """The details row below the header at `index`, None if there is none."""
    if index + 1 >= len(rows) or len(rows[index + 1]) < 2:
        return None
    return rows[index + 1]


def project_tasks(rows: Sequence[Sequence[str]]) -> tuple[ProjectTask, ...]:
    """Every task in table order (task 9.8): each header row's number and
    name, and the details row right below it, whose second cell is the Task
    Creator and last the Status (row 07). A header of any name without a
    details row is UnexpectedScreen."""
    found = []
    for index, task_no, name in _headers(rows):
        details = _details(rows, index)
        if details is None:
            raise UnexpectedScreen("task row not recognised")
        found.append(
            ProjectTask(
                task_no=task_no,
                name=name,
                status=details[-1].strip(),
                task_creator=details[1].strip(),
            )
        )
    return tuple(found)


def compaction_tasks(rows: Sequence[Sequence[str]]) -> dict[str, str]:
    """Task number -> Status cell for every Compaction Test header row: the
    same headers as `project_tasks`, filtered. Only their details rows are
    needed; one missing is PartialWrite (W2 reads it after Submit)."""
    tasks = {}
    for index, task_no, name in _headers(rows):
        if name != COMPACTION_TEST:
            continue
        details = _details(rows, index)
        if details is None:
            raise PartialWrite("task row not recognised", reason="TASK_ROW")
        tasks[task_no] = details[-1].strip()
    return tasks


def live_tasks(tasks: Mapping[str, str]) -> list[str]:
    """Compaction Test tasks that aren't Cancelled (test site, row 07)."""
    return [task for task, status in tasks.items() if status != CANCELLED]


def new_task(before: set[str], after: Mapping[str, str]) -> str:
    """Step 6 read-back: exactly one Compaction Test task not seen before."""
    new = [task for task in after if task not in before]
    if len(new) != 1:
        raise PartialWrite("new task not found", reason="NO_NEW_TASK")
    return new[0]
