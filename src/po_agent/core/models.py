"""Shared models: what MySys shows and what the booker takes, for every
client (ADR-003 decisions 2-3; SPEC.md -> Code style: pydantic at every
boundary). A client's own rules (B1's /048 PO, its readings) stay in its
package (`b1/models.py`)."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class NotePoolRow(BaseModel):
    """One Note Pool list row as read from the page, cells as shown.

    Cell text is untrusted page data: it never goes to run output.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    note_id: StrictStr = Field(min_length=1)  # the row's ID cell (row 05)
    subject_note: StrictStr  # title and body joined (row 01)
    project: StrictStr  # "---" when not linked
    assignee: StrictStr


class SkipReason(StrEnum):
    """Skip reasons, exactly docs/specs/spec.md section 3 (no Claude reasons
    since decisions, 2 Nov 2026)."""

    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    NO_PDF = "NO_PDF"
    MULTIPLE_PDFS = "MULTIPLE_PDFS"
    PDF_UNREADABLE = "PDF_UNREADABLE"
    NOT_B1 = "NOT_B1"
    NOT_COMPACTION = "NOT_COMPACTION"
    PO_MISMATCH = "PO_MISMATCH"
    READERS_DISAGREE = "READERS_DISAGREE"
    PROJECT_AMBIGUOUS = "PROJECT_AMBIGUOUS"
    NOTE_ALREADY_LINKED = "NOTE_ALREADY_LINKED"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    ADDRESS_UNVERIFIABLE = "ADDRESS_UNVERIFIABLE"
    DUPLICATE_TASK = "DUPLICATE_TASK"
    UNEXPECTED_SCREEN = "UNEXPECTED_SCREEN"  # before any write
    PARTIAL_WRITE = "PARTIAL_WRITE"  # after Submit; not a final skip


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class NoteSnapshot(Frozen):
    """The Note window as read: page text, untrusted, never in run output."""

    note_id: str = Field(min_length=1)
    title: str
    body: str
    attachment_names: tuple[str, ...]
    project_linked: bool  # False only when the window shows Link to Project


class SearchRow(Frozen):
    """One Projects search row, cells as shown."""

    pln: str
    client_ref_no: str
    company: str


class CompactionTask(Frozen):
    """One Compaction Test task on the project, as the task table shows it."""

    task_no: str
    status: str


class MySysLookup(Frozen):
    """The read-only project lookup (steps 8-10), values as MySys shows them.

    The project fields are empty when no single project was opened.
    """

    search_rows: tuple[SearchRow, ...]
    more_pages: bool  # a second results page exists
    project_internal_no: str = ""  # the project's Client Internal No.
    address: str = ""  # the project's one Address string, unparsed
    tasks: tuple[CompactionTask, ...] = ()


class Proceed(Frozen):
    """Step 11: the only input the booker takes. Every value is checked here
    again, so a malformed decision can't reach a write. MySys's own formats
    are checked here; a client's PO and file-name rules in its subclass
    (`b1.models.B1Proceed`), and only a client's decision engine builds one.

    `creator` is the Create New Task form's Creator, set at W1 and read back
    at W1 and W2 (ADR-003 decision 3; a client rule, never a constant in
    `mysys/`)."""

    note_id: str = Field(min_length=1)
    internal_no: str = Field(min_length=1)
    pln: str = Field(pattern=r"^pln_[0-9]+$")
    po_number: str = Field(min_length=1)
    email_body: str = Field(min_length=1, repr=False)  # the Note's body
    pdf_file_name: str = Field(min_length=1)
    pdf_bytes: bytes = Field(min_length=1, repr=False)
    # The project's Compaction Test task numbers at step 10, for W2.
    existing_task_nos: tuple[Annotated[str, Field(pattern=r"^tsk_[0-9]+$")], ...]
    creator: str = Field(min_length=1)


class Skip(Frozen):
    reason: SkipReason

    @property
    def retryable(self) -> bool:
        """Section 3: only PROJECT_NOT_FOUND is retried (final in the MVP)."""
        return self.reason is SkipReason.PROJECT_NOT_FOUND
