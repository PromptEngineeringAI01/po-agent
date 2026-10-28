"""Tests for mysys/guard.py, the action guard (task 1.4).

Headless Chromium on local HTML (page.set_content), offline: no site is
touched (CLAUDE.md Must never #2 and #3; decisions, 16 Oct 2026, D3). A click
is seen through an inline onclick that sets data-clicked, read back with
get_attribute; tests never act on the page themselves (guard_check.py).
"""

import traceback
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, sync_playwright

from po_agent.core.errors import GuardRefusal, UnexpectedScreen
from po_agent.mysys.guard import (
    ALLOWLIST,
    DENYLIST,
    ActionGuard,
    Allowed,
    Refusal,
    Refused,
)

FAKE_PDF = {
    "name": "fake_po.pdf",
    "mimeType": "application/pdf",
    "buffer": b"%PDF-1.4 fake",
}
PASSWORD = "s3cr3t-Value-42"


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


def button(name: str, attrs: str = "") -> str:
    return f"<button {attrs} onclick=\"this.dataset.clicked='yes'\">{name}</button>"


def window(heading: str, body: str, *, hidden: bool = False) -> str:
    """A floating window; hidden = minimised (still in the page)."""
    return f"<section{' hidden' if hidden else ''}><h2>{heading}</h2>{body}</section>"


def win(page: Page, heading: str) -> Locator:
    # CSS, so a hidden copy matches too: the guard must pick the visible one.
    return page.locator("section").filter(has=page.locator("h2", has_text=heading))


def clicked(locator: Locator) -> bool:
    return locator.get_attribute("data-clicked") == "yes"


def refusal(guard: ActionGuard, *args) -> Refusal:
    with pytest.raises(GuardRefusal) as caught:
        guard.act(*args)
    return caught.value.reason


# --- allowlist and denylist -------------------------------------------------


def test_allowlist_is_spec_section_5_plus_the_spec_additions():
    # docs/specs/spec.md §5, SPEC -> Guard additions, plan Open question 3.
    assert ALLOWLIST == {
        "login_username": "fill",
        "login_password": "fill",
        "login_submit": "click",
        "open_project_tab": "click",
        "open_note_pool": "click",
        "open_projects_subtab": "click",
        "leave_project_menu": "click",  # demo, 27 Oct 2026
        "open_pool": "click",
        "set_pool_filter": "select",
        "set_locked_filter": "select",
        "search_note_pool": "fill",
        "refresh_note_pool": "click",
        "open_note": "click",
        "select_note_user": "select",
        "select_note_pool": "select",
        "assign_note": "click",
        "download_attachment": "click",
        "search_project": "fill",
        "submit_project_search": "press",  # Enter, Joey 28 Oct 2026
        "open_project": "click",
        "open_create_new_task": "click",
        "set_creator": "select",
        "tick_compaction_test": "check",
        "set_po_number": "fill",
        "upload_document": "upload",
        "set_task_note": "fill",
        "untick_send_email_notification": "uncheck",
        "submit_task": "click",
        "open_hold": "click",
        "set_hold_note": "fill",
        "confirm_hold": "click",
        "link_to_project": "click",
        "link_search_project": "fill",
        "submit_link_search": "press",  # Enter, Joey 28 Oct 2026
        "link_select_project": "click",
        "mark_solved": "click",
        "search_task": "fill",
        "open_task_detail": "click",
    }


def test_denylist_is_the_spec_list():
    assert set(DENYLIST) == {
        "discard",
        "unlink",
        "cancel",
        "un-hold",
        "change project",
        "unassign",
        "remove",
        "delete",
        "close",
    }


# --- denylist on the element itself -----------------------------------------

DENYLISTED_NAMES = [
    "Discard",
    "Unlink",
    "Cancel",
    "Undo Cancellation",
    "Un-Hold",
    "Change Project",
    "Unassign",
    "Remove",
    "Delete",
    "close",
    "Close",
    "CLOSE",
]


@pytest.mark.parametrize("name", DENYLISTED_NAMES)
def test_act_refuses_each_denylisted_name_and_does_not_click(page, guard, name):
    page.set_content(window("Note 300001", button(name)))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name=name, exact=True)

    assert refusal(guard, "assign_note", scope, target) == Refusal.DENYLISTED
    assert not clicked(target)


