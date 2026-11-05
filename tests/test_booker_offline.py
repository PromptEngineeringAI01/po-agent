# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""The booker's W1 (task 4.1), W2 (task 4.2) and W3 (task 4.3), offline:
Create New Task filled and read back; then Submit and the read-back on the
task detail screen and the project's Documents tab; then Hold.

Headless Chromium on a fake MySys, a local HTML file that is base_url (no
site is touched): the Project menu, the Projects panel (Enter runs the search), the
project window and the Create New Task form, as mapped in docs/screen-map.md
rows 06-09, 24 and 26; after Submit the new task's rows (row 10), its detail
screen in the same window and the project's Documents tab (row 19); the
Hold Task dialog and the row after Hold (rows 11-12, laid out as the 16 Oct
capture). The assignee check runs for real inside
`Controls.before_write`; only `driver.search_note` (the Note Pool search) is
faked, as in tests/test_assignee_offline.py. The `Proceed` comes from
`decide()` on seam 1's p1-clean case with a fake PDF from seam 1's
`text_pdf`, never built by hand. Values are fake.

- `book()` takes only a `Proceed`, and only for the Note in hand; otherwise it
  stops before the W1 check or any page action.
- Then: `before_write(note_id, "W1")` -> reopen the project by its pln and
  check it again (the pln the search matches, Client Internal No., the
  settled Compaction Test tasks equal to the Proceed's) -> Create New Task:
  Creator, - Compaction Test, PO Number, the PDF to PO Documents from memory,
  Note = the email body -> the full read-back. Any mismatch is
  WriteNotStarted; once the form is open the browser context is closed.
- With stop_after="W1" Submit is never pressed.
- W2 (4.2): `before_write(note_id, "W2")` (no assignee check, D7; a kill
  switch here closes the context, nothing submitted) -> Submit, the
  partial-write line: from the click on every error is PartialWrite, except
  AccuracyBreach and GuardRefusal, which keep their type; each carries step
  W2. The new task is the one Compaction Test number not in step 10's set;
  its detail screen is opened from its own details row and must name it;
  PO Number, Lodged By, Notes and Task Creator are read there, then back to
  the project, the new task's Documents section (one Purchase Order row,
  the PDF's file), then Tasks. A wrong value is AccuracyBreach; a screen not
  as mapped is PartialWrite.
- W3 (4.3): `before_write(note_id, "W3")` (no assignee check, D7; a kill
  switch here is already PartialWrite, 3.5) -> Hold in the new task's own
  header row -> the dialog headed `Hold Task: <new task>` -> the note typed,
  no checkbox touched -> every check read before confirming: the Related
  Tasks boxes and Select-all (hidden ones too), Reset turn around time and
  "at this date" unticked, "every ... days" ticked with 0, the note exact.
  Anything else closes the browser context and is PartialWrite, the
  dialog's Hold never pressed. Confirm once -> the row shows Un-Hold and a
  Status starting "On-hold" with the note. Every error from W3 closes the
  context and carries step W3.
- W4 (4.4): `before_write(note_id, "W4")` runs the assignee check (D7) ->
  back to the Note window by "Finding a Note again" (row 25) -> Send Email
  unticked and read back -> Link to Project -> Choose Project: the pln
  searched with Enter -> Send Email read back again -> the one cell named
  exactly the pln, clicked once (never the row: its Site Address holds
  "Close") -> the project button reads the pln and Status still starts
  Pending. W5: `before_write(note_id, "W5")` (no assignee check) -> Send
  Email read back -> Solved once -> "Solved by <agent>", a new "Status
  changed ... Pending to Solved" log line, Solved disabled, and the Note
  ID search (Status filter read back Pending) with no row whose ID equals
  the Note ID. Every W4/W5 error closes the context and is PartialWrite
  with its step, except AccuracyBreach (another pln on the project button)
  and GuardRefusal, which keep their type.
"""

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, ConsoleMessage, Page, sync_playwright

from po_agent.b1 import booker
from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import decide
from po_agent.b1.models import CompactionTask, NotePoolRow, Proceed
from po_agent.core import controls
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import (
    AccuracyBreach,
    GuardRefusal,
    PartialWrite,
    WriteNotStarted,
)
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard, Refusal

_spec = importlib.util.spec_from_file_location(
    "seam1_cases_for_booker",
    Path(__file__).parent / "seam1" / "seam1_cases.py",
)
seam1_cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seam1_cases)

AGENT = "Agent 1 (MySys Only)"
CLEAN = next(case for case in seam1_cases.CASES if case.id == "p1-clean")
NOTE_ID = CLEAN.note.note_id
INTERNAL_NO = "2600001B"
PLN = "pln_10001"
FILE = "2600001B_048_1.pdf"
# Both readers read these lines alike (as tests/seam2/test_run_loop_offline.py).
PDF = seam1_cases.text_pdf(
    [line for line in CLEAN.pypdf_text.splitlines() if "(" not in line]
)
CANCELLED = ("tsk_200001", "Cancelled")
CLOSE = '<div><span title="Close">close</span></div>'

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


def proceed_for_p1() -> Proceed:
    """decide() on p1-clean, with one Cancelled task on the project at step 10."""
    lookup = CLEAN.lookup.model_copy(
        update={"tasks": (CompactionTask(task_no=CANCELLED[0], status=CANCELLED[1]),)}
    )
    decision = decide(
        CLEAN.note,
        INTERNAL_NO,
        rules.text_layer(PDF),
        rules.pypdf_text_layer(PDF),
        PDF,
        lookup,
        site="test",
        duplicate_ignores_cancelled=True,
    )
    assert isinstance(decision, Proceed)
    return decision


NEW_TASK = "tsk_200002"
# Row 19: the new task's detail screen, as booked (fake values).
DETAIL = {
    "po_number": "2600001B/048",
    "lodged_by": AGENT,
    "notes": CLEAN.note.body,
    "task_creator": "Perth Scheduling",
}
PO_ROW = ("Purchase Order", FILE)
# Row 11: the Hold Task dialog as mapped. `ticked` names the boxes that
# start ticked besides the reminder: related_0, related_hidden (a row the
# table hides), select_all, reset, at_date. `jobs` is the count the Related
# Tasks text states (the table has 3 rows); `related_outside` puts Related
# Tasks in the window but outside the heading and Note block; `extra_hold`
# adds a second Hold button to that block. After its Hold: `closes`, `holds`
# (the row then shows Un-Hold) and `status` (None: "On-hold Notes: <note>").
HOLD_DIALOG: dict[str, object] = {
    "heading": None,
    "jobs": 3,
    "relatedOutside": False,
    "extraHold": False,
    "ticked": [],
    "reminder": True,
    "days": "0",
    "noteSuffix": "",
    "closes": True,
    "holds": True,
    "status": None,
}


def task_rows(tasks: list[tuple[str, str]]) -> str:
    return "".join(
        f"<tr><td><div><span>({task}) | Compaction Test</span><button>Undo Cancellation</button></div></td></tr>"
        f"<tr><td>{AGENT}</td><td onclick=\"openTask('{task}')\">Perth Scheduling</td><td>{status}</td></tr>"
        for task, status in tasks
    )


def fake_mysys(
    *,
    tasks: list[tuple[str, str]],
    search_pln: str = PLN,
    internal_no: str = INTERNAL_NO,
    multiple: str = "",
    new_tasks: tuple[str, ...] = (NEW_TASK,),
    row_creator: str = "Perth Scheduling",
    form_closes: bool = True,
    opens_as: str | None = None,
    detail: dict[str, str] | None = None,
    documents: tuple[tuple[str, str], ...] | None = (PO_ROW,),
    documents_buttons: int = 1,
    hold: dict[str, object] | None = None,
) -> str:
    """base_url after login: the Project menu, the Projects panel (hidden
    until Projects is chosen), the project window and Create New Task.

    After Submit (W2): the form closes (unless `form_closes` is False) and,
    300 ms later, a header and details row and a select option per task in
    `new_tasks`. A details-row cell opens that task's detail screen in the
    project window (`opens_as`: another task number instead); "-- Select
    Task --" goes back. Documents lists a section per task: an older task's
    holds its own copy of the PDF; the first new task's holds `documents`
    (None: no section); Create New Task is then hidden, as live (it shows
    on the Tasks tab only). Every task's detail screen shows the same values,
    so only the task number tells them apart.

    W3: a new task's Hold opens the Hold Task dialog as mapped (row 11),
    changed by `hold` (HOLD_DIALOG's keys); its Hold closes it and puts the
    task on hold with the typed note (row 12)."""
    options = "".join(
        f"<option>({task}) [Compaction Test]</option>" for task, _ in tasks
    )
    data = json.dumps(
        {
            "newTasks": list(new_tasks),
            "rowCreator": row_creator,
            "formCloses": form_closes,
            "opensAs": opens_as,
            "detail": {**DETAIL, **(detail or {})},
            "documents": documents,
            "olderFile": FILE,
            "agent": AGENT,
            "hold": {**HOLD_DIALOG, **(hold or {})},
        }
    )
    documents_button = "<button onclick=\"show('documents')\">Documents</button>"
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
    <th>Company</th></tr></thead><tbody id="rows"></tbody></table>
  <div id="none">No record found.</div>
  <div id="footer"></div>
</div>
<div id="project" hidden><div>
  <h3 id="heading">{PLN} B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <select id="task_select" onchange="choose(this.value)"><option selected>-- Select Task --</option>{options}</select>
  <ul><li><strong>Lodged By:</strong> <span>&lt;project lodger&gt;</span></li>
    <li><strong>Client Internal No.:</strong> <span>{internal_no}</span></li>
    <li><strong>Address:</strong> <span>Lot 123 (#45) Sample Lane Sampleville 6000 WA</span></li></ul>
  <div id="task_view" hidden></div>
  <div id="project_tabs">
    <button onclick="show('tasks')">Tasks</button>{documents_button * documents_buttons}<button>Notes</button>
    <button id="create" onclick="document.getElementById('form').hidden = false">Create New Task</button>
  </div>
  <div id="tasks"><table><tbody id="task_rows">{task_rows(tasks)}</tbody></table></div>
  <div id="documents" hidden></div>
</div>{CLOSE}</div>
<div id="form" hidden><div>
  <h3>Create New Task</h3>
  <div><div>Multiple Units</div><input type="checkbox" aria-label="multiple" {multiple}></div>
  <div><div>Creator</div><select><option>Choose...</option><option selected>&lt;project creator&gt;</option><option>Perth Scheduling</option></select></div>
  <div><input type="checkbox" aria-label="- 1.Single Storey Engineering Bundle"> - 1.Single Storey Engineering Bundle</div>
  <div><input type="checkbox" aria-label="- Compaction Test"
    onchange="document.getElementById('sub_form').hidden = !this.checked"> - Compaction Test</div>
  <div id="sub_form" hidden>
    <div><div>Task Client</div><div>Same as Project <button>Select Client</button> <span>close</span></div></div>
    <div><div>Task Name</div><input aria-label="Task Name"></div>
    <div><div>PO Number</div><input></div>
    <div><div>PO Contact</div><select><option selected>Choose...</option><option>&lt;user&gt;</option></select></div>
    <div><div>PO Documents</div><div id="po_docs"><span>Upload <input type="file" onchange="addDoc(this, 'po_docs')"></span></div></div>
    <div><div>Documents</div><div id="docs"><span>Upload <input type="file" onchange="addDoc(this, 'docs')"></span></div></div>
    <div><div>Sale Office</div><select><option>... Use Default Office ...</option><option selected>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Delivery Office</div><select><option selected>Choose...</option><option>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Note</div><textarea></textarea></div>
  </div>
  <button onclick="submitTask()">Submit</button>
</div>{CLOSE}</div>
<div id="hold" hidden></div>
<script>
const FAKE = {data};
const PROJECT_HEADING = '{PLN} B1 Homes Sample Lane, Sampleville WA 6000';
function showProjects() {{
  document.getElementById('sub').hidden = true;
  document.getElementById('projects').hidden = false;
}}
function search(text) {{
  if (text !== '{INTERNAL_NO}') return;
  setTimeout(() => {{
    document.getElementById('none').hidden = true;
    document.getElementById('rows').innerHTML =
      '<tr><td><a href="#" onclick="document.getElementById(\\'project\\').hidden = false; return false">{search_pln}</a></td>'
      + '<td>{INTERNAL_NO}</td><td>Active</td><td>B1 Homes</td></tr>';
    document.getElementById('footer').textContent = 'Page 1 of 1(1 Items)';
  }}, 200);
}}
function addDoc(input, area) {{
  document.getElementById(area).insertAdjacentHTML('beforeend',
    '<table><tbody><tr><td>' + input.files[0].name + '</td><td>close</td></tr></tbody></table>');
}}
function submitTask() {{
  document.body.dataset.submitted = 'yes';
  if (FAKE.formCloses) document.getElementById('form').hidden = true;
  setTimeout(() => {{
    for (const task of FAKE.newTasks) {{
      document.getElementById('task_rows').insertAdjacentHTML('beforeend',
        '<tr><td><div><span>(' + task + ') | Compaction Test</span><div><button>Cancel</button>'
        + '<button onclick="openHold(\\'' + task + '\\')">Hold</button></div></div></td></tr>'
        + '<tr><td>' + FAKE.agent + '</td><td onclick="openTask(\\'' + task + '\\')">'
        + FAKE.rowCreator + '</td><td>New Project</td></tr>');
      const option = document.createElement('option');
      option.textContent = '(' + task + ') [Compaction Test]';
      document.getElementById('task_select').appendChild(option);
    }}
  }}, 300);
}}
function projectView(on) {{
  for (const id of ['project_tabs', 'tasks']) document.getElementById(id).hidden = !on;
  document.getElementById('documents').hidden = true;
  document.getElementById('task_view').hidden = on;
}}
function openTask(clicked) {{
  document.body.dataset.opened = clicked;
  const task = FAKE.opensAs || clicked;
  const d = FAKE.detail;
  document.getElementById('heading').textContent = 'TSK_' + task.slice(4)
    + ' PLN_' + '{PLN}'.slice(4) + ' B1 Homes Sample Lane, Sampleville WA 6000';
  document.getElementById('task_select').value = '(' + task + ') [Compaction Test]';
  const view = document.getElementById('task_view');
  view.innerHTML =
    '<div><div><h3>Active Stage</h3></div><div><button>Complete</button></div></div>'
    + '<div><div><h3>' + task + ' [Compaction Test]</h3></div><div><ul>'
    + '<li><strong>Created:</strong> <span>04/11/2026</span></li>'
    + '<li><strong>Lodged By:</strong> <span>' + d.lodged_by + '</span></li>'
    + '<li><strong>PO Number:</strong> <span>' + d.po_number + '</span></li></ul>'
    + '<div><hr><strong>Notes</strong><span id="notes"></span></div></div></div>'
    + '<div><div><h3>Client</h3></div><div><ul><li><strong>Project Company:</strong> <a href="#">B1 Homes</a></li></ul>'
    + '<hr><ul><li><strong><span>Task Creator:</span></strong> <a href="#">' + d.task_creator + '</a></li></ul></div></div>'
    + '<div><button>Certify Form</button><button>Documents</button><button>Save</button></div>';
  document.getElementById('notes').textContent = d.notes;
  projectView(false);
}}
function choose(value) {{
  if (value !== '-- Select Task --') return;
  document.getElementById('heading').textContent = PROJECT_HEADING;
  projectView(true);
}}
function docSection(task, rows) {{
  const body = rows.length === 0 ? '<div>No Document Found</div>'
    : '<table><thead><tr><th></th><th>Type</th><th>File</th><th>Document</th><th>Creator</th><th></th></tr></thead><tbody>'
      + rows.map(([type, file]) => '<tr><td><input type="checkbox"></td><td>' + type + '</td><td>' + file
        + ' <a href="#">file_download 1 KB</a></td><td>' + type + '</td><td>' + FAKE.agent
        + '</td><td><span title="Delete">close</span></td></tr>').join('')
      + '</tbody></table>';
  return '<div><div><h3>' + task + '</h3><div>Document Actions</div></div>' + body + '</div>';
}}
function show(view) {{
  // Tells the kill-switch test that W2 has ended (its Tasks click).
  if (view === 'tasks') console.log('tasks tab');
  document.getElementById('tasks').hidden = view !== 'tasks';
  // Live (seam 2, 4 Nov 2026): Create New Task shows on the Tasks tab only.
  document.getElementById('create').hidden = view !== 'tasks';
  const docs = document.getElementById('documents');
  docs.hidden = view !== 'documents';
  if (view !== 'documents') return;
  let html = docSection('{PLN}', []);
  for (const option of document.getElementById('task_select').options) {{
    const match = option.textContent.match(/^\\((tsk_\\d+)\\)/);
    if (!match) continue;
    if (match[1] !== FAKE.newTasks[0]) {{
      html += docSection(match[1], [['Purchase Order', FAKE.olderFile]]);
    }} else if (FAKE.documents !== null) {{
      html += docSection(match[1], FAKE.documents);
    }}
  }}
  docs.innerHTML = html;
}}
function box(id, label) {{
  const ticked = FAKE.hold.ticked.includes(id) ? ' checked' : '';
  return '<input type="checkbox" id="' + id + '"' + (label ? ' aria-label="' + label + '"' : '') + ticked + '>';
}}
function openHold(task) {{
  document.body.dataset.held = task;
  const h = FAKE.hold;
  const reminder = h.reminder ? ' checked' : '';
  const related = ['tsk_300001', 'tsk_300002'].map((t, i) =>
    '<tr><td>' + box('related_' + i) + '</td><td>' + t + ' Compaction Test</td><td>Active</td></tr>').join('')
    + '<tr hidden><td>' + box('related_hidden') + '</td><td>tsk_300003 Compaction Test</td><td>Active</td></tr>';
  const block = '<div><div>Related Tasks</div><div><p>There are ' + h.jobs + ' related jobs with the same sales type/ suburb/ estate. Select jobs to hold together.</p>'
    + '<table><thead><tr><th>' + box('select_all') + '</th><th>Task</th><th>Status</th></tr></thead><tbody>' + related + '</tbody></table></div></div>';
  const dialog = document.getElementById('hold');
  dialog.innerHTML = '<div><h3>Hold Task</h3><div>'
    + '<div><button onclick="confirmHold(\\'' + task + '\\')">Hold</button><h3>Hold Task: ' + (h.heading || task) + '</h3></div>'
    + '<div><div>Active task after selected task complete</div><select><option selected>Choose...</option></select></div>'
    + '<div><div>Reminder Email Setting</div><div>'
    + '<div><input type="checkbox" aria-label="Send me a reminder email every days"' + reminder + '> Send me a reminder email every '
    + '<input type="number" value="' + h.days + '"> days (0 days = no email reminders)</div>'
    + '<div>' + box('at_date', 'Send me a reminder email at this date:') + ' Send me a reminder email at this date: <input disabled></div></div></div>'
    + '<div><div>Reset turn around time</div>' + box('reset') + '</div>'
    + '<div><div>Note</div><input aria-label="Note" id="hold_note"></div>'
    + (h.extraHold ? '<div><button>Hold</button></div>' : '')
    + (h.relatedOutside ? '' : block)
    + '</div>' + (h.relatedOutside ? block : '') + '</div>{CLOSE}';
  if (h.noteSuffix) document.getElementById('hold_note').addEventListener('input',
    (event) => {{ if (!event.target.value.endsWith(h.noteSuffix)) event.target.value += h.noteSuffix; }});
  dialog.hidden = false;
}}
function confirmHold(task) {{
  const h = FAKE.hold;
  document.body.dataset.confirmed = (Number(document.body.dataset.confirmed || 0) + 1).toString();
  // Tells the W4 kill-switch test that the hold is confirmed.
  console.log('held');
  const note = document.getElementById('hold_note').value;
  if (!h.closes) return;
  const dialog = document.getElementById('hold');
  dialog.innerHTML = '';
  dialog.hidden = true;
  if (!h.holds) return;
  for (const span of document.querySelectorAll('#task_rows span')) {{
    if (span.textContent !== '(' + task + ') | Compaction Test') continue;
    const header = span.closest('tr');
    for (const button of header.querySelectorAll('button')) {{
      if (button.textContent === 'Hold') button.outerHTML = '<button>Un-Hold</button>';
    }}
    const cells = header.nextElementSibling.querySelectorAll('td');
    cells[cells.length - 1].textContent = h.status === null ? 'On-hold Notes: ' + note : h.status;
  }}
}}
</script>"""


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def serve(browser: Browser, tmp_path: Path) -> Iterator:
    """`serve(**fake)` writes `fake_mysys` to a file, which is base_url, and
    opens a fresh browser context; returns its page and the login."""
    contexts = []

    def open_page(**fake: object) -> tuple[Page, tuple[str, str, str]]:
        home = tmp_path / "mysys.html"
        home.write_text(fake_mysys(**fake), encoding="utf-8")  # type: ignore[arg-type]
        context = browser.new_context()
        contexts.append(context)
        page = context.new_page()
        page.set_default_timeout(2000)
        return page, (home.as_uri(), "fake-user", "fake-password")

    yield open_page
    for context in contexts:
        context.close()


class FakeSearch:
    """`driver.search_note` for the W1 assignee check: the Note with the
    agent. Records how many guard actions had run when it was called."""

    def __init__(self, guard: ActionGuard) -> None:
        self.guard = guard
        self.actions_before: list[int] = []

    def __call__(self, guard, page, base_url, username, password, note_id):
        self.actions_before.append(len(self.guard.history))
        row = NotePoolRow(
            note_id=note_id, subject_note="fake", project="---", assignee=AGENT
        )
        return "panel", driver.NotePoolList(rows=(row,), total=1, pages=1)


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


@pytest.fixture
def search(monkeypatch, guard) -> FakeSearch:
    fake = FakeSearch(guard)
    monkeypatch.setattr(driver, "search_note", fake)
    return fake


def run_book(
    served: tuple[Page, tuple[str, str, str]],
    guard: ActionGuard,
    proceed: object,
    note_id: str = NOTE_ID,
    stop_after: str = "W1",
    config_dir: Path = CONFIG_DIR,
) -> str | None:
    page, login = served
    gate = controls.Controls(
        "test",
        config_dir,
        assignee_check=controls.assignee_check(guard, page, login, AGENT),
    )
    return booker.book(
        proceed,  # type: ignore[arg-type]
        note_id=note_id,
        guard=guard,
        page=page,
        login=login,
        controls=gate,
        agent=AGENT,
        stop_after=stop_after,
    )


def actions(guard: ActionGuard) -> list[str]:
    return [action for action, _ in guard.history]


def test_book_takes_only_a_proceed(serve, guard, search):
    served = serve(tasks=[CANCELLED])
    not_a_proceed = proceed_for_p1().model_dump()

    with pytest.raises(TypeError):
        run_book(served, guard, not_a_proceed)

    assert search.actions_before == []
    assert actions(guard) == []


def test_a_proceed_for_another_note_writes_nothing(serve, guard, search):
    served = serve(tasks=[CANCELLED])

    with pytest.raises(WriteNotStarted):
        run_book(served, guard, proceed_for_p1(), note_id="1002")

    assert search.actions_before == []
    assert actions(guard) == []


def test_w1_checks_the_note_reopens_the_project_and_fills_the_form_without_submitting(
    serve, guard, search
):
    served = serve(tasks=[CANCELLED])
    page = served[0]

    run_book(served, guard, proceed_for_p1())

    # The W1 check first, before any page action.
    assert search.actions_before == [0]
    assert actions(guard) == REOPEN + FILL
    assert page.locator("body").get_attribute("data-submitted") is None
    # The PDF went to PO Documents, from memory; the Documents area has none.
    assert page.locator("#po_docs td").first.inner_text() == FILE
    assert page.locator("#docs table").count() == 0
    form = page.locator("#form")
    assert form.locator("select").nth(0).input_value() == "Perth Scheduling"
    assert form.locator("#sub_form input").nth(1).input_value() == "2600001B/048"
    assert form.locator("textarea").input_value() == CLEAN.note.body


@pytest.mark.parametrize(
    "fake",
    [
        # A task created since step 10: the reopened project has one more.
        {"tasks": [CANCELLED, ("tsk_200002", "New Project")]},
        # The search now matches another project.
        {"tasks": [CANCELLED], "search_pln": "pln_10009"},
        # The reopened project's Client Internal No. fails the match rule.
        {"tasks": [CANCELLED], "internal_no": "2600009B"},
    ],
    ids=["new-task", "other-pln", "other-internal-no"],
)
def test_a_reopened_project_not_as_decided_is_write_not_started(
    serve, guard, search, fake
):
    served = serve(**fake)

    with pytest.raises(WriteNotStarted):
        run_book(served, guard, proceed_for_p1())

    assert "open_create_new_task" not in actions(guard)


def test_a_read_back_mismatch_closes_the_browser_context_and_does_not_submit(
    serve, guard, search
):
    served = serve(tasks=[CANCELLED], multiple="checked")
    page = served[0]

    with pytest.raises(WriteNotStarted):
        run_book(served, guard, proceed_for_p1())

    assert "set_task_note" in actions(guard)
    assert "submit_task" not in actions(guard)
    assert page.is_closed()


def test_a_task_cancelled_at_step_10_and_live_again_is_write_not_started(
    serve, guard, search
):
    # Same task number as step 10, but no longer Cancelled (Undo
    # Cancellation meanwhile): booking now would make a duplicate.
    served = serve(tasks=[(CANCELLED[0], "New Project")])

    with pytest.raises(WriteNotStarted):
        run_book(served, guard, proceed_for_p1())

    assert "open_create_new_task" not in actions(guard)


# W2 (task 4.2): Submit, then the read-back on the task detail screen and the
# project's Documents tab (row 19).

W2 = [
    "submit_task",
    "open_new_task_detail",
    "back_to_project",
    "open_project_documents",
    "open_project_tasks",
]


def test_w2_submits_once_finds_the_new_task_and_reads_it_back(serve, guard, search):
    served = serve(tasks=[CANCELLED])
    page = served[0]

    task_no = run_book(served, guard, proceed_for_p1(), stop_after="W2")

    assert task_no == NEW_TASK
    # Only W1 runs the assignee check (D7): the form never leaves the window.
    assert search.actions_before == [0]
    assert actions(guard) == REOPEN + FILL + W2
    # The detail screen was opened from the new task's own details row.
    assert page.locator("body").get_attribute("data-opened") == NEW_TASK
    # Back on the project's task table, ready for W3.
    assert booking.project_window(page, PLN).locator("#tasks").is_visible()


@pytest.mark.parametrize(
    "fake",
    [
        {"new_tasks": ()},
        # Rows that arrived after step 10's 15 s (decisions, 4 Nov 2026):
        # an older task shows here as a second new one.
        {"new_tasks": (NEW_TASK, "tsk_200003")},
        {"form_closes": False},
        # The detail screen names another task (one with the same values).
        {"opens_as": CANCELLED[0]},
        # The project's Documents tab has no section for the new task.
        {"documents": None},
    ],
    ids=["no-new-task", "two-new-tasks", "form-open", "other-task", "no-section"],
)
def test_after_submit_a_screen_not_as_mapped_is_a_partial_write(
    serve, guard, search, monkeypatch, fake
):
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 2000)
    served = serve(tasks=[CANCELLED], **fake)

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W2")

    assert caught.value.step == "W2"
    assert actions(guard).count("submit_task") == 1


@pytest.mark.parametrize(
    "fake",
    [
        {"row_creator": "Someone Else"},
        {"detail": {"po_number": "2600009B/048"}},
        {"detail": {"lodged_by": "Someone Else"}},
        {"detail": {"notes": "Please find attached another file"}},
        {"detail": {"task_creator": "Someone Else"}},
        # "No Document Found": the PDF is missing.
        {"documents": ()},
        {"documents": (PO_ROW, PO_ROW)},
        {"documents": (("Invoice", FILE),)},
        {"documents": (("Purchase Order", "2600009B_048_1.pdf"),)},
    ],
    ids=[
        "row-task-creator",
        "po-number",
        "lodged-by",
        "notes",
        "task-creator",
        "no-document",
        "two-documents",
        "document-type",
        "document-file",
    ],
)
def test_after_submit_a_wrong_value_is_an_accuracy_breach(
    serve, guard, search, monkeypatch, fake
):
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 2000)
    served = serve(tasks=[CANCELLED], **fake)

    with pytest.raises(AccuracyBreach) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W2")

    assert caught.value.step == "W2"
    assert actions(guard).count("submit_task") == 1


