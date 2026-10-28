# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Tests for mysys/booking.py: the demo's Note, task and Hold screens.

Headless Chromium on local fakes of the test site's windows (page.set_content),
offline: no site is touched. The fakes follow the 16 Oct captures as written
up in docs/screen-map.md rows 02-04, 08-14 and 15b: each window holds its
heading and its own Close control; the Note body is a <pre> and the file
name beside the link a <span> (as on the site, 27 Oct). Values are fake. Tests never act on the
page themselves (guard_check.py): a click shows up through inline JS.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent.core.errors import (
    GuardRefusal,
    PartialWrite,
    UnexpectedScreen,
    WriteNotStarted,
)
from po_agent.mysys import booking
from po_agent.mysys.guard import ActionGuard

AGENT = "Agent 1 (MySys Only)"
POOL = "Agent Pool"
NOTE_ID = "300001"
FILE = "2600001B_048_1.pdf"
BODY = f"Please find attached Purchase Order / Quotation file {FILE}"
CLOSE = '<div><span title="Close">close</span></div>'
PDF = b"%PDF-1.4 fake"


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


def actions(guard: ActionGuard) -> list[str]:
    return [action for action, _ in guard.history]


def note_page(
    *,
    title: str = f"[B1 Homes] Order 2600001B/048 {BODY}",
    assignee: str = POOL,
    links: int = 1,
    assign_works: bool = True,
) -> str:
    link = f'<a href="index.php?option=com_cweb&download=1&user_note_id=95&file_name={FILE}">Download document</a>'
    works = "true" if assign_works else "false"
    return f"""
<div><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div>
    <h3>{title}</h3>
    <div><strong>Assignee:</strong> <span id="assignee">{assignee}</span> <button>Unlink</button></div>
    <div role="group" aria-label="Status buttons">
      <button disabled id="pending">Pending</button><button id="solved" onclick="solve()">Solved</button><button>Discard</button>
    </div>
    <select id="user"><option>--Select User--</option><option selected>{AGENT}</option><option>Fake Person</option></select>
    <select id="pool"><option selected>--Select Pool--</option><option>{POOL}</option></select>
    <button onclick="assign()">Assign</button>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"> Send Email Notification</span>
    <button>Link to Project</button>
    <ul><li><strong>Status:</strong> <span id="status">Pending</span></li></ul>
    <table><tbody><tr><td><span>{FILE}</span></td><td>{link * links}</td></tr></tbody></table>
    <pre>{BODY}</pre>
  </div>
</div>{CLOSE}</div>
<script>
function emailed() {{ if (document.getElementById('email').checked) document.body.dataset.emailed = 'yes'; }}
function assign() {{
  emailed();
  if (!{works}) return;
  const user = document.getElementById('user'), pool = document.getElementById('pool');
  const who = user.value !== '--Select User--' ? user.value : pool.value;
  document.getElementById('assignee').textContent = who;
  user.selectedIndex = 0; pool.selectedIndex = 0;
}}
function solve() {{
  emailed();
  document.getElementById('status').textContent = 'Solved by {AGENT}';
  document.getElementById('solved').disabled = true;
  document.getElementById('pending').disabled = false;
}}
</script>"""


# Note window (rows 02-04, 14, 15b)


def test_note_window_is_found_by_its_heading(page):
    page.set_content(note_page())
    window = booking.note_window(page, NOTE_ID)
    assert window.count() == 1
    assert booking.read_assignee(window) == POOL
    assert booking.read_status(window) == "Pending"
    assert booking.has_link_to_project(window)


def test_take_note_unticks_email_and_reads_back_the_agent(page, guard):
    page.set_content(note_page())
    window = booking.note_window(page, NOTE_ID)
    booking.take_note(guard, window, AGENT)
    assert booking.read_assignee(window) == AGENT
    assert page.locator("body").get_attribute("data-emailed") is None
    assert actions(guard) == [
        "untick_send_email_notification",
        "select_note_user",
        "assign_note",
    ]