@pytest.mark.parametrize(
    "html, locate",
    [
        (button("x", 'aria-label="Remove file"'), lambda s: s.get_by_role("button")),
        (button("x", 'title="Delete row"'), lambda s: s.get_by_role("button")),
        (
            '<input type="button" value="Close" '
            "onclick=\"this.dataset.clicked='yes'\">",
            lambda s: s.locator("input"),
        ),
        (
            "<div onclick=\"this.dataset.clicked='yes'\">Close</div>",
            lambda s: s.get_by_text("Close", exact=True),
        ),
    ],
    ids=["aria-label", "title", "input-value", "generic-text"],
)
def test_denylisted_word_in_any_name_source_is_refused(page, guard, html, locate):
    page.set_content(window("Note 300001", html))
    scope = win(page, "Note 300001")
    target = locate(scope)

    assert refusal(guard, "assign_note", scope, target) == Refusal.DENYLISTED
    assert not clicked(target)


def test_denylisted_name_from_a_label_for_is_refused(page, guard):
    page.set_content(
        window(
            "Note 300001",
            '<label for="t">Delete note</label><input id="t" type="text">',
        )
    )
    scope = win(page, "Note 300001")
    target = scope.locator("#t")

    assert refusal(guard, "set_task_note", scope, target, "x") == Refusal.DENYLISTED
    assert target.input_value() == ""


def test_window_text_does_not_count_only_the_element(page, guard):
    # A street named "... Close" in the heading and a window Close control.
    page.set_content(
        window(
            "pln_10001 B1 Homes 12 Sample Close",
            '<div class="ctl">Close</div>' + button("Create New Task"),
        )
    )
    scope = win(page, "pln_10001 B1 Homes 12 Sample Close")
    target = scope.get_by_role("button", name="Create New Task", exact=True)

    guard.act("open_create_new_task", scope, target)

    assert clicked(target)


def test_refusal_message_holds_no_page_text(page, guard):
    page.set_content(window("Note 300001", button("12 Sample Close")))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="12 Sample Close", exact=True)

    with pytest.raises(GuardRefusal) as caught:
        guard.act("assign_note", scope, target)

    assert "Sample" not in str(caught.value)
    assert "Sample" not in repr(caught.value.args)
    assert caught.value.action == "assign_note"
    assert caught.value.reason == Refusal.DENYLISTED


# --- select: the select's name plus the chosen option (D5) ------------------

STATUS_SELECT = (
    '<select aria-label="Status"><option>Pending</option>'
    "<option>Solved</option><option>Discard</option></select>"
)
USER_SELECT = (
    '<select aria-label="User"><option>--Select User--</option>'
    "<option selected>Sam Close</option>"
    "<option>Agent 1 (MySys Only)</option><option>Pat Remove</option></select>"
)


def test_select_refuses_a_denylisted_chosen_option(page, guard):
    page.set_content(window("Note Pool", STATUS_SELECT))
    scope = win(page, "Note Pool")
    target = scope.get_by_role("combobox", name="Status", exact=True)

    refused = refusal(guard, "set_pool_filter", scope, target, "Discard")

    assert refused == Refusal.DENYLISTED
    assert target.input_value() == "Pending"


def test_select_ignores_denylisted_options_that_are_not_chosen(page, guard):
    # "Sam Close" is even the current selection; only the chosen label counts.
    page.set_content(window("Note 300001", USER_SELECT))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("combobox", name="User", exact=True)

    guard.act("select_note_user", scope, target, "Agent 1 (MySys Only)")

    assert target.input_value() == "Agent 1 (MySys Only)"


@pytest.mark.parametrize("label", ["Agent 1", "agent 1 (mysys only)", "Nobody"])
def test_select_refuses_an_option_that_is_not_an_exact_label(page, guard, label):
    page.set_content(window("Note 300001", USER_SELECT))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("combobox", name="User", exact=True)

    refused = refusal(guard, "select_note_user", scope, target, label)

    assert refused == Refusal.OPTION_NOT_FOUND
    assert target.input_value() == "Sam Close"


