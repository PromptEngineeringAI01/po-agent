"""The Tasks read of every task (task 9.8) against B1's Compaction Test read
frozen in tests/oracle (main be84448): on rows whose headers carry only the
mapped buttons, B1's duplicate read is unchanged, both through
`compaction_tasks` (W2, W3, the hold read, demo) and through the lookup's
`tasks` (step 10's duplicate check, W1's reopen). A header with other
buttons on lines of their own is the one intended change (Joey, 25 Nov
2026; tests/test_project_tasks.py).

Rows are built from header, details, spacer and other cells in the shape
`driver.task_rows` returns. Values are fake.
"""

from hypothesis import given
from hypothesis import strategies as st
from oracle import reader_rules as old_rules

from po_agent.core.errors import PartialWrite, UnexpectedScreen
from po_agent.core.models import CompactionTask, MySysLookup
from po_agent.mysys import tasks

NAMES = st.sampled_from(
    [
        "Compaction Test",
        "Compaction Tests",
        "compaction test",
        "Compaction Test Re-test",
        "Site Classification",
        "Hold Point",
        "",
    ]
)
BUTTONS = st.lists(
    st.sampled_from(["Undo Cancellation", "Cancel", "Un-Hold", "Hold"]),
    max_size=3,
)
GAPS = st.sampled_from(["\n", "", " ", "\t", "  \n"])


@st.composite
def headers(draw: st.DrawFn) -> list[str]:
    task_no = draw(st.sampled_from(["tsk_100001", "tsk_100002", "tsk_9"]))
    cell = f"({task_no}) | {draw(NAMES)}"
    for button in draw(BUTTONS):
        cell += draw(GAPS) + button
    return [draw(st.sampled_from(["", " "])) + cell + draw(st.sampled_from(["", "\n"]))]


DETAILS = st.lists(
    st.sampled_from(["---", "", "Fake Creator", "Cancelled", "New Project", " x "]),
    min_size=1,
    max_size=4,
)
OTHER = st.sampled_from([[""], [], ["Fake text"], ["(tsk_100003)"], ["tsk_100001 | x"]])
ROWS = st.lists(st.one_of(headers(), DETAILS, OTHER), max_size=8)


def old_compaction(rows: list[list[str]]) -> dict[str, str] | None:
    """The frozen read, None where it raised PartialWrite."""
    try:
        return old_rules.compaction_tasks(rows)
    except PartialWrite:
        return None


@given(ROWS)
def test_compaction_tasks_match_the_frozen_b1_read(rows):
    try:
        new = tasks.compaction_tasks(rows)
    except PartialWrite:
        new = None

    assert new == old_compaction(rows)


@given(ROWS)
def test_the_lookups_compaction_tasks_match_the_frozen_b1_read(rows):
    old = old_compaction(rows)
    try:
        every = tasks.project_tasks(rows)
    except UnexpectedScreen:
        assert old is None  # only where B1 stopped too
        return

    lookup = MySysLookup(search_rows=(), more_pages=False, project_tasks=every)

    assert old is not None
    assert lookup.tasks == tuple(
        CompactionTask(task_no=task_no, status=status)
        for task_no, status in old.items()
    )