def test_a_guard_refusal_after_submit_keeps_its_type(serve, guard, search):
    # Two visible Documents buttons: the guard refuses the ambiguous target.
    served = serve(tasks=[CANCELLED], documents_buttons=2)

    with pytest.raises(GuardRefusal) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W2")

    assert caught.value.reason == Refusal.TARGET_AMBIGUOUS
    assert caught.value.step == "W2"
    assert actions(guard).count("submit_task") == 1


def test_the_kill_switch_at_w2_closes_the_context_and_submits_nothing(
    serve, guard, monkeypatch, tmp_path
):
    # The switch goes off between W1's check and W2's before_write.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    (config_dir / "test.toml").write_text(toml, "utf-8")
    w1_check = FakeSearch(guard)

    def switch_off_after_the_w1_check(*args):
        found = w1_check(*args)
        off = toml.replace("enabled = true", "enabled = false")
        (config_dir / "test.toml").write_text(off, "utf-8")
        return found

    monkeypatch.setattr(driver, "search_note", switch_off_after_the_w1_check)
    served = serve(tasks=[CANCELLED])

    with pytest.raises(controls.KillSwitch) as caught:
        run_book(
            served, guard, proceed_for_p1(), stop_after="W2", config_dir=config_dir
        )

    assert caught.value.step == "W2"
    assert "submit_task" not in actions(guard)
    assert served[0].is_closed()


