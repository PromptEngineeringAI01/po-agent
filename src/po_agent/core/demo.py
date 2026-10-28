"""The supervised demo: one trial PO, 2609017B -> pln_66935, booked the way
Joey does it by hand, with Joey's Enter before every write (decisions,
27 Oct 2026; screen map rows 01-14, 15b, 25-28).

1. Log in, Note Pool (Agent Pool, Locked), the one eligible 2609017B Note.
2. Open it; [Enter] take it: Send Email unticked, assigned to the agent.
3. Not linked yet; exactly one PDF link; download it into memory.
4. The PDF names B1 Homes and COMPACTION; its PO number is the file name's;
   its internal number is the Note's.
5. Reload, Projects search: the one B1 project is pln_66935; open it; its
   Client Internal No. matches; no Compaction Test task that isn't Cancelled.
6. [Enter] Create New Task, filled and read back; [Enter] Submit; the new
   task row shows.
7. [Enter] Hold with the hold note, no checkbox touched; read back On-hold.
8. Reload, reopen the Note; [Enter] Link to Project pln_66935; read back.
9. [Enter] Solved; read back.

`--until-check` runs steps 1-5 without taking the Note or asking anything:
it only reads (opening a Note and downloading change nothing, rows 02, 05).
On a failed check, an error or "n": the page's ARIA snapshot goes to
private/captures/test/demo-<step>.yml, and if the Note was taken, [Enter]
returns it to the pool (row 15b). The run then stops with its ALERT.
"""

import argparse
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from po_agent.b1 import reader_rules as rules
from po_agent.core import output
from po_agent.core import run as runs
from po_agent.core.config import Config
from po_agent.core.errors import PartialWrite, PoAgentError, WriteNotStarted
from po_agent.core.secrets import SecretName
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

# The one trial PO (Must never #6 allows its identifiers in committed files).
INTERNAL_NO = "2609017B"
PLN = "pln_66935"
DECLINED = "DECLINED"


@dataclass
class _Progress:
    step: str = "S1"
    note_id: str | None = None
    taken: bool = False  # the Note may be assigned to the agent
    written: bool = False  # Submit was pressed: a stop is now a partial write
    solved: bool = False


