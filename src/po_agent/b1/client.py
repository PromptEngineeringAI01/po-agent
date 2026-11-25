"""B1 Homes as the run loop's client (task 9.4; `core/client.py`). Pure, no
browser code: B1's values from its site profile (config/<site>.toml) and its
rules from `b1/decision.py`, `b1/readers.py` and `b1/reader_rules.py`."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from re import Pattern

from po_agent.b1 import decision, readers
from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import TitleRule
from po_agent.core.client import EligibleNote
from po_agent.core.config import Config
from po_agent.core.models import (
    MySysLookup,
    NotePoolFilters,
    NotePoolRow,
    NoteSnapshot,
    Proceed,
    ProjectRule,
    Skip,
)


def eligible_notes(
    rows: Sequence[NotePoolRow], rule: TitleRule, pool_name: str
) -> tuple[EligibleNote, ...]:
    """Step 0 on every row, in list order (newest first)."""
    found = []
    for row in rows:
        internal_no = decision.eligible_internal_no(row, rule, pool_name)
        if internal_no is not None:
            found.append(EligibleNote(note_id=row.note_id, internal_no=internal_no))
    return tuple(found)


@dataclass(frozen=True)
class B1Client:
    """B1's answers to `core.client.Client`, from the site's profile."""

    config: Config

    def filters(self) -> NotePoolFilters:
        return decision.note_pool_filters(self.config.pool_name)

    def eligible(self, rows: Sequence[NotePoolRow]) -> tuple[EligibleNote, ...]:
        return eligible_notes(rows, self.config.title_rule, self.config.pool_name)

    def po_number(self, note: EligibleNote) -> str:
        return f"{note.internal_no}/{rules.PO_SUFFIX}"

    def body_rule(self, file_name: str) -> Pattern[str]:
        return decision.body_rule(file_name)

    def project_rule(self) -> ProjectRule:
        return decision.B1ProjectRule(self.config.site)

    def decide(
        self,
        snapshot: NoteSnapshot,
        note: EligibleNote,
        pdf: bytes | None,
        lookup: Callable[[], MySysLookup],
    ) -> Skip | Proceed:
        texts = (
            readers.read(pdf)
            if pdf is not None
            else readers.PdfTexts(plumber="", pypdf="", data=b"")
        )
        return decision.decide(
            snapshot,
            note.internal_no,
            texts,
            lookup,
            site=self.config.site,
            duplicate_ignores_cancelled=self.config.duplicate_ignores_cancelled,
        )

    def document_type(self) -> str:
        return self.config.project_document_type

    def return_target(self) -> str:
        return self.config.pool_name