# W3 (task 4.3): Hold, every dialog check read before confirming (row 11),
# then the read-back on the task's row (row 12).

W3 = ["open_hold", "set_hold_note", "confirm_hold"]


def confirmed(page: Page) -> int:
    return int(page.locator("body").get_attribute("data-confirmed") or 0)


def test_w3_holds_the_new_task_once_and_reads_it_back(serve, guard, search):
    served = serve(tasks=[CANCELLED])
    page = served[0]

    task_no = run_book(served, guard, proceed_for_p1(), stop_after="W3")

    assert task_no == NEW_TASK
    # No assignee check at W3 (D7), and no checkbox action anywhere.
    assert search.actions_before == [0]
    assert actions(guard) == REOPEN + FILL + W2 + W3
    # Hold was the new task's own, and the dialog's Hold pressed once.
    assert page.locator("body").get_attribute("data-held") == NEW_TASK
    assert confirmed(page) == 1


@pytest.mark.parametrize(
    "hold",
    [
        # The dialog names another task.
        {"heading": CANCELLED[0]},
        {"ticked": ["related_0"]},
        # A related task the table doesn't show would still be held with it.
        {"ticked": ["related_hidden"]},
        {"ticked": ["select_all"]},
        {"ticked": ["reset"]},
        {"ticked": ["at_date"]},
        {"reminder": False},
        {"days": "7"},
        # The Note box doesn't keep the text as typed.
        {"noteSuffix": " X"},
        # More related jobs than rows: paged, or not all loaded yet.
        {"jobs": 60},
        # Related Tasks outside the block the ticked boxes are counted in.
        {"relatedOutside": True},
    ],
    ids=[
        "other-heading",
        "related-ticked",
        "hidden-related-ticked",
        "select-all-ticked",
        "reset-ticked",
        "at-date-ticked",
        "reminder-unticked",
        "reminder-days",
        "note-not-exact",
        "related-rows-missing",
        "related-outside-scope",
    ],
)
def test_a_hold_dialog_not_as_mapped_closes_the_context_and_is_never_confirmed(
    serve, guard, search, monkeypatch, hold
):
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 2000)
    served = serve(tasks=[CANCELLED], hold=hold)
    page = served[0]

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W3")

    assert caught.value.step == "W3"
    assert "confirm_hold" not in actions(guard)
    assert page.is_closed()


