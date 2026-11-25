"""The po-agent command (SPEC.md -> Commands, Code style, Exit codes).

    po-agent spike|run --site test|live [--client b1|summit] [--decide-only]
             [--headed] [--slow-mo N] [--detailed-log]
    po-agent preflight --site test|live [--client b1|summit]
    po-agent demo --site test [--headed] [--slow-mo N] [--until-check]
             [--probe-link]
             [--detailed-log]

`--site` picks config/<site>.toml and that site's MySys secrets (decisions,
10 Nov 2026, live profile); only Joey runs a live site, on the Mac Mini.
`--client` (task 9.3; SPEC.md -> Client 2, The separate run) defaults to b1;
summit is live only, with its own secret pair and config/clients/summit.toml.
Until its task lands, run (9.14) refuses summit with exit 2, after its
client file is validated; spike (9.11) and run --decide-only (9.12) are
built. The demo is
B1's and test site only. `preflight` (decisions, 20 Nov 2026, secrets
pre-flight) checks that the site's MySys secrets are set and well-formed and
prints their names and a status; it reads no config, opens no browser and
makes no network call.

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

Order: run_id (before anything can fail), command line, the client file
(Summit), the run lock per site and client (decisions, 21 Nov 2026: held by
another run -> INFO, exit 0; 23 Nov 2026: Summit's own lock), Summit's
refusal until its modes land (before any secret, login or browser), the
run's own client's leftover download folders swept (D2), config, the kill
switch (the site's, and the client file's) and the Perth window (3.5: exit
0, nothing launched), secrets, then the mode. Config and secret
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

from po_agent.b1.client import B1Client
from po_agent.core import controls, demo, output, run, runlock, runlog, secrets
from po_agent.core.client import Client
from po_agent.core.config import (
    CONFIG_DIR,
    SITE_HOSTS,
    ClientProfile,
    Config,
    load_client,
    load_config,
)
from po_agent.core.errors import ConfigError, PoAgentError, RunLockStuck, identifier
from po_agent.core.secrets import SecretName
from po_agent.core.trace import Trace
from po_agent.summit.client import SummitClient

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
STATE_DIR = Path(__file__).resolve().parents[2] / "state"  # git-ignored
DOWNLOAD_PREFIX = "po-agent-dl-"
# The run's safe trace by run_id, set by main() for the length of the run, so
# start() keeps its signature.
_TRACES: dict[str, Trace] = {}
UNEXPECTED_DETAIL = "unexpected error"

# --client (task 9.3); b1 is the default.
CLIENTS = ("b1", "summit")
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
    preflight = commands.add_parser("preflight", add_help=False, allow_abbrev=False)
    preflight.add_argument("--site", required=True)
    preflight.add_argument("--client", choices=CLIENTS, default="b1")
    for name in ("spike", "run", "demo"):
        command = commands.add_parser(name, add_help=False, allow_abbrev=False)
        command.add_argument("--site", required=True)
        if name != "demo":  # the demo stays B1's
            command.add_argument("--client", choices=CLIENTS, default="b1")
        command.add_argument("--headed", action="store_true")
        command.add_argument("--slow-mo", type=_slow_mo, default=0)
        command.add_argument("--detailed-log", action="store_true")
        if name == "run":
            command.add_argument("--decide-only", action="store_true")
        if name == "demo":
            command.add_argument("--until-check", action="store_true")
            command.add_argument("--probe-link", action="store_true")
    return parser


def secret_names(
    mode: output.Mode, site: str, client: str = "b1"
) -> tuple[SecretName, ...]:
    """The MySys secrets the mode needs on that site for that client: their
    own pair. The demo (Joey's Enter before each write, from the laptop) is
    test site only; Summit is live only."""
    if mode == "demo" and site != "test":
        raise ConfigError("the demo is test site only")
    try:
        return secrets.mysys_names(site, client)
    except ValueError:
        if site in SITE_HOSTS:
            raise ConfigError("the client does not run on that site") from None
        raise ConfigError("unknown site") from None


def new_run_id() -> str:
    """UTC start time plus 4 random hex characters: 20261016T013507Z-3fa2."""
    start = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{start}-{os.urandom(2).hex()}"


def _download_prefix(client: str) -> str:
    """B1's folders keep the name they had before there were two clients:
    po-agent-dl-<run_id>; Summit's are po-agent-dl-summit-<run_id>."""
    return DOWNLOAD_PREFIX if client == "b1" else f"{DOWNLOAD_PREFIX}{client}-"


def download_dir(client: str, run_id: str) -> Path:
    """The run's download folder in the system temp dir (D2)."""
    return Path(tempfile.gettempdir()) / f"{_download_prefix(client)}{run_id}"


def sweep_download_dirs(client: str = "b1") -> None:
    """Removes the client's leftover download folders from the system temp
    dir (D2). Only its own: the other client's run may be going on now
    (each client has its own run lock; task 9.5).

    A folder that can't be removed stops the run (exit 2) before login.
    Symlinks and junctions are left alone: rmtree refuses them, and they hold
    no download themselves.
    """
    # B1's prefix starts every other client's: skip theirs.
    others = tuple(
        _download_prefix(other) for other in CLIENTS if other not in ("b1", client)
    )
    for path in Path(tempfile.gettempdir()).glob(_download_prefix(client) + "*"):
        if others and path.name.startswith(others):
            continue
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
    profile: ClientProfile | None = None,
) -> int:
    """The mode's entry point and its exit code; it fills the summary's
    counts. The Note loop's run log goes to logs/ only with --detailed-log,
    and to the run's trace always. `profile`: the client's file, None for
    B1."""
    trace = _TRACES.get(summary.run_id)
    name = getattr(options, "client", "b1")  # the demo has no --client
    downloads = download_dir(name, summary.run_id)
    if mode == "demo":
        return demo.run(config, credentials, options, summary, downloads)
    client = client_for(name, config, profile)
    if mode == "spike":
        return run.spike(config, client, credentials, options, summary, profile)
    logs = LOGS_DIR if options.detailed_log else None
    if mode == "run":
        return run.book_run(
            config,
            client,
            credentials,
            options,
            summary,
            downloads,
            logs,
            CONFIG_DIR,
            trace,
            profile,
        )
    return run.decide_only(
        config, client, credentials, options, summary, downloads, logs, trace, profile
    )


