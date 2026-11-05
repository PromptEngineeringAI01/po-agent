"""The run modes (SPEC.md -> In the MVP). 1.8 builds the spike, 3.3 the
decide-only Note loop; 4.5 adds run.

The Note Pool is read once per run: later steps work through that fixed list
of Note IDs, so a Note skipped and returned to the pool isn't taken again in
the same run. Output is counts, skip reasons and identifiers only
(core/output.py).

Decide-only, for each eligible Note, oldest first by Note ID, up to
max_notes_per_run: find it ("Finding a Note again": reload, All Pools, the
exact ID) -> its Assignee is the pool, else NOTE_TAKEN and it is left alone
-> take it -> step 2a -> attachments -> download -> decide -> back to the
pool -> one NOTE line. The only writes are the two Assigns; the booker is
never called (Must never #7). Any error while the agent may hold a Note: the
browser closes, one return in a fresh browser context, then the run stops
(exit 1); if that return fails, the ALERT says the Note stays with the agent.
Before the list is read, the stale-Note stop (3.6, D6): a Pending Note
still with the agent stops the run (exit 1). The run cap is checked before
each Note is started (3.5); a KillSwitch from
`controls.before_write` takes the same return, then the run exits 0.

Run (4.5) is the same loop, but a PROCEED goes to the booker, `book()` W1-W5,
with `Controls` and the assignee check built for the browser context in
use -> NOTE "booked" with the task number. A skip goes back to the pool as
above. NoteTaken at the W1 check: that context is closed, NOTE "untouched"
NOTE_TAKEN, and the next Note runs in a fresh browser. From the Submit click
on (a PartialWrite, AccuracyBreach or GuardRefusal with step W2-W5; W2's
`before_write` errors come before the click and are not those types) the
Note is never returned to the pool, where it would look unbooked: its ALERT
names it, RUN_SUMMARY counts it as partial and the run stops; the stale-Note
stop holds every later run until Joey clears it (D6).
"""

import argparse
import shutil
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page

from po_agent.b1 import booker
from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import (
    TitleRule,
    check_note_and_pdf,
    check_second_reader,
    decide,
    eligible_internal_no,
)
from po_agent.b1.models import NotePoolRow, NoteSnapshot, Proceed, Skip, SkipReason
from po_agent.core import controls, output
from po_agent.core.config import Config
from po_agent.core.errors import (
    AccuracyBreach,
    GuardRefusal,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
    identifier,
)
from po_agent.core.runlog import RunLog
from po_agent.core.secrets import SecretName
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

# Run-output values only, not skip reasons (SPEC.md -> Code style).
DECIDE_ONLY = "DECIDE_ONLY"
NOTE_TAKEN = "NOTE_TAKEN"
# The booker's steps from the Submit click on (4.2): with one of these types,
# the task may exist in MySys. W2's before_write errors (KillSwitch, a config
# error) also say W2 but are other types and come before the click.
SUBMITTED_STEPS = ("W2", "W3", "W4", "W5")
SUBMITTED_TYPES = (PartialWrite, AccuracyBreach, GuardRefusal)
# Past W2's click every booker error is one of SUBMITTED_TYPES; any other
# error that names one of these steps is still a partial write.
AFTER_W2 = ("W3", "W4", "W5")


@dataclass(frozen=True)
class EligibleNote:
    note_id: str
    internal_no: str


def eligible_notes(
    rows: Sequence[NotePoolRow], rule: TitleRule, pool_name: str
) -> tuple[EligibleNote, ...]:
    """Step 0 on every row, in list order (newest first)."""
    found = []
    for row in rows:
        internal_no = eligible_internal_no(row, rule, pool_name)
        if internal_no is not None:
            found.append(EligibleNote(note_id=row.note_id, internal_no=internal_no))
    return tuple(found)


def oldest_first(found: Sequence[EligibleNote], cap: int) -> tuple[EligibleNote, ...]:
    """By Note ID as a number (a longer ID is newer), at most `cap`."""
    ordered = sorted(found, key=lambda note: (len(note.note_id), note.note_id))
    return tuple(ordered[:cap])