@pytest.mark.parametrize(
    "hold",
    [
        {"closes": False},
        # Nothing changed: the row still shows Hold.
        {"holds": False},
        {"status": "On-hold"},
        {"status": "New Project"},
    ],
    ids=[
        "dialog-stays-open",
        "no-un-hold",
        "status-without-note",
        "status-not-on-hold",
    ],
)
def test_after_the_hold_confirm_a_read_back_not_as_mapped_is_a_partial_write(
    serve, guard, search, monkeypatch, hold
):
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 2000)
    served = serve(tasks=[CANCELLED], hold=hold)
    page = served[0]

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W3")

    assert caught.value.step == "W3"
    # Made once, never retried.
    assert actions(guard).count("confirm_hold") == 1
    assert page.is_closed()


def test_the_kill_switch_at_w3_is_a_partial_write_and_nothing_is_held(
    serve, guard, search, tmp_path
):
    # The switch goes off as W2 ends (its Tasks click), before W3's check.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    (config_dir / "test.toml").write_text(toml, "utf-8")
    served = serve(tasks=[CANCELLED])
    page = served[0]

    def switch_off(message: ConsoleMessage) -> None:
        if message.text == "tasks tab":
            off = toml.replace("enabled = true", "enabled = false")
            (config_dir / "test.toml").write_text(off, "utf-8")

    page.on("console", switch_off)

    with pytest.raises(PartialWrite) as caught:
        run_book(
            served, guard, proceed_for_p1(), stop_after="W3", config_dir=config_dir
        )

    assert caught.value.step == "W3"
    assert actions(guard)[-1] == "open_project_tasks"
    assert "open_hold" not in actions(guard)
    assert page.is_closed()


