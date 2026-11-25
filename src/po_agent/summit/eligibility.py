"""Summit's list eligibility on the Note Pool rows (task 9.11; SPEC.md ->
Client 2: Summit Home, Which Notes; docs/decisions.md, 24 Nov 2026, Summit
assignee rule).

Pure, no click, as B1's step 0. A row is eligible only when all four hold:
- its Source cell equals the client's `sender` exactly (the bare address;
  live's list shows no display name);
- its Project cell reads `---`;
- the assignee rule: a run starting before `any_assignee_before` (08:00 in
  the site's time zone, Perth) takes any assignee but an agent account; a
  later run only `---`. The run's own start time decides (no state between
  runs);
- its Subject/Note cell has the Summit title shape `<company> - <any text> -
  PO: <PO> - <any word>`, the whole cell (live shows a Summit email Note's
  title alone there), with one `PO:` and the PO's value once.
READY or ISSUED doesn't matter: the PDF decides. Anything else is
untouched, with no NOTE line.
"""

import re
from collections.abc import Collection, Sequence
from datetime import datetime, time
from zoneinfo import ZoneInfo

from po_agent.core.client import EligibleNote
from po_agent.core.models import NotePoolRow
from po_agent.summit.company import fold

UNASSIGNED = "---"  # an empty Assignee or Project cell (screen-map row 01)
# <company> - <any text> - PO: <d>/<d>/<d> - <any word>, the whole cell.
_TITLE = re.compile(
    r"(?P<company>\S.*?) - \S.* - PO: (?P<po>[0-9]+/[0-9]+/[0-9]+) - \S+"
)
# Any "PO:" label, as the decision engine counts them (summit/decision.py).
_PO_LABEL = re.compile(r"(?<![0-9A-Za-z])PO:")


def first_run(started: datetime, before: time, tz: str) -> bool:
    """The run is the day's first: it started before `before` in `tz`."""
    return started.astimezone(ZoneInfo(tz)).time() < before


def title_po(cell: str) -> str | None:
    """The PO of a cell with the Summit title shape, else None."""
    match = _TITLE.fullmatch(cell)
    if match is None or len(_PO_LABEL.findall(cell)) != 1:
        return None
    po = match.group("po")
    return po if cell.count(po) == 1 else None


def _assignee_passes(
    assignee: str, agents: Collection[str], any_assignee: bool
) -> bool:
    """An agent account never; `---` always; anyone else (a person, a pool)
    only in the day's first run. A blank cell names nobody: never."""
    if fold(assignee) in {fold(agent) for agent in agents}:
        return False
    return assignee == UNASSIGNED or (any_assignee and bool(assignee.strip()))


def eligible_notes(
    rows: Sequence[NotePoolRow],
    *,
    sender: str,
    agents: Collection[str],
    any_assignee: bool,
) -> tuple[EligibleNote, ...]:
    """Every eligible row, in list order: its Note ID and the PO before its
    first "/" (the Client Ref No. the project is searched by). `agents`: the
    agent accounts' user names, never taken; `any_assignee`: the run is the
    day's first."""
    found = []
    for row in rows:
        if row.source != sender or row.project != UNASSIGNED:
            continue
        if not _assignee_passes(row.assignee, agents, any_assignee):
            continue
        po = title_po(row.subject_note)
        if po is not None:
            found.append(
                EligibleNote(
                    note_id=row.note_id,
                    internal_no=po.split("/")[0],
                    title=row.subject_note,
                )
            )
    return tuple(found)