def test_take_note_that_does_not_read_back_stops(page, guard):
    page.set_content(note_page(assign_works=False))
    with pytest.raises(UnexpectedScreen):
        booking.take_note(guard, booking.note_window(page, NOTE_ID), AGENT)


def test_return_note_is_one_assign_to_the_pool(page, guard):
    page.set_content(note_page(assignee=AGENT))
    window = booking.note_window(page, NOTE_ID)
    booking.return_note(guard, window, POOL)
    assert booking.read_assignee(window) == POOL
    assert page.locator("body").get_attribute("data-emailed") is None
    assert actions(guard).count("assign_note") == 1


def test_download_links_are_read_from_the_note_window(page):
    page.set_content(note_page(links=2))
    hrefs = booking.download_hrefs(booking.note_window(page, NOTE_ID))
    assert len(hrefs) == 2 and all(h.endswith(FILE) for h in hrefs)


def test_note_body_is_the_body_line_not_a_title_with_the_same_text(page):
    page.set_content(note_page(title=BODY))
    assert booking.note_body(booking.note_window(page, NOTE_ID), FILE) == BODY


def test_mark_solved_unticks_email_and_reads_back(page, guard):
    page.set_content(note_page(assignee=AGENT))
    window = booking.note_window(page, NOTE_ID)
    booking.mark_solved(guard, window, AGENT)
    assert booking.read_status(window) == f"Solved by {AGENT}"
    assert page.locator("body").get_attribute("data-emailed") is None


# Create New Task (rows 08-09)


def task_form_page(*, multiple: str = "") -> str:
    return f"""
<div><div>
  <h3>Create New Task</h3>
  <div><div>Multiple Units</div><input type="checkbox" aria-label="multiple" {multiple}></div>
  <div><div>Creator</div><select><option>Choose...</option><option selected>&lt;project creator&gt;</option><option>Perth Scheduling</option></select></div>
  <div><input type="checkbox" aria-label="- 1.Single Storey Engineering Bundle"> - 1.Single Storey Engineering Bundle</div>
  <div>
    <div><input type="checkbox" aria-label="- Compaction Test"> - Compaction Test</div>
    <div><div>Task Client</div><div>Same as Project <button>Select Client</button> <span>close</span></div></div>
    <div><div>Task Name</div><input aria-label="Task Name"></div>
    <div><div>PO Number</div><input></div>
    <div><div>PO Contact</div><select><option selected>Choose...</option><option>&lt;user&gt;</option></select></div>
    <div><div>PO Documents</div><div><span>Upload <input type="file" onchange="addDoc(this, 'po_rows')"></span>
      <table><tbody id="po_rows"></tbody></table></div></div>
    <div><div>Documents</div><div><span>Upload <input type="file" onchange="addDoc(this, 'doc_rows')"></span>
      <table><tbody id="doc_rows"></tbody></table></div></div>
    <div><div>Sale Office</div><select><option>... Use Default Office ...</option><option selected>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Delivery Office</div><select><option selected>Choose...</option><option>Prompt Engineering Pty Ltd</option></select></div>
    <div><div>Note</div><textarea></textarea></div>
  </div>
  <button onclick="document.body.dataset.submitted='yes'">Submit</button>
</div>{CLOSE}</div>
<script>
function addDoc(input, rows) {{
  document.getElementById(rows).innerHTML += '<tr><td>' + input.files[0].name + '</td><td>close</td></tr>';
}}
</script>"""


def test_task_form_is_filled_and_read_back(page, guard):
    page.set_content(task_form_page())
    form = booking.task_form(page)
    booking.fill_task_form(guard, form, "2600001B/048", BODY, FILE, PDF)
    assert page.locator("body").get_attribute("data-submitted") is None
    assert "upload_document" in actions(guard)
    booking.submit_task(guard, form)
    assert page.locator("body").get_attribute("data-submitted") == "yes"