def test_a_guard_refusal_at_w3_keeps_its_type_and_closes_the_context(
    serve, guard, search
):
    # A second Hold button in the dialog: the confirm is ambiguous.
    served = serve(tasks=[CANCELLED], hold={"extraHold": True})
    page = served[0]

    with pytest.raises(GuardRefusal) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W3")

    assert caught.value.reason == Refusal.TARGET_AMBIGUOUS
    assert caught.value.step == "W3"
    # Refused, so never pressed.
    assert guard.history[-1] == ("confirm_hold", Refusal.TARGET_AMBIGUOUS)
    assert ("confirm_hold", "done") not in guard.history
    assert page.is_closed()


# W4 and W5 (task 4.4): back to the Note window (row 25), Link to Project
# through Choose Project (row 20), then Solved (row 14).

W4 = [
    "open_note",
    "untick_send_email_notification",
    "link_to_project",
    "link_search_project",
    "submit_link_search",
    "link_select_project",
]
W5 = ["mark_solved"]
PERSON = "Fake Person"
# Row 20: the one result row's Site Address. A "... Close" street: the row's
# own name would trip the denylist, so only the pln cell can be clicked.
SITE = "1 Sample Close Sampleville"
# The Note window as reopened (rows 02, 13, 14, 20), changed by `note`:
# `results` is the pln cell of each Choose Project result row; `linksTo` the
# project button the select shows; `reticks` ticks Send Email Notification
# again when the search runs; `extraLink` / `extraSolved` add a second Link
# to Project / Solved button; after Solved: `solvedStatus`, `solvedLog` (a
# new "Status changed" line) and `solvedDisables` (Solved off, Pending on).
NOTE_WINDOW: dict[str, object] = {
    "results": [PLN],
    "linksTo": PLN,
    "statusAfterLink": f"Pending by {AGENT}",
    "reticks": False,
    "extraLink": False,
    "extraSolved": False,
    "pickerOpens": True,
    "solvedStatus": f"Solved by {AGENT}",
    "solvedLog": True,
    "solvedDisables": True,
}


