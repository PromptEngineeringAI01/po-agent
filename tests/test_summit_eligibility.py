"""Summit's Note Pool filters and list eligibility (task 9.11; SPEC.md ->
Client 2: Summit Home, Which Notes; docs/decisions.md, 24 Nov 2026, Summit
assignee rule).

A row is eligible only when all four hold: Source equals the client's
`sender` exactly; Project reads `---`; the assignee rule (a run starting
before `any_assignee_before`, 08:00 Perth, takes any assignee but an agent
account; later runs only `---`); the title shape `<company> - <any text> -
PO: <d>/<d>/<d> - <any word>` with the PO exactly once. READY or ISSUED
doesn't matter. Pure: no click, no MySys. The run's start time is the
client's, from the injectable clock. Values are fake (fake mailbox, sender
domain and companies); expected values are written out from SPEC.md.
"""

import tomllib
from datetime import UTC, datetime

import pytest
from fakes.mysys import (
    SUMMIT_AGENT,
    SUMMIT_MAILBOX,
    SUMMIT_SENDER,
    UNASSIGNED,
    summit_row,
    summit_title,
)

from po_agent.core.client import EligibleNote
from po_agent.core.config import CONFIG_DIR, load_config, parse_client
from po_agent.core.models import NotePoolFilters
from po_agent.summit.client import SummitClient

# Perth is UTC+8 all year. Wednesday 25 Nov 2026.
AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, 59, tzinfo=UTC)
AT_0800_PERTH = datetime(2026, 11, 25, 0, 0, 0, tzinfo=UTC)
AT_1000_PERTH = datetime(2026, 11, 25, 2, 0, 0, tzinfo=UTC)
AGENT_1 = "Agent 1 (MySys Only)"  # config/live.toml's agent
PERSON = "Fake Admin"


def profile():
    with open(CONFIG_DIR / "clients" / "summit.toml", "rb") as file:
        data = tomllib.load(file)
    data.update(source_filter=SUMMIT_MAILBOX, sender=SUMMIT_SENDER)
    return parse_client(data)


def summit(started: datetime = AT_1000_PERTH) -> SummitClient:
    return SummitClient(load_config("live", CONFIG_DIR), profile(), started)


def eligible_ids(rows, started: datetime = AT_1000_PERTH) -> list[str]:
    return [note.note_id for note in summit(started).eligible(rows)]


# --- the filters ------------------------------------------------------------------


def test_summit_sets_source_and_unlocked_and_leaves_the_pool_at_its_default():
    assert summit().filters() == NotePoolFilters(
        pool=None, source=SUMMIT_MAILBOX, locked="Unlocked"
    )


# --- all four hold ----------------------------------------------------------------


def test_a_row_where_all_four_hold_is_eligible_by_the_po_s_first_group():
    # The project is searched by the PO before its first "/" (SPEC.md ->
    # Client 2, Decision checks: Client Ref No.).
    found = summit().eligible([summit_row("462001")])

    assert found == (EligibleNote(note_id="462001", internal_no="123456"),)


@pytest.mark.parametrize("word", ["READY", "ISSUED"])
def test_ready_and_issued_are_both_eligible(word):
    assert eligible_ids([summit_row("462001", title=summit_title(word=word))]) == [
        "462001"
    ]


def test_eligible_rows_keep_the_list_order():
    rows = [summit_row("462003"), summit_row("462001"), summit_row("462002")]

    assert eligible_ids(rows) == ["462003", "462001", "462002"]


# --- Source equals the sender exactly ----------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        f"Fake Builder <{SUMMIT_SENDER}>",  # a display name: not the bare address
        "NoReply@Fake-Builder.test",  # another case
        "noreply@other-builder.test",  # another sender
        SUMMIT_MAILBOX,  # the receiving mailbox, not the sender
        "",
    ],
)
def test_a_source_other_than_the_sender_exactly_is_untouched(source):
    assert eligible_ids([summit_row("462001", source=source)]) == []


def test_a_row_whose_source_was_not_read_is_untouched():
    row = summit_row("462001").model_copy(update={"source": None})

    assert eligible_ids([row]) == []


# --- Project reads --- -------------------------------------------------------------


@pytest.mark.parametrize("project", ["pln_10001", ""])
def test_a_linked_row_is_untouched(project):
    assert eligible_ids([summit_row("462001", project=project)]) == []


# --- the assignee rule -------------------------------------------------------------


@pytest.mark.parametrize("started", [AT_0759_PERTH, AT_0800_PERTH, AT_1000_PERTH])
def test_an_unassigned_row_is_eligible_in_every_run(started):
    assert eligible_ids([summit_row("462001", assignee=UNASSIGNED)], started) == [
        "462001"
    ]


@pytest.mark.parametrize(
    ("started", "eligible"),
    [(AT_0759_PERTH, ["462001"]), (AT_0800_PERTH, []), (AT_1000_PERTH, [])],
)
def test_a_person_s_row_is_eligible_only_before_08_00_perth(started, eligible):
    assert eligible_ids([summit_row("462001", assignee=PERSON)], started) == eligible


def test_a_pool_s_row_is_eligible_only_before_08_00_perth():
    rows = [summit_row("462001", assignee="Fake Allocation Pool")]

    assert eligible_ids(rows, AT_0759_PERTH) == ["462001"]
    assert eligible_ids(rows, AT_0800_PERTH) == []


@pytest.mark.parametrize("agent", [AGENT_1, SUMMIT_AGENT])
@pytest.mark.parametrize("started", [AT_0759_PERTH, AT_1000_PERTH])
def test_an_agent_held_row_is_never_eligible(agent, started):
    assert eligible_ids([summit_row("462001", assignee=agent)], started) == []


# --- the title shape ---------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        # the PO twice
        "Fake Builder Homes - Lot 1 PO: 123456/020/01 - PO: 123456/020/01 - READY",
        "Fake Builder Homes - Lot 1 123456/020/01 - PO: 123456/020/01 - READY",
        # malformed PO
        "Fake Builder Homes - Lot 1 - PO: 123456/020 - READY",
        "Fake Builder Homes - Lot 1 - PO: 123456/020/01A - READY",
        "Fake Builder Homes - Lot 1 - PO: ABC/020/01 - READY",
        "Fake Builder Homes - Lot 1 - PO 123456/020/01 - READY",
        # no PO
        "Fake Builder Homes - Lot 1 - READY",
        # no word after the PO
        "Fake Builder Homes - Lot 1 - PO: 123456/020/01",
        "Fake Builder Homes - Lot 1 - PO: 123456/020/01 - ",
        # no company, or no text between the company and the PO
        " - Lot 1 - PO: 123456/020/01 - READY",
        "Fake Builder Homes - PO: 123456/020/01 - READY",
        # more after the word (a body joined to the title)
        "Fake Builder Homes - Lot 1 - PO: 123456/020/01 - READY Please find attached",
        "",
    ],
)
def test_a_title_off_the_shape_is_untouched(title):
    assert eligible_ids([summit_row("462001", title=title)]) == []
