"""The supervised demo's read-only steps, offline (task 9.2): the values the
demo hands the shared driver are B1's, the profile's pool with Locked and
the "ends with the file name" body rule. MySys is faked at the driver's
and booking's steps (as tests/fakes/mysys.py does for the run); the trial
PO's internal number is the demo's own (Must never #6 allows it).
"""

import argparse

import pytest

from po_agent.core import demo, output
from po_agent.core.config import load_config
from po_agent.core.models import NotePoolFilters, NotePoolRow
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

FILE = f"{demo.INTERNAL_NO}_048_1.pdf"
HREF = f"https://example.invalid/download?file_name={FILE}"


class Stop(Exception):
    """Ends the demo once the body has been asked for."""


@pytest.fixture
def seen(monkeypatch) -> dict:
    """The demo's MySys steps up to the body read, each faked; what the
    demo passes is recorded."""
    seen: dict = {}
    config = load_config("test")
    row = NotePoolRow(
        note_id="300001",
        subject_note=f"Please find attached file {FILE}",
        project="---",
        assignee=config.pool_name,
    )

    def filters(guard, panel, value):
        seen["filters"] = value

    def body(window, rule):
        seen["body_rule"] = rule
        raise Stop

    fakes = {
        (driver, "go_home"): lambda page, url: None,
        (driver, "login"): lambda guard, page, user, password: None,
        (driver, "open_note_pool"): lambda guard, page: "panel",
        (booking, "leave_menu"): lambda guard, page: None,
        (driver, "set_note_pool_filters"): filters,
        (driver, "read_note_pool"): lambda guard, panel: driver.NotePoolList(
            rows=(row,), total=1, pages=1
        ),
        (booking, "open_note"): lambda guard, page, panel, note_id: "window",
        (booking, "has_link_to_project"): lambda window: True,
        (booking, "download_hrefs"): lambda window: [HREF],
        (booking, "note_body"): body,
    }
    for (module, name), fake in fakes.items():
        monkeypatch.setattr(module, name, fake)
    with pytest.raises(Stop):
        demo._steps(
            ActionGuard(),
            None,  # type: ignore[arg-type]
            config,
            {"mysys_test_username": "fake-user", "mysys_test_password": "fake-pw"},
            argparse.Namespace(probe_link=False, until_check=True),
            output.RunSummary(run_id="20261124T000000Z-abcd"),
            demo._Progress(),
        )
    seen["pool"] = config.pool_name
    return seen


def test_the_demo_filters_the_profile_s_pool_locked(seen, capsys):
    assert seen["filters"] == NotePoolFilters(pool=seen["pool"], locked="Locked")


def test_the_demo_s_body_is_the_one_ending_with_the_pdf_s_file_name(seen, capsys):
    rule = seen["body_rule"]
    assert rule.search(f"Please find attached file {FILE} \n")
    assert not rule.search(f"Please find attached file {demo.INTERNAL_NO}_048_2.pdf")
    assert not rule.search(f"{FILE} is attached")