@contextmanager
def _browser(*, slow_mo: int, downloads: Path) -> Iterator[Page]:
    """As driver.open_browser, with downloads in the run's own folder (D2).

    Always headed: in headless Chromium the test site's content area takes no
    clicks (the body intercepts them; found 27 Oct 2026), and Joey watches."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False, slow_mo=slow_mo, downloads_path=downloads
        )
        try:
            page = browser.new_context(accept_downloads=True).new_page()
            page.set_default_timeout(driver.LOAD_TIMEOUT_MS)
            yield page
        finally:
            browser.close()


def _ask(step: output.AskStep, progress: _Progress) -> None:
    if output.ask(step):
        return
    if progress.written:
        raise PartialWrite("stopped at a prompt", step=progress.step, reason=DECLINED)
    raise WriteNotStarted("stopped at a prompt", step=progress.step, reason=DECLINED)


def run(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
) -> int:
    guard = ActionGuard()
    progress = _Progress()
    try:
        with _browser(slow_mo=options.slow_mo, downloads=downloads) as page:
            try:
                _steps(guard, page, config, credentials, options, summary, progress)
            except Exception as error:
                if getattr(error, "reason", None) != DECLINED:
                    if booking.save_snapshot(page, progress.step):
                        output.info("demo: page snapshot saved")
                if isinstance(error, PartialWrite):
                    summary.partial = 1
                if progress.taken and not progress.solved:
                    _offer_return(guard, page, config, progress)
                if isinstance(error, PoAgentError) and error.step is None:
                    error.step = progress.step
                raise
    finally:
        shutil.rmtree(downloads, ignore_errors=True)
    return 0


def _offer_return(
    guard: ActionGuard, page: Page, config: Config, progress: _Progress
) -> None:
    """[Enter] the Note back to the pool (row 15b); never raises."""
    if not output.ask("return the Note to the pool"):
        output.info("demo: note not returned to the pool")
        return
    try:
        window = booking.find_note_again(
            guard, page, str(config.base_url), progress.note_id
        )
        booking.return_note(guard, window, config.pool_name)
    except Exception:
        booking.save_snapshot(page, "return")
        output.info("demo: note not returned to the pool")
        return
    progress.taken = False
    output.info("demo: note returned to the pool")


def _steps(
    guard: ActionGuard,
    page: Page,
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    progress: _Progress,
) -> None:
    agent, pool, base_url = (
        config.agent_user_name,
        config.pool_name,
        str(config.base_url),
    )

    # 1. Log in, the Note Pool, the one 2609017B Note.
    driver.go_home(page, base_url)
    driver.login(
        guard,
        page,
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )
    output.info("logged in")
    panel = driver.open_note_pool(guard, page)
    booking.leave_menu(guard, page)
    driver.set_note_pool_filters(guard, panel, pool)
    output.info("note pool filters set")
    listing = driver.read_note_pool(guard, panel)
    eligible = runs.eligible_notes(listing.rows, config.title_rule, pool)
    found = [note for note in eligible if note.internal_no == INTERNAL_NO]
    summary.seen, summary.eligible = len(listing.rows), len(eligible)
    if len(found) != 1:
        raise WriteNotStarted("trial Note not found once", reason="NOTE_NOT_FOUND")
    note_id = progress.note_id = found[0].note_id
    output.info("demo: note found")

    # 2. Open the Note; [Enter] take it.
    progress.step = "S2"
    window = booking.open_note(guard, page, panel, note_id)
    if options.probe_link:
        # Link to Project's search on the untaken Note; nothing selected.
        booking.probe_link(guard, page, window, PLN)
        output.info("demo: link probe done")
        return
    if not options.until_check:
        _ask("take the Note", progress)
        progress.taken = True
        booking.take_note(guard, window, agent)
        output.info("demo: note taken")

    # 3. Not linked yet, exactly one PDF, downloaded into memory.
    progress.step = "S3"
    if not booking.has_link_to_project(window):
        raise WriteNotStarted("Note already linked", reason="NOTE_ALREADY_LINKED")
    file_name = rules.pdf_file_name(booking.download_hrefs(window))
    file_po = rules.po_from_file_name(file_name)
    body = booking.note_body(window, file_name)
    downloaded, data = booking.download_pdf(guard, page, window)
    if downloaded != file_name:
        raise WriteNotStarted("download not the linked file", reason="NO_PDF")
    output.info("demo: attachment downloaded")

    # 4. The PDF checks.
    progress.step = "S4"
    po_number = rules.check_pdf(rules.pdf_text(data), file_po, INTERNAL_NO)
    output.info("demo: pdf checks passed")

    # 5. Reload, Projects search, the project and its tasks.
    progress.step = "S5"
    driver.go_home(page, base_url)
    projects = booking.open_projects(guard, page)
    rows = booking.search_projects(guard, page, projects, INTERNAL_NO)
    pln = rules.match_project(rows, INTERNAL_NO)
    if pln != PLN:
        raise WriteNotStarted("not the trial project", reason="PROJECT_MISMATCH")
    project = booking.open_project(guard, page, projects, pln)
    if not rules.same_internal_no(booking.client_internal_no(project), INTERNAL_NO):
        raise WriteNotStarted("project internal number", reason="PROJECT_MISMATCH")
    tasks = rules.compaction_tasks(booking.task_rows(project))
    if rules.live_tasks(tasks):
        raise WriteNotStarted("Compaction Test task exists", reason="DUPLICATE_TASK")
    output.info("demo: project checked")
    if options.until_check:
        output.info("demo: read-only checks done")
        return

    # 6. [Enter] Create New Task, read back; [Enter] Submit; the new row.
    progress.step = "S6"
    _ask("create the Compaction Test task", progress)
    form = booking.open_task_form(guard, page, project)
    booking.fill_task_form(guard, form, po_number, body, file_name, data)
    output.info("demo: task form filled")
    _ask("submit the task", progress)
    progress.written = True
    booking.submit_task(guard, form)
    task_id = booking.wait_new_task(form, project, set(tasks))
    output.info("demo: task created")

    # 7. [Enter] Hold: the note typed, no checkbox touched, the dialog's Hold.
    progress.step = "S7"
    _ask("put the task On Hold", progress)
    dialog = booking.open_hold(guard, page, project, task_id)
    booking.fill_hold(guard, dialog)
    booking.confirm_hold(guard, page, dialog)
    booking.check_on_hold(project, task_id)
    output.info("demo: task on hold")

    # 8. Reload, the Note again; [Enter] Link to Project.
    progress.step = "S8"
    window = booking.find_note_again(guard, page, base_url, note_id)
    if booking.read_assignee(window) != agent:
        raise PartialWrite("Note no longer assigned to the agent")
    booking.untick_send_email(guard, window)
    _ask("link the Note to the project", progress)
    booking.link_project(guard, page, window, pln)
    output.info("demo: note linked")

    # 9. [Enter] Solved.
    progress.step = "S9"
    _ask("mark the Note Solved", progress)
    booking.mark_solved(guard, window, agent)
    progress.solved = True
    output.info("demo: note solved")
    summary.booked = 1
    output.note(
        output.Note(
            note_id=note_id,
            outcome="booked",
            po_number=po_number,
            pln=pln,
            task_id=task_id,
        )
    )
