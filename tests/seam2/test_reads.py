"""Seam 2, the read-only lookups on the MySys test site (task 3.2; marker
testsite).

The download is the same code for every PO, so one Note proves it: the one
eligible 2609034B Note in the Agent Pool is opened (not taken: opening and
downloading change nothing, rows 02, 05), its one "Download document" link
counted and the PDF downloaded into memory, the download folder left empty.
The project reads need no Note: for each trial PO, the Projects search and
the project window read into a MySysLookup, whose match is the trial pln,
whatever its tasks' state (Joey, 2 Nov 2026: no reset for a read-only test).
Only reading actions are done. Assertions use counts, action names and the
trial identifiers only, never an address or page text.

On the laptop (the main checkout's private/fixtures/ found), each trial PO's
lookup is also written to private/fixtures/lookup-<internal no>.json, to copy
into its real-PO case for 2.6's S3 evidence. Never on the Mac Mini, which has
no private/, and never into a committed file.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from po_agent.b1.decision import check_project
from po_agent.core import run
from po_agent.mysys import driver

pytestmark = pytest.mark.testsite

# SPEC.md -> Trial conditions.
TRIAL_PLNS = {"2609017B": "pln_66935", "2609034B": "pln_66938", "2610002B": "pln_66940"}
READING = {
    "login_username",
    "login_password",
    "login_submit",
    "open_project_tab",
    "open_note_pool",
    "open_projects_subtab",
    "move_pointer_off_menu",
    "set_pool_filter",
    "set_locked_filter",
    "open_note",
    "download_attachment",
    "search_project",
    "submit_project_search",
    "open_project",
}
DOWNLOAD_NOTE = "2609034B"  # its Note stays in the Agent Pool (3.1)
RETRIED = {"open_note", "open_project"}  # opening clicks a covered page may fail


def private_fixtures() -> Path | None:
    """The main checkout's private/fixtures/, on the laptop only."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    env = os.environ.get("SEAM1_PRIVATE_DIR")
    folder = Path(env) if env else Path(common).parent / "private"
    path = folder / "fixtures"
    return path if path.is_dir() else None


@pytest.fixture
def login(config, credentials) -> tuple[str, str, str]:
    return (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )


def only_reading(guard) -> bool:
    return {action for action, _ in guard.history} <= READING and all(
        outcome == "done" or (outcome == "failed" and action in RETRIED)
        for action, outcome in guard.history
    )


def test_reads_downloads_the_pdf_of_one_note(config, login, guard, tmp_path):
    downloads = tmp_path / "po-agent-dl-20261102T000000Z-seam"
    downloads.mkdir()

    with driver.open_browser(headed=False, slow_mo=0, downloads=downloads) as page:
        driver.reload_home(guard, page, *login)
        panel = driver.open_note_pool(guard, page)
        driver.leave_menu(guard, page)
        driver.set_note_pool_filters(guard, panel, config.pool_name)
        listing = driver.read_note_pool(guard, panel)
        # Precondition: the one eligible 2609034B Note in the Agent Pool.
        found = [
            note
            for note in run.eligible_notes(
                listing.rows, config.title_rule, config.pool_name
            )
            if note.internal_no == DOWNLOAD_NOTE
        ]
        if listing.pages != 1 or len(found) != 1:
            pytest.fail(
                f"not in the reset state: {DOWNLOAD_NOTE} eligible={len(found)}"
            )

        window = driver.open_note(guard, page, panel, found[0].note_id)
        with driver.note_downloads(page, downloads):
            names = driver.attachment_names(window)
            pdf = driver.download_pdf(guard, page, window)

    assert isinstance(pdf, driver.Pdf)
    assert names == (pdf.file_name,)
    assert pdf.file_name.startswith(f"{DOWNLOAD_NOTE}_048")
    assert pdf.data.startswith(b"%PDF")
    assert not [path for path in downloads.rglob("*") if path.is_file()]
    assert only_reading(guard)


@pytest.mark.parametrize("internal_no", list(TRIAL_PLNS))
def test_reads_each_trial_project(config, login, guard, internal_no):
    with driver.open_browser(headed=False, slow_mo=0) as page:
        lookup = driver.project_lookup(guard, page, *login, internal_no, config.site)

    assert check_project(lookup, internal_no, config.site) == TRIAL_PLNS[internal_no]
    assert lookup.more_pages is False
    assert lookup.address  # read, not compared: never an address in a test
    assert all(task.task_no.startswith("tsk_") for task in lookup.tasks)
    assert only_reading(guard)

    fixtures = private_fixtures()
    if fixtures is not None:
        (fixtures / f"lookup-{internal_no}.json").write_text(
            json.dumps(lookup.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