def _read_eligible(
    guard: ActionGuard, panel: Locator, config: Config, summary: output.RunSummary
) -> tuple[EligibleNote, ...]:
    """The run's one Note Pool read: step 0 on every row, counts printed."""
    listing = driver.read_note_pool(guard, panel)
    found = eligible_notes(listing.rows, config.title_rule, config.pool_name)
    summary.seen = len(listing.rows)
    summary.eligible = len(found)
    output.info(
        "note pool read: {rows} rows, {eligible} eligible",
        rows=len(listing.rows),
        eligible=len(found),
    )
    if listing.pages > 1:
        output.info(
            "note pool has more pages: only page 1 of {pages} read",
            pages=listing.pages,
        )
    return found


def spike(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
) -> int:
    """Log in, filter and read the Note Pool once, print counts. Read-only."""
    guard = ActionGuard()
    with driver.open_browser(headed=options.headed, slow_mo=options.slow_mo) as page:
        driver.go_home(page, str(config.base_url))
        driver.login(
            guard,
            page,
            credentials["mysys_test_username"],
            credentials["mysys_test_password"],
        )
        output.info("logged in")
        panel = driver.open_note_pool(guard, page)
        driver.set_note_pool_filters(guard, panel, config.pool_name)
        output.info("note pool filters set")
        _read_eligible(guard, panel, config, summary)
    return 0


@dataclass
class _Progress:
    note_id: str | None = None  # the Note being worked on
    taken: bool = False  # it may be assigned to the agent


class _Browser:
    """The run's one browser at a time (Playwright's sync API holds one per
    thread). `fresh()` closes the one open and opens another."""

    def __init__(self, options: argparse.Namespace, downloads: Path) -> None:
        self.options = options
        self.downloads = downloads
        self._open: AbstractContextManager[Page] | None = None

    def open(self) -> Page:
        browser = driver.open_browser(
            headed=self.options.headed,
            slow_mo=self.options.slow_mo,
            downloads=self.downloads,
        )
        page = browser.__enter__()
        self._open = browser
        return page

    def close(self) -> None:
        browser, self._open = self._open, None
        if browser is not None:
            browser.__exit__(None, None, None)

    def fresh(self) -> Page:
        self.close()
        return self.open()


def _close_context(page: Page) -> None:
    """Abandons whatever is open; a failed close never stops the run here."""
    try:
        page.context.close()
    except Exception:  # noqa: BLE001 - e.g. an already closed context
        pass


def _submitted(error: BaseException) -> bool:
    """The error came from the Submit click on: the task may exist."""
    step = getattr(error, "step", None)
    if isinstance(error, SUBMITTED_TYPES):
        return step in SUBMITTED_STEPS
    return isinstance(error, Exception) and step in AFTER_W2


def decide_only(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
) -> int:
    """The decide-only run. `downloads` is the run's po-agent-dl-<run_id>
    folder (D2), removed at the end; `logs` is set only with --detailed-log.
    The error event goes to the run log here; cli.py writes its traceback."""
    return _note_loop(config, credentials, options, summary, downloads, logs, None)


def book_run(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
    config_dir: Path,
) -> int:
    """The run that books (4.5): as decide-only, but a PROCEED is booked.
    `config_dir` is where `before_write` re-reads the kill switch."""
    return _note_loop(
        config, credentials, options, summary, downloads, logs, config_dir
    )


