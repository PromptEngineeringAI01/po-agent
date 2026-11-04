"""The booker: W1-W5 with read-back (SPEC.md -> MySys screen rules;
docs/specs/spec.md §6). Task 4.1 builds W1; 4.2-4.4 add the later steps.

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
"""

from playwright.sync_api import Page

from po_agent.b1.models import Proceed
from po_agent.core.controls import Controls
from po_agent.core.errors import GuardRefusal, WriteNotStarted
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

# The steps built so far; `stop_after` must name one of them.
BUILT = ("W1",)


def book(
    proceed: Proceed,
    *,
    note_id: str,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
    stop_after: str,
) -> None:
    """Books the Note `note_id` (the one the run loop holds) as `proceed`
    decided, up to and including `stop_after`."""
    if not isinstance(proceed, Proceed):
        raise TypeError("book() takes only a Proceed from decide()")
    if stop_after not in BUILT:
        raise NotImplementedError("only W1 is built (task 4.1)")
    if proceed.note_id != note_id:
        raise WriteNotStarted("decision is for another Note", step="W1")
    _w1(proceed, guard, page, login, controls)


def _w1(
    proceed: Proceed,
    guard: ActionGuard,
    page: Page,
    login: tuple[str, str, str],
    controls: Controls,
) -> None:
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
        try:
            page.context.close()  # abandons the form: nothing is saved
        except Exception:  # noqa: BLE001 - e.g. a dead event loop
            pass  # the original error below is the one that counts
        if isinstance(error, GuardRefusal | WriteNotStarted):
            raise
        raise WriteNotStarted(
            "Create New Task not filled", note_id=note_id, step="W1"
        ) from error