def pool_row(note_id: str, assignee: str, project: str = "---") -> NotePoolRow:
    return NotePoolRow(
        note_id=note_id, subject_note="fake", project=project, assignee=assignee
    )


def note_pool_page(
    rows: tuple[NotePoolRow, ...], status_filter: str, note: dict[str, object]
) -> str:
    """base_url reloaded (row 25): the Note Pool with the Note ID searched,
    listing `rows`, and the Note window behind the Note's ID cell, opened
    fresh (Send Email Notification ticked, row 02)."""
    n = {**NOTE_WINDOW, **note}
    listed = "".join(
        f"<tr><td onclick=\"document.getElementById('note').hidden = false\">{row.note_id}</td>"
        f"<td>{row.subject_note}</td><td>{row.project}</td><td>{row.assignee}</td></tr>"
        for row in rows
    )
    status = "".join(
        f"<option{' selected' if s == status_filter else ''}>{s}</option>"
        for s in ("Pending", "Solved", "Discard")
    )
    footer = (
        f"<div>Page 1 of 1({len(rows)} Items)</div>"
        if rows
        else "<div>No record could be found.</div>"
    )
    extra_link = "<button>Link to Project</button>" if n["extraLink"] else ""
    extra_solved = "<div><button>Solved</button></div>" if n["extraSolved"] else ""
    return f"""
<ul><li><span>Project</span><ul hidden><li>Note Pool</li><li>Projects</li></ul></li></ul>
<div>
  <button>New Note</button><input aria-label="Search/filter" value="{NOTE_ID}">
  <select name="filter_allocation_pool_id"><option selected>All Pools</option><option>Agent Pool</option></select>
  <select name="filter_status">{status}</select>
  <select name="filter_lock_status"><option selected>All</option><option>Locked</option></select>
  <button>Refresh</button>
  <table><thead><tr><th>ID</th><th>Subject/Note</th><th>Project</th><th>Assignee</th></tr></thead>
    <tbody>{listed}</tbody></table>
  {footer}
</div>
<div id="note" hidden><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div>
    <h3>[B1 Homes] Order 2600001B/048</h3>
    <div><strong>Assignee:</strong> <span>{AGENT}</span> <button>Unlink</button></div>
    <div role="group" aria-label="Status buttons">
      <button id="pending" disabled>Pending</button><button id="solved" onclick="solve()">Solved</button><button>Discard</button>
    </div>{extra_solved}
    <select><option>--Select User--</option><option selected>{AGENT}</option></select>
    <select><option selected>--Select Pool--</option><option>Agent Pool</option></select>
    <button>Assign</button>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"> Send Email Notification</span>
    <span id="link"><button onclick="openPicker()">Link to Project</button>{extra_link}</span>
    <ul><li><strong>Status:</strong> <span id="status">Pending by {PERSON}</span></li></ul>
    <div><h4>Logs</h4><ul id="logs">
      <li><em>04 Nov 2026 09:00 User Assigned: (By {AGENT})</em> From <strong>Agent Pool</strong> to <strong>{AGENT}</strong><hr></li>
    </ul></div>
  </div>
</div>{CLOSE}</div>
<div id="picker"></div>
<script>
const NOTE = {json.dumps(n)};
function count(name) {{
  document.body.dataset[name] = (Number(document.body.dataset[name] || 0) + 1).toString();
}}
function emailed() {{
  if (document.getElementById('email').checked) document.body.dataset.emailed = 'yes';
}}
function openPicker() {{
  if (!NOTE.pickerOpens) return;
  setTimeout(() => {{
    document.getElementById('picker').innerHTML = '<div><div><h3>Choose Project</h3>'
      + '<input aria-label="Search/filter" onkeydown="linkKey(event, this.value)">'
      + '<input aria-label="After..."><input aria-label="Before...">'
      + '<table><tbody id="results"></tbody></table></div>{CLOSE}</div>';
  }}, 300);
}}
function linkKey(event, text) {{
  if (event.key !== 'Enter') return;
  if (NOTE.reticks) document.getElementById('email').checked = true;
  if (text !== '{PLN}') return;
  setTimeout(() => {{
    document.getElementById('results').innerHTML = NOTE.results.map((pln) =>
      '<tr><td onclick="pick()">' + pln + '</td><td>2600001B</td><td>01/11/2026</td>'
      + '<td>&lt;project creator&gt;</td><td></td><td>B1 Homes</td><td>{SITE}</td><td>6000</td></tr>').join('');
  }}, 300);
}}
function pick() {{
  count('picked');
  emailed();
  // Tells the W5 kill-switch test that the Note is linked.
  console.log('linked');
  document.getElementById('picker').innerHTML = '';
  setTimeout(() => {{
    document.getElementById('link').innerHTML = '<button>' + NOTE.linksTo
      + '</button><button>Change Project</button><button>Unlink</button>';
    document.getElementById('status').textContent = NOTE.statusAfterLink;
  }}, 300);
}}
function solve() {{
  count('solved');
  emailed();
  setTimeout(() => {{
    document.getElementById('status').textContent = NOTE.solvedStatus;
    if (NOTE.solvedLog) {{
      const li = document.createElement('li');
      li.innerHTML = '<em>04 Nov 2026 09:05 Status changed: (By {AGENT})</em> From <strong>Pending</strong> to <strong>Solved</strong><hr>';
      document.getElementById('logs').prepend(li);
    }}
    if (NOTE.solvedDisables) {{
      document.getElementById('solved').disabled = true;
      document.getElementById('pending').disabled = false;
    }}
  }}, 300);
}}
</script>"""


