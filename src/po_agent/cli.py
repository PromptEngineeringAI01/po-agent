"""The po-agent command (SPEC.md -> Commands, Code style, Exit codes).

    po-agent spike|run --site test [--decide-only] [--headed] [--slow-mo N]
             [--detailed-log]

Every run ends with RUN_SUMMARY as its last stdout line, whatever happened.
A typed error becomes its ALERT and exit code; anything else is caught here
and becomes ALERT UNEXPECTED_SCREEN with a fixed detail, exit 1. Nothing goes
to stderr, because an exception's text can quote page content: the traceback
goes to logs/ only with --detailed-log, else nowhere.

Order: run_id (before anything can fail), command line, leftover download
folders swept (D2), run-mode refusal (D1, until 4.5), config, secrets, then
the mode. Config and secret problems exit 2 before any browser is launched.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from po_agent.core import output, run, secrets
from po_agent.core.config import CONFIG_DIR, Config, load_config
from po_agent.core.errors import (
    AccuracyBreach,
    ConfigError,
    GuardRefusal,
    LoginFailed,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
    WriteNotStarted,
    identifier,
)
from po_agent.core.secrets import SecretName

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
DOWNLOAD_PREFIX = "po-agent-dl-"
UNEXPECTED_DETAIL = "unexpected error"

# A subclass maps like its nearest listed base. WriteNotStarted has no ALERT
# kind of its own: the run stops (exit 1), as for an unexpected screen.
ALERT_KINDS: dict[type[PoAgentError], output.AlertKind] = {
    PartialWrite: "PARTIAL_WRITE",
    AccuracyBreach: "ACCURACY_BREACH",
    GuardRefusal: "GUARD_REFUSAL",
    UnexpectedScreen: "UNEXPECTED_SCREEN",
    WriteNotStarted: "UNEXPECTED_SCREEN",
    LoginFailed: "LOGIN_FAILED",
    ConfigError: "CONFIG",
}
_MYSYS: tuple[SecretName, ...] = ("mysys_test_username", "mysys_test_password")
SECRETS_FOR: dict[output.Mode, tuple[SecretName, ...]] = {
    "spike": _MYSYS,
    "decide-only": (*_MYSYS, "anthropic_api_key"),
}


class _Parser(argparse.ArgumentParser):
    """Raises ConfigError where argparse would print to stderr and exit, and
    drops argparse's message, which can echo what was typed
    (https://docs.python.org/3.12/library/argparse.html#exiting-methods).
    Subparsers are built with the same class."""

    def error(self, message: str):
        raise ConfigError("invalid command line")

    def exit(self, status: int = 0, message: str | None = None):
        raise ConfigError("invalid command line")


def _slow_mo(value: str) -> int:
    number = int(value)  # ValueError -> argparse calls error()
    if number < 0:
        raise ValueError("negative")
    return number


def _parser() -> _Parser:
    # add_help=False: help text isn't part of the stdout contract.
    # allow_abbrev=False: only the exact option names.
    parser = _Parser(prog="po-agent", add_help=False, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("spike", "run"):
        command = commands.add_parser(name, add_help=False, allow_abbrev=False)
        command.add_argument("--site", required=True)
        command.add_argument("--headed", action="store_true")
        command.add_argument("--slow-mo", type=_slow_mo, default=0)
        command.add_argument("--detailed-log", action="store_true")
        if name == "run":
            command.add_argument("--decide-only", action="store_true")
    return parser


def new_run_id() -> str:
    """UTC start time plus 4 random hex characters: 20261016T013507Z-3fa2."""
    start = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{start}-{os.urandom(2).hex()}"


def sweep_download_dirs() -> None:
    """Removes leftover po-agent-dl-* folders from the system temp dir (D2).

    A folder that can't be removed stops the run (exit 2) before login.
    Symlinks and junctions are left alone: rmtree refuses them, and they hold
    no download themselves.
    """
    for path in Path(tempfile.gettempdir()).glob(DOWNLOAD_PREFIX + "*"):
        if not path.is_dir() or path.is_symlink() or path.is_junction():
            continue
        shutil.rmtree(path, ignore_errors=True)
        if path.exists():
            raise ConfigError("leftover download folder not removed")


def start(
    mode: output.Mode,
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
) -> int:
    """The mode's entry point and its exit code; it fills the summary's
    counts. M3 builds decide-only."""
    if mode == "spike":
        return run.spike(config, credentials, options, summary)
    output.info("decide-only not built yet")
    return 0


def _run(
    mode: output.Mode, options: argparse.Namespace, summary: output.RunSummary
) -> int:
    sweep_download_dirs()
    if mode == "run":
        raise ConfigError("run mode not built yet")
    config = load_config(options.site, CONFIG_DIR)
    credentials = {name: secrets.get(name) for name in SECRETS_FOR[mode]}
    output.info("config loaded")
    return start(mode, config, credentials, options, summary)


def _alert_kind(error: PoAgentError) -> output.AlertKind:
    for cls in type(error).__mro__:
        if cls in ALERT_KINDS:
            return ALERT_KINDS[cls]
    return "UNEXPECTED_SCREEN"


def _log_traceback(run_id: str, error: BaseException) -> None:
    # format_exception follows __cause__ and __context__ itself and honours
    # `raise ... from None`, so a Playwright message the guard hid stays
    # hidden; never walk the chain by hand
    # (https://docs.python.org/3.12/library/traceback.html#traceback.format_exception).
    event = {
        "ts": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "note_id": getattr(error, "note_id", None),
        "step": getattr(error, "step", None),
        "event": "traceback",
        "ok": False,
        "traceback": "".join(traceback.format_exception(error)),
    }
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOGS_DIR / f"{run_id}.jsonl", "a", encoding="utf-8") as file:
            file.write(json.dumps(event) + "\n")
    except OSError:
        pass  # the ALERT and RUN_SUMMARY still go out


def _report(error: BaseException, run_id: str, detailed_log: bool) -> int:
    if detailed_log:
        _log_traceback(run_id, error)
    if isinstance(error, PoAgentError):
        # str(error): the fixed detail plus identifiers (core/errors.py).
        line = output.Alert(note_id=error.note_id, step=error.step, detail=str(error))
        output.alert(_alert_kind(error), line)
        return error.exit_code
    detail = f"{UNEXPECTED_DETAIL} (type={identifier(type(error).__name__)})"
    output.alert("UNEXPECTED_SCREEN", output.Alert(detail=detail))
    return 1


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    summary = output.RunSummary(run_id=new_run_id())
    detailed_log = False
    try:
        options = _parser().parse_args(argv)
        detailed_log = options.detailed_log
        mode: output.Mode = (
            "decide-only" if getattr(options, "decide_only", False) else options.command
        )
        summary.mode = mode
        summary.site = "test" if options.site == "test" else None
        exit_code = _run(mode, options, summary)
    except BaseException as error:  # the catch-all: nothing reaches stderr
        exit_code = _report(error, summary.run_id, detailed_log)
    summary.duration_s = round(time.monotonic() - started)
    summary.exit_code = exit_code
    output.run_summary(summary)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
