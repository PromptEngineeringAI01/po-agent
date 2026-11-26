"""The run modes (SPEC.md -> In the MVP). 1.8 builds the spike, 3.3 the
decide-only Note loop; 4.5 adds run.

The Note Pool is read once per run: later steps work through that fixed list
of Note IDs, so a Note skipped and returned to the pool isn't taken again in
the same run. Output is counts, skip reasons and identifiers only
(core/output.py).

Decide-only, for each eligible Note, newest first by Note ID, up to
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

The peek (task 9.12; SPEC.md -> Client 2, The peek): a client with a client
file (Summit) decides every Note read-only before any take. Per Note: find
it again, read "Assignee:" (the original assignee, kept as read), then the
same reads and decision as above, with no take, no return, no Send Email
click and no write; the NOTE line is "untouched" with the skip reason, or
DECIDE_ONLY for a Note that would be booked. Its run cap counts Notes
opened (`max_peeks_per_run`) and bookings (`max_notes_per_run`).

The take (task 9.13; SPEC.md -> The take and the booking): in the run that
books, a peeked PROCEED is taken only now. The kill switch is re-read, the
Note found again, and its "Assignee:" must still read the original
assignee (else "untouched" NOTE_TAKEN, never taken); Agent 2 takes it as
B1's take does, and the window must still show Link to Project; then the
booker. A Note taken and stopped before Submit goes back, by the same stop
path as B1's, to its original assignee (`driver.return_to_assignee`); a
name in both of the Note window's lists or neither (`---` among them:
decisions, 26 Nov 2026) stays with the agent, ALERT "Note not returned".
`cli.py` refuses Summit's run until its booking lands (9.14).

Hold re-check (decisions, 11 Nov 2026, hold re-check): right after login,
before the stale-Note read and before any Note, both modes re-read the
tasks the safe trace says were booked on this site today and on the
previous working day, newest first, at most HOLD_RECHECK_CAP, read only. A
task no longer held, or not found, prints ALERT HOLD_LOST with the booking's Note ID and
the run goes on; Cancelled is not an alert. Each booking writes its trace
event after W5 for the next runs. No trace, no bookings: nothing is read
or printed.
"""

import argparse
import shutil
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from playwright.sync_api import Locator, Page

from po_agent.core import controls, output
from po_agent.core.client import Client, EligibleNote
from po_agent.core.config import ClientProfile, Config
from po_agent.core.errors import (
    AccuracyBreach,
    GuardRefusal,
    MorePages,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
    identifier,
)
from po_agent.core.models import (
    NotePoolFilters,
    NoteSnapshot,
    Proceed,
    Skip,
    SkipReason,
)
from po_agent.core.runlog import RunLog
from po_agent.core.secrets import SecretName, mysys_names
from po_agent.core.trace import Booking, Trace
from po_agent.mysys import booker, driver
from po_agent.mysys.guard import ActionGuard

# Run-output values only, not skip reasons (SPEC.md -> Code style).
DECIDE_ONLY = "DECIDE_ONLY"
NOTE_TAKEN = "NOTE_TAKEN"
# The booker's steps from the Submit click on (4.2): with one of these types,
# the task may exist in MySys. W2's before_write errors (KillSwitch, a config
# error) also say W2 but are other types and come before the click.
SUBMITTED_STEPS = ("W2", "W3", "W4", "W5")
SUBMITTED_TYPES = (PartialWrite, AccuracyBreach, GuardRefusal)
# Past W2's click every booker error is one of SUBMITTED_TYPES (Ctrl+C
# included); any other error that names one of these steps is still a
# partial write.
AFTER_W2 = ("W3", "W4", "W5")
# The hold re-check: tasks read per run, newest first (about 15-20 s each).
HOLD_RECHECK_CAP = 10
HOLD_LOST_DETAIL = {
    "not_on_hold": "booked task not on hold",
    "not_found": "booked task not found",
}


class Account(NamedTuple):
    """The run's MySys account (task 9.5; SPEC.md -> The separate run): the
    agent's user name in MySys and its secret pair. B1: Agent 1, the site's
    pair. Summit: its client file's agent (Agent 2) and its own pair, so the
    stale-Note stop's My Notes is Agent 2's."""

    agent: str
    username: SecretName
    password: SecretName


