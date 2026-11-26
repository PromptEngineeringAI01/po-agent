"""The client interface (task 9.4; ADR-003 decision 2; SPEC.md -> Client 2:
What is shared with B1, and what is Summit's).

`core/run.py` asks a client for what differs between B1 and Summit and
imports neither package (tests/test_mysys_client_free.py). B1's answers are
pinned through the run loop's offline tests (tests/seam2/
test_run_loop_offline.py, tests/test_run_spike.py, tests/test_exit_codes.py,
tests/test_hold_recheck.py), which pass unchanged; here: the interface holds
SPEC's differences and nothing more (ADR-003's rule of three), and Summit's
implementation was filled task by task: 9.11 filled `filters` and
`eligible` (tests/test_summit_eligibility.py), 9.12 `po_number`,
`body_rule`, `project_rule` and `decide` (tests/test_summit_client.py,
tests/test_summit_decide_only.py), 9.13 `return_target`
(tests/test_summit_take_return.py), 9.14 `document_type`
(tests/test_summit_booking.py): no member refuses any more.
"""

import tomllib
from datetime import UTC, datetime

import pytest

from po_agent.b1.client import B1Client
from po_agent.core.client import Client, EligibleNote
from po_agent.core.config import CONFIG_DIR, load_config, parse_client
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


def members(cls: type) -> set[str]:
    return {name for name in vars(cls) if not name.startswith("_")}


def test_the_interface_holds_spec_s_differences_and_nothing_more() -> None:
    assert members(Client) == MEMBERS


@pytest.mark.parametrize("implementation", [B1Client, SummitClient])
def test_each_client_implements_every_member(implementation: type) -> None:
    assert MEMBERS <= members(implementation)


def summit_profile():
    with open(CONFIG_DIR / "clients" / "summit.toml", "rb") as file:
        return parse_client(tomllib.load(file))


def summit() -> SummitClient:
    started = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)
    return SummitClient(load_config("live", CONFIG_DIR), summit_profile(), started)


def test_summit_s_w2_documents_type_is_its_client_file_s() -> None:
    # SPEC.md -> config shape: project_document_type = "Client Documents"
    # (S4, confirmed in S.0; task 9.14).
    assert summit().document_type() == "Client Documents"


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
