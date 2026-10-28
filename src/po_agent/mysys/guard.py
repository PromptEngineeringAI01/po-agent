"""The action guard: the only code that acts on a MySys page (task 1.4).

Every click, fill, tick, select or upload is a named action on the allowlist,
on exactly one visible element inside one visible window (the scope), and is
refused if the element's own name or text hits the denylist
(docs/specs/spec.md §5; SPEC.md -> MySys screen rules -> Guard additions).

`vet()` resolves the element and decides; it only reads the page. `act()`
calls `vet()`, raises `GuardRefusal` before any page interaction, and acts on
the element `vet()` resolved, never a second lookup (D3). scripts/guard_check.py
fails the build on a page action anywhere but in `act()`.

Refusal reasons and error details are fixed strings, never page text: a
denylisted name can be an address ("... Close"). Typed values (the password)
are never stored or logged. A Playwright error becomes a fixed
`UnexpectedScreen` without its message, which quotes the call (`fill("<the
password>")`) and the locator (a heading can hold an address).
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from playwright.sync_api import ElementHandle, FilePayload, Locator
from playwright.sync_api import Error as PlaywrightError

from po_agent.core.errors import GuardRefusal, UnexpectedScreen


class Kind(StrEnum):
    CLICK = "click"
    FILL = "fill"
    CHECK = "check"
    UNCHECK = "uncheck"
    SELECT = "select"
    UPLOAD = "upload"


# docs/specs/spec.md §5, SPEC -> Guard additions, tasks/plan.md Open question 3.
ALLOWLIST: dict[str, Kind] = {
    # Log in and module navigation
    "login_username": Kind.FILL,
    "login_password": Kind.FILL,
    "login_submit": Kind.CLICK,
    "open_project_tab": Kind.CLICK,
    "open_note_pool": Kind.CLICK,
    "open_projects_subtab": Kind.CLICK,
    # Moves the mouse off the Project hover menu so it closes: while open,
    # the page takes no clicks (decisions, 27 Oct 2026).
    "leave_project_menu": Kind.CLICK,
    # Note Pool
    "open_pool": Kind.CLICK,
    "set_pool_filter": Kind.SELECT,
    "set_locked_filter": Kind.SELECT,
    "search_note_pool": Kind.FILL,
    "refresh_note_pool": Kind.CLICK,  # row 27 (decisions, 25 Oct 2026)
    "open_note": Kind.CLICK,
    # Note window
    "select_note_user": Kind.SELECT,
    "select_note_pool": Kind.SELECT,
    "assign_note": Kind.CLICK,
    "download_attachment": Kind.CLICK,
    "untick_send_email_notification": Kind.UNCHECK,
    "link_to_project": Kind.CLICK,
    "link_search_project": Kind.FILL,
    # Click the Choose Project heading so focus leaves the search box and
    # the search runs (decisions, 28 Oct 2026).
    "link_run_search": Kind.CLICK,
    "link_select_project": Kind.CLICK,
    "mark_solved": Kind.CLICK,
    # Projects and Create New Task
    "search_project": Kind.FILL,
    # fill alone may not run it: click the plain "Search" label to move focus
    # (SPEC.md -> Project search; decisions, 27 Oct 2026).
    "run_project_search": Kind.CLICK,
    "open_project": Kind.CLICK,
    "open_create_new_task": Kind.CLICK,
    "set_creator": Kind.SELECT,
    "tick_compaction_test": Kind.CHECK,
    "set_po_number": Kind.FILL,
    "upload_document": Kind.UPLOAD,
    "set_task_note": Kind.FILL,
    "submit_task": Kind.CLICK,
    # Hold
    "open_hold": Kind.CLICK,
    "set_hold_note": Kind.FILL,
    "confirm_hold": Kind.CLICK,
    # Task detail (read-only screen)
    "search_task": Kind.FILL,
    "open_task_detail": Kind.CLICK,
}

# Matched lowercased, as substrings: "cancel" also catches "Undo Cancellation",
# "close" every window Close, the PDF's remove cell and Task Client's clear.
DENYLIST = (
    "discard",
    "unlink",
    "cancel",
    "un-hold",
    "change project",
    "unassign",
    "remove",
    "delete",
    "close",
)
# Attributes that can carry an element's name besides its accessible name.
NAME_ATTRIBUTES = ("aria-label", "title", "value", "alt")
HOLD_HEADING = re.compile(r"^Hold Task\b")
# First line of an ARIA snapshot: `- button "Assign"`, `- text: Close`.
# https://playwright.dev/python/docs/aria-snapshots
SNAPSHOT_HEAD = re.compile(r'- ([a-z]+)(?: "((?:[^"\\]|\\.)*)")?')
HANDLE_TIMEOUT_MS = 2000


class Refusal(StrEnum):
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    SCOPE_NOT_FOUND = "SCOPE_NOT_FOUND"
    SCOPE_AMBIGUOUS = "SCOPE_AMBIGUOUS"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    TARGET_OUTSIDE_SCOPE = "TARGET_OUTSIDE_SCOPE"
    WRONG_ELEMENT = "WRONG_ELEMENT"
    NAME_UNREADABLE = "NAME_UNREADABLE"
    DENYLISTED = "DENYLISTED"
    PENDING_BUTTON = "PENDING_BUTTON"
    HOLD_CHECKBOX = "HOLD_CHECKBOX"
    OPTION_NOT_FOUND = "OPTION_NOT_FOUND"


@dataclass(frozen=True)
class Allowed:
    # repr=False: a handle's preview can show page text.
    element: ElementHandle = field(repr=False)


@dataclass(frozen=True)
class Refused:
    reason: Refusal


Value = str | FilePayload | None


def _value_fits(kind: Kind, value: Value) -> bool:
    if kind in (Kind.CLICK, Kind.CHECK, Kind.UNCHECK):
        return value is None
    if kind in (Kind.FILL, Kind.SELECT):
        return isinstance(value, str)
    return (
        isinstance(value, dict)
        and set(value) == {"name", "mimeType", "buffer"}
        and isinstance(value["buffer"], bytes)
    )


def _count_refusal(count: int, none: Refusal, many: Refusal) -> Refusal | None:
    if count == 0:
        return none
    if count > 1:
        return many
    return None


class ActionGuard:
    def __init__(self) -> None:
        # (action name, "done", "failed" or the refusal reason); never a value.
        self.history: list[tuple[str, str]] = []

    def vet(
        self, action: str, scope: Locator, target: Locator, value: Value = None
    ) -> Allowed | Refused:
        """Resolve the one element `action` would act on, and allow or refuse.

        Reads the page only. Checks, in order: the action is allowlisted and
        the value fits it; the scope is exactly one visible window; the target
        is exactly one visible element, inside that window; the element's own
        name and text (for a select: its name plus the chosen option) miss the
        denylist; it isn't the Pending button; it isn't a checkbox while a
        Hold Task window is open.
        """
        try:
            return self._vet(action, scope, target, value)
        except PlaywrightError:
            raise UnexpectedScreen(
                "guard could not read the page", action=action
            ) from None

    def _vet(
        self, action: str, scope: Locator, target: Locator, value: Value
    ) -> Allowed | Refused:
        kind = ALLOWLIST.get(action)
        if kind is None:
            return Refused(Refusal.UNKNOWN_ACTION)
        if not _value_fits(kind, value):
            return Refused(Refusal.VALUE_MISMATCH)

        # Locator.visible matches visible elements only, checked when used:
        # https://playwright.dev/python/docs/api/class-locator#locator-visible
        window = scope.visible
        if reason := _count_refusal(
            window.count(), Refusal.SCOPE_NOT_FOUND, Refusal.SCOPE_AMBIGUOUS
        ):
            return Refused(reason)
        if reason := _count_refusal(
            target.visible.count(), Refusal.TARGET_NOT_FOUND, Refusal.TARGET_AMBIGUOUS
        ):
            return Refused(reason)
        # and_ matches both locators; window.locator("*") is every element in
        # the window: https://playwright.dev/python/docs/api/class-locator#locator-and
        resolved = target.visible.and_(window.locator("*"))
        if resolved.count() != 1:
            return Refused(Refusal.TARGET_OUTSIDE_SCOPE)

        page = scope.page
        is_select = resolved.and_(page.locator("select")).count() == 1
        if (kind == Kind.SELECT) != is_select:
            return Refused(Refusal.WRONG_ELEMENT)

        # Pin the element now: act() uses this handle, never a second lookup.
        # https://playwright.dev/python/docs/api/class-locator#locator-element-handle
        element = resolved.element_handle(timeout=HANDLE_TIMEOUT_MS)

        # Role and accessible name from the ARIA snapshot's first line; a
        # select's options are on the lines below and are skipped (D5).
        # https://playwright.dev/python/docs/api/class-locator#locator-aria-snapshot
        head = SNAPSHOT_HEAD.match(resolved.aria_snapshot())
        if head is None:
            return Refused(Refusal.NAME_UNREADABLE)
        role, name = head.group(1), head.group(2) or ""
        texts = [name, *(element.get_attribute(a) or "" for a in NAME_ATTRIBUTES)]
        if is_select:
            texts.append(str(value))  # the chosen option, never the others
        else:
            texts.append(element.text_content() or "")
        own_text = " ".join(texts).lower()

        if any(word in own_text for word in DENYLIST):
            return Refused(Refusal.DENYLISTED)
        if role == "button" and "pending" in own_text:
            return Refused(Refusal.PENDING_BUTTON)
        if self._hold_window_open(page) and (
            kind in (Kind.CHECK, Kind.UNCHECK)
            or role == "checkbox"
            or resolved.get_by_role("checkbox").count() > 0
            or resolved.and_(page.locator("label")).count() > 0
        ):
            return Refused(Refusal.HOLD_CHECKBOX)
        if is_select and not self._has_option(resolved, str(value)):
            return Refused(Refusal.OPTION_NOT_FOUND)
        return Allowed(element)

    def act(
        self, action: str, scope: Locator, target: Locator, value: Value = None
    ) -> None:
        """vet(), then act on the element vet() resolved.

        Raises GuardRefusal on a refusal, before any page interaction, and
        UnexpectedScreen (fixed detail) if Playwright fails.

        The only place a page action is called (scripts/guard_check.py).
        """
        try:
            verdict = self.vet(action, scope, target, value)
        except UnexpectedScreen:
            self.history.append((action, "failed"))
            raise
        if isinstance(verdict, Refused):
            self.history.append((action, verdict.reason))
            raise GuardRefusal(
                "guard refused the action", action=action, reason=verdict.reason
            )
        element = verdict.element
        # ElementHandle actions on the pinned element; Playwright prefers
        # Locators, but a Locator would look the element up again (spec §5).
        # https://playwright.dev/python/docs/api/class-elementhandle
        try:
            match ALLOWLIST[action]:
                case Kind.CLICK:
                    element.click()
                case Kind.FILL:
                    element.fill(value)
                case Kind.CHECK:
                    element.check()
                case Kind.UNCHECK:
                    element.uncheck()
                case Kind.SELECT:
                    element.select_option(label=value)
                case Kind.UPLOAD:
                    # A FilePayload uploads from memory, never from a path (D2).
                    element.set_input_files(value)
        except PlaywrightError:
            self.history.append((action, "failed"))
            raise UnexpectedScreen("guard action failed", action=action) from None
        self.history.append((action, "done"))

    @staticmethod
    def _hold_window_open(page) -> bool:
        # Any visible Hold Task window on the page, whatever the scope.
        heading = page.get_by_role("heading", name=HOLD_HEADING)
        return heading.visible.count() > 0

    @staticmethod
    def _has_option(select: Locator, label: str) -> bool:
        exact = re.compile(rf"^{re.escape(label)}$")
        return select.locator("option").filter(has_text=exact).count() == 1
