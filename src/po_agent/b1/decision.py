"""The decision engine (SPEC.md -> In the MVP; docs/specs/spec.md section 2).

Pure functions, no browser code. `decide()` takes the project lookup as a
callable: the run passes the driver's read of MySys, seam 1 a fixture, and
`decide()` calls it only once the Note and PDF checks pass (task 8.3).
"""

import re
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from po_agent.b1 import reader_rules as rules
from po_agent.b1 import readers
from po_agent.b1.models import B1Proceed, DeterministicReading
from po_agent.core.models import (
    CompactionTask,
    MySysLookup,
    NotePoolRow,
    NoteSnapshot,
    SearchRow,
    Skip,
    SkipReason,
)

# Each profile's Note Pool title rule: test-body-filename on test,
# live-b1-title on live (core/config.py).
TitleRule = Literal["test-body-filename", "live-b1-title"]
# The profile's site; the project match rule is the same on both (Joey's
# look at live, 10 Nov 2026).
Site = Literal["test", "live"]

UNLINKED_PROJECT = "---"
# B1's Creator on every task it books (ADR-003 decision 3: a client rule,
# carried in the Proceed; SPEC.md -> Client 2: Creator table).
CREATOR = "Perth Scheduling"
# Spec open question 10: live numbers look like 2609034B; until confirmed,
# accept upper-case letters and digits only.
_INTERNAL_NO = r"[0-9A-Z]+"
# <internal no>_048[_n].pdf, not part of a longer word or file name.
_TEST_FILENAME = re.compile(
    rf"(?<![0-9A-Za-z_])({_INTERNAL_NO})_048(?:_[0-9]+)?\.pdf(?![0-9A-Za-z_.])"
)
# The title [B1 Homes] Order <internal no>/048 at the start of the cell, then
# the body or nothing.
_LIVE_TITLE = re.compile(rf"\[B1 Homes\] Order ({_INTERNAL_NO})/048(?=\s|$)")
# Live's second-number check: <internal no>_048[_n].pdf or <internal no>/048
# anywhere in the cell, with _TEST_FILENAME's leading boundary. Wider than
# the test rule, so it refuses more, never less: any case (compare upper
# case), and a following "." still counts ("... file <n>_048_1.pdf.").
_LIVE_PO = re.compile(
    r"(?<![0-9A-Za-z_])([0-9A-Z]+)(?:_048(?:_[0-9]+)?\.pdf|/048)(?![0-9A-Za-z_])",
    re.IGNORECASE,
)


def eligible_internal_no(
    row: NotePoolRow, rule: TitleRule, pool_name: str
) -> str | None:
    """Step 0: the internal number if the row is eligible, else None.

    Eligible: the Subject/Note cell matches the title rule, the Project cell
    reads "---" and the Assignee cell reads pool_name (so a person's Note is
    never taken, even if the pool filter didn't apply). Anything uncertain,
    such as two different internal numbers in one cell, is not eligible: on
    live, a body naming another number as <n>_048[_m].pdf or <n>/048
    (Joey, 24 Nov 2026).
    """
    if row.project.strip() != UNLINKED_PROJECT or row.assignee.strip() != pool_name:
        return None
    cell = row.subject_note.strip()
    if rule == "test-body-filename":
        found = {m.group(1) for m in _TEST_FILENAME.finditer(cell)}
        return found.pop() if len(found) == 1 else None
    if rule == "live-b1-title":
        match = _LIVE_TITLE.match(cell)
        if not match:
            return None
        found = {m.group(1).upper() for m in _LIVE_PO.finditer(cell)}
        return match.group(1) if found == {match.group(1)} else None
    raise ValueError("unknown title rule")


