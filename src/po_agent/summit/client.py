"""Summit Home as the run loop's client (task 9.4; `core/client.py`; SPEC.md
-> Client 2: Summit Home). A stub: every member refuses with ConfigError
(ALERT CONFIG, exit 2), as `cli.py` refuses Summit's modes, until tasks
9.9-9.14 fill it. Pure, no browser code, as `b1/`."""

from collections.abc import Callable, Sequence
from re import Pattern
from typing import NoReturn

from po_agent.core.client import EligibleNote
from po_agent.core.errors import ConfigError
from po_agent.core.models import (
    MySysLookup,
    NotePoolFilters,
    NotePoolRow,
    NoteSnapshot,
    Proceed,
    ProjectRule,
    Skip,
)


def _refuse() -> NoReturn:
    raise ConfigError("mode not built for this client yet")


class SummitClient:
    """Summit's answers to `core.client.Client`: none yet."""

    def filters(self) -> NotePoolFilters:
        _refuse()

    def eligible(self, rows: Sequence[NotePoolRow]) -> tuple[EligibleNote, ...]:
        _refuse()

    def po_number(self, note: EligibleNote) -> str:
        _refuse()

    def body_rule(self, file_name: str) -> Pattern[str]:
        _refuse()

    def project_rule(self) -> ProjectRule:
        _refuse()

    def decide(
        self,
        snapshot: NoteSnapshot,
        note: EligibleNote,
        pdf: bytes | None,
        lookup: Callable[[], MySysLookup],
    ) -> Skip | Proceed:
        _refuse()

    def document_type(self) -> str:
        _refuse()

    def return_target(self) -> str:
        _refuse()