# --- Pending button and Hold-dialog checkboxes ------------------------------

STATUS_BUTTONS = (
    '<div role="group" aria-label="Status buttons">'
    + button("Pending")
    + button("Solved")
    + button("Discard")
    + "</div>"
)


def test_pending_button_is_refused(page, guard):
    page.set_content(window("Note 300001", STATUS_BUTTONS))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Pending", exact=True)

    assert refusal(guard, "mark_solved", scope, target) == Refusal.PENDING_BUTTON
    assert not clicked(target)


def test_solved_button_is_allowed(page, guard):
    page.set_content(window("Note 300001", STATUS_BUTTONS))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Solved", exact=True)

    guard.act("mark_solved", scope, target)

    assert clicked(target)


HOLD_WINDOW_BODY = (
    '<label><input type="checkbox" checked> Send me a reminder email every days'
    "</label>"
    '<label><input type="checkbox"> Job 1</label>' + button("Hold")
)


@pytest.mark.parametrize(
    "action, name, ticked",
    [
        (
            "untick_send_email_notification",
            "Send me a reminder email every days",
            True,
        ),
        ("tick_compaction_test", "Job 1", False),
    ],
)
def test_any_checkbox_in_a_hold_window_is_refused(page, guard, action, name, ticked):
    page.set_content(window("Hold Task: tsk_200001", HOLD_WINDOW_BODY))
    scope = win(page, "Hold Task: tsk_200001")
    target = scope.get_by_role("checkbox", name=name, exact=True)

    assert refusal(guard, action, scope, target) == Refusal.HOLD_CHECKBOX
    assert target.is_checked() is ticked


def test_checkbox_elsewhere_is_refused_while_a_hold_window_is_open(page, guard):
    page.set_content(
        window("Hold Task: tsk_200001", HOLD_WINDOW_BODY)
        + window(
            "Note 300001",
            '<label><input type="checkbox" checked> Send Email Notification</label>',
        )
    )
    scope = win(page, "Note 300001")
    target = scope.get_by_role("checkbox", name="Send Email Notification", exact=True)

    refused = refusal(guard, "untick_send_email_notification", scope, target)

    assert refused == Refusal.HOLD_CHECKBOX
    assert target.is_checked()


@pytest.mark.parametrize("hold_window_minimised", [False, True])
def test_send_email_untick_is_allowed_without_a_visible_hold_window(
    page, guard, hold_window_minimised
):
    hold = (
        window("Hold Task: tsk_200001", HOLD_WINDOW_BODY, hidden=True)
        if hold_window_minimised
        else ""
    )
    page.set_content(
        hold
        + window(
            "Note 300001",
            '<label><input type="checkbox" checked> Send Email Notification</label>',
        )
    )
    scope = win(page, "Note 300001")
    target = scope.get_by_role("checkbox", name="Send Email Notification", exact=True)

    guard.act("untick_send_email_notification", scope, target)

    assert not target.is_checked()


def test_hold_confirm_button_in_the_hold_window_is_allowed(page, guard):
    page.set_content(window("Hold Task: tsk_200001", HOLD_WINDOW_BODY))
    scope = win(page, "Hold Task: tsk_200001")
    target = scope.get_by_role("button", name="Hold", exact=True)

    guard.act("confirm_hold", scope, target)

    assert clicked(target)


# --- scope and exactly one visible match ------------------------------------


def test_no_match_is_refused(page, guard):
    page.set_content(window("Note 300001", button("Solved")))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Assign", exact=True)

    assert refusal(guard, "assign_note", scope, target) == Refusal.TARGET_NOT_FOUND


def test_two_visible_matches_are_refused(page, guard):
    page.set_content(window("Note 300001", button("Assign") + button("Assign")))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Assign", exact=True)

    assert refusal(guard, "assign_note", scope, target) == Refusal.TARGET_AMBIGUOUS
    assert not clicked(target.first)
    assert not clicked(target.last)