class FakeNotePool:
    """`driver.search_note` through W5. The first call is W1's assignee
    check, as FakeSearch. Every later call (W4's check, W4's way back to the
    Note, W5's read-back) reloads base_url, as live: the page becomes
    `note_pool_page`, the Note listed with `w4_assignee` until Solved was
    pressed, then `after_solved`. Before each reload it keeps what the page
    recorded (`seen`: picked, solved, emailed). Records how many guard
    actions had run at each call."""

    def __init__(
        self,
        guard: ActionGuard,
        *,
        w4_assignee: str = AGENT,
        # A Note whose ID only contains the Note ID: not the Note.
        after_solved: tuple[NotePoolRow, ...] = (pool_row(f"{NOTE_ID}2", PERSON),),
        status_filter: str = "Pending",
        note: dict[str, object] | None = None,
    ) -> None:
        self.guard = guard
        self.w4_assignee = w4_assignee
        self.after_solved = after_solved
        self.status_filter = status_filter
        self.note = note or {}
        self.actions_before: list[int] = []
        self.seen: dict[str, str] = {}

    def __call__(self, guard, page, base_url, username, password, note_id):
        self.actions_before.append(len(self.guard.history))
        if len(self.actions_before) == 1:
            rows = (pool_row(note_id, AGENT),)
            return "panel", driver.NotePoolList(rows=rows, total=1, pages=1)
        for name in ("picked", "solved", "emailed"):
            value = page.locator("body").get_attribute(f"data-{name}")
            if value is not None:
                self.seen[name] = value
        if "solved" in self.seen:
            rows = self.after_solved
        else:
            rows = (pool_row(note_id, self.w4_assignee),)
        page.set_content(note_pool_page(rows, self.status_filter, self.note))
        listing = driver.NotePoolList(rows=rows, total=len(rows), pages=1)
        return driver.note_pool_panel(page), listing


@pytest.fixture
def short_waits(monkeypatch) -> None:
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 2000)
    monkeypatch.setattr(booking, "LINK_TIMEOUT_MS", 2000)


def through_w5(monkeypatch, guard: ActionGuard, **fake: object) -> FakeNotePool:
    pool = FakeNotePool(guard, **fake)  # type: ignore[arg-type]
    monkeypatch.setattr(driver, "search_note", pool)
    return pool


BEFORE_W4 = REOPEN + FILL + W2 + W3


