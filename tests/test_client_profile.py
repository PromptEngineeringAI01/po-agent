"""Tests for the client profile config/clients/summit.toml (task 9.3; SPEC.md
-> Client 2: Summit Home, Creator table and The separate run; decisions,
23 Nov 2026, separate run, and 24 Nov 2026, Summit creator table).

B1's values stay in config/<site>.toml; only Summit has a client file. Every
breach of the file's rules is a ConfigError (ALERT CONFIG, exit 2) naming the
field, never echoing the value. Nothing here touches MySys or a secret.
"""

import tomllib
from datetime import time
from pathlib import Path

import pytest

from po_agent.core.config import load_client, parse_client
from po_agent.core.errors import ConfigError

ROOT = Path(__file__).resolve().parent.parent
SUMMIT_TOML = ROOT / "config" / "clients" / "summit.toml"

# SPEC.md -> Creator table, with Joey's corrections of 24, 25 and 26 Nov 2026:
# (name, aliases, creator, creator_rule), in the table's order.
SPEC_CREATOR_TABLE = [
    (
        "Summit Easystart",
        ("New Gen and EasyStart", "New Generation and EasyStart"),
        "NH Sub Floor",
        None,
    ),
    ("Summit Homes Group", (), "Compactions", None),
    ("Summit New Homes", (), "NH Sub Floor", None),
    ("Summit SouthWest", ("Summit South West",), "Compactions", None),
    ("Summit Granny Flats", (), "Alison Wells", None),
    (
        "Summit Projects",
        ("Summit Developments", "Summit Project"),
        None,
        "previous_task",
    ),
    ("Summit Renovations", (), None, "previous_task"),
    ("Summit Homes Display", (), None, "previous_task"),
]


def committed() -> dict:
    return tomllib.loads(SUMMIT_TOML.read_text(encoding="utf-8"))


def with_changes(**changes) -> dict:
    data = committed()
    data.update(changes)
    return data


def with_company(index: int, **changes) -> dict:
    """The committed file with one company row changed; a value of None
    removes that key."""
    data = committed()
    rows = [dict(row) for row in data["company"]]
    for key, value in changes.items():
        if value is None:
            rows[index].pop(key, None)
        else:
            rows[index][key] = value
    data["company"] = rows
    return data


def refused(data: dict) -> ConfigError:
    with pytest.raises(ConfigError) as caught:
        parse_client(data)
    assert caught.value.exit_code == 2
    assert caught.value.alert_kind == "CONFIG"
    return caught.value


# --- the committed file --------------------------------------------------------


def test_the_committed_summit_file_loads_with_specs_values():
    profile = load_client("summit", "live")

    assert profile.client == "summit"
    assert profile.sites == ("live",)
    assert profile.enabled is False  # flipped by its own PR before the spike (S.2)
    assert profile.max_notes_per_run == 1  # the watched runs book one (S.4)
    assert profile.max_peeks_per_run == 10  # SPEC draft value (open question S3)
    assert profile.agent_user_name == "Agent 2 (Summit Homes)"
    assert profile.source_filter == "support@prompteng.com.au"
    assert profile.sender == "noreply@summithomesgroup.com.au"
    assert profile.locked_filter == "Unlocked"
    assert profile.any_assignee_before == time(8, 0)
    assert profile.project_document_type == "Client Documents"


def test_the_committed_creator_table_is_specs():
    profile = load_client("summit", "live")

    rows = [
        (company.name, company.aliases, company.creator, company.creator_rule)
        for company in profile.company
    ]
    assert rows == SPEC_CREATOR_TABLE


def test_the_old_company_name_is_not_in_the_file():
    # Summit Home Improvement is now Summit Renovations (decisions, 24 Nov
    # 2026); the aliases are pinned row by row above.
    text = SUMMIT_TOML.read_text(encoding="utf-8")

    assert "Home Improvement" not in text


def test_the_profile_is_frozen():
    profile = load_client("summit", "live")

    with pytest.raises(Exception):  # noqa: B017 - pydantic's frozen error
        profile.enabled = True


