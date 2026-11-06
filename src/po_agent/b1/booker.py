"""The booker: W1-W5 with read-back (SPEC.md -> MySys screen rules;
docs/specs/spec.md §6). Tasks 4.1-4.4 build them.

`book()` takes only a `Proceed` from the decision engine, for the Note in
hand. It reuses the demo's proven steps (mysys/booking.py) but never its
snapshots (page text on disk) or its retried opening clicks for a committing
click. Every page action goes through the guard.

W1: `before_write(note_id, "W1")` (the assignee check reloads, so step 10's
project window is gone) -> the project reopened by its pln and checked again
-> Create New Task: Creator, - Compaction Test, PO Number, the PDF to PO
Documents from memory (D2), Note = the email body -> the full read-back.
Nothing is submitted in W1: any problem once the form is open closes the
browser context, which abandons the form (the upload is saved only by
Submit, M0b.2), and is WriteNotStarted.

W2: `before_write(note_id, "W2")` (no assignee check, D7; a stop here closes
the context, nothing submitted) -> Submit, the partial-write line -> the one
new Compaction Test task (row 10) -> its detail screen, opened from its own
details row and read back (row 19) -> back to the project, its Documents
section for the new task -> Tasks. From the Submit click on, every error is
PartialWrite (a Ctrl+C or other BaseException too), except AccuracyBreach
and GuardRefusal, which keep their type; each carries step W2. With one
of those three types, step W2 tells the run loop the task may exist (4.5:
never returned to the pool); W2's `before_write` errors also say W2 but
come before the click.

W3: `before_write(note_id, "W3")` (no assignee check, D7; a kill switch here
is already PartialWrite, 3.5) -> Hold in the new task's own header row -> the
dialog headed `Hold Task: <new task>` -> the note typed, no checkbox touched
-> every check read (row 11) -> the dialog's own Hold, once -> the row read
back with Un-Hold and an On-hold Status holding the note (row 12). Every
error closes the browser context (an open dialog is abandoned unconfirmed)
and is PartialWrite, except AccuracyBreach and GuardRefusal, which keep their
type; each carries step W3.

W4: `before_write(note_id, "W4")` (the assignee check, D7: any failure is
PartialWrite) -> back to the Note window as row 25 maps it (reload, the Note
ID under All Pools, the row whose ID equals it, opened: Send Email is ticked
again) -> Send Email unticked and read back -> Link to Project -> Choose
Project: the pln searched (Enter) -> Send Email read back again -> the one
cell named exactly the pln, once (row 20) -> the project button reads the
pln (another pln: AccuracyBreach) and Status still starts Pending.

W5: `before_write(note_id, "W5")` (no assignee check, D7) -> Send Email
read back unticked -> Solved, once -> "Solved by <agent>", Solved disabled,
a new "Status changed ... Pending to Solved" log line (row 14) -> the Note
ID searched again under Status Pending: no row whose ID equals it.

W4 and W5 errors close the browser context and carry their step:
PartialWrite, except AccuracyBreach and GuardRefusal, which keep their type.
Pending, Discard, Change Project and Unlink are never targeted.
"""

from collections.abc import Callable
from typing import NoReturn

from playwright.sync_api import Locator, Page

from po_agent.b1.models import Proceed
from po_agent.core.controls import Controls
from po_agent.core.errors import (
    AccuracyBreach,
    GuardRefusal,
    PartialWrite,
    PoAgentError,
    WriteNotStarted,
)
from po_agent.core.runlog import RunLog
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

# The steps built so far; `stop_after` must name one of them.
BUILT = ("W1", "W2", "W3", "W4", "W5")


def book(
    proceed: Proceed,
    *,
    note_id: str,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
    agent: str,
    stop_after: str,
    log: RunLog | None = None,
) -> str | None:
    """Books the Note `note_id` (the one the run loop holds) as `proceed`
    decided, up to and including `stop_after`. Returns the new task number
    once W2 has run. With `log`, W4's and W5's Send Email read-backs are
    `email_notification_unticked` events (5.2)."""
    if not isinstance(proceed, Proceed):
        raise TypeError("book() takes only a Proceed from decide()")
    if stop_after not in BUILT:
        raise ValueError("stop_after must be W1-W5")
    if proceed.note_id != note_id:
        raise WriteNotStarted("decision is for another Note", step="W1")
    project, form = _w1(proceed, guard, page, login, controls)
    if stop_after == "W1":
        return None
    task_no = _w2(proceed, guard, page, controls, agent, project, form)
    if stop_after == "W2":
        return task_no
    _w3(proceed, guard, page, controls, task_no)
    if stop_after == "W3":
        return task_no
    window = _w4(proceed, guard, page, login, controls, log)
    if stop_after == "W4":
        return task_no
    _w5(proceed, guard, page, login, controls, agent, window, log)
    return task_no


def _close_context(page: Page) -> None:
    """Abandons whatever is open; a failed close never hides the error the
    caller is about to raise."""
    try:
        page.context.close()
    except Exception:  # noqa: BLE001 - e.g. a dead event loop
        pass


def _w1(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
) -> tuple[Locator, Locator]:
    note_id = proceed.note_id
    controls.before_write(note_id, "W1")
    # The MVP is test site only (Must never #3).
    project = driver.reopen_project(guard, page, *login, proceed, "test")
    try:
        form = booking.open_task_form(guard, page, project)
        booking.fill_task_form(
            guard,
            form,
            proceed.po_number,
            proceed.email_body,
            proceed.pdf_file_name,
            proceed.pdf_bytes,
        )
    except Exception as error:
        _close_context(page)  # abandons the form: nothing is saved
        if isinstance(error, GuardRefusal | WriteNotStarted):
            raise
        raise WriteNotStarted(
            "Create New Task not filled", note_id=note_id, step="W1"
        ) from error
    return project, form


