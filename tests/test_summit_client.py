"""Summit's client members the peek uses (task 9.12; core/client.py; SPEC.md
-> Client 2: Summit Home, The peek, Decision checks).

Pure, no browser: the PO a NOTE line shows (the title's full PO), the
project rule the driver's reads use (one row whose Client Ref No. is the PO
before its first "/" under a table company; the opened project's Client
Internal No. equal again), and the decision on what the peek read, with
the Note's original assignee recorded as read: a staff user, a pool or
`---` (9.13 returns a taken Note to it). The body rule is pinned on a page
in tests/test_summit_note_window.py. Values are fake; company names and
creators are the committed client file's.
"""

from datetime import UTC, datetime

import pytest
from fakes.mysys import (
    SUMMIT_BODY,
    SUMMIT_SENDER,
    summit_file,
    summit_lookup,
    summit_pdf,
    summit_row,
    summit_titled,
)

from po_agent.core.client import EligibleNote
from po_agent.core.config import CONFIG_DIR, load_client, load_config
from po_agent.core.models import (
    MySysLookup,
    NoteSnapshot,
    SearchRow,
    Skip,
    SkipReason,
)
from po_agent.summit.client import SummitClient
from po_agent.summit.models import SummitProceed

AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, tzinfo=UTC)  # the first run


def summit() -> SummitClient:
    profile = load_client("summit", "live", CONFIG_DIR).model_copy(
        update={"sender": SUMMIT_SENDER}
    )
    return SummitClient(load_config("live", CONFIG_DIR), profile, AT_0759_PERTH)


def listed(assignee: str = "---") -> EligibleNote:
    """The Note as list eligibility keeps it from its Note Pool row."""
    (note,) = summit().eligible(
        [summit_row("462001", title=summit_titled(), assignee=assignee)]
    )
    return note


def snapshot(assignee: str, names: tuple[str, ...] = (summit_file(),)) -> NoteSnapshot:
    return NoteSnapshot(
        note_id="462001",
        title=summit_titled(),
        body=SUMMIT_BODY,
        attachment_names=names,
        project_linked=False,
        assignee=assignee,
    )


def test_a_note_line_shows_the_title_s_full_po():
    assert summit().po_number(listed()) == "123456/020/01"


@pytest.mark.parametrize("original", ["---", "PO Allocation Pool", "Fake Admin"])
def test_the_decision_keeps_the_original_assignee_as_read(original):
    decision = summit().decide(
        snapshot(original), listed(original), summit_pdf(), summit_lookup
    )

    assert isinstance(decision, SummitProceed)
    assert decision.original_assignee == original
    assert (decision.po_number, decision.pln, decision.creator) == (
        "123456/020/01",
        "pln_20001",
        "Compactions",
    )
    assert decision.email_body == SUMMIT_BODY


def test_no_pdf_downloaded_decides_without_a_project_lookup():
    def lookup() -> MySysLookup:
        raise AssertionError("no project lookup for a Note without its PDF")

    decision = summit().decide(snapshot("---", names=()), listed(), None, lookup)

    assert decision == Skip(reason=SkipReason.NO_PDF)


def test_the_project_rule_matches_the_client_ref_under_a_table_company():
    rows = (
        SearchRow(
            pln="pln_20009", client_ref_no="123456", company="Fake Other Builder"
        ),
        SearchRow(
            pln="pln_20001", client_ref_no=" 123456 ", company="Summit Homes Group"
        ),
    )

    assert summit().project_rule().match(rows, False, "123456") == "pln_20001"


def test_the_project_rule_finds_none_without_a_table_company():
    rows = (
        SearchRow(
            pln="pln_20009", client_ref_no="123456", company="Fake Other Builder"
        ),
    )

    assert summit().project_rule().match(rows, False, "123456") == Skip(
        reason=SkipReason.PROJECT_NOT_FOUND
    )


def test_the_project_rule_s_judge_needs_the_client_internal_no_again():
    rule = summit().project_rule()

    assert rule.judge(summit_lookup("123456"), "123456") == "pln_20001"
    assert rule.judge(summit_lookup("123456", internal_no="123457"), "123456") == (
        Skip(reason=SkipReason.UNEXPECTED_SCREEN)
    )