def client_for(name: str, config: Config, profile: ClientProfile | None) -> Client:
    """The run loop's client (task 9.4; core/client.py). Summit's reads its
    client file and the run's start time (its assignee rule, task 9.11);
    `_run` refuses its run that books before this until 9.14."""
    if name == "summit":
        if profile is None:
            raise ConfigError("client file not loaded")
        return SummitClient(config, profile, controls.now())
    return B1Client(config)


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


def _preflight(site: str, client: str) -> int:
    """Each secret's status, then exit 2 if any is not ok. Reads only the
    secrets' presence and shape; their values are never kept."""
    checks = [
        output.SecretCheck(name=name, status=secrets.inspect(name))
        for name in secret_names("preflight", site, client)
    ]
    for check in checks:
        output.secret_check(check)
    if any(check.status != "ok" for check in checks):
        raise ConfigError("secrets not ready")
    output.info("preflight: secrets ok")
    return 0


def _run(
    mode: output.Mode,
    options: argparse.Namespace,
    summary: output.RunSummary,
    trace: Trace,
) -> int:
    if mode == "preflight":
        # Before the run lock: it reads nothing but the secrets, so it neither
        # takes nor needs the lock.
        return _preflight(options.site, options.client)
    if mode == "demo" and not _demo_read_only(options) and not options.headed:
        # Joey approves each write at a prompt: he must see the page.
        raise ConfigError("a demo that writes needs --headed")
    client = getattr(options, "client", "b1")  # the demo has no --client
    names = secret_names(mode, options.site, client)  # before any file is read
    # A client file is checked first (ALERT CONFIG on any breach).
    profile = None if client == "b1" else load_client(client, options.site, CONFIG_DIR)
    # The run lock (core/runlock.py), per site and client, before anything
    # else touches disk or MySys: the sweep below deletes the client's other
    # runs' download folders.
    try:
        lock = runlock.acquire(STATE_DIR / runlock.lock_name(options.site, client))
    except runlock.RunLockHeld as held:
        if held.held_s is not None and held.held_s > runlock.STUCK_AFTER_S:
            raise RunLockStuck("run lock held for over an hour") from None
        output.info("run lock held: run not started")
        return 0
    except OSError:
        raise ConfigError("run lock not available") from None
    try:
        return _run_locked(mode, options, summary, trace, names, client, profile)
    finally:
        lock.release()


def _run_locked(
    mode: output.Mode,
    options: argparse.Namespace,
    summary: output.RunSummary,
    trace: Trace,
    names: tuple[SecretName, ...],
    client: str,
    profile: ClientProfile | None,
) -> int:
    if client == "summit" and mode == "run":
        # Refused until its task lands (run 9.14): before any secret is
        # read, any login or any browser. The spike: 9.11; decide-only: 9.12.
        raise ConfigError("mode not built for this client yet")
    if profile is None:  # B1: the sweep's call as before there were two clients
        sweep_download_dirs()
    else:
        sweep_download_dirs(client)
    config = load_config(options.site, CONFIG_DIR)
    _start_trace(trace, config)
    if not controls.run_enabled(config, profile):
        output.info("kill switch on: run not started")
        return 0
    if mode in WINDOW_MODES and not controls.in_window(
        config.run_window, controls.now()
    ):
        output.info("outside the run window: run not started")
        return 0
    credentials = {name: secrets.get(name) for name in names}
    output.info("config loaded")
    if profile is None:  # B1: start's call as before there were two clients
        return start(mode, config, credentials, options, summary)
    return start(mode, config, credentials, options, summary, profile)


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
        detailed_log = getattr(options, "detailed_log", False)
        mode: output.Mode = (
            "decide-only" if getattr(options, "decide_only", False) else options.command
        )
        summary.mode = mode
        summary.site = options.site if options.site in ("test", "live") else None
        summary.client = getattr(options, "client", "b1")  # the demo is B1's
        exit_code = _run(mode, options, summary, trace)
    except BaseException as error:  # noqa: BLE001 - the catch-all: nothing reaches stderr
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