def _w2(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    controls: Controls,
    agent: str,
    project: Locator,
    form: Locator,
) -> str:
    note_id = proceed.note_id
    try:
        controls.before_write(note_id, "W2")
    except Exception:
        _close_context(page)  # abandons the filled form: nothing submitted
        raise
    # The partial-write line: from here on the task may exist in MySys.
    try:
        booking.submit_task(guard, form)
        task_no = booking.new_task_after_submit(
            form, project, set(proceed.existing_task_nos)
        )
        details = booking.check_new_task_row(project, task_no, agent)
        booking.open_task_detail(guard, project, details)
        window = booking.check_task_detail(
            page, task_no, proceed.po_number, proceed.email_body, agent
        )
        booking.back_to_project(guard, page, window, proceed.pln)
        booking.check_project_document(
            guard, page, proceed.pln, task_no, proceed.pdf_file_name
        )
        return task_no
    except GuardRefusal as error:
        raise GuardRefusal(
            "guard refused the action",
            action=error.action,
            reason=error.reason,
            note_id=note_id,
            step="W2",
        ) from error
    except AccuracyBreach as error:
        raise AccuracyBreach(
            "wrong value on read-back", field=error.field, note_id=note_id, step="W2"
        ) from error
    except PoAgentError as error:
        raise PartialWrite(
            "task not read back after Submit",
            reason=error.reason,
            note_id=note_id,
            step="W2",
        ) from error
    except BaseException as error:  # Ctrl+C too: the task may exist
        raise PartialWrite(
            "task not read back after Submit", note_id=note_id, step="W2"
        ) from error


def _w3(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    controls: Controls,
    task_no: str,
) -> None:
    note_id = proceed.note_id
    try:
        controls.before_write(note_id, "W3")  # PartialWrite here (3.5)
        project = booking.project_window(page, proceed.pln)
        dialog = booking.open_hold(guard, page, project, task_no)
        booking.fill_hold(guard, dialog)
        booking.confirm_hold(guard, page, dialog)
        booking.check_on_hold(project, task_no)
    except BaseException as error:  # Ctrl+C too
        _close_context(page)  # an open Hold dialog is abandoned unconfirmed
        if isinstance(error, GuardRefusal):
            raise GuardRefusal(
                "guard refused the action",
                action=error.action,
                reason=error.reason,
                note_id=note_id,
                step="W3",
            ) from error
        if isinstance(error, AccuracyBreach):
            raise AccuracyBreach(
                "wrong value on read-back",
                field=error.field,
                note_id=note_id,
                step="W3",
            ) from error
        if isinstance(error, PoAgentError):
            raise PartialWrite(
                "task not held",
                reason=error.reason,
                field=error.field,
                note_id=note_id,
                step="W3",
            ) from error
        raise PartialWrite("task not held", note_id=note_id, step="W3") from error


def _stop_after_submit(
    page: Page, error: BaseException, note_id: str, step: str
) -> NoReturn:
    """W4 and W5: closes the browser context (an open Choose Project is
    abandoned unselected), then raises the error with its step:
    PartialWrite, except AccuracyBreach and GuardRefusal, which keep their
    type. A PartialWrite that already names the step (before_write's) is
    raised as it is."""
    _close_context(page)
    if isinstance(error, PartialWrite) and error.step == step:
        raise error
    if isinstance(error, GuardRefusal):
        raise GuardRefusal(
            "guard refused the action",
            action=error.action,
            reason=error.reason,
            note_id=note_id,
            step=step,
        ) from error
    if isinstance(error, AccuracyBreach):
        raise AccuracyBreach(
            "wrong value on read-back", field=error.field, note_id=note_id, step=step
        ) from error
    if isinstance(error, PoAgentError):
        raise PartialWrite(
            "Note not linked and solved",
            reason=error.reason,
            field=error.field,
            note_id=note_id,
            step=step,
        ) from error
    raise PartialWrite(
        "Note not linked and solved", note_id=note_id, step=step
    ) from error


def _unticked(log: RunLog | None, note_id: str, step: str) -> Callable[[], None]:
    """The run-log event for Send Email read back unticked before `step`'s
    Note-window write."""

    def logged() -> None:
        if log is not None:
            log.event(
                "email_notification_unticked", note_id=note_id, step=step, ok=True
            )

    return logged


def _w4(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
    log: RunLog | None,
) -> Locator:
    note_id = proceed.note_id
    try:
        controls.before_write(note_id, "W4")  # the assignee check (D7)
        window = driver.find_note_again(guard, page, *login, note_id)  # row 25
        booking.link_project(
            guard, page, window, proceed.pln, unticked=_unticked(log, note_id, "W4")
        )
        return window
    except BaseException as error:  # Ctrl+C too
        _stop_after_submit(page, error, note_id, "W4")


def _w5(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
    agent: str,
    window: Locator,
    log: RunLog | None,
) -> None:
    note_id = proceed.note_id
    try:
        controls.before_write(note_id, "W5")  # no assignee check (D7)
        before = driver.log_line_count(window)
        booking.mark_solved(
            guard, window, agent, unticked=_unticked(log, note_id, "W5")
        )
        booking.check_solved_log(window, before)
        driver.gone_from_pending(guard, page, *login, note_id)
    except BaseException as error:  # Ctrl+C too
        _stop_after_submit(page, error, note_id, "W5")
