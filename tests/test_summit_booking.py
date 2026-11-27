# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Summit's booking, W1-W5 (task 9.14; SPEC.md -> Client 2: The take and
the booking; tasks/plan.md 9.14; decisions, 26 Nov 2026, Summit booking).

Two layers, values fake, expected values written out from SPEC.md, the plan
and the advisor's 26 Nov 2026 decisions:

- The shared booker on a fake MySys page (headless Chromium, offline, a
  local HTML file that is base_url, as tests/test_booker_offline.py): W1's
  reopen and Create New Task, W2's Submit and read-backs, with a Summit
  Proceed from Summit's own decision engine (never built by hand). The
  decided creator, from the table or from the previous task, reaches the
  form and every read-back; the Creator options are read before anything
  is selected and the creator must be exactly one of them, surrounding
  whitespace stripped, case-sensitive, else WRITE_NOT_STARTED /
  CREATOR_UNKNOWN with nothing selected; W1's reopen re-applies the
  previous-task rule and needs the same task and Task Creator; the
  Documents name is the PDF's or that name with every "-" filed as "_",
  nothing else; the long body is read back whitespace-collapsed on the task
  detail. Only `driver.search_note` (W1's assignee check) is faked.
- The command on the offline fake MySys (tests/fakes/mysys.py):
  `run --client summit` books up to the client file's `max_notes_per_run`
  (bookings; each test sets its own cap), and a creator not in the select stops before Submit with the Note
  returned under 9.13's rules (`---` stays with Agent 2 with the ALERT).

B1's booking stays pinned by tests/test_booker_offline.py and B1's seam 2
booking cases.
"""

import json
import re
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import keyring
import pytest
from fakes.config import switched
from fakes.mysys import (
    SUMMIT_AGENT,
    SUMMIT_MAILBOX,
    SUMMIT_SENDER,
    FakeMySys,
    install,
    summit_lookup,
    summit_note,
    summit_pdf,
    summit_row,
    summit_titled,
)
from keyring.backends.null import Keyring as NullKeyring
from playwright.sync_api import Browser, Page

from po_agent import cli
from po_agent.b1 import readers
from po_agent.core import controls, secrets
from po_agent.core.config import CONFIG_DIR, load_client
from po_agent.core.errors import AccuracyBreach, WriteNotStarted
from po_agent.core.models import MySysLookup, NoteSnapshot, ProjectTask, SearchRow
from po_agent.mysys import booker, driver
from po_agent.mysys.guard import ActionGuard
from po_agent.summit.decision import SummitProjectRule, decide
from po_agent.summit.models import SummitProceed

# Local fakes: every MySys wait short (tests/fakes/browser.py).
pytestmark = pytest.mark.usefixtures("short_waits")

AGENT = SUMMIT_AGENT  # Agent 2 (Summit Homes), config/clients/summit.toml
NOTE_ID = "462001"
PO = "123456/020/01"  # a fake Summit PO (SPEC: three digit groups)
CLIENT_REF = "123456"  # the PO before its first "/"
PLN = "pln_20001"
NEW_TASK = "tsk_200002"
# A fake PDF name holding "-": S.0 saw MySys file a staff upload's "-" as "_".
FILE = "PO-123456-020-01-READY.pdf"
FILED = "PO_123456_020_01_READY.pdf"  # every "-" as "_"
# SPEC -> Creator table: Summit Homes Group's creator is Compactions;
# Summit Renovations' is the previous task's Task Creator.
TABLE_COMPANY, TABLE_CREATOR = "Summit Homes Group", "Compactions"
PREVIOUS_COMPANY = "Summit Renovations"
# The project's tasks: a Cancelled Compaction Test (it doesn't block a
# Summit booking, decisions 25 Nov 2026) and two other tasks. The previous
# task is the highest-numbered one not Compaction Test and not Cancelled.
CANCELLED = ("tsk_200001", "Compaction Test", "Fake Staff One", "Cancelled")
SITE_START = ("tsk_300001", "Site Start", "Fake Staff One", "Complete")
ENGINEERING = ("tsk_300002", "Engineering", "Fake Staff Two", "Active")
TASKS = [CANCELLED, SITE_START, ENGINEERING]
PREVIOUS_CREATOR = "Fake Staff Two"
# The Creator options a Summit project offers (fake staff, the two
# creators); the select opens at the Project Creator (S.0).
CREATORS = ("Compactions", "NH Sub Floor", "Fake Staff One", "Fake Staff Two")
# A long Summit email body: tables (tab-separated cells), several lots
# carried as they are, a line of text and a Disclaimer (shapes only).
LONG_BODY = "\n".join(
    [
        "Fake Builder Header",
        "Purchase Order\t123456/020/01",
        "Summit:123456 Lot 1 Fake Street",
        "Summit:123456 Lot 2 Fake Street",
        "Item\tQuantity\tUnit",
        "COMPACTION TEST\t1\tEA",
        "Please book the compaction test.",
        "Disclaimer: fake disclaimer text " + "that runs on " * 20,
    ]
)

REOPEN = [
    "open_project_tab",
    "open_projects_subtab",
    "move_pointer_off_menu",
    "search_project",
    "submit_project_search",
    "open_project",
]
FILL = [
    "open_create_new_task",
    "set_creator",
    "tick_compaction_test",
    "set_po_number",
    "upload_document",
    "set_task_note",
]
W2 = [
    "submit_task",
    "open_new_task_detail",
    "back_to_project",
    "open_project_documents",
    "open_project_tasks",
]
CLOSE = '<div><span title="Close">close</span></div>'


def task_rows(tasks) -> str:
    rows = ""
    for task_no, name, creator, status in tasks:
        buttons = "<button>Undo Cancellation</button>" if status == "Cancelled" else ""
        rows += (
            f"<tr><td><div><span>({task_no}) | {name}</span>{buttons}</div></td></tr>"
            f"<tr><td>Fake Lodger</td><td>{creator}</td><td>{status}</td></tr>"
        )
    return rows


def summit_mysys(
    *,
    company: str,
    tasks,
    creators: tuple[str, ...] = CREATORS,
    filed: str | None = None,
    doc_file: str | None = None,
) -> str:
    """base_url after login: the Project menu, the Projects panel, the
    project window (rows 06-07, 26) and Create New Task (rows 08-09), laid
    out as tests/test_booker_offline.py maps them, with a Summit project:
    one search row under `company`, its Client Internal No. and `tasks`.

    The Creator select holds "Choose...", the Project Creator (chosen when
    it opens, S.0) and `creators` as their option texts. The Documents
    block shows the upload as `filed` (None: its own name). After Submit
    the new task's rows show the agent and the chosen creator; its detail
    screen shows the form's PO Number, the agent, the Note as MySys renders
    it (line breaks as <br>) and the chosen creator; the Documents tab's
    section for it has one Client Documents row whose File starts with
    `doc_file` (None: what the Documents block showed)."""
    compaction = [t for t in tasks if t[1] == "Compaction Test"]
    options = "".join(
        f"<option>({task_no}) [Compaction Test]</option>" for task_no, *_ in compaction
    )
    creator_options = "".join(f"<option>{text}</option>" for text in creators)
    data = json.dumps(
        {
            "newTask": NEW_TASK,
            "agent": AGENT,
            "filed": filed,
            "docFile": doc_file,
            "company": company,
        }
    )
    return f"""
<ul><li><span onclick="document.getElementById('sub').hidden = false">Project</span>
  <ul id="sub" hidden><li>Note Pool</li><li onclick="showProjects()">Projects</li></ul></li></ul>
<div id="projects" hidden>
  <button>Reset Filter</button>
  <div><div>Search</div><input aria-label="Search..."
    onkeydown="if (event.key === 'Enter') search(this.value)"></div>
  <div><div>Status</div><select><option selected>All Projects</option><option>Cancelled</option></select></div>
  <div><div>Eng Type</div><select><option selected>All Eng Types</option></select></div>
  <div><div>Sales Type</div><select><option selected>All Sales Types</option></select></div>
  <table><thead><tr><th>Project No.</th><th>Client Ref No.</th><th>Status</th>
    <th>Company</th></tr></thead><tbody id="rows"><tr><td><a href="#">pln_20500</a></td>
    <td>999999</td><td>Draft</td><td>Other Homes</td></tr></tbody></table>
  <div id="none" hidden>No record found.</div>
  <div id="footer">Page 1 of 1(1 Items)</div>
</div>
<div id="project" hidden><div>
  <h3 id="heading">{PLN} Fake Builder Lot 1 Fake Street</h3>
  <select id="task_select" onchange="choose(this.value)"><option selected>-- Select Task --</option>{options}</select>
  <ul><li><strong>Lodged By:</strong> <span>&lt;project lodger&gt;</span></li>
    <li><strong>Client Internal No.:</strong> <span>{CLIENT_REF}</span></li>
    <li><strong>Address:</strong> <span>Lot 1 Fake Street Fakeville 6000 WA</span></li></ul>
  <div id="task_view" hidden></div>
  <div id="project_tabs">
    <button onclick="show('tasks')">Tasks</button><button onclick="show('documents')">Documents</button><button>Notes</button>
    <button id="create" onclick="document.getElementById('form').hidden = false">Create New Task</button>
  </div>
  <div id="tasks"><table><tbody id="task_rows">{task_rows(tasks)}</tbody></table></div>
  <div id="documents" hidden></div>
</div>{CLOSE}</div>
<div id="form" hidden><div>
  <h3>Create New Task</h3>
  <div><div>Multiple Units</div><input type="checkbox" aria-label="multiple"></div>
  <div><div>Creator</div><select id="creator"><option>Choose...</option><option selected>Fake Project Creator</option>{creator_options}</select></div>
  <div><input type="checkbox" aria-label="- 1.Single Storey Engineering Bundle"> - 1.Single Storey Engineering Bundle</div>
  <div><input type="checkbox" aria-label="- Compaction Test"
    onchange="document.getElementById('sub_form').hidden = !this.checked"> - Compaction Test</div>
  <div id="sub_form" hidden>
    <div><div>Task Client</div><div>Same as Project <button>Select Client</button> <span>close</span></div></div>
    <div><div>Task Name</div><input aria-label="Task Name"></div>
    <div><div>PO Number</div><input id="po_number"></div>
    <div><div>PO Contact</div><select><option selected>Choose...</option><option>&lt;user&gt;</option></select></div>
    <div><div>PO Documents</div><div id="po_docs"><span>Upload <input type="file"></span></div></div>
    <div><div>Documents</div><div id="docs"><span>Upload <input type="file" onchange="addDoc(this)"></span></div></div>
    <div><div>Sale Office</div><select><option>... Use Default Office ...</option><option selected>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Delivery Office</div><select><option selected>Choose...</option><option>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Note</div><textarea id="note"></textarea></div>
  </div>
  <button onclick="submitTask()">Submit</button>
</div>{CLOSE}</div>
<script>
const FAKE = {data};
const byId = (id) => document.getElementById(id);
const PROJECT_HEADING = '{PLN} Fake Builder Lot 1 Fake Street';
let shownName = null;
function showProjects() {{
  byId('sub').hidden = true;
  byId('projects').hidden = false;
}}
function search(text) {{
  if (text !== '{CLIENT_REF}') return;
  setTimeout(() => {{
    byId('none').hidden = true;
    byId('rows').innerHTML =
      '<tr><td><a href="#" onclick="document.getElementById(\\'project\\').hidden = false; return false">{PLN}</a></td>'
      + '<td>{CLIENT_REF}</td><td>Active</td><td>' + FAKE.company + '</td></tr>';
    byId('footer').textContent = 'Page 1 of 1(1 Items)';
  }}, 200);
}}
function addDoc(input) {{
  shownName = FAKE.filed || input.files[0].name;
  byId('docs').insertAdjacentHTML('beforeend',
    '<table><tbody><tr><td>' + shownName + '</td><td>close</td></tr></tbody></table>');
}}
function submitTask() {{
  document.body.dataset.submitted = 'yes';
  const select = byId('creator');
  FAKE.booked = {{
    creator: select.options[select.selectedIndex].textContent.trim(),
    po: byId('po_number').value,
    note: byId('note').value,
  }};
  // What the form held at Submit, for the test to read.
  document.body.dataset.creator = FAKE.booked.creator;
  document.body.dataset.po = FAKE.booked.po;
  document.body.dataset.note = FAKE.booked.note;
  byId('form').hidden = true;
  setTimeout(() => {{
    const task = FAKE.newTask;
    byId('task_rows').insertAdjacentHTML('beforeend',
      '<tr><td><div><span>(' + task + ') | Compaction Test</span><div><button>Cancel</button>'
      + '<button>Hold</button></div></div></td></tr>'
      + '<tr><td>' + FAKE.agent + '</td><td onclick="openTask(\\'' + task + '\\')">'
      + FAKE.booked.creator + '</td><td>New Project</td></tr>');
    const option = document.createElement('option');
    option.textContent = '(' + task + ') [Compaction Test]';
    byId('task_select').appendChild(option);
  }}, 300);
}}
function projectView(on) {{
  for (const id of ['project_tabs', 'tasks']) byId(id).hidden = !on;
  byId('documents').hidden = true;
  byId('task_view').hidden = on;
}}
function openTask(task) {{
  document.body.dataset.opened = task;
  const b = FAKE.booked;
  byId('heading').textContent = 'TSK_' + task.slice(4) + ' PLN_' + '{PLN}'.slice(4) + ' Fake Builder';
  byId('task_select').value = '(' + task + ') [Compaction Test]';
  byId('task_view').innerHTML =
    '<div><div><h3>' + task + ' [Compaction Test]</h3></div><div><ul>'
    + '<li><strong>Lodged By:</strong> <span>' + FAKE.agent + '</span></li>'
    + '<li><strong>PO Number:</strong> <span>' + b.po + '</span></li></ul>'
    + '<div><hr><strong>Notes</strong><span id="notes"></span></div></div></div>'
    + '<div><div><h3>Client</h3></div><div><hr><ul><li><strong><span>Task Creator:</span></strong> <a href="#">'
    + b.creator + '</a></li></ul></div></div>';
  byId('notes').innerText = b.note;  // MySys renders the Note's line breaks
  projectView(false);
}}
function choose(value) {{
  if (value !== '-- Select Task --') return;
  byId('heading').textContent = PROJECT_HEADING;
  projectView(true);
}}
function docSection(task, rows) {{
  const body = rows.length === 0 ? '<div>No Document Found</div>'
    : '<table><thead><tr><th></th><th>Type</th><th>File</th><th>Document</th></tr></thead><tbody>'
      + rows.map(([type, file]) => '<tr><td><input type="checkbox"></td><td>' + type + '</td><td>' + file
        + ' <a href="#">file_download 1 KB</a></td><td>' + type + '</td></tr>').join('')
      + '</tbody></table>';
  return '<div><div><h3>' + task + '</h3><div>Document Actions</div></div>' + body + '</div>';
}}
function show(view) {{
  byId('tasks').hidden = view !== 'tasks';
  byId('create').hidden = view !== 'tasks';
  const docs = byId('documents');
  docs.hidden = view !== 'documents';
  if (view !== 'documents') return;
  docs.innerHTML = docSection('{PLN}', [])
    + docSection(FAKE.newTask, [['Client Documents', FAKE.docFile || shownName]]);
}}
</script>"""


# `browser` is tests/conftest.py's: one headless Chromium per module.


@pytest.fixture
def folder(tmp_path) -> Path:
    """A config folder: the committed live profile and Summit client file,
    `enabled` on, so the booker's kill-switch re-reads pass."""
    folder = tmp_path / "config"
    (folder / "clients").mkdir(parents=True)
    (folder / "live.toml").write_text(
        (CONFIG_DIR / "live.toml").read_text("utf-8"), "utf-8"
    )
    text = (CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8")
    (folder / "clients" / "summit.toml").write_text(switched(text, True), "utf-8")
    return folder


@pytest.fixture
def serve(browser: Browser, tmp_path: Path) -> Iterator:
    """`serve(**fake)` writes `summit_mysys` to a file, which is base_url,
    and opens a fresh browser context; returns its page and the login."""
    contexts = []

    def open_page(**fake: object) -> tuple[Page, tuple[str, str, str]]:
        home = tmp_path / "mysys.html"
        home.write_text(summit_mysys(**fake), encoding="utf-8")  # type: ignore[arg-type]
        context = browser.new_context()
        contexts.append(context)
        page = context.new_page()
        page.set_default_timeout(2000)
        return page, (home.as_uri(), "fake-user", "fake-password")

    yield open_page
    for context in contexts:
        context.close()


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


@pytest.fixture(autouse=True)
def search(monkeypatch):
    """`driver.search_note` for W1's assignee check: the Note with Agent 2."""

    def fake(guard, page, base_url, username, password, note_id):
        row = summit_row(note_id, assignee=AGENT)
        return "panel", driver.NotePoolList(rows=(row,), total=1, pages=1)

    monkeypatch.setattr(driver, "search_note", fake)


def lookup_of(company: str, tasks) -> MySysLookup:
    return MySysLookup(
        search_rows=(SearchRow(pln=PLN, client_ref_no=CLIENT_REF, company=company),),
        more_pages=False,
        project_internal_no=CLIENT_REF,
        project_tasks=tuple(
            ProjectTask(task_no=n, name=name, task_creator=c, status=s)
            for n, name, c, s in tasks
        ),
    )


def proceed_for(company: str, tasks=TASKS) -> SummitProceed:
    """Summit's decision engine on a fake Note, PDF and project lookup (the
    peek's reads), with the committed creator table."""
    snapshot = NoteSnapshot(
        note_id=NOTE_ID,
        title=summit_titled(PO, company),
        body=LONG_BODY,
        attachment_names=(FILE,),
        project_linked=False,
        assignee="---",
    )
    decision = decide(
        snapshot,
        "---",
        readers.read(summit_pdf(PO, company)),
        lambda: lookup_of(company, tasks),
        companies=load_client("summit", "live", CONFIG_DIR).company,
    )
    assert isinstance(decision, SummitProceed)
    return decision


def run_book(served, guard, proceed, folder, stop_after="W2") -> str | None:
    page, login = served
    gate = controls.Controls(
        "live",
        folder,
        controls.assignee_check(guard, page, login, AGENT),
        client="summit",
    )
    return booker.book(
        proceed,
        note_id=NOTE_ID,
        guard=guard,
        page=page,
        login=login,
        controls=gate,
        agent=AGENT,
        project_rule=SummitProjectRule(
            load_client("summit", "live", CONFIG_DIR).company
        ),
        document_type="Client Documents",
        stop_after=stop_after,
    )


def actions(guard: ActionGuard) -> list[str]:
    return [action for action, _ in guard.history]


def booked(page: Page) -> dict:
    """What the form held at Submit."""
    body = page.locator("body")
    return {key: body.get_attribute(f"data-{key}") for key in ("creator", "po", "note")}


# --- the decided creator reaches the form and every read-back -----------------


@pytest.mark.parametrize(
    ("company", "creator"),
    [(TABLE_COMPANY, TABLE_CREATOR), (PREVIOUS_COMPANY, PREVIOUS_CREATOR)],
    ids=["table-creator", "previous-task-creator"],
)
def test_the_decided_creator_reaches_the_w1_form_and_every_read_back(
    company, creator, serve, guard, folder
):
    served = serve(company=company, tasks=TASKS)
    page = served[0]
    proceed = proceed_for(company)
    assert proceed.creator == creator

    task_no = run_book(served, guard, proceed, folder)

    # W1's form and W2's new task row, detail and Documents tab read it back.
    assert task_no == NEW_TASK
    assert actions(guard) == REOPEN + FILL + W2
    assert booked(page) == {"creator": creator, "po": PO, "note": LONG_BODY}
    assert page.locator("body").get_attribute("data-opened") == NEW_TASK


def test_the_long_body_is_read_back_whitespace_collapsed_on_the_task_detail(
    serve, guard, folder
):
    # MySys shows the Note with its line breaks as <br>; the detail's Notes
    # read back with whitespace collapsed (SPEC -> Email body: as B1).
    served = serve(company=TABLE_COMPANY, tasks=TASKS)
    page = served[0]

    run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert page.locator("#notes br").count() == len(LONG_BODY.splitlines()) - 1


# --- the Creator select: read first, exact after stripping, else CREATOR_UNKNOWN


@pytest.mark.parametrize(
    "creators",
    [
        (" Compactions ", "NH Sub Floor"),  # surrounding whitespace on the option
        (" Compactions ", "NH Sub Floor"),  # non-breaking spaces
    ],
    ids=["spaces", "nbsp"],
)
def test_an_option_matching_after_stripping_whitespace_is_selected(
    creators, serve, guard, folder
):
    served = serve(company=TABLE_COMPANY, tasks=TASKS, creators=creators)
    page = served[0]

    run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert booked(page)["creator"] == TABLE_CREATOR


@pytest.mark.parametrize(
    "creators",
    [
        ("NH Sub Floor", "Fake Staff Two"),  # not offered
        ("compactions", "NH Sub Floor"),  # another case
        ("Compactions (left) Compactions (left)",),  # a repeated label
        ("Compaction", "Compactions Team"),  # near names
        ("Compactions", "Compactions"),  # offered twice
    ],
    ids=["absent", "case", "repeated-label", "near", "twice"],
)
def test_a_creator_not_exactly_one_option_is_write_not_started_with_nothing_selected(
    creators, serve, guard, folder
):
    served = serve(company=TABLE_COMPANY, tasks=TASKS, creators=creators)
    page = served[0]

    with pytest.raises(WriteNotStarted) as stopped:
        run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert (stopped.value.reason, stopped.value.step) == ("CREATOR_UNKNOWN", "W1")
    # The form was opened, nothing was selected or filled, nothing submitted.
    assert actions(guard) == [*REOPEN, "open_create_new_task"]
    assert page.is_closed()


# --- W1's recheck of the previous task ------------------------------------------


@pytest.mark.parametrize(
    "tasks",
    [
        # A later task by another person, created between the peek and W1.
        [*TASKS, ("tsk_300003", "Retaining Wall", "Fake Staff Three", "Active")],
        # The previous task's Task Creator changed.
        [CANCELLED, SITE_START, (*ENGINEERING[:2], "Fake Staff Three", "Active")],
        # The previous task was cancelled: another task is now the previous one.
        [CANCELLED, SITE_START, (*ENGINEERING[:3], "Cancelled")],
    ],
    ids=["later-task", "creator-changed", "previous-cancelled"],
)
def test_a_previous_task_changed_since_the_peek_is_write_not_started_before_the_form(
    tasks, serve, guard, folder
):
    served = serve(company=PREVIOUS_COMPANY, tasks=tasks)

    with pytest.raises(WriteNotStarted) as stopped:
        run_book(served, guard, proceed_for(PREVIOUS_COMPANY), folder)

    assert stopped.value.step == "W1"
    assert stopped.value.detail == "project changed since the decision"
    assert actions(guard) == REOPEN  # Create New Task never opened


def test_a_later_task_that_does_not_change_the_previous_task_still_books(
    serve, guard, folder
):
    # A later Compaction-free task, Cancelled: not a previous-task candidate.
    later = ("tsk_300003", "Retaining Wall", "Fake Staff Three", "Cancelled")
    served = serve(company=PREVIOUS_COMPANY, tasks=[*TASKS, later])
    page = served[0]

    run_book(served, guard, proceed_for(PREVIOUS_COMPANY), folder)

    assert booked(page)["creator"] == PREVIOUS_CREATOR


# --- the Documents file name: the PDF's, or with every "-" filed as "_" --------


@pytest.mark.parametrize(
    ("filed", "doc_file"),
    [(None, None), (FILED, FILED), (None, FILED), (FILED, FILE)],
    ids=["as-is", "underscored", "underscored-at-w2", "underscored-at-w1"],
)
def test_the_documents_name_is_the_pdfs_or_every_dash_filed_as_underscore(
    filed, doc_file, serve, guard, folder
):
    served = serve(company=TABLE_COMPANY, tasks=TASKS, filed=filed, doc_file=doc_file)

    task_no = run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert task_no == NEW_TASK


@pytest.mark.parametrize(
    "filed",
    [
        "PO_123456-020-01-READY.pdf",  # only some "-" filed as "_"
        "PO-123456-020-01-READY (1).pdf",  # a near match
        "PO 123456 020 01 READY.pdf",  # "-" as a space
    ],
    ids=["partly-underscored", "near", "spaces"],
)
def test_any_other_documents_name_at_w1_is_write_not_started(
    filed, serve, guard, folder
):
    served = serve(company=TABLE_COMPANY, tasks=TASKS, filed=filed)
    page = served[0]

    with pytest.raises(WriteNotStarted) as stopped:
        run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert stopped.value.field == "documents"
    assert "submit_task" not in actions(guard)
    assert page.is_closed()


def test_any_other_documents_name_at_w2_is_an_accuracy_breach(serve, guard, folder):
    served = serve(
        company=TABLE_COMPANY, tasks=TASKS, doc_file="PO_123456-020-01-READY.pdf"
    )

    with pytest.raises(AccuracyBreach) as stopped:
        run_book(served, guard, proceed_for(TABLE_COMPANY), folder)

    assert (stopped.value.field, stopped.value.step) == ("document_file", "W2")


# --- the command: `run --client summit` books up to its cap -------------------

RUN = ["run", "--site", "live", "--client", "summit"]
STAFF = "Fake Admin"  # a staff user as the original assignee
POOL = "PO Allocation Pool"
AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, tzinfo=UTC)  # any assignee
AT_1000_PERTH = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)  # only `---`


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake Summit secrets, temp, logs and a config folder with the
    committed live profile (its trace off) and Summit client file (fake
    mailbox and sender, `enabled` on)."""
    for name in secrets.SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_USERNAME", "fake-summit-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_PASSWORD", "fake-summit-pass")
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    folder = tmp_path / "config"
    (folder / "clients").mkdir(parents=True)
    live = (CONFIG_DIR / "live.toml").read_text("utf-8").splitlines()
    live = [line for line in live if not line.startswith("trace_dir")]
    live.append(f'trace_dir = "{(tmp_path / "trace").as_posix()}"')
    (folder / "live.toml").write_text("\n".join(live) + "\n", "utf-8")
    text = switched((CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8"), True)
    for old, new in (
        (
            'source_filter = "support@prompteng.com.au"',
            f'source_filter = "{SUMMIT_MAILBOX}"',
        ),
        ('sender = "noreply@summithomesgroup.com.au"', f'sender = "{SUMMIT_SENDER}"'),
    ):
        assert text.count(old) == 1
        text = text.replace(old, new)
    (folder / "clients" / "summit.toml").write_text(text, "utf-8")
    monkeypatch.setattr(cli, "CONFIG_DIR", folder)
    yield monkeypatch
    keyring.set_keyring(previous)


def fake_mysys(env, tmp_path, notes, **kwargs) -> FakeMySys:
    rows = tuple(
        summit_row(
            note_id,
            title=summit_titled(f"{note.internal_no}/020/01"),
            assignee=note.assignee,
        )
        for note_id, note in notes.items()
    )
    fake = FakeMySys(
        notes=notes,
        rows=rows,
        config_dir=tmp_path / "config",
        kill_file="clients/summit.toml",
        logs_dir=tmp_path / "logs",
        note_users=(AGENT, STAFF),
        note_pools=(POOL,),
        **kwargs,
    )
    return install(env, fake, summit=True)


def capped(tmp_path: Path, cap: int) -> None:
    """The env's Summit client file with `max_notes_per_run = cap`, whatever
    the committed file says, so a cap test never depends on it."""
    file = tmp_path / "config" / "clients" / "summit.toml"
    text, count = re.subn(
        r"(?m)^max_notes_per_run = \d+",
        f"max_notes_per_run = {cap}",
        file.read_text("utf-8"),
    )
    assert count == 1
    file.write_text(text, "utf-8")


def run_summit(env, capsys, at: datetime) -> tuple[int, list[str]]:
    env.setattr(controls, "now", lambda: at)
    code = cli.main(RUN)
    out = capsys.readouterr()
    assert out.err == ""
    return code, out.out.splitlines()


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


def alerts_of(lines: list[str]) -> list[tuple[str, dict]]:
    found = []
    for line in lines:
        if line.startswith("ALERT "):
            kind, _, body = line.removeprefix("ALERT ").partition(" ")
            found.append((kind, json.loads(body)))
    return found


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def test_run_client_summit_books_one_note_per_run_at_cap_1(env, capsys, tmp_path):
    # Two Notes that would both be booked; the client file's cap is 1.
    fake = fake_mysys(
        env,
        tmp_path,
        {"462002": summit_note("654321/020/01"), "462001": summit_note()},
    )
    capped(tmp_path, 1)

    code, lines = run_summit(env, capsys, AT_1000_PERTH)

    assert code == 0
    assert notes_of(lines) == [
        {
            "note_id": "462002",  # newest first
            "outcome": "booked",
            "reason": None,
            "field": None,
            "po_number": "654321/020/01",  # the full PO
            "pln": "pln_20001",
            "task_id": "tsk_200002",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_aud": 0.0,
        }
    ]
    assert "INFO  run cap reached: 1 notes left for the next run" in lines
    summary = summary_of(lines)
    assert (summary["client"], summary["booked"], summary["exit_code"]) == (
        "summit",
        1,
        0,
    )
    # Agent 2 lodges and solves; the table's creator is set and read back;
    # W2's Documents Type is the client file's.
    assert fake.creators == [
        ("fill", "Compactions"),
        ("task_row", "Compactions"),
        ("open_detail", "Compactions"),
        ("detail", "Compactions"),
    ]
    assert {agent for _, agent in fake.agents} == {AGENT}
    assert fake.document_types == ["Client Documents"]
    assert fake.notes["462002"].assignee == AGENT  # booked: never returned
    assert not [c for c in fake.calls if c.startswith("find_again 462001")]


def test_run_client_summit_books_several_notes_in_one_run(env, capsys, tmp_path):
    # Three Notes that would all be booked; the client file's cap is 2: the
    # run books the two newest, one after the other, and leaves the third
    # untouched for the next run (decisions, 27 Nov 2026, Summit cap 15).
    fake = fake_mysys(
        env,
        tmp_path,
        {
            "462003": summit_note(
                "654322/020/01", lookup=summit_lookup("654322", pln="pln_20003")
            ),
            "462002": summit_note(
                "654321/020/01", lookup=summit_lookup("654321", pln="pln_20002")
            ),
            "462001": summit_note(),
        },
    )
    capped(tmp_path, 2)

    code, lines = run_summit(env, capsys, AT_1000_PERTH)

    assert code == 0
    assert [
        (n["note_id"], n["outcome"], n["po_number"], n["pln"]) for n in notes_of(lines)
    ] == [
        ("462003", "booked", "654322/020/01", "pln_20003"),  # newest first
        ("462002", "booked", "654321/020/01", "pln_20002"),  # its own project
    ]
    assert "INFO  run cap reached: 1 notes left for the next run" in lines
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert (summary["client"], summary["booked"], summary["exit_code"]) == (
        "summit",
        2,
        0,
    )
    assert fake.notes["462003"].assignee == AGENT  # booked: never returned
    assert fake.notes["462002"].assignee == AGENT
    assert fake.notes["462001"].assignee != AGENT  # never taken
    assert not [c for c in fake.calls if c.startswith("find_again 462001")]


def test_a_second_note_for_a_project_booked_in_the_same_run_is_a_duplicate(
    env, capsys, tmp_path
):
    # The same PO sent twice: with a cap above 1 both Notes are peeked in one
    # run. The second Note's peek reads the project's Tasks table again and
    # finds the Compaction Test task the first booking added (decisions, 27
    # Nov 2026, Summit cap 15), so it is never taken.
    fake = fake_mysys(
        env,
        tmp_path,
        {"462002": summit_note(), "462001": summit_note()},
    )
    capped(tmp_path, 2)

    code, lines = run_summit(env, capsys, AT_1000_PERTH)

    assert code == 0
    assert [(n["note_id"], n["outcome"], n["reason"]) for n in notes_of(lines)] == [
        ("462002", "booked", None),
        ("462001", "untouched", "DUPLICATE_TASK"),
    ]
    assert alerts_of(lines) == []
    assert summary_of(lines)["booked"] == 1
    assert [c for c in fake.calls if c.startswith("submit")] == ["submit 462002"]
    assert fake.notes["462001"].assignee != AGENT  # never taken


@pytest.mark.parametrize("original", [STAFF, POOL])
def test_a_creator_not_in_the_select_stops_and_returns_the_note(
    original, env, capsys, tmp_path
):
    note = summit_note(assignee=original)
    fake = fake_mysys(env, tmp_path, {NOTE_ID: note}, creator_options=("NH Sub Floor",))

    code, lines = run_summit(env, capsys, AT_0759_PERTH)

    assert code == 1
    ((kind, alert),) = alerts_of(lines)
    assert kind == "UNEXPECTED_SCREEN"  # WriteNotStarted's ALERT
    assert "reason=CREATOR_UNKNOWN" in alert["detail"]
    assert alert["step"] == "W1"  # the ops runbook keys on the step
    assert "Note not returned" not in alert["detail"]
    assert notes_of(lines) == []
    assert fake.notes[NOTE_ID].assignee == original
    assert not [c for c in fake.calls if c.startswith("submit")]


def test_a_dashes_original_stays_with_agent_2_with_the_alert_naming_the_reason(
    env, capsys, tmp_path
):
    # Joey, 26 Nov 2026: a taken `---` Note stays with Agent 2 ("先留給
    # Agent 2"); the ALERT still says why the booking stopped.
    fake = fake_mysys(
        env, tmp_path, {NOTE_ID: summit_note()}, creator_options=("NH Sub Floor",)
    )

    code, lines = run_summit(env, capsys, AT_1000_PERTH)

    assert code == 1
    ((kind, alert),) = alerts_of(lines)
    assert kind == "UNEXPECTED_SCREEN"
    assert alert["detail"].startswith("run stopped; Note not returned")
    assert "reason=CREATOR_UNKNOWN" in alert["detail"]
    assert alert["note_id"] == NOTE_ID
    assert fake.notes[NOTE_ID].assignee == AGENT
    assert not [c for c in fake.calls if c.startswith("submit")]
