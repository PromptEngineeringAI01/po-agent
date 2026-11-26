"""Summit Home as the run loop's client (task 9.4; `core/client.py`; SPEC.md
-> Client 2: Summit Home). Built: its Note Pool filters and list eligibility
(task 9.11, `summit/eligibility.py`); what the peek needs (task 9.12): the PO
a NOTE line shows, the one-iframe body rule, the project rule and the
decision (`summit/decision.py`) on what the peek read, with the Note's
original assignee; where a Note taken and stopped before Submit goes back
(task 9.13: its original assignee). The W2 Documents Type refuses with
ConfigError (ALERT CONFIG, exit 2), as `cli.py` refuses Summit's run, until
task 9.14 fills it. Pure, no browser code, as `b1/`."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn

from po_agent.b1 import readers
from po_agent.core.client import EligibleNote
from po_agent.core.config import ClientProfile, Config
from po_agent.core.errors import ConfigError
from po_agent.core.models import (
    MySysLookup,
    NotePoolFilters,
    NotePoolRow,
    NoteSnapshot,
    OneIframeBody,
    Proceed,
    ProjectRule,
    Skip,
)
from po_agent.summit import decision, eligibility


def _refuse() -> NoReturn:
    raise ConfigError("mode not built for this client yet")


@dataclass(frozen=True)
class SummitClient:
    """Summit's answers to `core.client.Client`, from its client file
    (`profile`) and the site's profile (`config`: the other agent account's
    user name and the time zone). `started`: the run's start, from
    `controls.now`, for the assignee rule."""

    config: Config
    profile: ClientProfile
    started: datetime

    def filters(self) -> NotePoolFilters:
        # Assigned Pool stays at its default: Summit has no pool.
        return NotePoolFilters(
            source=self.profile.source_filter, locked=self.profile.locked_filter
        )

    def eligible(self, rows: Sequence[NotePoolRow]) -> tuple[EligibleNote, ...]:
        first_run = eligibility.first_run(
            self.started, self.profile.any_assignee_before, self.config.run_window.tz
        )
        return eligibility.eligible_notes(
            rows,
            sender=self.profile.sender,
            # Agent 2 (this client's) and Agent 1 (B1's, the site's).
            agents=(self.profile.agent_user_name, self.config.agent_user_name),
            any_assignee=first_run,
        )

    def po_number(self, note: EligibleNote) -> str:
        # The title's full PO; its list eligibility kept only titles with one.
        return eligibility.title_po(note.title) or note.internal_no

    def body_rule(self, file_name: str) -> OneIframeBody:
        # The email iframe, whatever the PDF's name (SPEC: Email body).
        return OneIframeBody()

    def project_rule(self) -> ProjectRule:
        return decision.SummitProjectRule(self.profile.company)

    def decide(
        self,
        snapshot: NoteSnapshot,
        note: EligibleNote,
        pdf: bytes | None,
        lookup: Callable[[], MySysLookup],
    ) -> Skip | Proceed:
        """SPEC's Summit table on the peek's reads: the snapshot holds the
        Note Pool row's title and "Assignee:" as read (the original
        assignee). No PDF downloaded: no text, and the attachment checks
        decide before any reader result is used."""
        texts = (
            readers.read(pdf)
            if pdf is not None
            else readers.PdfTexts(plumber="", pypdf="", data=b"")
        )
        return decision.decide(
            snapshot,
            snapshot.assignee,
            texts,
            lookup,
            companies=self.profile.company,
        )

    def document_type(self) -> str:
        _refuse()

    def return_target(self, original: str) -> str:
        # SPEC: Return to the original assignee, as the peek read it; the
        # driver strips it and finds it in exactly one of the Note window's
        # lists, else the Note stays with Agent 2 (task 9.13).
        return original