def _note_loop(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
    config_dir: Path | None,
) -> int:
    """`config_dir` None: decide-only, nothing booked."""
    guard = ActionGuard()
    log = RunLog(summary.run_id, guard, logs)
    login = (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )
    progress = _Progress()
    started = controls.now()
    browser = _Browser(options, downloads)
    try:
        try:
            page = browser.open()
            driver.go_home(page, login[0])
            driver.login(guard, page, login[1], login[2])
            output.info("logged in")
            panel = driver.open_note_pool(guard, page)
            driver.leave_menu(guard, page)
            controls.stale_note_stop(guard, panel, config.agent_user_name)
            driver.set_note_pool_filters(guard, panel, config.pool_name)
            output.info("note pool filters set")
            found = _read_eligible(guard, panel, config, summary)
            ordered = oldest_first(found, len(found))
            for done, note in enumerate(ordered):
                if controls.cap_reached(config, started, done):
                    output.info(
                        "run cap reached: {left} notes left for the next run",
                        left=len(ordered) - done,
                    )
                    break
                try:
                    with driver.note_downloads(page, downloads):
                        line = _one_note(
                            guard, page, config, login, log, note, progress, config_dir
                        )
                except controls.NoteTaken:
                    # At the W1 check, nothing written: the Note stays with
                    # the person, and the next Note gets a fresh browser.
                    _close_context(page)
                    progress.taken = False
                    line = _untouched(note)
                    page = browser.fresh()
                output.note(line)
                progress.note_id = None  # done: a later error isn't this Note's
                if line.outcome == "skipped":
                    summary.skipped += 1
                elif line.outcome == "booked":
                    summary.booked += 1
        finally:
            browser.close()
    except BaseException as error:
        submitted = _submitted(error)
        if submitted:
            summary.partial += 1
        # The return first: nothing else in here may stop it. Ctrl+C or a
        # system exit skips it, and the ALERT still names the Note. From the
        # Submit click on it is never returned.
        returned = not progress.taken or (
            not submitted
            and isinstance(error, Exception)
            and _return_after_stop(guard, config, options, login, log, progress.note_id)
        )
        try:
            log.event(
                "error",
                note_id=progress.note_id,
                step=getattr(error, "step", None),
                ok=False,
                type=type(error).__name__,
            )
        except OSError:
            pass  # the ALERT and RUN_SUMMARY still go out
        if submitted:
            if not isinstance(error, PoAgentError):
                raise PartialWrite(
                    "run stopped after Submit",
                    note_id=progress.note_id,
                    step=getattr(error, "step", None),
                ) from error
            if error.note_id is None:
                error.note_id = identifier(progress.note_id)
            raise
        if isinstance(error, controls.KillSwitch) and returned:
            output.info("kill switch on: run stopped")
            return 0
        # The original error stays in the traceback as the cause.
        if not returned:
            raise UnexpectedScreen(
                "run stopped; Note not returned to the pool",
                note_id=progress.note_id,
            ) from error
        if progress.note_id is None:
            raise
        if not isinstance(error, PoAgentError):
            raise UnexpectedScreen("run stopped", note_id=progress.note_id) from error
        if error.note_id is None:
            error.note_id = identifier(progress.note_id)
        raise
    finally:
        shutil.rmtree(downloads, ignore_errors=True)
    return 0


def _po_number(note: EligibleNote) -> str:
    return f"{note.internal_no}/{rules.PO_SUFFIX}"


def _untouched(note: EligibleNote) -> output.Note:
    return output.Note(
        note_id=note.note_id,
        outcome="untouched",
        reason=NOTE_TAKEN,
        po_number=_po_number(note),
    )


def _one_note(
    guard: ActionGuard,
    page: Page,
    config: Config,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
    config_dir: Path | None,
) -> output.Note:
    note_id = progress.note_id = note.note_id
    progress.taken = False
    po_number = _po_number(note)
    window = driver.find_note_again(guard, page, *login, note_id)
    in_pool = driver.read_assignee(window) == config.pool_name
    log.event("assignee_check", note_id=note_id, step="2", ok=in_pool)
    if not in_pool:  # a person has it: never taken
        return _untouched(note)
    progress.taken = True
    driver.take_note(guard, window, config.agent_user_name, log, note_id)
    decision = _decide(guard, page, config, login, log, note, window)
    if isinstance(decision, Skip) and decision.reason is SkipReason.UNEXPECTED_SCREEN:
        raise UnexpectedScreen("project not as searched", note_id=note_id, step="8")
    if config_dir is not None and isinstance(decision, Proceed):
        task_no = _book(guard, page, config, login, decision, config_dir)
        log.flush(note_id=note_id, step="W5")
        progress.taken = False  # booked: linked and Solved, never returned
        return output.Note(
            note_id=note_id,
            outcome="booked",
            po_number=po_number,
            pln=decision.pln,
            task_id=task_no,
        )
    # Found again and read before it goes back: the open window can be
    # minutes old, and a person may have taken the Note meanwhile.
    window = driver.find_note_again(guard, page, *login, note_id)
    still_ours = driver.read_assignee(window) == config.agent_user_name
    log.event("assignee_check", note_id=note_id, step="return", ok=still_ours)
    if not still_ours:  # a person has it now: left with them
        progress.taken = False
        return _untouched(note)
    driver.return_note(
        guard, window, config.agent_user_name, config.pool_name, log, note_id
    )
    progress.taken = False
    proceed = isinstance(decision, Proceed)
    reason = DECIDE_ONLY if proceed else decision.reason.value
    log.event("skip", note_id=note_id, step="decide", ok=True, reason=reason)
    return output.Note(
        note_id=note_id,
        outcome="skipped",
        reason=reason,
        po_number=po_number,
        pln=decision.pln if proceed else None,
    )