class NoteChecked(BaseModel):
    """Steps 2a-4 passed: what the later steps and Proceed take from them."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    internal_no: str
    pdf_file_name: str
    # The Note's body as MySys shows it: never the title.
    email_body: str = Field(repr=False)
    reading: DeterministicReading


def check_note_and_pdf(
    note: NoteSnapshot, internal_no: str, pdf_text: str
) -> Skip | NoteChecked:
    """Steps 2a-4 in section 2 order; the first failing check decides.

    internal_no is step 0's. pdf_text is the PDF's text layer, "" when it has
    none or can't be read (reader_rules.text_layer).
    """
    if note.project_linked:
        return Skip(reason=SkipReason.NOTE_ALREADY_LINKED)
    names = note.attachment_names
    if len(names) > 1:  # any second attachment, as the link count (SPEC.md)
        return Skip(reason=SkipReason.MULTIPLE_PDFS)
    if not names or not names[0].lower().endswith(".pdf"):
        return Skip(reason=SkipReason.NO_PDF)
    if not pdf_text.strip():
        return Skip(reason=SkipReason.PDF_UNREADABLE)
    reading = rules.read_pdf(pdf_text, names[0], note.title)
    if reading.issuer != rules.ISSUER:
        return Skip(reason=SkipReason.NOT_B1)
    if not reading.contains_compaction:
        return Skip(reason=SkipReason.NOT_COMPACTION)
    po_number = f"{internal_no}/{rules.PO_SUFFIX}"
    if (
        reading.po_number != po_number
        or reading.po_from_filename != po_number
        or reading.po_from_title not in (None, po_number)
    ):
        return Skip(reason=SkipReason.PO_MISMATCH)
    return NoteChecked(
        internal_no=internal_no,
        pdf_file_name=names[0],
        email_body=note.body,
        reading=reading,
    )


def _client_ref(internal_no: str, site: Site) -> str | None:
    """The Client Ref No. a matching project holds, lower case; None when
    there is no internal number to match. The bare internal number on both
    sites: live's Projects search shows it so too, and `/048` belongs to the
    Note's title (Joey's look at live, 10 Nov 2026)."""
    if site not in ("test", "live"):
        raise ValueError("unknown site")
    wanted = internal_no.strip().lower()
    return wanted or None


def _is_ref(value: str, ref: str | None) -> bool:
    return ref is not None and value.strip().lower() == ref


def match_project(
    rows: Sequence[SearchRow], more_pages: bool, internal_no: str, site: Site
) -> Skip | str:
    """Step 8's match rule (SPEC.md -> MySys screen rules -> Project search):
    the pln of the one B1 Homes row whose Client Ref No. (trimmed, any case)
    is <internal no>, on both sites. Other rows are ignored. The driver
    (3.2) calls this to choose the pln link it opens."""
    ref = _client_ref(internal_no, site)
    # A set: a list can show the same row twice (screen map row 27).
    plns = {
        row.pln
        for row in rows
        if row.company.strip() == rules.COMPANY and _is_ref(row.client_ref_no, ref)
    }
    if more_pages or len(plns) > 1:
        return Skip(reason=SkipReason.PROJECT_AMBIGUOUS)
    if not plns:
        return Skip(reason=SkipReason.PROJECT_NOT_FOUND)
    return plns.pop()


def check_project(lookup: MySysLookup, internal_no: str, site: Site) -> Skip | str:
    """Step 8: the matched pln, and the opened project's Client Internal No.
    satisfies the same rule, else UNEXPECTED_SCREEN (the run loop stops)."""
    pln = match_project(lookup.search_rows, lookup.more_pages, internal_no, site)
    if isinstance(pln, Skip):
        return pln
    if not _is_ref(lookup.project_internal_no, _client_ref(internal_no, site)):
        return Skip(reason=SkipReason.UNEXPECTED_SCREEN)
    return pln


def check_duplicate(
    tasks: Sequence[CompactionTask], ignores_cancelled: bool
) -> Skip | tuple[str, ...]:
    """Step 10 (MVP strict): any Compaction Test task counts, whatever its PO
    number; a Cancelled one only when ignores_cancelled is false. On a pass,
    every existing task number, Cancelled ones too, for W2."""
    for task in tasks:
        if not (ignores_cancelled and task.status.strip() == rules.CANCELLED):
            return Skip(reason=SkipReason.DUPLICATE_TASK)
    return tuple(task.task_no for task in tasks)


def decide(
    note: NoteSnapshot,
    internal_no: str,
    texts: readers.PdfTexts,
    lookup: Callable[[], MySysLookup],
    *,
    site: Site,
    duplicate_ignores_cancelled: bool,
) -> Skip | B1Proceed:
    """Steps 2a-11 in section 2 order on the inputs given; the first failing
    step decides: steps 2a-4, the second reader, the project lookup (8), the
    address check against the project's address (9), the duplicate check
    (10). Code only, no Claude (decisions, 2 Nov 2026).

    texts holds both readers' text layers (readers.read). lookup is the
    project read in MySys (step 8): called once, and only when steps 2a-4
    and the second reader pass. The address check runs on both texts
    (readers.check_address).
    """
    checked = check_note_and_pdf(note, internal_no, texts.plumber)
    if isinstance(checked, Skip):
        return checked
    second = readers.check_second_reader(texts)
    if second is not None:
        return second
    found = lookup()
    pln = check_project(found, internal_no, site)
    if isinstance(pln, Skip):
        return pln
    address = readers.check_address(texts, found.address)
    if address is not None:
        return Skip(reason=address)
    task_nos = check_duplicate(found.tasks, duplicate_ignores_cancelled)
    if isinstance(task_nos, Skip):
        return task_nos
    return B1Proceed(
        note_id=note.note_id,
        internal_no=checked.internal_no,
        pln=pln,
        po_number=checked.reading.po_number,
        email_body=checked.email_body,
        pdf_file_name=checked.pdf_file_name,
        pdf_bytes=texts.data,
        existing_task_nos=task_nos,
        creator=CREATOR,
    )