def test_target_outside_the_scope_is_refused(page, guard):
    page.set_content(
        window("Create New Task", "<p>form</p>")
        + window("pln_10001 B1 Homes", button("Submit"))
    )
    scope = win(page, "Create New Task")
    target = page.get_by_role("button", name="Submit", exact=True)

    refused = refusal(guard, "submit_task", scope, target)

    assert refused == Refusal.TARGET_OUTSIDE_SCOPE
    assert not clicked(target)


def test_scope_not_found_is_refused(page, guard):
    page.set_content(window("Note 300001", button("Hold")))
    scope = win(page, "Hold Task: tsk_999999")
    target = scope.get_by_role("button", name="Hold", exact=True)

    assert refusal(guard, "confirm_hold", scope, target) == Refusal.SCOPE_NOT_FOUND


def test_two_visible_scopes_are_refused(page, guard):
    page.set_content(
        window("Note 300001", button("Assign")) + window("Note 300001", "<p>x</p>")
    )
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Assign", exact=True)

    assert refusal(guard, "assign_note", scope, target) == Refusal.SCOPE_AMBIGUOUS
    assert not clicked(target)


def test_hidden_copy_in_a_minimised_window_is_never_the_one_acted_on(page, guard):
    page.set_content(
        window("Note 300001", button("Assign", 'id="hidden"'), hidden=True)
        + window("Note 300001", button("Assign", 'id="shown"'))
    )
    scope = win(page, "Note 300001")
    target = scope.locator("button", has_text="Assign")  # matches both copies

    guard.act("assign_note", scope, target)

    assert clicked(page.locator("#shown"))
    assert not clicked(page.locator("#hidden"))


# --- action names and values ------------------------------------------------


def test_unknown_action_is_refused(page, guard):
    page.set_content(window("Note 300001", button("Assign")))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Assign", exact=True)

    assert refusal(guard, "press_assign", scope, target) == Refusal.UNKNOWN_ACTION
    assert not clicked(target)


@pytest.mark.parametrize(
    "action, value",
    [
        ("assign_note", "x"),
        ("tick_compaction_test", "x"),
        ("set_po_number", None),
        ("set_po_number", FAKE_PDF),
        ("select_note_user", None),
        ("upload_document", "fake_po.pdf"),
        ("upload_document", None),
    ],
)
def test_value_that_does_not_fit_the_action_is_refused(page, guard, action, value):
    page.set_content(window("Note 300001", button("Assign")))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Assign", exact=True)

    assert refusal(guard, action, scope, target, value) == Refusal.VALUE_MISMATCH
    assert not clicked(target)


def test_unknown_action_is_refused_without_touching_the_page(browser, guard):
    page = browser.new_page()
    scope = page.locator("section")
    target = scope.get_by_role("button", name="Assign", exact=True)
    page.close()  # any page call would now raise a Playwright error

    verdict = guard.vet("press_assign", scope, target)
    assert verdict == Refused(Refusal.UNKNOWN_ACTION)
    assert refusal(guard, "press_assign", scope, target) == Refusal.UNKNOWN_ACTION


# --- each kind acts on the element and reads back ---------------------------

CREATE_TASK_FORM = (
    '<label for="po">PO Number</label><input id="po" type="text">'
    '<label><input type="checkbox"> - Compaction Test</label>'
    '<label for="doc">PO Documents</label>'
    '<input id="doc" type="file" '
    'onchange="this.dataset.files=this.files[0].name">'
    + '<label for="cr">Creator</label>'
    '<select id="cr"><option>Project Creator</option>'
    "<option>Perth Scheduling</option></select>" + button("Submit")
)


def test_fill_check_select_and_upload_act_and_read_back(page, guard):
    page.set_content(window("Create New Task", CREATE_TASK_FORM))
    scope = win(page, "Create New Task")
    po = scope.get_by_label("PO Number", exact=True)
    compaction = scope.get_by_role("checkbox", name="- Compaction Test", exact=True)
    creator = scope.get_by_label("Creator", exact=True)
    upload = scope.get_by_label("PO Documents", exact=True)

    guard.act("set_po_number", scope, po, "2600001B/048")
    guard.act("tick_compaction_test", scope, compaction)
    guard.act("set_creator", scope, creator, "Perth Scheduling")
    guard.act("upload_document", scope, upload, FAKE_PDF)

    assert po.input_value() == "2600001B/048"
    assert compaction.is_checked()
    assert creator.input_value() == "Perth Scheduling"
    assert upload.get_attribute("data-files") == "fake_po.pdf"