def test_task_form_with_another_box_ticked_does_not_submit(page, guard):
    page.set_content(task_form_page(multiple="checked"))
    with pytest.raises(WriteNotStarted):
        booking.fill_task_form(
            guard, booking.task_form(page), "2600001B/048", BODY, FILE, PDF
        )
    assert "submit_task" not in actions(guard)


# Project window and Hold (rows 07, 10-12)


def project_page(*, related: str = "") -> str:
    return f"""
<div><div>
  <h3>pln_10001 B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <ul><li><strong>Client Internal No.:</strong> <span>2600001B</span></li></ul>
  <button>Create New Task</button>
  <table><tbody>
    <tr><td><div><span>(tsk_200001) | Compaction Test</span><button>Undo Cancellation</button></div></td></tr>
    <tr><td>{AGENT}</td><td>Perth Scheduling</td><td>Cancelled</td></tr>
    <tr><td><div><span>(tsk_200002) | Compaction Test</span><div><button>Cancel</button><button id="hold_btn" onclick="openHold()">Hold</button></div></div></td></tr>
    <tr><td>{AGENT}</td><td>Perth Scheduling</td><td id="status">New Project</td></tr>
  </tbody></table>
</div>{CLOSE}</div>
<div id="hold" hidden><div>
  <h3>Hold Task</h3>
  <div>
    <div><button onclick="confirmHold()">Hold</button><h3>Hold Task: tsk_200002</h3></div>
    <div><div>Reminder Email Setting</div>
      <input type="checkbox" checked aria-label="Send me a reminder email every days"> Send me a reminder email every <input type="number" value="0"> days
      <input type="checkbox" aria-label="Send me a reminder email at this date:"> Send me a reminder email at this date:</div>
    <div><div>Reset turn around time</div><input type="checkbox" aria-label="reset"></div>
    <div><div>Note</div><input aria-label="Note"></div>
    <div><div>Related Tasks</div><table><tbody><tr><td><input type="checkbox" aria-label="related" {related}></td><td>tsk_100001 Compaction Test</td></tr></tbody></table></div>
  </div>
</div>{CLOSE}</div>
<script>
function openHold() {{ document.getElementById('hold').hidden = false; }}
function confirmHold() {{
  document.getElementById('hold').hidden = true;
  document.getElementById('status').textContent = 'On-hold Notes: ' + document.querySelector('[aria-label=Note]').value;
  document.getElementById('hold_btn').textContent = 'Un-Hold';
}}
</script>"""


def test_project_window_reads_internal_no_and_tasks(page):
    page.set_content(project_page())
    window = booking.project_window(page, "pln_10001")
    assert booking.client_internal_no(window) == "2600001B"
    rows = booking.task_rows(window)
    assert rows[0][0].startswith("(tsk_200001) | Compaction Test")
    assert rows[3][-1] == "New Project"


def test_hold_fills_the_note_and_confirms_with_the_dialogs_own_button(page, guard):
    page.set_content(project_page())
    project = booking.project_window(page, "pln_10001")
    dialog = booking.open_hold(guard, page, project, "tsk_200002")
    booking.fill_hold(guard, dialog)
    booking.confirm_hold(guard, page, dialog)
    assert booking.task_rows(project)[3][-1] == "On-hold Notes: ON HOLD UNTIL CALL UP"
    booking.check_on_hold(project, "tsk_200002")


def test_hold_with_a_related_task_ticked_does_not_confirm(page, guard):
    page.set_content(project_page(related="checked"))
    project = booking.project_window(page, "pln_10001")
    dialog = booking.open_hold(guard, page, project, "tsk_200002")
    with pytest.raises(PartialWrite):
        booking.fill_hold(guard, dialog)
    assert "confirm_hold" not in actions(guard)


