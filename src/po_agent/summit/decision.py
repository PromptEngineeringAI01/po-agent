"""Summit's decision engine (task 9.9; SPEC.md -> Client 2: Summit Home,
Decision checks and skip reasons, Creator table).

Pure functions, no browser code, as `b1/decision.py`. `decide()` applies
SPEC's table in its order, cheap first, so a non-compaction PDF costs no
project search: the Note checks; the PDF checks on both readers' text
(`reader_rules.check_pdf`, task 9.7); the PDF's PO against the Note
title's; the title's and the PDF's company in the creator table; then the
one project lookup: the project match and its Client Internal No., the
three companies on one table row, the duplicate check and the creator.
The first failing check decides; anything uncertain is a skip. No address
check for Summit (decisions, 23 Nov 2026): the identity link is the PO.
"""

import re
from collections.abc import Callable, Sequence

from po_agent.b1.readers import PdfTexts
from po_agent.core.config import Company
from po_agent.core.models import (
    COMPACTION_TEST,
    MySysLookup,
    NoteSnapshot,
    ProjectTask,
    SearchRow,
    Skip,
    SkipReason,
)
from po_agent.mysys.tasks import CANCELLED
from po_agent.summit import reader_rules as rules
from po_agent.summit.company import fold, row_for
from po_agent.summit.models import PO_PATTERN, SummitProceed

# The title shape <company> - <any text> - PO: <PO> - <any word>.
_TITLE_COMPANY_END = " - "
_TITLE_PO = re.compile(r"(?<![0-9A-Za-z])PO:\s*(\S*)")
# A Task Creator cell that names nobody.
_NO_CREATOR = ("", "---")


def _skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


def title_parts(title: str) -> tuple[str, str]:
    """The Note title's company (the text before the first " - ", trimmed)
    and its PO, "" when the title doesn't hold exactly one well-formed
    `PO: <d>/<d>/<d>`."""
    company = title.split(_TITLE_COMPANY_END, 1)[0].strip()
    values = _TITLE_PO.findall(title)
    po = values[0] if len(values) == 1 else ""
    return company, po if re.fullmatch(PO_PATTERN, po) else ""


def match_project(
    rows: Sequence[SearchRow],
    more_pages: bool,
    client_ref: str,
    companies: Sequence[Company],
) -> Skip | tuple[str, Company]:
    """The one project whose Client Ref No. (trimmed, any case) is
    `client_ref` and whose Company names a table row: its pln and that row.
    None -> PROJECT_NOT_FOUND; more than one, or a second page ->
    PROJECT_AMBIGUOUS. The same row shown twice is one project."""
    wanted = fold(client_ref)
    found: dict[tuple[str, str], Company] = {}
    for row in rows:
        company = row_for(row.company, companies)
        if wanted and fold(row.client_ref_no) == wanted and company is not None:
            found[(row.pln, company.name)] = company
    if more_pages or len(found) > 1:
        return _skip(SkipReason.PROJECT_AMBIGUOUS)
    if not found:
        return _skip(SkipReason.PROJECT_NOT_FOUND)
    ((pln, _), company), *_ = found.items()
    return pln, company


def previous_task(tasks: Sequence[ProjectTask]) -> Skip | ProjectTask:
    """The task with the highest task number whose name is not Compaction
    Test and whose Status is not Cancelled, with a Task Creator. None, a
    Task Creator empty or `---`, or that number shown twice with different
    Task Creators -> CREATOR_UNKNOWN."""
    candidates = [
        task
        for task in tasks
        if task.name.strip() != COMPACTION_TEST and task.status.strip() != CANCELLED
    ]
    if not candidates:
        return _skip(SkipReason.CREATOR_UNKNOWN)
    top = max(int(task.task_no.removeprefix("tsk_")) for task in candidates)
    at_top = [t for t in candidates if int(t.task_no.removeprefix("tsk_")) == top]
    creators = {task.task_creator.strip() for task in at_top}
    if len(creators) != 1 or creators & set(_NO_CREATOR):
        return _skip(SkipReason.CREATOR_UNKNOWN)
    return at_top[0]


def is_duplicate(found: MySysLookup) -> bool:
    """Any Compaction Test task not Cancelled, whatever its PO; a Cancelled
    one doesn't block a Summit booking (Joey, 25 Nov 2026). Every row is
    read, not one status per number, so a number shown twice, once not
    Cancelled, still counts (9.9 review)."""
    rows = [
        task.status
        for task in found.project_tasks
        if task.name.strip() == COMPACTION_TEST
    ]
    rows += [task.status for task in found.tasks]
    return any(status.strip() != CANCELLED for status in rows)


def decide(
    note: NoteSnapshot,
    original_assignee: str,
    texts: PdfTexts,
    lookup: Callable[[], MySysLookup],
    *,
    companies: Sequence[Company],
) -> Skip | SummitProceed:
    """SPEC's Summit decision table in order on the Note window as read
    (its title too), the Note's original assignee, both readers' text of
    its PDF, and the creator table. `lookup` is the read-only project read
    in MySys: called once, and only when every Note, PDF, PO and company
    check before it passes."""
    if note.project_linked:
        return _skip(SkipReason.NOTE_ALREADY_LINKED)
    names = note.attachment_names
    if len(names) > 1:  # any second attachment, as B1's link count
        return _skip(SkipReason.MULTIPLE_PDFS)
    if not names or not names[0].lower().endswith(".pdf"):
        return _skip(SkipReason.NO_PDF)
    reading = rules.check_pdf(texts)
    if isinstance(reading, Skip):
        return reading
    title_company, title_po = title_parts(note.title)
    if not title_po or reading.po_number != title_po:
        return _skip(SkipReason.PO_MISMATCH)
    title_row = row_for(title_company, companies)
    pdf_row = row_for(reading.company, companies)
    if title_row is None or pdf_row is None:
        return _skip(SkipReason.COMPANY_UNKNOWN)

    client_ref = reading.po_number.split("/")[0]
    found = lookup()
    matched = match_project(found.search_rows, found.more_pages, client_ref, companies)
    if isinstance(matched, Skip):
        return matched
    pln, project_row = matched
    if fold(found.project_internal_no) != fold(client_ref):
        return _skip(SkipReason.UNEXPECTED_SCREEN)
    if not title_row.name == pdf_row.name == project_row.name:
        return _skip(SkipReason.COMPANY_MISMATCH)
    if is_duplicate(found):
        return _skip(SkipReason.DUPLICATE_TASK)

    previous: ProjectTask | None = None
    creator = project_row.creator
    if project_row.creator_rule == "previous_task":
        found_previous = previous_task(found.project_tasks)
        if isinstance(found_previous, Skip):
            return found_previous
        previous = found_previous
        creator = previous.task_creator.strip()
    if creator is None:  # the client file holds exactly one of the two
        return _skip(SkipReason.CREATOR_UNKNOWN)
    return SummitProceed(
        note_id=note.note_id,
        internal_no=client_ref,
        pln=pln,
        po_number=reading.po_number,
        email_body=note.body,
        pdf_file_name=names[0],
        pdf_bytes=texts.data,
        existing_task_nos=tuple(task.task_no for task in found.tasks),
        creator=creator,
        original_assignee=original_assignee,
        previous_task_no=None if previous is None else previous.task_no,
        previous_task_creator=None if previous is None else creator,
    )
