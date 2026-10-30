"""The decision engine (SPEC.md -> In the MVP; docs/specs/spec.md section 2).

Pure functions, no browser code.
"""

import re
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from po_agent.b1 import reader_rules as rules
from po_agent.b1.address import verify_address
from po_agent.b1.models import (
    CompactionTask,
    DeterministicReading,
    MySysLookup,
    NotePoolRow,
    NoteSnapshot,
    Proceed,
    Reading,
    SearchRow,
    Skip,
    SkipReason,
)

# test-body-filename is the only rule a config can select in the MVP;
# live-b1-title exists for offline tests of real live Notes (SPEC.md, section 2 row).
TitleRule = Literal["test-body-filename", "live-b1-title"]
# The code is test site only (Must never #3); "live" is the live match rule as
# pure logic, for offline tests, with no host or config behind it.
Site = Literal["test", "live"]
ReaderMode = Literal["hybrid", "deterministic-only"]

UNLINKED_PROJECT = "---"
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


def eligible_internal_no(
    row: NotePoolRow, rule: TitleRule, pool_name: str
) -> str | None:
    """Step 0: the internal number if the row is eligible, else None.

    Eligible: the Subject/Note cell matches the title rule, the Project cell
    reads "---" and the Assignee cell reads pool_name (so a person's Note is
    never taken, even if the pool filter didn't apply). Anything uncertain,
    such as two different internal numbers in one cell, is not eligible.
    """
    if row.project.strip() != UNLINKED_PROJECT or row.assignee.strip() != pool_name:
        return None
    cell = row.subject_note.strip()
    if rule == "test-body-filename":
        found = {m.group(1) for m in _TEST_FILENAME.finditer(cell)}
        return found.pop() if len(found) == 1 else None
    if rule == "live-b1-title":
        match = _LIVE_TITLE.match(cell)
        return match.group(1) if match else None
    raise ValueError("unknown title rule")


class NoteChecked(BaseModel):
    """Steps 2a-4 passed: what the later steps and Proceed take from them."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    internal_no: str
    pdf_file_name: str
    # The Note's body as MySys shows it: never the title, never Claude.
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
    there is no internal number to match."""
    wanted = internal_no.strip().lower()
    if site == "test":
        ref = wanted
    elif site == "live":
        ref = f"{wanted}/{rules.PO_SUFFIX}"
    else:
        raise ValueError("unknown site")
    return ref if wanted else None


def _is_ref(value: str, ref: str | None) -> bool:
    return ref is not None and value.strip().lower() == ref


def match_project(
    rows: Sequence[SearchRow], more_pages: bool, internal_no: str, site: Site
) -> Skip | str:
    """Step 8's match rule (SPEC.md -> MySys screen rules -> Project search):
    the pln of the one B1 Homes row whose Client Ref No. (trimmed, any case)
    is <internal no> on test or <internal no>/048 on live. Other rows are
    ignored. The driver (3.2) calls this to choose the pln link it opens."""
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


class ClaudeUnavailable(Exception):
    """The Claude reader timed out or failed after its retry (step 6)."""


def _readers_agree(deterministic: DeterministicReading, claude: Reading) -> bool:
    """Step 7: identical issuer, COMPACTION, PO number and internal number."""
    return (
        claude.issuer == deterministic.issuer
        and claude.contains_compaction == deterministic.contains_compaction
        and claude.po_number == deterministic.po_number
        and claude.client_internal_no == deterministic.client_internal_no
    )


def decide(
    note: NoteSnapshot,
    internal_no: str,
    pdf_text: str,
    pdf_bytes: bytes,
    lookup: MySysLookup,
    *,
    site: Site,
    reader_mode: ReaderMode,
    duplicate_ignores_cancelled: bool,
    read_claude: Callable[[], str] | None = None,
) -> Skip | Proceed:
    """Steps 2a-11 in section 2 order on the inputs given; the first failing
    step decides. Deterministic-only mode has no Claude extraction to verify,
    so a PO that passes step 8 skips ADDRESS_UNVERIFIABLE at step 9 (C4).

    read_claude (hybrid only) returns Claude's raw JSON reading. It must turn
    every timeout and SDK error into ClaudeUnavailable (2.5); any other
    exception propagates. It is called only after steps 2a-4 pass.
    """
    if reader_mode not in ("hybrid", "deterministic-only"):
        raise ValueError("unknown reader mode")
    reader = read_claude if reader_mode == "hybrid" else None
    if reader_mode == "hybrid" and reader is None:
        raise ValueError("hybrid mode needs a Claude reader")
    checked = check_note_and_pdf(note, internal_no, pdf_text)
    if isinstance(checked, Skip):
        return checked
    claude: Reading | None = None
    if reader is not None:
        try:
            raw = reader()
        except ClaudeUnavailable:
            return Skip(reason=SkipReason.CLAUDE_UNAVAILABLE)
        try:
            claude = Reading.model_validate_json(raw)
        except ValidationError:
            return Skip(reason=SkipReason.CLAUDE_INVALID_OUTPUT)
        if not _readers_agree(checked.reading, claude):
            return Skip(reason=SkipReason.READERS_DISAGREE)
    pln = check_project(lookup, internal_no, site)
    if isinstance(pln, Skip):
        return pln
    if claude is None:
        return Skip(reason=SkipReason.ADDRESS_UNVERIFIABLE)
    address = verify_address(claude, pdf_text, lookup.address)
    if address is not None:
        return Skip(reason=address)
    task_nos = check_duplicate(lookup.tasks, duplicate_ignores_cancelled)
    if isinstance(task_nos, Skip):
        return task_nos
    return Proceed(
        note_id=note.note_id,
        internal_no=checked.internal_no,
        pln=pln,
        po_number=checked.reading.po_number,
        email_body=checked.email_body,
        pdf_file_name=checked.pdf_file_name,
        pdf_bytes=pdf_bytes,
        existing_task_nos=task_nos,
    )
