"""The detailed run log (task 3.1): JSON lines in logs/<run_id>.jsonl,
written only with --detailed-log.

One object per event: {"ts", "run_id", "note_id", "step", "event", "ok"}
plus one name for some events (the guard action, the field read back, the
error's type, the skip reason). Never a value: no page text, no typed value.
Names pass through core/errors.identifier, so one that isn't an identifier
is written as "<redacted>".

Guard actions come from `guard.history` and are written, in order, before
the next event, so the log keeps the order 5.2 checks (Send Email read back
unticked after the last change and before each Assign).

The traceback event is written by `write_traceback` alone (cli.py calls it
for the error that ends the run), so it also works before a RunLog exists.

Every event but the traceback also goes to the safe trace (core/trace.py,
task 7.3), with or without --detailed-log: its name and pass/fail, the skip
reason or the error type, never more. The one exception is `booked`: the
trace's booked event also holds the task's pln, task number, internal
number and site, for the next runs' hold re-check (decisions, 11 Nov 2026, hold
re-check).
"""

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path

from po_agent.core.errors import identifier
from po_agent.core.trace import Trace
from po_agent.mysys.guard import ActionGuard

EVENTS = (
    "guard_action",
    "assignee_check",
    "email_notification_unticked",
    "read_back",
    "skip",
    "error",
    "hold_check",
)
NAME_KEYS = ("action", "field", "type", "reason")


class RunLog:
    """Writes no file when `directory` is None (no --detailed-log); `trace`
    gets every event but the traceback either way."""

    def __init__(
        self,
        run_id: str,
        guard: ActionGuard,
        directory: Path | None,
        trace: Trace | None = None,
    ) -> None:
        self.run_id = run_id
        self.guard = guard
        self.path = directory / f"{run_id}.jsonl" if directory is not None else None
        self.trace = trace
        self._written = 0  # guard.history entries already written

    def event(
        self,
        event: str,
        *,
        note_id: str | None,
        step: str | None,
        ok: bool,
        **name: str,
    ) -> None:
        if event not in EVENTS or set(name) - set(NAME_KEYS) or len(name) > 1:
            raise ValueError("event not in the run log contract")
        self.flush(note_id=note_id, step=step)
        names = {key: identifier(value) for key, value in name.items()}
        self._write(event, note_id, step, ok, names)

    def booked(
        self, *, note_id: str, pln: str, task_id: str, internal_no: str, site: str
    ) -> None:
        """A booking that passed W5: the run log's "booked" event (with
        --detailed-log) and the trace's booked event, which the next runs'
        hold re-check reads."""
        self.flush(note_id=note_id, step="W5")
        if self.trace is not None:
            self.trace.booked(
                note_id=note_id,
                pln=pln,
                task_id=task_id,
                internal_no=internal_no,
                site=site,
            )
        if self.path is None:
            return
        ids = {"pln": pln, "task_id": task_id, "internal_no": internal_no, "site": site}
        names = {key: identifier(value) for key, value in ids.items()}
        _append(self.path, _line(self.run_id, "booked", note_id, "W5", True, names))

    def flush(self, *, note_id: str | None, step: str | None) -> None:
        """Writes the guard actions taken since the last write, name only."""
        for action, outcome in self.guard.history[self._written :]:
            self._write(
                "guard_action",
                note_id,
                step,
                outcome == "done",
                {"action": identifier(action)},
            )
        self._written = len(self.guard.history)

    def _write(
        self,
        event: str,
        note_id: str | None,
        step: str | None,
        ok: bool,
        extra: dict[str, str | None],
    ) -> None:
        if self.trace is not None:
            self._trace(event, note_id, step, ok, extra)
        if self.path is None:
            return
        _append(self.path, _line(self.run_id, event, note_id, step, ok, extra))

    def _trace(
        self,
        event: str,
        note_id: str | None,
        step: str | None,
        ok: bool,
        extra: dict[str, str | None],
    ) -> None:
        assert self.trace is not None
        outcome = "pass" if ok else "fail"
        # .get: a missing name key is written as null, never a KeyError.
        name: str | None
        if event == "guard_action":
            name = extra.get("action")
        elif event == "read_back":
            field = extra.get("field")
            name = f"read_back.{field}" if field else None
        elif event == "skip":
            name, outcome = "decision", extra.get("reason")
        elif event == "error":
            name, outcome = "error", extra.get("type")
        else:
            name = event
        self.trace.event(note_id=note_id, step=step, name=name, outcome=outcome)


def write_traceback(directory: Path, run_id: str, error: BaseException) -> None:
    """Appends the error's traceback to <directory>/<run_id>.jsonl as one
    "traceback" event in the run log's line format (cli._report, with
    --detailed-log). Needs no RunLog: a config error is reported before one
    exists. Never goes to the safe trace. A file error is swallowed, so the
    ALERT and RUN_SUMMARY still go out."""
    # format_exception follows __cause__ and __context__ itself and honours
    # `raise ... from None`, so a Playwright message the guard hid stays
    # hidden; never walk the chain by hand
    # (https://docs.python.org/3.12/library/traceback.html#traceback.format_exception).
    text = "".join(traceback.format_exception(error))
    # A PoAgentError's note_id and step, or KillSwitch's and NoteTaken's.
    note_id = _str_or_none(getattr(error, "note_id", None))
    step = _str_or_none(getattr(error, "step", None))
    line = _line(run_id, "traceback", note_id, step, False, {"traceback": text})
    try:
        _append(directory / f"{run_id}.jsonl", line)
    except OSError:
        pass


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _line(
    run_id: str,
    event: str,
    note_id: str | None,
    step: str | None,
    ok: bool,
    extra: dict[str, str | None],
) -> str:
    line = {
        "ts": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "note_id": identifier(note_id),
        "step": identifier(step),
        "event": event,
        "ok": ok,
        **extra,
    }
    return json.dumps(line) + "\n"


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as file:
        file.write(line)