def client_name(profile: ClientProfile | None) -> str:
    """The run's client: B1 has no client file."""
    return "b1" if profile is None else profile.client


def account(config: Config, profile: ClientProfile | None) -> Account:
    username, password = mysys_names(config.site, client_name(profile))
    agent = config.agent_user_name if profile is None else profile.agent_user_name
    return Account(agent, username, password)


def newest_first(found: Sequence[EligibleNote], cap: int) -> tuple[EligibleNote, ...]:
    """By Note ID as a number (a longer ID is newer), newest first, at most
    `cap`. With no state between runs, an old Note that always skips (e.g.
    PROJECT_NOT_FOUND) would otherwise take every run's cap; newest first,
    it is retried each run after the newer ones (decisions, 10 Nov 2026,
    newest first)."""
    ordered = sorted(
        found, key=lambda note: (len(note.note_id), note.note_id), reverse=True
    )
    return tuple(ordered[:cap])


def _read_eligible(
    guard: ActionGuard,
    panel: Locator,
    client: Client,
    filters: NotePoolFilters,
    summary: output.RunSummary,
) -> tuple[EligibleNote, ...]:
    """The run's one Note Pool read: the client's step 0 on every row,
    counts printed. A second page is never read, so it stops the run before
    any Note is taken: MorePages, ALERT MORE_PAGES, exit 1 (7.2; decisions,
    5 Nov 2026). In run modes the stale-Note read, a superset, stops first.
    A client that filters by Source reads the Source column too (9.11)."""
    if filters.source is None:  # B1: the read as before there were two clients
        listing = driver.read_note_pool(guard, panel)
    else:
        listing = driver.read_note_pool(guard, panel, with_source=True)
    found = client.eligible(listing.rows)
    summary.seen = len(listing.rows)
    summary.eligible = len(found)
    output.info(
        "note pool read: {rows} rows, {eligible} eligible",
        rows=len(listing.rows),
        eligible=len(found),
    )
    if listing.pages > 1:
        raise MorePages("Note Pool has more pages: page 2 not read")
    return found


def spike(
    config: Config,
    client: Client,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    profile: ClientProfile | None = None,
) -> int:
    """Log in, filter and read the Note Pool once, print counts. Read-only.
    The client's filters are asked before the browser opens, so a client
    that refuses stops before any login (9.4 review). `profile`: the
    client's file, None for B1."""
    filters = client.filters()
    _, username, password = account(config, profile)
    guard = ActionGuard()
    with driver.open_browser(headed=options.headed, slow_mo=options.slow_mo) as page:
        driver.go_home(page, str(config.base_url))
        driver.login(guard, page, credentials[username], credentials[password])
        output.info("logged in")
        panel = driver.open_note_pool(guard, page)
        driver.set_note_pool_filters(guard, panel, filters)
        output.info("note pool filters set")
        _read_eligible(guard, panel, client, filters, summary)
    return 0


@dataclass
class _Progress:
    note_id: str | None = None  # the Note being worked on
    taken: bool = False  # it may be assigned to the agent
    original: str = ""  # its "Assignee:" as read before the take
    # The booker's own error once it is past the Submit click, kept where it
    # was raised: a later cleanup error must not hide it (4.5 review).
    submitted: BaseException | None = None


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
        if browser is None:
            return
        try:
            browser.__exit__(None, None, None)
        except Exception:  # noqa: BLE001 - e.g. Chromium already gone
            pass  # a failed close never hides the error that stopped the run

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
    return step in AFTER_W2


def decide_only(
    config: Config,
    client: Client,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
    trace: Trace | None = None,
    profile: ClientProfile | None = None,
) -> int:
    """The decide-only run. `downloads` is the run's po-agent-dl-<run_id>
    folder (D2), removed at the end; `logs` is set only with --detailed-log.
    The error event goes to the run log here; cli.py writes its traceback.
    `trace` gets the run log's events (7.3). `profile`: the client's file,
    None for B1."""
    return _note_loop(
        config,
        client,
        credentials,
        options,
        summary,
        downloads,
        logs,
        None,
        trace,
        profile,
    )