def test_task_not_on_hold_is_a_partial_write(page):
    page.set_content(project_page())
    with pytest.raises(PartialWrite):
        booking.check_on_hold(booking.project_window(page, "pln_10001"), "tsk_200002")


def test_the_guard_still_refuses_a_hold_dialog_checkbox(page, guard):
    page.set_content(project_page())
    project = booking.project_window(page, "pln_10001")
    dialog = booking.open_hold(guard, page, project, "tsk_200002")
    box = dialog.get_by_role("checkbox", name="Send me a reminder email every days")
    with pytest.raises(GuardRefusal):
        guard.act("untick_send_email_notification", dialog, box)


# Live, 28 Oct 2026: "label not found once" right after the project window
# opened (S5) and right after Assign (S2). The labels render after the window
# shows, Assign re-renders the Note window, and other windows can be open.

LATE = 400  # ms


def two_windows(*, assign_rerenders: bool = False) -> str:
    rerender = "true" if assign_rerenders else "false"
    return f"""
<div><div>
  <h3>pln_10001 B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <ul id="details"></ul>
  <button>Create New Task</button>
</div>{CLOSE}</div>
<div><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div id="note_body">
    <div id="who"></div>
    <div role="group" aria-label="Status buttons"><button disabled>Pending</button><button>Solved</button></div>
    <select id="user"><option>--Select User--</option><option selected>{AGENT}</option></select>
    <select id="pool"><option selected>--Select Pool--</option><option>{POOL}</option></select>
    <button onclick="assign()">Assign</button>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"> Send Email Notification</span>
  </div>
</div>{CLOSE}</div>
<script>
function showWho(name) {{
  document.getElementById('who').innerHTML =
    '<strong>Assignee:</strong> ' + name + ' <button>Unlink</button>';
}}
setTimeout(() => {{
  document.getElementById('details').innerHTML =
    '<li><strong>Client Internal No.:</strong> <span>2600001B</span></li>';
  showWho('{POOL}');
}}, {LATE});
function assign() {{
  const user = document.getElementById('user');
  const who = user.value;
  user.selectedIndex = 0;
  if ({rerender}) {{
    document.getElementById('who').innerHTML = '';
    setTimeout(() => showWho(who), {LATE});
  }} else {{
    showWho(who);
  }}
}}
</script>"""


def test_client_internal_no_waits_for_the_details_to_render(page):
    page.set_content(two_windows())
    project = booking.project_window(page, "pln_10001")
    assert booking.client_internal_no(project) == "2600001B"


def test_assignee_waits_for_the_note_window_to_render(page):
    page.set_content(two_windows())
    assert booking.read_assignee(booking.note_window(page, NOTE_ID)) == POOL


def test_take_note_reads_back_after_assign_re_renders_the_window(page, guard):
    page.set_content(two_windows(assign_rerenders=True))
    window = booking.note_window(page, NOTE_ID)
    booking.read_assignee(window)  # rendered before the take, as live
    booking.take_note(guard, window, AGENT)
    assert booking.read_assignee(window) == AGENT


# Live S5, 28 Oct 2026 (laptop snapshot): one visible "Client Internal No.:"
# between the window heading and Create New Task, still "not found once".
# The label's spaces may be non-breaking: the snapshot shows plain spaces.


def project_page_as_live(space: str) -> str:
    label = space.join(["Client", "Internal", "No.:"])
    return f"""
<div><div>
  <h3>pln_10001 B1 Homes Lot 123 (#45) Sample Lane Sampleville 6000 WA</h3>
  <a href="#">pln_10001</a>
  <select aria-label="-- Select Task --"><option selected>-- Select Task --</option>
    <option>(tsk_200001) [Compaction Test]</option></select>
  <h3>New Project</h3>
  <div><h3>pln_10001</h3>
    <ul>
      <li><strong>Lodged{space}By:</strong> {AGENT}</li>
      <li><strong>{label}</strong> 2600001B</li>
    </ul>
    <ul hidden><li><strong>{label}</strong> 2600009B</li></ul>
  </div>
  <button>Create New Task</button>
  <table><tbody></tbody></table>
</div>{CLOSE}</div>"""