# --- validation: one test per rule ---------------------------------------------


def test_a_company_with_both_creator_and_creator_rule_is_refused():
    error = refused(with_company(0, creator_rule="previous_task"))

    assert "company" in str(error)


def test_a_company_with_neither_creator_nor_creator_rule_is_refused():
    error = refused(with_company(0, creator=None))

    assert "company" in str(error)


def test_a_creator_rule_other_than_previous_task_is_refused():
    error = refused(with_company(5, creator_rule="first_task"))

    assert "company" in str(error)
    assert "first_task" not in str(error)


@pytest.mark.parametrize(
    "index, changes",
    [
        # a second row named like the first, after trim and case-fold
        (1, {"name": "  summit EASYSTART "}),
        # an alias equal to another row's name
        (1, {"aliases": ["SUMMIT PROJECTS"]}),
        # an alias equal to another row's alias
        (1, {"aliases": [" new gen and easystart"]}),
        # an alias equal to its own row's name
        (1, {"aliases": ["summit homes group"]}),
        # the same alias twice in one row
        (1, {"aliases": ["Summit Extra", "summit extra "]}),
    ],
    ids=[
        "name-twice",
        "alias-is-a-name",
        "alias-twice-across-rows",
        "alias-is-own-name",
        "alias-twice-in-a-row",
    ],
)
def test_names_and_aliases_must_be_unique_after_trim_and_case_fold(index, changes):
    error = refused(with_company(index, **changes))

    assert "company" in str(error)


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_name_or_alias_is_refused(value):
    refused(with_company(2, name=value))
    refused(with_company(2, aliases=[value]))


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_creator_is_refused(value):
    # A blank creator would only stop at W1 (CREATOR_UNKNOWN); the file is
    # refused at load instead (9.3 review nit 2).
    error = refused(with_company(2, creator=value))

    assert "company" in str(error)


@pytest.mark.parametrize("sites", [["test"], ["live", "test"], [], ["LIVE"], "live"])
def test_sites_may_only_be_live(sites):
    error = refused(with_changes(sites=sites))

    assert "sites" in str(error)


def test_an_unknown_key_is_refused():
    error = refused(with_changes(surprise=1))

    assert "surprise" in str(error)


def test_an_unknown_key_in_a_company_is_refused():
    error = refused(with_company(0, creater="NH Sub Floor"))

    assert "creater" in str(error)


@pytest.mark.parametrize(
    "changes",
    [
        {"enabled": "false"},
        {"max_notes_per_run": 0},
        {"max_peeks_per_run": 0},
        {"locked_filter": "Locked"},
        {"client": "b1"},
        {"company": []},
    ],
)
def test_bad_values_are_refused(changes):
    refused(with_changes(**changes))


# --- loading -----------------------------------------------------------------


def test_summit_is_refused_on_the_test_site():
    with pytest.raises(ConfigError) as caught:
        load_client("summit", "test")

    assert caught.value.exit_code == 2


@pytest.mark.parametrize("client", ["b1", "acme", "../live", "SUMMIT", ""])
def test_only_summit_has_a_client_file(client, tmp_path):
    # tmp_path holds a valid file under every one of those names' paths: a
    # refused client never reaches it.
    (tmp_path / "clients").mkdir()
    (tmp_path / "clients" / "summit.toml").write_text(
        SUMMIT_TOML.read_text("utf-8"), "utf-8"
    )
    with pytest.raises(ConfigError):
        load_client(client, "live", config_dir=tmp_path)


def test_a_missing_client_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_client("summit", "live", config_dir=tmp_path)


def test_a_client_file_that_is_not_toml_is_a_config_error(tmp_path):
    (tmp_path / "clients").mkdir()
    (tmp_path / "clients" / "summit.toml").write_text("client = \n", "utf-8")

    with pytest.raises(ConfigError):
        load_client("summit", "live", config_dir=tmp_path)
