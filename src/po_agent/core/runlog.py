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

Every event but the traceback also goes to the safe trace (core/trace.py,
task 7.3), with or without --detailed-log: its name and pass/fail, the skip
reason or the error type, never more.
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

    def error(
        self, error: BaseException, *, note_id: str | None, step: str | None
    ) -> None:
        """The error's type name, then its traceback as a separate event."""
        self.event(
            "error", note_id=note_id, step=step, ok=False, type=type(error).__name__
        )
        # format_exception honours `raise ... from None`.
        text = "".join(traceback.format_exception(error))
        self._write("traceback", note_id, step, False, {"traceback": text})

    def _write(
        self,
        event: str,
        note_id: str | None,
        step: str | None,
        ok: bool,
        extra: dict[str, str | None],
    ) -> None:
        if self.trace is not None and event != "traceback":
            self._trace(event, note_id, step, ok, extra)
        if self.path is None:
            return
        line = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "note_id": identifier(note_id),
            "step": identifier(step),
            "event": event,
            "ok": ok,
            **extra,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(json.dumps(line) + "\n")

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
        if event == "guard_action":
            name = extra["action"]
        elif event == "read_back":
            name = f"read_back.{extra['field']}"
        elif event == "skip":
            name, outcome = "decision", extra["reason"]
        elif event == "error":
            name, outcome = "error", extra["type"]
        else:
            name = event
        self.trace.event(note_id=note_id, step=step, name=name, outcome=outcome)
