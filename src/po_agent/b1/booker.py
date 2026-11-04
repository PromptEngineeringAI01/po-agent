"""The booker: W1-W5 with read-back (SPEC.md -> MySys screen rules;
docs/specs/spec.md §6). Tasks 4.1-4.2 build W1 and W2; 4.3-4.4 add the
later steps.

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
PartialWrite, except AccuracyBreach and GuardRefusal, which keep their type;
each carries step W2, which tells the run loop the task may exist (4.5:
never returned to the pool).
"""

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
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

# The steps built so far; `stop_after` must name one of them.
BUILT = ("W1", "W2")


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
) -> str | None:
    """Books the Note `note_id` (the one the run loop holds) as `proceed`
    decided, up to and including `stop_after`. Returns the new task number
    once W2 has run."""
    if not isinstance(proceed, Proceed):
        raise TypeError("book() takes only a Proceed from decide()")
    if stop_after not in BUILT:
        raise NotImplementedError("only W1 and W2 are built (tasks 4.1-4.2)")
    if proceed.note_id != note_id:
        raise WriteNotStarted("decision is for another Note", step="W1")
    project, form = _w1(proceed, guard, page, login, controls)
    if stop_after == "W1":
        return None
    return _w2(proceed, guard, page, controls, agent, project, form)


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
        project = booking.back_to_project(guard, page, window, proceed.pln)
        booking.check_project_document(
            guard, page, project, task_no, proceed.pdf_file_name
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
    except Exception as error:
        raise PartialWrite(
            "task not read back after Submit", note_id=note_id, step="W2"
        ) from error
