"""The run controls (SPEC.md -> §8 run controls; docs/specs/spec.md §8),
built before any booking code (D1).

- Kill switch: `enabled` is read at run start (cli.py) and again from
  config/<site>.toml before every write step (`Controls.before_write`).
- Perth window: `run` and `run --decide-only` start only Mon-Fri 07:00-18:00
  in `run_window.tz`; `spike`, `demo` and seam 2 ignore it.
- Run cap: checked before each Note is started; a Note in progress is
  finished (Open question 7).
- Stale-Note stop (D6): `run` and `run --decide-only`, after login and
  before the eligible list is read; `spike` skips it.
- Assignee check (3.6), before W1 and W4 only (D7): a fresh Note Pool read,
  never the open Note window (row 23: it doesn't refresh its Assignee).
  The booker reopens the window it needs afterwards (row 25).

`now` is the one clock; tests replace it.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from playwright.sync_api import Locator, Page

from po_agent.core.config import Config, RunWindow, load_config
from po_agent.core.errors import ConfigError, PartialWrite, UnexpectedScreen
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

STEPS = ("W1", "W2", "W3", "W4", "W5")
# Nothing is submitted before W3 (W2 submits the task), so a stop there
# leaves nothing in MySys but the Note with the agent.
NOT_SUBMITTED = ("W1", "W2")
# D7: a fresh Note Pool read leaves the window the booker is in.
ASSIGNEE_CHECK_STEPS = ("W1", "W4")

AssigneeCheck = Callable[[str, str], None]


def now() -> datetime:
    return datetime.now(UTC)


def in_window(window: RunWindow, at: datetime) -> bool:
    """Mon-Fri (the only `days` value), start <= local time < end."""
    try:
        zone = ZoneInfo(window.tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError("unknown time zone", field="run_window.tz") from None
    local = at.astimezone(zone)
    return local.weekday() < 5 and window.start <= local.time() < window.end


def cap_reached(config: Config, started: datetime, done: int) -> bool:
    """Before starting a Note: `done` Notes started since `started`."""
    elapsed = now() - started
    return done >= config.max_notes_per_run or elapsed >= timedelta(
        minutes=config.max_run_minutes
    )


class KillSwitch(Exception):
    """`enabled = false` before W1 or W2: the run returns the Note to the
    pool in a fresh browser context and exits 0."""

    def __init__(
        self,
        detail: str = "kill switch on",
        *,
        note_id: str | None = None,
        step: str | None = None,
    ) -> None:
        self.note_id = note_id
        self.step = step
        super().__init__(detail)


def stale_note_stop(guard: ActionGuard, panel: Locator, agent: str) -> None:
    """A Pending Note still with the agent was left by an earlier run's
    partial write or failed return: the run takes no Note (D6). Only page 1
    can be read, so a second page stops the run too (after page 1's rows,
    so a stale Note there is named)."""
    listing = driver.read_agent_notes(guard, panel, agent)
    for row in listing.rows:
        if row.assignee == agent:
            raise UnexpectedScreen(
                "a Note is still assigned to the agent from an earlier run",
                note_id=row.note_id,
            )
    if listing.pages > 1:
        raise UnexpectedScreen("Note Pool has more pages: stale-Note read incomplete")


class NoteTaken(Exception):
    """A person has the Note at the W1 check (nothing written yet): the run
    closes the browser context and leaves the Note with them, outcome
    "untouched", reason NOTE_TAKEN."""

    def __init__(self, *, note_id: str, step: str) -> None:
        self.note_id = note_id
        self.step = step
        super().__init__("Note taken by someone else")


def assignee_check(
    guard: ActionGuard, page: Page, login: tuple[str, str, str], agent: str
) -> AssigneeCheck:
    """The check `Controls` runs before W1 and W4: reload, search the Note
    ID under All Pools, and the one row whose ID cell equals it must have
    Assignee `agent`. Someone else -> NoteTaken before W1. Before W4 the
    task exists and is on hold, so any failure is PartialWrite: the Note
    stays with the agent and is never returned to the pool, where it would
    look unbooked (3.6 review). `page` is the booker's browser context:
    build one check per context."""

    def check(note_id: str, step: str) -> None:
        _, listing = driver.search_note(guard, page, *login, note_id)
        row = driver.exact_row(listing, note_id)
        if row is None:
            raise UnexpectedScreen("Note not found once", note_id=note_id, step=step)
        if row.assignee != agent:
            raise NoteTaken(note_id=note_id, step=step)

    def checked(note_id: str, step: str) -> None:
        if step in NOT_SUBMITTED:
            check(note_id, step)
            return
        try:
            check(note_id, step)
        except NoteTaken:
            raise PartialWrite(
                "Note taken mid-booking", note_id=note_id, step=step
            ) from None
        except Exception as error:
            raise PartialWrite(
                "assignee check failed mid-booking", note_id=note_id, step=step
            ) from error

    return checked


class Controls:
    """The booker's gate before each W step. `assignee_check(note_id, step)`
    raises if the Note isn't with the agent (3.6)."""

    def __init__(
        self, site: str, config_dir: Path, assignee_check: AssigneeCheck
    ) -> None:
        self.site = site
        self.config_dir = config_dir
        self.assignee_check = assignee_check

    def before_write(self, note_id: str, step: str) -> None:
        if step not in STEPS:
            raise ValueError("not a write step")
        submitted = step not in NOT_SUBMITTED
        try:
            enabled = load_config(self.site, self.config_dir).enabled
        except ConfigError:
            if submitted:
                raise PartialWrite(
                    "config not readable mid-booking", note_id=note_id, step=step
                ) from None
            raise
        if not enabled:
            if submitted:
                raise PartialWrite(
                    "kill switch on mid-booking", note_id=note_id, step=step
                )
            raise KillSwitch(note_id=note_id, step=step)
        if step in ASSIGNEE_CHECK_STEPS:
            self.assignee_check(note_id, step)
