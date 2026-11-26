"""The client interface (task 9.4; ADR-003 decision 2; SPEC.md -> Client 2:
What is shared with B1, and what is Summit's).

`core/run.py` asks a client for what differs between B1 and Summit and
imports neither package (tests/test_mysys_client_free.py). B1's answers are
pinned through the run loop's offline tests (tests/seam2/
test_run_loop_offline.py, tests/test_run_spike.py, tests/test_exit_codes.py,
tests/test_hold_recheck.py), which pass unchanged; here: the interface holds
SPEC's differences and nothing more (ADR-003's rule of three), and Summit's
implementation refuses every one not built yet: 9.11 filled `filters` and
`eligible` (tests/test_summit_eligibility.py), 9.12 `po_number`,
`body_rule`, `project_rule` and `decide` (tests/test_summit_client.py,
tests/test_summit_decide_only.py), 9.13 `return_target`
(tests/test_summit_take_return.py), 9.14 the rest.
"""

import tomllib
from datetime import UTC, datetime

import pytest

from po_agent.b1.client import B1Client
from po_agent.core.client import Client, EligibleNote
from po_agent.core.config import CONFIG_DIR, load_config, parse_client
from po_agent.core.errors import ConfigError
from po_agent.core.models import MySysLookup, NoteSnapshot
from po_agent.summit.client import SummitClient

# The plan's list (9.4) of what the run loop asks a client, one member per
# SPEC difference: the Note Pool filters; list eligibility (it reads the
# Source cell once 9.11 reads it); the PO a NOTE line shows; the body rule;
# the project rule (the client judges what the driver reads); the decision,
# whose Proceed carries the Creator and the Documents file name; the W2
# Documents Type; and the return target.
MEMBERS = {
    "filters",
    "eligible",
    "po_number",
    "body_rule",
    "project_rule",
    "decide",
    "document_type",
    "return_target",
}

NOTE = EligibleNote(note_id="300001", internal_no="123456")
SNAPSHOT = NoteSnapshot(
    note_id="300001",
    title="",
    body="fake body",
    attachment_names=("123456_020_01.pdf",),
    project_linked=False,
)


def lookup() -> MySysLookup:
    raise AssertionError("no MySys read for a client that refuses")


# One refusal per member: the call the run loop makes.
SUMMIT_CALLS = {
    "document_type": (),
}


def members(cls: type) -> set[str]:
    return {name for name in vars(cls) if not name.startswith("_")}


def test_the_interface_holds_spec_s_differences_and_nothing_more() -> None:
    assert members(Client) == MEMBERS


@pytest.mark.parametrize("implementation", [B1Client, SummitClient])
def test_each_client_implements_every_member(implementation: type) -> None:
    assert MEMBERS <= members(implementation)


# Built in 9.11 (tests/test_summit_eligibility.py), 9.12, the peek
# (tests/test_summit_client.py), and 9.13, the return
# (tests/test_summit_take_return.py).
SUMMIT_BUILT = {
    "filters",
    "eligible",
    "po_number",
    "body_rule",
    "project_rule",
    "decide",
    "return_target",
}


def summit_profile():
    with open(CONFIG_DIR / "clients" / "summit.toml", "rb") as file:
        return parse_client(tomllib.load(file))


def summit() -> SummitClient:
    started = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)
    return SummitClient(load_config("live", CONFIG_DIR), summit_profile(), started)


def test_every_member_not_built_has_a_summit_refusal_row() -> None:
    assert set(SUMMIT_CALLS) == MEMBERS - SUMMIT_BUILT


@pytest.mark.parametrize(("member", "args"), sorted(SUMMIT_CALLS.items()))
def test_summit_s_stub_refuses_every_member(member: str, args: tuple) -> None:
    # As 9.3's refusal of Summit's modes: ALERT CONFIG, exit 2, before any
    # MySys read (the lookup is never called).
    with pytest.raises(ConfigError) as refused:
        getattr(summit(), member)(*args)

    assert refused.value.exit_code == 2
    assert str(refused.value) == "mode not built for this client yet"


def test_b1_s_values_come_from_its_site_profile() -> None:
    # B1's values stay in config/<site>.toml (SPEC.md -> The separate run).
    config = load_config("test", CONFIG_DIR)
    client = B1Client(config)

    # B1's return goes to its pool whoever had the Note before the take.
    assert client.return_target("Fake Person") == "Agent Pool"
    assert client.document_type() == "Client Documents"
    assert client.po_number(EligibleNote(note_id="300001", internal_no="2600001B")) == (
        "2600001B/048"
    )