def test_w4_w5_link_the_pln_cell_mark_solved_and_read_back(serve, guard, monkeypatch):
    pool = through_w5(monkeypatch, guard)
    served = serve(tasks=[CANCELLED])

    task_no = run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert task_no == NEW_TASK
    assert actions(guard) == BEFORE_W4 + W4 + W5
    # W1's check; W4's check before any W4 action, then the way back to the
    # Note (row 25); no check at W5 (D7), then W5's read-back after Solved.
    w4 = len(BEFORE_W4)
    assert pool.actions_before == [0, w4, w4, w4 + len(W4) + len(W5)]
    # The cell, once (the row would have been refused); Solved once; no
    # notification sent by either.
    assert pool.seen == {"picked": "1", "solved": "1"}


@pytest.mark.parametrize(
    "fake",
    [
        # Someone took the Note during W1-W3 (D7): caught at the W4 check.
        {"w4_assignee": PERSON},
        # No cell named exactly the pln (a longer pln only contains it).
        {"note": {"results": ["pln_100011"]}},
        {"note": {"results": [PLN, PLN]}},
        # The box ticks itself again: read back just before the select.
        {"note": {"reticks": True}},
    ],
    ids=["note-taken", "no-pln-cell", "two-pln-cells", "email-ticked-again"],
)
def test_before_the_link_select_a_screen_not_as_mapped_links_nothing(
    serve, guard, monkeypatch, short_waits, fake
):
    through_w5(monkeypatch, guard, **fake)
    served = serve(tasks=[CANCELLED])

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.step == "W4"
    assert "link_select_project" not in actions(guard)
    assert served[0].is_closed()


def test_a_choose_project_that_never_opens_saves_no_page_snapshot(
    serve, guard, monkeypatch, short_waits, tmp_path
):
    # The booker never writes page text to disk (decisions, 3 Nov 2026, M4
    # gate): the demo's snapshot on a missing Choose Project is demo only.
    snapshots = tmp_path / "captures"
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", snapshots)
    through_w5(monkeypatch, guard, note={"pickerOpens": False})
    served = serve(tasks=[CANCELLED])

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.step == "W4"
    assert actions(guard)[-1] == "link_to_project"
    assert not snapshots.exists()
    assert served[0].is_closed()


def test_after_the_link_select_a_status_not_pending_is_a_partial_write(
    serve, guard, monkeypatch, short_waits
):
    through_w5(monkeypatch, guard, note={"statusAfterLink": f"Solved by {PERSON}"})
    served = serve(tasks=[CANCELLED])

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.step == "W4"
    assert actions(guard).count("link_select_project") == 1
    assert "mark_solved" not in actions(guard)
    assert served[0].is_closed()


def test_a_project_button_with_another_pln_is_an_accuracy_breach(
    serve, guard, monkeypatch, short_waits
):
    through_w5(monkeypatch, guard, note={"linksTo": "pln_10009"})
    served = serve(tasks=[CANCELLED])

    with pytest.raises(AccuracyBreach) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.step == "W4"
    assert "mark_solved" not in actions(guard)
    assert served[0].is_closed()


@pytest.mark.parametrize(
    "fake",
    [
        {"note": {"solvedStatus": f"Solved by {PERSON}"}},
        {"note": {"solvedLog": False}},
        {"note": {"solvedDisables": False}},
        # Still listed under Pending: the row's ID equals the Note ID.
        {"after_solved": (pool_row(NOTE_ID, AGENT, PLN),)},
        # Searched under another Status: an empty list proves nothing.
        {"status_filter": "Solved"},
    ],
    ids=[
        "solved-by-someone-else",
        "no-log-line",
        "solved-still-enabled",
        "still-pending",
        "status-filter-not-pending",
    ],
)
def test_after_solved_a_read_back_not_as_mapped_is_a_partial_write(
    serve, guard, monkeypatch, short_waits, fake
):
    through_w5(monkeypatch, guard, **fake)
    served = serve(tasks=[CANCELLED])

    with pytest.raises(PartialWrite) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.step == "W5"
    # Made once, never retried.
    assert actions(guard).count("mark_solved") == 1
    assert served[0].is_closed()


@pytest.mark.parametrize(
    ("message", "step", "last", "never"),
    [
        ("held", "W4", "confirm_hold", "open_note"),
        ("linked", "W5", "link_select_project", "mark_solved"),
    ],
)
def test_the_kill_switch_at_w4_or_w5_is_a_partial_write(
    serve, guard, monkeypatch, tmp_path, message, step, last, never
):
    # The switch goes off once the previous write is made, before the step's
    # before_write; W5's before_write still reads it, with no assignee check.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    (config_dir / "test.toml").write_text(toml, "utf-8")
    pool = through_w5(monkeypatch, guard)
    served = serve(tasks=[CANCELLED])
    page = served[0]

    def switch_off(console: ConsoleMessage) -> None:
        if console.text == message:
            off = toml.replace("enabled = true", "enabled = false")
            (config_dir / "test.toml").write_text(off, "utf-8")

    page.on("console", switch_off)

    with pytest.raises(PartialWrite) as caught:
        run_book(
            served, guard, proceed_for_p1(), stop_after="W5", config_dir=config_dir
        )

    assert caught.value.step == step
    assert actions(guard)[-1] == last
    assert never not in actions(guard)
    # The switch is read before W4's assignee check.
    assert len(pool.actions_before) == (1 if step == "W4" else 3)
    assert page.is_closed()


@pytest.mark.parametrize(
    ("note", "action", "step"),
    [
        ({"extraLink": True}, "link_to_project", "W4"),
        ({"extraSolved": True}, "mark_solved", "W5"),
    ],
)
def test_a_guard_refusal_at_w4_or_w5_keeps_its_type_and_closes_the_context(
    serve, guard, monkeypatch, short_waits, note, action, step
):
    # A second button of the same name: the click is ambiguous.
    through_w5(monkeypatch, guard, note=note)
    served = serve(tasks=[CANCELLED])

    with pytest.raises(GuardRefusal) as caught:
        run_book(served, guard, proceed_for_p1(), stop_after="W5")

    assert caught.value.reason == Refusal.TARGET_AMBIGUOUS
    assert caught.value.step == step
    # Refused, so never pressed.
    assert guard.history[-1] == (action, Refusal.TARGET_AMBIGUOUS)
    assert served[0].is_closed()
