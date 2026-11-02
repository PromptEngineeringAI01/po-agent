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
pool -> one NOTE line. The only writes are the two Assigns; no booking code
is imported (Must never #7). Any error while the agent may hold a Note: the
browser closes, one return in a fresh browser context, then the run stops
(exit 1); if that return fails, the ALERT says the Note stays with the agent.
"""

import argparse
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import (
    TitleRule,
    check_note_and_pdf,
    check_second_reader,
    decide,
    eligible_internal_no,
)
from po_agent.b1.models import NotePoolRow, NoteSnapshot, Proceed, Skip, SkipReason
from po_agent.core import output
from po_agent.core.config import Config
from po_agent.core.errors import PoAgentError, UnexpectedScreen
from po_agent.core.runlog import RunLog
from po_agent.core.secrets import SecretName
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

# Run-output values only, not skip reasons (SPEC.md -> Code style).
DECIDE_ONLY = "DECIDE_ONLY"
NOTE_TAKEN = "NOTE_TAKEN"


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
    guard = ActionGuard()
    log = RunLog(summary.run_id, guard, logs)
    login = (
        str(config.base_url),
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )
    progress = _Progress()
    try:
        with driver.open_browser(
            headed=options.headed, slow_mo=options.slow_mo, downloads=downloads
        ) as page:
            driver.go_home(page, login[0])
            driver.login(guard, page, login[1], login[2])
            output.info("logged in")
            panel = driver.open_note_pool(guard, page)
            driver.leave_menu(guard, page)
            driver.set_note_pool_filters(guard, panel, config.pool_name)
            output.info("note pool filters set")
            found = _read_eligible(guard, panel, config, summary)
            for note in oldest_first(found, config.max_notes_per_run):
                with driver.note_downloads(page, downloads):
                    line = _one_note(guard, page, config, login, log, note, progress)
                output.note(line)
                if line.outcome == "skipped":
                    summary.skipped += 1
    except Exception as error:
        if isinstance(error, PoAgentError) and error.note_id is None:
            error.note_id = progress.note_id
        log.event(
            "error",
            note_id=progress.note_id,
            step=getattr(error, "step", None),
            ok=False,
            type=type(error).__name__,
        )
        if progress.taken and not _return_after_stop(
            guard, config, options, login, log, progress.note_id
        ):
            # The original error stays in the traceback as the cause.
            raise UnexpectedScreen(
                "run stopped; Note not returned to the pool",
                note_id=progress.note_id,
            ) from error
        raise
    finally:
        shutil.rmtree(downloads, ignore_errors=True)
    return 0


def _one_note(
    guard: ActionGuard,
    page: Page,
    config: Config,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
) -> output.Note:
    note_id = progress.note_id = note.note_id
    progress.taken = False
    po_number = f"{note.internal_no}/{rules.PO_SUFFIX}"
    window = driver.find_note_again(guard, page, *login, note_id)
    in_pool = driver.read_assignee(window) == config.pool_name
    log.event("assignee_check", note_id=note_id, step="2", ok=in_pool)
    if not in_pool:  # a person has it: never taken
        return output.Note(
            note_id=note_id, outcome="untouched", reason=NOTE_TAKEN, po_number=po_number
        )
    progress.taken = True
    driver.take_note(guard, window, config.agent_user_name, log, note_id)
    decision, still_open = _decide(guard, page, config, login, log, note, window)
    if isinstance(decision, Skip) and decision.reason is SkipReason.UNEXPECTED_SCREEN:
        raise UnexpectedScreen("project not as searched", note_id=note_id, step="8")
    if still_open is None:  # the project read reloaded: the window is gone
        still_open = driver.find_note_again(guard, page, *login, note_id)
    driver.return_note(
        guard, still_open, config.agent_user_name, config.pool_name, log, note_id
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


def _decide(
    guard: ActionGuard,
    page: Page,
    config: Config,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    window: Locator,
) -> tuple[Skip | Proceed, Locator | None]:
    """Steps 2a-11 on what the Note window and MySys show. The project is
    read only once the Note and PDF checks pass; that read reloads, so the
    window comes back as None."""
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
        return early, window
    second = check_second_reader(plumber, pypdf)
    if second is not None:
        return second, window
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
    return decision, None


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