@pytest.mark.parametrize("space", [" ", "&nbsp;", " \n  "])
def test_client_internal_no_reads_whatever_the_spaces_in_its_label(page, space):
    page.set_content(project_page_as_live(space))
    project = booking.project_window(page, "pln_10001")
    assert booking.client_internal_no(project) == "2600001B"


# Live S8, 28 Oct 2026: Link to Project opens a floating window "Choose
# Project" holding textboxes "Search/filter", "After..." and "Before..." and
# no results until a search runs (here: when focus leaves the box, as in the
# Note Pool). The Note Pool panel's own "Search/filter" is on the page too.
# The Note's Status reads "Pending by <agent>" once it is assigned.


def link_page() -> str:
    return f"""
<div><input aria-label="Search/filter"><button>New Note</button></div>
<div><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div>
    <div><strong>Assignee:</strong> {AGENT} <button>Unlink</button></div>
    <div role="group" aria-label="Status buttons"><button disabled>Pending</button></div>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"></span>
    <span id="link"><button onclick="openPicker()">Link to Project</button></span>
    <ul><li><strong>Status:</strong> Pending by {AGENT}</li></ul>
  </div>
</div>{CLOSE}</div>
<div id="picker"></div>
<script>
function openPicker() {{
  if (document.getElementById('email').checked) document.body.dataset.emailed = 'yes';
  setTimeout(() => {{
    document.getElementById('picker').innerHTML = `<div><div>
      <h3>Choose Project</h3>
      <input aria-label="Search/filter" onblur="search(this.value)">
      <input aria-label="After..."><input aria-label="Before...">
      <table><tbody id="results"></tbody></table>
    </div>{CLOSE}</div>`;
  }}, 300);
}}
function search(text) {{
  if (text !== 'pln_10001') return;
  document.getElementById('results').innerHTML =
    '<tr><td><a href="#" onclick="pick()">pln_10001</a></td><td>B1 Homes</td></tr>';
}}
function pick() {{
  document.getElementById('picker').innerHTML = '';
  document.getElementById('link').innerHTML =
    '<button>pln_10001</button><button>Change Project</button><button>Unlink</button>';
}}
</script>"""


def test_link_project_searches_the_choose_project_window_and_reads_back(page, guard):
    page.set_content(link_page())
    window = booking.note_window(page, NOTE_ID)
    booking.link_project(guard, page, window, "pln_10001")
    assert window.get_by_role("button", name="pln_10001", exact=True).count() == 1
    assert page.locator("body").get_attribute("data-emailed") is None
    assert actions(guard)[-4:] == [
        "link_to_project",
        "link_search_project",
        "link_run_search",
        "link_select_project",
    ]


# Live S8 again, 28 Oct 2026 12:09: the Choose Project heading showed at once
# but its Search/filter only after the 15 s page wait had given up. The
# picker gets its own, longer wait. --probe-link searches without selecting.


def slow_link_page(delay_ms: int) -> str:
    page = link_page()
    assert page.count("}, 300);") == 1
    return page.replace("}, 300);", f"}}, {delay_ms});")


def test_link_project_waits_longer_than_a_page_load_for_the_picker(
    page, guard, monkeypatch
):
    monkeypatch.setattr(booking, "LOAD_TIMEOUT_MS", 500)
    page.set_content(slow_link_page(1500))
    window = booking.note_window(page, NOTE_ID)
    booking.link_project(guard, page, window, "pln_10001")
    assert window.get_by_role("button", name="pln_10001", exact=True).count() == 1


