# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""The booker's W1 (task 4.1), offline: Create New Task filled and read back,
never submitted.

Headless Chromium on a fake MySys, a local HTML file that is base_url (no
site is touched): the Project menu, the Projects panel (Enter runs the search), the
project window and the Create New Task form, as mapped in docs/screen-map.md
rows 06-09, 24 and 26. The assignee check runs for real inside
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
- 4.1 never presses Submit.
"""

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent.b1 import booker
from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import decide
from po_agent.b1.models import CompactionTask, NotePoolRow, Proceed
from po_agent.core import controls
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import WriteNotStarted
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

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


def task_rows(tasks: list[tuple[str, str]]) -> str:
    return "".join(
        f"<tr><td><div><span>({task}) | Compaction Test</span><button>Undo Cancellation</button></div></td></tr>"
        f"<tr><td>{AGENT}</td><td>Perth Scheduling</td><td>{status}</td></tr>"
        for task, status in tasks
    )


def fake_mysys(
    *,
    tasks: list[tuple[str, str]],
    search_pln: str = PLN,
    internal_no: str = INTERNAL_NO,
    multiple: str = "",
) -> str:
    """base_url after login: the Project menu, the Projects panel (hidden
    until Projects is chosen), the project window and Create New Task."""
    options = "".join(
        f"<option>({task}) [Compaction Test]</option>" for task, _ in tasks
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
    <th>Company</th></tr></thead><tbody id="rows"></tbody></table>
  <div id="none">No record found.</div>
  <div id="footer"></div>
</div>
<div id="project" hidden><div>
  <h3>{PLN} B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <select><option selected>-- Select Task --</option>{options}</select>
  <ul><li><strong>Client Internal No.:</strong> <span>{internal_no}</span></li>
    <li><strong>Address:</strong> <span>Lot 123 (#45) Sample Lane Sampleville 6000 WA</span></li></ul>
  <button onclick="document.getElementById('form').hidden = false">Create New Task</button>
  <table><tbody>{task_rows(tasks)}</tbody></table>
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
  <button onclick="document.body.dataset.submitted = 'yes'">Submit</button>
</div>{CLOSE}</div>
<script>
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
) -> None:
    page, login = served
    gate = controls.Controls(
        "test",
        CONFIG_DIR,
        assignee_check=controls.assignee_check(guard, page, login, AGENT),
    )
    booker.book(
        proceed,  # type: ignore[arg-type]
        note_id=note_id,
        guard=guard,
        page=page,
        login=login,
        controls=gate,
        stop_after="W1",
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
