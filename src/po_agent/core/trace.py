"""The safe trace (task 7.3): one JSON line per event in
<trace_dir>/<YYYY-MM-DD>.jsonl, on every run whose config sets `trace_dir`
and whose trace folder's parent exists (the Mac Mini wrapper makes
~/Library/Logs/po-agent; the laptop and CI have none, so they write nothing).

An event is a `TraceEvent` and nothing else: run_id, ts (UTC), note_id, step,
name (a check or the guard's mapped control name), outcome (pass, fail, a
skip reason or an error type) and duration_ms (since the run's previous
event). Every field has a closed type; a value outside it is written as null,
so page text, a PDF line, an address or a Note body can't be written even if
code passed one. No traceback, no message, no typed value.

The day's file is named by the date in the run window's time zone, so one
working day is one file. At run start, files named <date>.jsonl older than
RETENTION_DAYS are deleted; nothing else in the folder is touched. Writing
the trace never stops a run: an OSError is dropped.
"""

import re
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_serializer,
)

from po_agent.b1.models import SkipReason
from po_agent.mysys.guard import ALLOWLIST

RETENTION_DAYS = 90
RUN_ID = r"^\d{8}T\d{6}Z-[0-9a-f]{4}$"
_FILE_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")

STEPS = frozenset(
    {str(n) for n in range(12)}
    | {"2a", "W1", "W2", "W3", "W4", "W5", "return", "decide"}
)
# The run log's checks (core/runlog.py) and the trace's own events.
CHECKS = frozenset(
    {
        "assignee_check",
        "email_notification_unticked",
        "read_back.link_to_project",
        "read_back.assignee",
        "read_back.log_line",
        "read_back.status",
        "decision",
        "error",
        "run_end",
    }
)
NAMES = CHECKS | frozenset(ALLOWLIST)
# DECIDE_ONLY: core/run.py's skip reason for a decide-only PROCEED.
OUTCOMES = frozenset({"pass", "fail", "DECIDE_ONLY"} | {r.value for r in SkipReason})
# An error type is a class name: type(error).__name__, never a message.
_ERROR_TYPE = re.compile(r"[A-Z][A-Za-z0-9]{0,63}")
_NOTE_ID = re.compile(r"[0-9]{1,12}")


def _one_of(allowed: frozenset[str]):
    def check(value: str) -> str:
        if value not in allowed:
            raise ValueError("not in the trace contract")
        return value

    return AfterValidator(check)


def _matches(pattern: re.Pattern[str]):
    def check(value: str) -> str:
        if not pattern.fullmatch(value):
            raise ValueError("not in the trace contract")
        return value

    return AfterValidator(check)


def _outcome(value: str) -> str:
    if value in OUTCOMES or _ERROR_TYPE.fullmatch(value):
        return value
    raise ValueError("not in the trace contract")


NoteId = Annotated[str, _matches(_NOTE_ID)]
Step = Annotated[str, _one_of(STEPS)]
Name = Annotated[str, _one_of(NAMES)]
Outcome = Annotated[str, AfterValidator(_outcome)]


class TraceEvent(BaseModel):
    # extra="forbid": no field beyond these
    # (https://docs.pydantic.dev/latest/api/config/).
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(pattern=RUN_ID)
    ts: datetime
    note_id: NoteId | None
    step: Step | None
    name: Name | None
    outcome: Outcome | None
    duration_ms: int = Field(ge=0)

    @field_serializer("ts")
    def _iso(self, ts: datetime) -> str:
        # As the run log writes it: 2026-11-02T02:00:00+00:00.
        return ts.isoformat()


# Each field's closed type, to drop a value outside it before the event is
# built (https://docs.pydantic.dev/latest/concepts/type_adapter/).
_FIELD_TYPES: dict[str, TypeAdapter[str | None]] = {
    "note_id": TypeAdapter(NoteId | None),
    "step": TypeAdapter(Step | None),
    "name": TypeAdapter(Name | None),
    "outcome": TypeAdapter(Outcome | None),
}


def _kept(field: str, value: object) -> str | None:
    """The value if it fits the field's closed type, else None."""
    try:
        return _FIELD_TYPES[field].validate_python(value)
    except ValidationError:
        return None


class Trace:
    """Writes nothing until `start()` names a folder whose parent exists."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.path: Path | None = None
        self._last = time.monotonic()

    def start(self, directory: Path | None, today: date) -> None:
        """Deletes the files older than RETENTION_DAYS, then writes to
        today's file. No folder, no parent folder, or one that can't be
        read: no trace, and the run goes on."""
        if directory is None:
            return
        try:
            if not directory.parent.is_dir():
                return
            directory.mkdir(exist_ok=True)
            _delete_old(directory, today)
        except OSError:
            return
        self.path = directory / f"{today.isoformat()}.jsonl"
        self._last = time.monotonic()

    def event(
        self,
        *,
        note_id: str | None,
        step: str | None,
        name: str | None,
        outcome: str | None,
    ) -> None:
        if self.path is None:
            return
        now = time.monotonic()
        values = {"note_id": note_id, "step": step, "name": name, "outcome": outcome}
        try:
            line = TraceEvent(
                run_id=self.run_id,
                ts=datetime.now(UTC),
                duration_ms=max(0, round((now - self._last) * 1000)),
                **{field: _kept(field, value) for field, value in values.items()},
            )
        except ValidationError:
            return  # e.g. a run_id not in the contract: nothing written
        self._last = now
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(line.model_dump_json() + "\n")
        except OSError:
            pass  # the run goes on; its output is unchanged

    def end(self, error: BaseException | None) -> None:
        """The run's last event: pass, or the reported error's type."""
        self.event(
            note_id=getattr(error, "note_id", None),
            step=getattr(error, "step", None),
            name="run_end",
            outcome="pass" if error is None else type(error).__name__,
        )


def _delete_old(directory: Path, today: date) -> None:
    oldest = today - timedelta(days=RETENTION_DAYS)
    for path in directory.iterdir():
        found = _FILE_NAME.fullmatch(path.name)
        if not found or not path.is_file() or path.is_symlink():
            continue
        try:
            day = date.fromisoformat(found.group(1))
        except ValueError:
            continue
        if day < oldest:
            try:
                path.unlink()
            except OSError:
                continue  # one stuck file doesn't stop the trace
