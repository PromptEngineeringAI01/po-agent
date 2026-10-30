"""Decision-engine models (SPEC.md -> Code style: pydantic at every boundary)."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator


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
    """Skip reasons, exactly docs/specs/spec.md section 3."""

    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    NO_PDF = "NO_PDF"
    MULTIPLE_PDFS = "MULTIPLE_PDFS"
    PDF_UNREADABLE = "PDF_UNREADABLE"
    NOT_B1 = "NOT_B1"
    NOT_COMPACTION = "NOT_COMPACTION"
    PO_MISMATCH = "PO_MISMATCH"
    CLAUDE_UNAVAILABLE = "CLAUDE_UNAVAILABLE"
    CLAUDE_INVALID_OUTPUT = "CLAUDE_INVALID_OUTPUT"
    READERS_DISAGREE = "READERS_DISAGREE"
    PROJECT_AMBIGUOUS = "PROJECT_AMBIGUOUS"
    NOTE_ALREADY_LINKED = "NOTE_ALREADY_LINKED"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    ADDRESS_UNVERIFIABLE = "ADDRESS_UNVERIFIABLE"
    DUPLICATE_TASK = "DUPLICATE_TASK"
    UNEXPECTED_SCREEN = "UNEXPECTED_SCREEN"  # before any write
    PARTIAL_WRITE = "PARTIAL_WRITE"  # after Submit; not a final skip


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Reading(_Frozen):
    """What a reader found in the PDF (section 3); both readers fill it.

    Empty means not found. The deterministic reader leaves the address empty
    in hybrid mode.
    """

    issuer: str = ""
    contains_compaction: bool
    po_number: str = ""
    client_internal_no: str = ""
    site_lot: str = ""
    site_street: str = ""
    site_suburb: str = ""


class ClaudeReading(Reading):
    """Claude's reading as its JSON must give it: every field required, so a
    missing one is invalid output (CLAUDE_INVALID_OUTPUT), never a default.
    Also the structured-output schema sent to Claude (b1/reader_claude.py)."""

    issuer: str
    contains_compaction: bool
    po_number: str
    client_internal_no: str
    site_lot: str
    site_street: str
    site_suburb: str


class DeterministicReading(Reading):
    """The deterministic reading also carries the file name's and, on live,
    the title's PO number (section 3)."""

    po_from_filename: str = ""
    po_from_title: str | None = None  # live title rule only


class NoteSnapshot(_Frozen):
    """The Note window as read: page text, untrusted, never in run output."""

    note_id: str = Field(min_length=1)
    title: str
    body: str
    attachment_names: tuple[str, ...]
    project_linked: bool  # False only when the window shows Link to Project


class SearchRow(_Frozen):
    """One Projects search row, cells as shown."""

    pln: str
    client_ref_no: str
    company: str


class CompactionTask(_Frozen):
    """One Compaction Test task on the project, as the task table shows it."""

    task_no: str
    status: str


class MySysLookup(_Frozen):
    """The read-only project lookup (steps 8-10), values as MySys shows them.

    The project fields are empty when no single project was opened.
    """

    search_rows: tuple[SearchRow, ...]
    more_pages: bool  # a second results page exists
    project_internal_no: str = ""  # the project's Client Internal No.
    address: str = ""  # the project's one Address string, unparsed
    tasks: tuple[CompactionTask, ...] = ()


class Proceed(_Frozen):
    """Step 11: the only input the booker takes. Every value is checked here
    again, so a malformed decision can't reach a write."""

    note_id: str = Field(min_length=1)
    internal_no: str = Field(pattern=r"^[0-9A-Z]+$")
    pln: str = Field(pattern=r"^pln_[0-9]+$")
    po_number: str = Field(pattern=r"^[0-9A-Z]+/048$")
    email_body: str = Field(min_length=1, repr=False)  # the Note's body
    pdf_file_name: str = Field(pattern=r"^[0-9A-Z]+_048(_[0-9]+)?\.(?i:pdf)$")
    pdf_bytes: bytes = Field(min_length=1, repr=False)
    # The project's Compaction Test task numbers at step 10, for W2.
    existing_task_nos: tuple[Annotated[str, Field(pattern=r"^tsk_[0-9]+$")], ...]

    @model_validator(mode="after")
    def _po_is_this_internal_numbers(self) -> Self:
        if self.po_number != f"{self.internal_no}/048":
            raise ValueError("po_number is not this internal number's /048 PO")
        return self


class Skip(_Frozen):
    reason: SkipReason

    @property
    def retryable(self) -> bool:
        """Section 3: only PROJECT_NOT_FOUND is retried (final in the MVP)."""
        return self.reason is SkipReason.PROJECT_NOT_FOUND