# --- vet() decides, act() acts ----------------------------------------------


def test_vet_refuses_without_clicking(page, guard):
    page.set_content(window("Note 300001", STATUS_BUTTONS))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Discard", exact=True)

    verdict = guard.vet("mark_solved", scope, target)

    assert verdict == Refused(Refusal.DENYLISTED)
    assert not clicked(target)
    assert guard.history == []


def test_vet_allows_without_clicking(page, guard):
    page.set_content(window("Note 300001", STATUS_BUTTONS))
    scope = win(page, "Note 300001")
    target = scope.get_by_role("button", name="Solved", exact=True)

    verdict = guard.vet("mark_solved", scope, target)

    assert isinstance(verdict, Allowed)
    assert not clicked(target)


# --- history and typed values -----------------------------------------------

LOGIN_FORM = (
    '<label for="u">Username</label><input id="u" type="text">'
    '<label for="p">Password</label><input id="p" type="password">' + button("Log in")
)


def test_history_records_action_and_outcome_only(page, guard):
    page.set_content(
        window("Login", LOGIN_FORM) + window("Note 300001", button("Unlink"))
    )
    login = win(page, "Login")
    note = win(page, "Note 300001")
    password = login.get_by_label("Password", exact=True)

    guard.act("login_password", login, password, PASSWORD)
    with pytest.raises(GuardRefusal):
        guard.act(
            "assign_note", note, note.get_by_role("button", name="Unlink", exact=True)
        )

    assert password.input_value() == PASSWORD
    assert guard.history == [
        ("login_password", "done"),
        ("assign_note", Refusal.DENYLISTED),
    ]


def test_typed_value_never_appears_in_history_verdict_or_error(page, guard):
    page.set_content(window("Login", LOGIN_FORM))
    login = win(page, "Login")
    password = login.get_by_label("Password", exact=True)
    missing = login.get_by_label("Passcode", exact=True)

    verdict = guard.vet("login_password", login, password, PASSWORD)
    guard.act("login_password", login, password, PASSWORD)
    with pytest.raises(GuardRefusal) as caught:
        guard.act("login_password", login, missing, PASSWORD)

    for text in (repr(verdict), repr(guard.history), str(caught.value)):
        assert PASSWORD not in text
    assert PASSWORD not in repr(caught.value.args)


# --- review fixes: untested refusals and Playwright error text --------------


def test_element_with_no_readable_name_is_refused(page, guard):
    page.set_content(window("Note 300001", button("Assign", 'aria-hidden="true"')))
    scope = win(page, "Note 300001")
    target = scope.locator("button")

    assert refusal(guard, "assign_note", scope, target) == Refusal.NAME_UNREADABLE
    assert not clicked(target)


@pytest.mark.parametrize(
    "action, value, locate",
    [
        ("set_pool_filter", "Pending", lambda s: s.locator("input")),
        ("search_note_pool", "300001", lambda s: s.locator("select")),
    ],
)
def test_select_kind_and_select_element_must_go_together(
    page, guard, action, value, locate
):
    page.set_content(
        window("Note Pool", '<input aria-label="Search" type="text">' + STATUS_SELECT)
    )
    scope = win(page, "Note Pool")

    assert refusal(guard, action, scope, locate(scope), value) == Refusal.WRONG_ELEMENT
    assert scope.locator("input").input_value() == ""
    assert scope.locator("select").input_value() == "Pending"


@pytest.mark.parametrize(
    "locate",
    [
        lambda s: s.locator("label", has_text="Job 1"),
        lambda s: s.locator("div.row"),
    ],
    ids=["label", "row"],
)
def test_click_on_a_label_or_row_holding_a_hold_checkbox_is_refused(
    page, guard, locate
):
    page.set_content(
        window(
            "Hold Task: tsk_200001",
            '<div class="row"><label><input type="checkbox"> Job 1</label></div>'
            + button("Hold"),
        )
    )
    scope = win(page, "Hold Task: tsk_200001")

    refused = refusal(guard, "confirm_hold", scope, locate(scope))

    assert refused == Refusal.HOLD_CHECKBOX
    assert not scope.get_by_role("checkbox", name="Job 1", exact=True).is_checked()


