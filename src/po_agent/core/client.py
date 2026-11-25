"""The client interface (task 9.4; ADR-003 decision 2; SPEC.md -> Client 2:
What is shared with B1, and what is Summit's).

`core/run.py` asks the run's client for every value that differs between
clients and imports no client package: `b1/client.py` implements it for
B1, `summit/client.py` as a stub that refuses until tasks 9.9-9.14 fill it.
The CLI picks the client (`--client`, task 9.3). One member per difference
SPEC lists, nothing for a client not yet known (ADR-003's rule of three):

- the Note Pool filters to set, each read back (`filters`);
- list eligibility on the Note Pool rows (`eligible`; Summit's reads the
  Source cell once the driver reads it, 9.11) and the PO a NOTE line shows
  (`po_number`);
- the body rule (`body_rule`);
- the project rule: `mysys/` reads the Projects search, the project and its
  Tasks, the client judges them (`project_rule`);
- the decision, pure: its `Proceed` carries the Creator and the Documents
  file name (`decide`); the W2 Documents Type (`document_type`);
- where a Note taken and stopped before Submit goes back (`return_target`).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from re import Pattern
from typing import Protocol

from po_agent.core.models import (
    MySysLookup,
    NotePoolFilters,
    NotePoolRow,
    NoteSnapshot,
    Proceed,
    ProjectRule,
    Skip,
)


@dataclass(frozen=True)
class EligibleNote:
    """A Note Pool row the client's list eligibility kept: its Note ID and
    the number its project is searched by."""

    note_id: str
    internal_no: str


class Client(Protocol):
    """What the run loop asks a client (module docstring)."""

    def filters(self) -> NotePoolFilters:
        """The Note Pool filters the run sets and reads back."""
        ...

    def eligible(self, rows: Sequence[NotePoolRow]) -> tuple[EligibleNote, ...]:
        """List eligibility on every row, in list order: no click."""
        ...

    def po_number(self, note: EligibleNote) -> str:
        """The PO a NOTE line shows for this Note."""
        ...

    def body_rule(self, file_name: str) -> Pattern[str]:
        """Which text in the Note window is the email body, given the PDF's
        file name."""
        ...

    def project_rule(self) -> ProjectRule:
        """The match rule for the driver's project reads and W1's reopen."""
        ...

    def decide(
        self,
        snapshot: NoteSnapshot,
        note: EligibleNote,
        pdf: bytes | None,
        lookup: Callable[[], MySysLookup],
    ) -> Skip | Proceed:
        """Every check on what the Note window showed, the PDF's bytes (None
        when none was downloaded) and the project `lookup` (called at most
        once, only when the Note and PDF checks pass). Pure: no browser."""
        ...

    def document_type(self) -> str:
        """W2's read-back: the Type of the new task's Documents row."""
        ...

    def return_target(self) -> str:
        """Where a Note taken and then skipped or stopped before Submit goes
        back: B1's pool. Summit's return to the original assignee comes with
        its take (9.13)."""
        ...