def book_run(
    config: Config,
    client: Client,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
    config_dir: Path,
    trace: Trace | None = None,
    profile: ClientProfile | None = None,
) -> int:
    """The run that books (4.5): as decide-only, but a PROCEED is booked.
    `config_dir` is where `before_write` re-reads the kill switch."""
    return _note_loop(
        config,
        client,
        credentials,
        options,
        summary,
        downloads,
        logs,
        config_dir,
        trace,
        profile,
    )


def _note_loop(
    config: Config,
    client: Client,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
    downloads: Path,
    logs: Path | None,
    config_dir: Path | None,
    trace: Trace | None,
    profile: ClientProfile | None,
) -> int:
    """`config_dir` None: decide-only, nothing booked. The client's filters
    and project rule are asked first, so a client that refuses stops before
    any login (the 9.4 review's guard). The
    run's account, caps, kill switch and hold re-check are its client's
    (`profile`, None for B1; task 9.5). A client file's client peeks
    (`_peek_note`, 9.12) and, in the run that books, takes a PROCEED only
    after it (9.13)."""
    filters = client.filters()
    client.project_rule()
    guard = ActionGuard()
    log = RunLog(summary.run_id, guard, logs, trace)
    run_as = account(config, profile)
    name = client_name(profile)
    agent = run_as.agent
    login = (
        str(config.base_url),
        credentials[run_as.username],
        credentials[run_as.password],
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
            if trace is not None:
                bookings = trace.recent_bookings(config.site, name)
                _hold_recheck(guard, page, client, login, log, bookings)
            if config.stale_read == "my_notes":
                # Live: the agent's My Notes, between two reloads, so the
                # Note Pool opens from a fresh page (decisions, 10 Nov 2026,
                # My Notes).
                driver.reload_home(guard, page, *login)
                controls.my_notes_stop(guard, page)
                driver.reload_home(guard, page, *login)
            panel = driver.open_note_pool(guard, page)
            driver.leave_menu(guard, page)
            if config.stale_read == "note_pool":
                controls.stale_note_stop(guard, panel, agent)
            driver.set_note_pool_filters(guard, panel, filters)
            output.info("note pool filters set")
            found = _read_eligible(guard, panel, client, filters, summary)
            try:
                # The opening guard actions (login, Note Pool, filters):
                # step 0, no Note, even when no Note follows (7.3 review).
                log.flush(note_id=None, step="0")
            except OSError:
                pass  # the run goes on
            ordered = newest_first(found, len(found))
            for done, note in enumerate(ordered):
                if controls.cap_reached(
                    config, started, done, profile=profile, booked=summary.booked
                ):
                    output.info(
                        "run cap reached: {left} notes left for the next run",
                        left=len(ordered) - done,
                    )
                    break
                try:
                    with driver.note_downloads(page, downloads):
                        if profile is not None:
                            line = _peek_note(
                                guard,
                                page,
                                config,
                                client,
                                login,
                                log,
                                note,
                                progress,
                                config_dir,
                                profile,
                            )
                        else:
                            line = _one_note(
                                guard,
                                page,
                                config,
                                client,
                                login,
                                log,
                                note,
                                progress,
                                config_dir,
                                profile,
                            )
                except controls.NoteTaken:
                    # At the W1 check, nothing written: the Note stays with
                    # the person, and the next Note gets a fresh browser.
                    _close_context(page)
                    progress.taken = False
                    line = _untouched(client, note)
                    page = browser.fresh()
                output.note(line)
                progress.note_id = None  # done: a later error isn't this Note's
                if line.outcome == "skipped":
                    summary.skipped += 1
                elif line.outcome == "booked":
                    summary.booked += 1
        finally:
            browser.close()
    except BaseException as caught:
        # Past the Submit click, the booker's own error is the one reported,
        # whatever a cleanup raised after it.
        error = progress.submitted or caught
        submitted = progress.submitted is not None or _submitted(error)
        if submitted:
            summary.partial += 1
        # The return first: nothing else in here may stop it. Ctrl+C or a
        # system exit skips it, and the ALERT still names the Note. From the
        # Submit click on it is never returned.
        returned = not progress.taken or (
            not submitted
            and isinstance(error, Exception)
            and _return_after_stop(
                guard,
                agent,
                client,
                options,
                login,
                log,
                progress.note_id,
                progress.original,
                profile,
            )
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
            # The booker's, even when a cleanup raised after it; its own
            # cause (or `from None`) is kept for the traceback.
            raise error from error.__cause__
        if isinstance(error, controls.KillSwitch) and returned:
            output.info("kill switch on: run stopped")
            return 0
        # The original error stays in the traceback as the cause.
        if not returned and profile is None:  # B1's goes back to its pool
            raise UnexpectedScreen(
                "run stopped; Note not returned to the pool",
                note_id=progress.note_id,
            ) from error
        if not returned:  # to its original assignee: a user, a pool or ---
            raise UnexpectedScreen(
                "run stopped; Note not returned", note_id=progress.note_id
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


def _hold_recheck(
    guard: ActionGuard,
    page: Page,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    bookings: Sequence[Booking],
) -> None:
    """Re-reads each recent booking's task, read only (driver.recheck_hold),
    then reloads so the Note Pool opens from a fresh page. The reads' guard
    actions are traced with no Note; each result is a hold_check event under
    the booking's Note. A read that fails raises, as any read does, before
    any Note is taken."""
    if not bookings:
        return
    checked = bookings[:HOLD_RECHECK_CAP]
    lost = 0
    for booked in checked:
        state = driver.recheck_hold(guard, page, *login, booked, client.project_rule())
        held = state not in HOLD_LOST_DETAIL
        try:
            log.flush(note_id=None, step="0")
            log.event("hold_check", note_id=booked.note_id, step="0", ok=held)
        except OSError:
            pass  # the ALERT still goes out
        if not held:
            lost += 1
            output.alert(
                "HOLD_LOST",
                output.Alert(
                    note_id=booked.note_id,
                    step="hold_check",
                    detail=HOLD_LOST_DETAIL[state],
                ),
            )
    output.info(
        "hold re-check: {checked} checked, {lost} not on hold",
        checked=len(checked),
        lost=lost,
    )
    if len(bookings) > len(checked):
        output.info(
            "hold re-check cap reached: {left} tasks not checked",
            left=len(bookings) - len(checked),
        )
    driver.reload_home(guard, page, *login)


def _untouched(client: Client, note: EligibleNote) -> output.Note:
    return output.Note(
        note_id=note.note_id,
        outcome="untouched",
        reason=NOTE_TAKEN,
        po_number=client.po_number(note),
    )


def _one_note(
    guard: ActionGuard,
    page: Page,
    config: Config,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
    config_dir: Path | None,
    profile: ClientProfile | None = None,
) -> output.Note:
    """One Note, as the run's agent for the run's client (`profile`, None
    for B1)."""
    agent = account(config, profile).agent
    note_id = progress.note_id = note.note_id
    progress.taken = False
    po_number = client.po_number(note)
    window = driver.find_note_again(guard, page, *login, note_id)
    assignee = progress.original = driver.read_assignee(window)
    in_pool = assignee == config.pool_name
    log.event("assignee_check", note_id=note_id, step="2", ok=in_pool)
    if not in_pool:  # a person has it: never taken
        return _untouched(client, note)
    progress.taken = True
    driver.take_note(guard, window, agent, log, note_id)
    decision = _decide(guard, page, client, login, log, note, window)
    if isinstance(decision, Skip) and decision.reason is SkipReason.UNEXPECTED_SCREEN:
        raise UnexpectedScreen("project not as searched", note_id=note_id, step="8")
    if config_dir is not None and isinstance(decision, Proceed):
        return _book_note(
            guard,
            page,
            config,
            client,
            login,
            log,
            note,
            progress,
            decision,
            config_dir,
            profile,
        )
    # Found again and read before it goes back: the open window can be
    # minutes old, and a person may have taken the Note meanwhile.
    window = driver.find_note_again(guard, page, *login, note_id)
    still_ours = driver.read_assignee(window) == agent
    log.event("assignee_check", note_id=note_id, step="return", ok=still_ours)
    if not still_ours:  # a person has it now: left with them
        progress.taken = False
        return _untouched(client, note)
    driver.return_note(
        guard, window, agent, client.return_target(assignee), log, note_id
    )
    progress.taken = False
    if isinstance(decision, Proceed):
        reason, pln = DECIDE_ONLY, decision.pln
    else:
        reason, pln = decision.reason.value, None
    log.event("skip", note_id=note_id, step="decide", ok=True, reason=reason)
    return output.Note(
        note_id=note_id,
        outcome="skipped",
        reason=reason,
        po_number=po_number,
        pln=pln,
    )


def _peek_note(
    guard: ActionGuard,
    page: Page,
    config: Config,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
    config_dir: Path | None,
    profile: ClientProfile,
) -> output.Note:
    """SPEC's peek, steps 1-4: found again (All Pools, the exact ID) and
    opened, "Assignee:" read as the original assignee, then _decide's reads
    (link, attachments, download, body, project lookup) and the decision.
    Only read-only actions: an untouched Note, and every Note in
    decide-only (`config_dir` None), is never taken, so never returned. A
    Client Internal No. that differs stops the run, as B1's. In the run
    that books, a PROCEED goes on to the take (`_take_and_book`)."""
    note_id = progress.note_id = note.note_id
    progress.taken = False
    window = driver.find_note_again(guard, page, *login, note_id)
    original = progress.original = driver.read_assignee(window)
    decision = _decide(guard, page, client, login, log, note, window, original)
    if isinstance(decision, Skip) and decision.reason is SkipReason.UNEXPECTED_SCREEN:
        raise UnexpectedScreen("project not as searched", note_id=note_id, step="8")
    if config_dir is not None and isinstance(decision, Proceed):
        return _take_and_book(
            guard,
            page,
            config,
            client,
            login,
            log,
            note,
            progress,
            decision,
            config_dir,
            profile,
        )
    if isinstance(decision, Proceed):
        reason, pln = DECIDE_ONLY, decision.pln
    else:
        reason, pln = decision.reason.value, None
    log.event("skip", note_id=note_id, step="decide", ok=True, reason=reason)
    return output.Note(
        note_id=note_id,
        outcome="untouched",
        reason=reason,
        po_number=client.po_number(note),
        pln=pln,
    )


def _take_and_book(
    guard: ActionGuard,
    page: Page,
    config: Config,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
    proceed: Proceed,
    config_dir: Path,
    profile: ClientProfile,
) -> output.Note:
    """SPEC's take, once the peek decided PROCEED: the kill switch re-read
    (KillSwitch: nothing taken); found again, its "Assignee:" must still
    read the original assignee the peek read (`progress.original`), else a
    person has it: "untouched" NOTE_TAKEN, never taken; Agent 2 takes it
    (B1's take: Send Email unticked and read back, user = the agent, pool
    --Select Pool--, one Assign, read back); the window must still show
    Link to Project; then the booker. A stop from the take until the
    Submit click returns it to the original assignee (`_return_after_stop`)."""
    note_id = note.note_id
    agent = account(config, profile).agent
    check = controls.assignee_check(guard, page, login, agent, log)
    gate = controls.Controls(
        config.site, config_dir, check, client=client_name(profile)
    )
    gate.before_take(note_id)
    window = driver.find_note_again(guard, page, *login, note_id)
    same = driver.read_assignee(window) == progress.original
    log.event("assignee_check", note_id=note_id, step="2", ok=same)
    if not same:  # a person has it now: never taken
        return _untouched(client, note)
    progress.taken = True
    driver.take_note(guard, window, agent, log, note_id)
    if not driver.is_unlinked(window, log, note_id):
        raise UnexpectedScreen(
            "Link to Project not shown after the take", note_id=note_id, step="2a"
        )
    return _book_note(
        guard,
        page,
        config,
        client,
        login,
        log,
        note,
        progress,
        proceed,
        config_dir,
        profile,
    )


def _book_note(
    guard: ActionGuard,
    page: Page,
    config: Config,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    progress: _Progress,
    proceed: Proceed,
    config_dir: Path,
    profile: ClientProfile | None,
) -> output.Note:
    """W1-W5 for a Note the agent holds, then the trace's booked event and
    the NOTE line "booked". From the Submit click on, the booker's own
    error is kept (`progress.submitted`): the Note is never returned."""
    note_id = note.note_id
    try:
        task_no = _book(
            guard,
            page,
            config,
            client,
            login,
            proceed,
            config_dir,
            note_id=note_id,
            log=log,
            profile=profile,
        )
    except BaseException as error:
        if _submitted(error):
            progress.submitted = error
        raise
    progress.taken = False  # booked: linked and Solved, never returned
    try:
        # Flushes W5's guard actions, then the trace's booked event for the
        # next runs' hold re-check.
        log.booked(
            note_id=note_id,
            pln=proceed.pln,
            task_id=task_no,
            internal_no=note.internal_no,
            site=config.site,
            client=client_name(profile),
        )
    except OSError:
        pass  # the NOTE line still goes out
    return output.Note(
        note_id=note_id,
        outcome="booked",
        po_number=client.po_number(note),
        pln=proceed.pln,
        task_id=task_no,
    )


def _book(
    guard: ActionGuard,
    page: Page,
    config: Config,
    client: Client,
    login: tuple[str, str, str],
    proceed: Proceed,
    config_dir: Path,
    *,
    note_id: str,
    log: RunLog | None = None,
    profile: ClientProfile | None = None,
) -> str:
    """W1-W5 for this browser context: the assignee check holds its page.
    `note_id` is the Note the run holds: a decision for another Note is
    WriteNotStarted before W1."""
    agent = account(config, profile).agent
    check = controls.assignee_check(guard, page, login, agent, log)
    gate = controls.Controls(
        config.site, config_dir, check, client=client_name(profile)
    )
    task_no = booker.book(
        proceed,
        note_id=note_id,
        guard=guard,
        page=page,
        login=login,
        controls=gate,
        agent=agent,
        project_rule=client.project_rule(),
        document_type=client.document_type(),
        stop_after="W5",
        log=log,
    )
    if task_no is None:  # stop_after W5 always returns it
        raise PartialWrite("no task number after W5", note_id=note_id, step="W5")
    return task_no


def _decide(
    guard: ActionGuard,
    page: Page,
    client: Client,
    login: tuple[str, str, str],
    log: RunLog,
    note: EligibleNote,
    window: Locator,
    assignee: str = "",
) -> Skip | Proceed:
    """Steps 2a-11 on what the Note window and MySys show: the driver reads,
    the client decides. The client calls the project lookup only once the
    Note and PDF checks pass (that read reloads, so the window is gone after
    it). `assignee`: "Assignee:" as the peek read it ("" for B1)."""
    note_id = note.note_id
    linked = not driver.is_unlinked(window, log, note_id)
    names: tuple[str, ...] = ()
    pdf = None
    if not linked:
        names = driver.attachment_names(window)
        pdf = driver.download_pdf(guard, page, window)
    snapshot = NoteSnapshot(
        note_id=note_id,
        # The Note Pool cell's title: B1's step 0 read its rule there and
        # keeps ""; Summit's decision reads its company and PO.
        title=note.title,
        body=driver.note_body(window, client.body_rule(pdf.file_name)) if pdf else "",
        attachment_names=names,
        project_linked=linked,
        assignee=assignee,
    )
    return client.decide(
        snapshot,
        note,
        pdf.data if pdf else None,
        lambda: driver.project_lookup(
            guard, page, *login, note.internal_no, client.project_rule()
        ),
    )


def _return_after_stop(
    guard: ActionGuard,
    agent: str,
    client: Client,
    options: argparse.Namespace,
    login: tuple[str, str, str],
    log: RunLog,
    note_id: str | None,
    original: str,
    profile: ClientProfile | None,
) -> bool:
    """One return through the normal path in a fresh browser context
    ("Finding a Note again"): B1's to its pool; a client file's client's
    to the original assignee (`original`, "Assignee:" as read before the
    take; task 9.13). True when the Note is no longer with the agent
    afterwards; never raises."""
    if note_id is None:
        return False
    target = client.return_target(original)
    try:
        with driver.open_browser(
            headed=options.headed, slow_mo=options.slow_mo
        ) as page:
            window = driver.find_note_again(guard, page, *login, note_id)
            if driver.read_assignee(window) != agent:
                pass  # a person has it now: left with them
            elif profile is None:  # B1: its pool, as before there were two clients
                driver.return_note(guard, window, agent, target, log, note_id)
            else:
                driver.return_to_assignee(guard, window, agent, target, log, note_id)
    except Exception:  # noqa: BLE001 - never raises: any failure is "not returned"
        return False
    return True
