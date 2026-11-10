"""The po-agent command (SPEC.md -> Commands, Code style, Exit codes).

    po-agent spike|run --site test|live [--decide-only] [--headed]
             [--slow-mo N] [--detailed-log]
    po-agent demo --site test [--headed] [--slow-mo N] [--until-check]
             [--probe-link]
             [--detailed-log]

`--site` picks config/<site>.toml and that site's MySys secrets (decisions,
10 Nov 2026, live profile); only Joey runs a live site, on the Mac Mini.
The demo is test site only.

`demo` books the one trial PO 2609017B, supervised: it waits for Joey's
Enter before every write; --until-check stops after the read-only checks
(steps 1-5) and writes nothing (decisions, 27 Oct 2026); --probe-link
opens Choose Project on the untaken Note, searches the pln, snapshots
and stops without selecting (28 Oct 2026).

Every run ends with RUN_SUMMARY as its last stdout line, whatever happened.
A typed error becomes its ALERT and exit code (both declared on its class,
core/errors.py); anything else is caught here and becomes ALERT
UNEXPECTED_SCREEN with a fixed detail, exit 1. Nothing goes to stderr,
because an exception's text can quote page content: the traceback goes to
logs/ only with --detailed-log (core/runlog.write_traceback), else nowhere.

The safe trace (7.3) starts right after config is loaded, when config sets
`trace_dir` (core/trace.py): the run log's events, then one run_end event
(pass, or the reported error's type). It is a file, never stdout.

Order: run_id (before anything can fail), command line, leftover download
folders swept (D2), config, the kill switch and the Perth window (3.5:
exit 0, nothing launched), secrets, then the mode. Config and secret
problems exit 2 before any browser is launched. `run` books since 4.5 (its
refusal until then, D1, is gone); `run --decide-only` books nothing.
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from po_agent.core import controls, demo, output, run, runlog, secrets
from po_agent.core.config import CONFIG_DIR, Config, load_config
from po_agent.core.errors import ConfigError, PoAgentError, identifier
from po_agent.core.secrets import SecretName
from po_agent.core.trace import Trace

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
DOWNLOAD_PREFIX = "po-agent-dl-"
# The run's safe trace by run_id, set by main() for the length of the run, so
# start() keeps its signature.
_TRACES: dict[str, Trace] = {}
UNEXPECTED_DETAIL = "unexpected error"

# The Perth window (3.5): spike and demo are laptop work and ignore it.
WINDOW_MODES: tuple[output.Mode, ...] = ("run", "decide-only")


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
    for name in ("spike", "run", "demo"):
        command = commands.add_parser(name, add_help=False, allow_abbrev=False)
        command.add_argument("--site", required=True)
        command.add_argument("--headed", action="store_true")
        command.add_argument("--slow-mo", type=_slow_mo, default=0)
        command.add_argument("--detailed-log", action="store_true")
        if name == "run":
            command.add_argument("--decide-only", action="store_true")
        if name == "demo":
            command.add_argument("--until-check", action="store_true")
            command.add_argument("--probe-link", action="store_true")
    return parser


def secret_names(mode: output.Mode, site: str) -> tuple[SecretName, ...]:
    """The MySys secrets the mode needs on that site: its own pair. The demo
    (Joey's Enter before each write, from the laptop) is test site only."""
    if mode == "demo" and site != "test":
        raise ConfigError("the demo is test site only")
    try:
        return secrets.mysys_names(site)
    except ValueError:
        raise ConfigError("unknown site") from None


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
    counts. The Note loop's run log goes to logs/ only with --detailed-log,
    and to the run's trace always."""
    trace = _TRACES.get(summary.run_id)
    if mode == "spike":
        return run.spike(config, credentials, options, summary)
    downloads = Path(tempfile.gettempdir()) / f"{DOWNLOAD_PREFIX}{summary.run_id}"
    if mode == "demo":
        return demo.run(config, credentials, options, summary, downloads)
    logs = LOGS_DIR if options.detailed_log else None
    if mode == "run":
        return run.book_run(
            config, credentials, options, summary, downloads, logs, CONFIG_DIR, trace
        )
    return run.decide_only(
        config, credentials, options, summary, downloads, logs, trace
    )


def _demo_read_only(options: argparse.Namespace) -> bool:
    return options.until_check or options.probe_link


def _start_trace(trace: Trace, config: Config) -> None:
    """Today's file is named by the run window's date (Perth). The trace
    never stops a run: if this fails, the run goes on without it."""
    try:
        directory = Path(config.trace_dir).expanduser() if config.trace_dir else None
        today = controls.now().astimezone(ZoneInfo(config.run_window.tz)).date()
    except Exception:  # noqa: BLE001 - e.g. no home folder, unknown time zone
        return
    trace.start(directory, today)


def _run(
    mode: output.Mode,
    options: argparse.Namespace,
    summary: output.RunSummary,
    trace: Trace,
) -> int:
    sweep_download_dirs()
    if mode == "demo" and not _demo_read_only(options) and not options.headed:
        # Joey approves each write at a prompt: he must see the page.
        raise ConfigError("a demo that writes needs --headed")
    names = secret_names(mode, options.site)  # before any file is read
    config = load_config(options.site, CONFIG_DIR)
    _start_trace(trace, config)
    if not config.enabled:
        output.info("kill switch on: run not started")
        return 0
    if mode in WINDOW_MODES and not controls.in_window(
        config.run_window, controls.now()
    ):
        output.info("outside the run window: run not started")
        return 0
    credentials = {name: secrets.get(name) for name in names}
    output.info("config loaded")
    return start(mode, config, credentials, options, summary)


def _report(error: BaseException, run_id: str, detailed_log: bool) -> int:
    if detailed_log:
        runlog.write_traceback(LOGS_DIR, run_id, error)
    if isinstance(error, PoAgentError):
        # str(error): the fixed detail plus identifiers (core/errors.py).
        line = output.Alert(note_id=error.note_id, step=error.step, detail=str(error))
        output.alert(error.alert_kind, line)
        return error.exit_code
    detail = f"{UNEXPECTED_DETAIL} (type={identifier(type(error).__name__)})"
    output.alert("UNEXPECTED_SCREEN", output.Alert(detail=detail))
    return 1


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    summary = output.RunSummary(run_id=new_run_id())
    trace = _TRACES[summary.run_id] = Trace(summary.run_id)
    detailed_log = False
    failure: BaseException | None = None
    try:
        options = _parser().parse_args(argv)
        detailed_log = options.detailed_log
        mode: output.Mode = (
            "decide-only" if getattr(options, "decide_only", False) else options.command
        )
        summary.mode = mode
        summary.site = options.site if options.site in ("test", "live") else None
        exit_code = _run(mode, options, summary, trace)
    except BaseException as error:  # the catch-all: nothing reaches stderr
        failure = error
        exit_code = _report(error, summary.run_id, detailed_log)
    trace.end(failure)
    del _TRACES[summary.run_id]
    summary.duration_s = round(time.monotonic() - started)
    summary.exit_code = exit_code
    output.run_summary(summary)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
