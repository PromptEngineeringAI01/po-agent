"""The run output (stdout) contract (SPEC.md -> Code style). The ONLY module
that prints; scripts/guard_check.py fails on `print` anywhere else in src/.

    INFO  <fixed message>
    NOTE  {"note_id": ..., "outcome": ..., ...}
    ALERT <KIND> {"note_id": ..., "step": ..., "detail": ...}
    RUN_SUMMARY {"run_id": ..., ...}

INFO messages are fixed templates. NOTE, ALERT and RUN_SUMMARY are pydantic
models with exactly the contract fields; identifier fields that don't look
like an identifier are replaced by "<redacted>". An ALERT detail is a typed
error's message (a fixed detail plus identifiers, core/errors.py) or a fixed
detail in cli.py. So PDF text, addresses and Note bodies can't reach stdout.
"""

import json
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from po_agent.core.errors import identifier

InfoMessage = Literal[
    "config loaded",
    "spike not built yet",
    "decide-only not built yet",
]
AlertKind = Literal[
    "PARTIAL_WRITE",
    "ACCURACY_BREACH",
    "GUARD_REFUSAL",
    "UNEXPECTED_SCREEN",
    "LOGIN_FAILED",
    "CONFIG",
]
Mode = Literal["run", "decide-only", "spike"]

# Runs after the str check, so `identifier` only ever sees a str or None
# (https://docs.pydantic.dev/latest/concepts/validators/#field-after-validator).
Identifier = Annotated[str, AfterValidator(identifier)]
Count = Annotated[int, Field(ge=0)]


class _Line(BaseModel):
    # extra="forbid": no field beyond the contract; validate_assignment: the
    # run updates RunSummary's counts in place and they are checked too
    # (https://docs.pydantic.dev/latest/api/config/).
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Note(_Line):
    note_id: Identifier
    outcome: Literal["booked", "skipped", "untouched", "partial"]
    reason: Identifier | None = None
    field: Identifier | None = None
    po_number: Identifier | None = None
    pln: Identifier | None = None
    task_id: Identifier | None = None
    tokens_in: Count = 0
    tokens_out: Count = 0
    cost_aud: float = Field(0.0, ge=0)


class Alert(_Line):
    note_id: Identifier | None = None
    step: Identifier | None = None
    detail: str


class RunSummary(_Line):
    run_id: str = Field(pattern=r"^\d{8}T\d{6}Z-[0-9a-f]{4}$")
    site: Literal["test"] | None = None
    mode: Mode | None = None
    seen: Count = 0
    eligible: Count = 0
    booked: Count = 0
    skipped: Count = 0
    partial: Count = 0
    duration_s: Count = 0
    tokens_in: Count = 0
    tokens_out: Count = 0
    cost_aud: float = Field(0.0, ge=0)
    exit_code: int = 0


def _emit(line: str) -> None:
    # flush: the Mac Mini wrapper appends stdout to runs.log as it comes.
    print(line, flush=True)


def _json(model: BaseModel) -> str:
    # json.dumps' default separators give the contract's `{"a": 1, "b": 2}`.
    return json.dumps(model.model_dump(mode="json"))


def info(message: InfoMessage) -> None:
    if message not in get_args(InfoMessage):
        raise ValueError("INFO message is not a fixed template")
    _emit(f"INFO  {message}")


def note(line: Note) -> None:
    _emit(f"NOTE  {_json(line)}")


def alert(kind: AlertKind, line: Alert) -> None:
    if kind not in get_args(AlertKind):
        raise ValueError("unknown ALERT kind")
    _emit(f"ALERT {kind} {_json(line)}")


def run_summary(line: RunSummary) -> None:
    """Always the run's last line (cli.main)."""
    _emit(f"RUN_SUMMARY {_json(line)}")
