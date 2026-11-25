"""The project's Tasks table as MySys shows it (screen-map rows 07, 10):
shared parsing for every client, no browser code (task 9.2, moved from
`b1/reader_rules.py`). Cell text is untrusted: it never goes into an error.
"""

import re
from collections.abc import Mapping, Sequence

from po_agent.core.errors import PartialWrite

# "(tsk_200001) | Compaction Test" plus the row's button texts, which
# inner text can run on without a break.
_TASK_HEADER = re.compile(
    r"\((tsk_[0-9]+)\) \| Compaction Test"
    r"(?:\s*(?:Undo Cancellation|Cancel|Un-Hold|Hold))*\s*"
)
CANCELLED = "Cancelled"


def compaction_tasks(rows: Sequence[Sequence[str]]) -> dict[str, str]:
    """Task number -> Status cell for every "(tsk_...) | Compaction Test"
    header row. The details row right below it ends with the Status cell."""
    tasks = {}
    for index, cells in enumerate(rows):
        match = _TASK_HEADER.fullmatch(cells[0].strip()) if cells else None
        if match is None:
            continue
        if index + 1 >= len(rows) or len(rows[index + 1]) < 2:
            raise PartialWrite("task row not recognised", reason="TASK_ROW")
        tasks[match.group(1)] = rows[index + 1][-1].strip()
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
