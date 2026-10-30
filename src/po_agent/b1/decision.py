"""The decision engine (SPEC.md -> In the MVP; docs/specs/spec.md section 2).

Pure functions, no browser code.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from po_agent.b1 import reader_rules as rules
from po_agent.b1.models import (
    DeterministicReading,
    NotePoolRow,
    NoteSnapshot,
    Skip,
    SkipReason,
)

# test-body-filename is the only rule a config can select in the MVP;
# live-b1-title exists for offline tests of real live Notes (SPEC.md, section 2 row).
TitleRule = Literal["test-body-filename", "live-b1-title"]

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