def _book(
    guard: ActionGuard,
    page: Page,
    config: Config,
    login: tuple[str, str, str],
    proceed: Proceed,
    config_dir: Path,
) -> str:
    """W1-W5 for this browser context: the assignee check holds its page."""
    check = controls.assignee_check(guard, page, login, config.agent_user_name)
    gate = controls.Controls("test", config_dir, check)  # test site only
    task_no = booker.book(
        proceed,
        note_id=proceed.note_id,
        guard=guard,
        page=page,
        login=login,
        controls=gate,
        agent=config.agent_user_name,
        stop_after="W5",
    )
    if task_no is None:  # stop_after W5 always returns it
        raise PartialWrite("no task number after W5", note_id=proceed.note_id)
    return task_no


def _decide(
    guard: ActionGuard,
    page: Page,
    config: Config,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    window: Locator,
) -> Skip | Proceed:
    """Steps 2a-11 on what the Note window and MySys show. The project is
    read only once the Note and PDF checks pass (that read reloads, so the
    window is gone after it)."""
    note_id = note.note_id
    linked = not driver.is_unlinked(window, log, note_id)
    names: tuple[str, ...] = ()
    pdf = None
    if not linked:
        names = driver.attachment_names(window)
        pdf = driver.download_pdf(guard, page, window)
    data = pdf.data if pdf else b""
    snapshot = NoteSnapshot(
        note_id=note_id,
        title="",  # the test title rule reads the body only
        body=driver.note_body(window, pdf.file_name) if pdf else "",
        attachment_names=names,
        project_linked=linked,
    )
    plumber = rules.text_layer(data) if pdf else ""
    pypdf = rules.pypdf_text_layer(data) if pdf else ""
    early = check_note_and_pdf(snapshot, note.internal_no, plumber)
    if isinstance(early, Skip):
        return early
    second = check_second_reader(plumber, pypdf)
    if second is not None:
        return second
    lookup = driver.project_lookup(guard, page, *login, note.internal_no, "test")
    decision = decide(
        snapshot,
        note.internal_no,
        plumber,
        pypdf,
        data,
        lookup,
        site="test",
        duplicate_ignores_cancelled=config.duplicate_ignores_cancelled,
    )
    return decision


def _return_after_stop(
    guard: ActionGuard,
    config: Config,
    options: argparse.Namespace,
    login: tuple[str, str, str],
    log: RunLog,
    note_id: str | None,
) -> bool:
    """One return through the normal path in a fresh browser context
    ("Finding a Note again"). True when the Note is no longer with the
    agent afterwards; never raises."""
    if note_id is None:
        return False
    try:
        with driver.open_browser(
            headed=options.headed, slow_mo=options.slow_mo
        ) as page:
            window = driver.find_note_again(guard, page, *login, note_id)
            if driver.read_assignee(window) == config.agent_user_name:
                driver.return_note(
                    guard,
                    window,
                    config.agent_user_name,
                    config.pool_name,
                    log,
                    note_id,
                )
    except Exception:
        return False
    return True
