"""Shared models: what MySys shows and what the booker takes, for every
client (ADR-003 decisions 2-3; SPEC.md -> Code style: pydantic at every
boundary). A client's own rules (B1's /048 PO, its readings) stay in its
package (`b1/models.py`)."""

from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol, Self

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
    # The Source cell, the sender's bare address (row 01); None when the
    # read didn't ask for it (B1's reads; Summit's eligible read does, 9.11).
    source: StrictStr | None = None


class SkipReason(StrEnum):
    """Skip reasons: docs/specs/spec.md section 3 (no Claude reasons since
    decisions, 2 Nov 2026), and Summit's three (SPEC.md -> Client 2,
    Decision checks; task 9.9). The trace's closed outcome set follows."""

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
    COMPANY_UNKNOWN = "COMPANY_UNKNOWN"  # Summit: a name not in the table
    COMPANY_MISMATCH = "COMPANY_MISMATCH"  # Summit: names on different rows
    CREATOR_UNKNOWN = "CREATOR_UNKNOWN"  # Summit: no creator to write


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


COMPACTION_TEST = "Compaction Test"  # MySys's task name (row 07)


class CompactionTask(Frozen):
    """One Compaction Test task on the project, as the task table shows it."""

    task_no: str
    status: str


class ProjectTask(Frozen):
    """One task of any name on the project, as the Tasks table shows it:
    its header row "(tsk_<n>) | <name>" and its details row's Task Creator
    and Status cells (row 07; task 9.8). Cells as shown ("---" or empty
    too): a client judges them."""

    task_no: str = Field(pattern=r"^tsk_[0-9]+$")
    name: str
    status: str
    task_creator: str


class MySysLookup(Frozen):
    """The read-only project lookup (steps 8-10), values as MySys shows them.

    The project fields are empty when no single project was opened.
    """

    search_rows: tuple[SearchRow, ...]
    more_pages: bool  # a second results page exists
    project_internal_no: str = ""  # the project's Client Internal No.
    address: str = ""  # the project's one Address string, unparsed
    # Every task in table order (task 9.8); `tasks` are its Compaction Test
    # ones (B1's duplicate check), derived when left out.
    project_tasks: tuple[ProjectTask, ...] = ()
    tasks: tuple[CompactionTask, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _compaction_from_every_task(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("project_tasks") and "tasks" not in data:
            every = [ProjectTask.model_validate(t) for t in data["project_tasks"]]
            return {**data, "tasks": _compaction(every)}
        return data

    @model_validator(mode="after")
    def _same_rows(self) -> Self:
        if self.project_tasks and self.tasks != _compaction(self.project_tasks):
            raise ValueError("tasks are not the Compaction Test project_tasks")
        return self


def _compaction(project_tasks: Sequence[ProjectTask]) -> tuple[CompactionTask, ...]:
    """The Compaction Test tasks, one per number (the last row's status), as
    the task number -> status read before 9.8."""
    statuses = {t.task_no: t.status for t in project_tasks if t.name == COMPACTION_TEST}
    return tuple(CompactionTask(task_no=n, status=s) for n, s in statuses.items())


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


class NotePoolFilters(Frozen):
    """The Note Pool filters a client's run sets, each read back; every
    other filter stays at its default (screen-map rows 01, 27). A client
    value (ADR-003 decision 3): `mysys/` holds none. B1 sets its pool;
    Summit sets Source and leaves Assigned Pool at its default (task 9.11).
    With `source` set, the run's read takes the Source column too."""

    pool: str | None = Field(None, min_length=1)  # Assigned Pool; None: default
    source: str | None = Field(None, min_length=1)  # Source; None: default
    locked: Literal["Locked", "Unlocked"]  # Locked/Unlocked


class Skip(Frozen):
    reason: SkipReason

    @property
    def retryable(self) -> bool:
        """Section 3: only PROJECT_NOT_FOUND is retried (final in the MVP)."""
        return self.reason is SkipReason.PROJECT_NOT_FOUND


class ProjectRule(Protocol):
    """A client's project match rule (ADR-003 decision 3): `mysys/` reads
    the Projects search and the project, the client judges them."""

    def match(
        self, rows: Sequence[SearchRow], more_pages: bool, internal_no: str
    ) -> Skip | str:
        """Step 8: the pln to open from page 1's search rows, else a Skip
        (nothing is opened)."""
        ...

    def judge(self, lookup: MySysLookup, internal_no: str) -> Skip | str:
        """The opened project still passes: its pln, else a Skip."""
        ...