def test_failed_action_is_a_fixed_error_without_the_typed_value(page, guard):
    # Playwright's own message quotes the call: fill("<the password>").
    page.set_content(
        window(
            "Login",
            '<label for="p">Password</label><input id="p" type="password" disabled>',
        )
    )
    page.set_default_timeout(300)
    login = win(page, "Login")
    password = login.get_by_label("Password", exact=True)

    with pytest.raises(UnexpectedScreen) as caught:
        guard.act("login_password", login, password, PASSWORD)

    shown = "".join(traceback.format_exception(caught.value))
    assert PASSWORD not in shown
    assert caught.value.action == "login_password"
    assert guard.history == [("login_password", "failed")]


def test_page_error_while_vetting_is_a_fixed_error_without_page_text(browser, guard):
    # A scope found by a heading can quote an address; Playwright's message
    # quotes the locator.
    page = browser.new_page()
    scope = win(page, "pln_10001 B1 Homes 12 Sample Close")
    target = scope.get_by_role("button", name="Create New Task", exact=True)
    page.close()

    with pytest.raises(UnexpectedScreen) as caught:
        guard.vet("open_create_new_task", scope, target)

    assert "Sample" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.action == "open_create_new_task"


# Joey, 28 Oct 2026: Enter runs the two project searches. PRESS allows only
# the key "Enter", only on those search boxes; everything else is refused.

PRESS_PAGE = (
    "<section><h2>Projects</h2>"
    "<input aria-label='Search...' "
    "onkeydown=\"if (event.key === 'Enter') this.dataset.entered = 'yes'\">"
    "<input aria-label='Search/filter'>"
    "<input aria-label='Note'><button>Search</button></section>"
)


@pytest.mark.parametrize(
    ("action", "name"),
    [("submit_project_search", "Search..."), ("submit_link_search", "Search/filter")],
)
def test_enter_is_allowed_on_its_search_box(page, guard, action, name):
    page.set_content(PRESS_PAGE)
    box = page.get_by_role("textbox", name=name, exact=True)
    guard.act(action, page.locator("section"), box, "Enter")
    if name == "Search...":
        assert box.get_attribute("data-entered") == "yes"


@pytest.mark.parametrize("key", ["Tab", "a", "Control+Enter", "enter", "", None])
def test_any_other_key_is_refused(page, guard, key):
    page.set_content(PRESS_PAGE)
    box = page.get_by_role("textbox", name="Search...", exact=True)
    assert refusal(
        guard, "submit_project_search", page.locator("section"), box, key
    ) == (Refusal.VALUE_MISMATCH)
    assert box.get_attribute("data-entered") is None


@pytest.mark.parametrize(
    ("action", "locate"),
    [
        ("submit_project_search", lambda p: p.get_by_role("textbox", name="Note")),
        (
            "submit_project_search",
            lambda p: p.get_by_role("textbox", name="Search/filter"),
        ),
        ("submit_project_search", lambda p: p.get_by_role("button", name="Search")),
        ("submit_link_search", lambda p: p.get_by_role("textbox", name="Search...")),
    ],
)
def test_enter_on_any_other_target_is_refused(page, guard, action, locate):
    page.set_content(PRESS_PAGE)
    target = locate(page)
    assert refusal(guard, action, page.locator("section"), target, "Enter") == (
        Refusal.WRONG_ELEMENT
    )


def test_enter_is_only_for_the_press_actions(page, guard):
    page.set_content(PRESS_PAGE)
    box = page.get_by_role("textbox", name="Search...", exact=True)
    # A fill may type the text "Enter" (it presses no key): allowed, as before.
    verdict = guard.vet("search_project", page.locator("section"), box, "Enter")
    assert isinstance(verdict, Allowed)
    # Any non-press action given "Enter" as a key is refused.
    assert refusal(guard, "open_note", page.locator("section"), box, "Enter") == (
        Refusal.VALUE_MISMATCH
    )