def test_probe_link_searches_and_selects_nothing(page, guard, tmp_path, monkeypatch):
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", tmp_path)
    page.set_content(link_page())
    window = booking.note_window(page, NOTE_ID)
    booking.probe_link(guard, page, window, "pln_10001")
    assert "link_select_project" not in actions(guard)
    assert actions(guard)[-3:] == [
        "link_to_project",
        "link_search_project",
        "link_run_search",
    ]
    assert window.get_by_role("button", name="Link to Project").count() == 1
    results = (tmp_path / "demo-probe-link-results.yml").read_text(encoding="utf-8")
    assert "pln_10001" in results


def test_snapshot_includes_child_frames(page, tmp_path, monkeypatch):
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", tmp_path)
    page.set_content(
        "<h3>Choose Project</h3>"
        "<iframe srcdoc=\"<input aria-label='Inside frame'>\"></iframe>"
    )
    page.frames[-1].wait_for_load_state()
    path = booking.save_snapshot(page, "frames")
    assert "Inside frame" in path.read_text(encoding="utf-8")


# Live probe, 28 Oct 2026 12:28: "link probe done", yet the results snapshot
# held no Choose Project window. While its content loads, the window is only
# a heading, and "heading + a Search/filter box" matched an ancestor holding
# the Note Pool's own Search/filter. The probe must fail loudly instead.


def heading_first_link_page(*, closes_on_heading_click: bool = False) -> str:
    """Choose Project's heading shows at once, its boxes 400 ms later."""
    closes = "true" if closes_on_heading_click else "false"
    page = link_page()
    old = """  setTimeout(() => {
    document.getElementById('picker').innerHTML = `<div><div>
      <h3>Choose Project</h3>"""
    assert page.count(old) == 1
    return page.replace(
        old,
        f"""  document.getElementById('picker').innerHTML =
    `<div id="cp"><div><h3 onclick="if ({closes}) this.closest('#cp').remove()">Choose Project</h3></div></div>`;
  setTimeout(() => {{
    document.getElementById('picker').innerHTML = `<div id="cp"><div>
      <h3 onclick="if ({closes}) this.closest('#cp').remove()">Choose Project</h3>""",
    )


def test_link_project_fills_the_pickers_box_not_the_note_pools(page, guard):
    page.set_content(heading_first_link_page())
    window = booking.note_window(page, NOTE_ID)
    booking.link_project(guard, page, window, "pln_10001")
    pool_search = page.get_by_role("textbox", name="Search/filter").first
    assert pool_search.input_value() == ""
    assert window.get_by_role("button", name="pln_10001", exact=True).count() == 1


def test_probe_link_snapshots_each_sub_step(page, guard, tmp_path, monkeypatch):
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", tmp_path)
    page.set_content(heading_first_link_page())
    booking.probe_link(guard, page, booking.note_window(page, NOTE_ID), "pln_10001")
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "demo-probe-link-1-opened.yml",
        "demo-probe-link-2-filled.yml",
        "demo-probe-link-3-searched.yml",
        "demo-probe-link-results.yml",
    ]
    assert "Choose Project" in (tmp_path / names[0]).read_text(encoding="utf-8")


def test_probe_link_fails_when_the_pln_is_not_listed(
    page, guard, tmp_path, monkeypatch
):
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(booking, "LINK_TIMEOUT_MS", 1500)
    page.set_content(heading_first_link_page())
    with pytest.raises(UnexpectedScreen):
        booking.probe_link(guard, page, booking.note_window(page, NOTE_ID), "pln_99999")


def test_probe_link_fails_when_choose_project_closes(
    page, guard, tmp_path, monkeypatch
):
    monkeypatch.setattr(booking, "SNAPSHOT_DIR", tmp_path)
    page.set_content(heading_first_link_page(closes_on_heading_click=True))
    with pytest.raises(UnexpectedScreen):
        booking.probe_link(guard, page, booking.note_window(page, NOTE_ID), "pln_10001")
