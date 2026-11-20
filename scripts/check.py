"""The one check command (= CI): `uv run scripts/check.py`.

Runs each step in order, stops on the first failure, and prints
"check: all passed" when every step passes:

- default: ruff format --check, ruff check, guard check, repo data, then the
  offline tests in parallel (pytest-xdist; decisions, 19 Nov 2026).
- `--quick <test paths>`: the same fast steps on the whole repo, then pytest
  on only those paths with the same marker filter, in parallel only past
  QUICK_PARALLEL_MIN selected tests. An inner-loop check, not the gate.
- `--repo-data-only`: just the repo-data rule (the pre-commit hook).

`-n` lives here, never in pyproject `addopts`, so a plain `uv run pytest`
(seam 2 included) stays serial; tests/xdist_guard.py fails any `testsite`
test inside an xdist worker, before its fixtures.
"""

import argparse
import fnmatch
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"
# One worker per CPU, at most 12: on the laptop's 24 logical CPUs, 24 workers
# made the 2 s short page waits time out (decisions, 19 Nov 2026).
PYTEST_PARALLEL = ("-n", "auto", "--maxprocesses", "12", "--dist", "load")
QUICK_PARALLEL_MIN = 50

# Everything below is matched lowercased, so any case is caught.
# Folder names that must never be tracked, at any depth (as in .gitignore).
BANNED_DIRS = {
    "private",
    "logs",
    "state",
    ".state",
    "traces",
    ".playwright-cli",
    "secrets",
    ".env",
}
PDF_FIXTURES = "tests/seam1/fixtures/pdfs/"
# File-name patterns banned in any folder.
BANNED_NAMES = {
    "secret file": (".env", ".env.*"),
    "trace or capture file": ("*trace*.zip", "*.har", "*.webm"),
    "image (screen captures are real data)": (
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.webp",
        "*.gif",
    ),
}
LIVE_CONFIG = "config/live*.toml"
# The one committed live config, at the repo root; it holds no secrets
# (decisions, 10 Nov 2026, live profile).
COMMITTED_LIVE_CONFIG = "config/live.toml"

Step = tuple[str, Callable[[], bool]]


def classify(path: str) -> str | None:
    """Why a tracked path breaks the repo-data rule, or None if it's allowed."""
    lower = path.lower()
    parts = lower.split("/")
    for part in parts[:-1]:
        if part in BANNED_DIRS:
            return f"under {part}/"
    if lower.endswith(".pdf") and not lower.startswith(PDF_FIXTURES):
        return f"PDF outside {PDF_FIXTURES}"
    name = parts[-1]
    for reason, patterns in BANNED_NAMES.items():
        for pattern in patterns:
            if fnmatch.fnmatchcase(name, pattern):
                return f"{reason} ({pattern})"
    if path != COMMITTED_LIVE_CONFIG and fnmatch.fnmatchcase(
        "/".join(parts[-2:]), LIVE_CONFIG
    ):
        return f"live config ({LIVE_CONFIG})"
    return None


def repo_data_violations(root: Path) -> list[str]:
    """One "<path>: <reason>" line per tracked or staged path that breaks the rule."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return [f"{root}: git ls-files failed (not a git repo?)"]
    violations = []
    for path in result.stdout.split("\0"):
        if not path:
            continue
        reason = classify(path)
        if reason:
            violations.append(f"{path}: {reason}")
    return violations


def repo_data() -> bool:
    violations = repo_data_violations(ROOT)
    for line in violations:
        print(f"repo-data: {line}")
    return not violations


def command(*args: str) -> Callable[[], bool]:
    def run() -> bool:
        return subprocess.run([sys.executable, "-m", *args], cwd=ROOT).returncode == 0

    return run


def script(path: str) -> Callable[[], bool]:
    def run() -> bool:
        return subprocess.run([sys.executable, path], cwd=ROOT).returncode == 0

    return run


FAST_STEPS: list[Step] = [
    ("ruff format --check .", command("ruff", "format", "--check", ".")),
    ("ruff check .", command("ruff", "check", ".")),
    ("guard check", script("scripts/guard_check.py")),
    ("repo data", repo_data),
]

STEPS: list[Step] = [
    *FAST_STEPS,
    (
        f'pytest tests -m "{PYTEST_MARKERS}" {" ".join(PYTEST_PARALLEL)}',
        command("pytest", "tests", "-m", PYTEST_MARKERS, *PYTEST_PARALLEL),
    ),
]


def selected_tests(paths: list[str]) -> int:
    """How many tests `--quick` would run (0 if collection fails: the run
    itself then reports the error)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", PYTEST_MARKERS]
        + paths,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sum("::" in line for line in result.stdout.splitlines())


def quick_steps(paths: list[str]) -> list[Step]:
    def run_tests() -> bool:
        parallel = selected_tests(paths) > QUICK_PARALLEL_MIN
        extra = PYTEST_PARALLEL if parallel else ()
        return command("pytest", *paths, "-m", PYTEST_MARKERS, *extra)()

    return [
        *FAST_STEPS,
        (
            f'pytest {" ".join(paths)} -m "{PYTEST_MARKERS}"'
            f" (+ {' '.join(PYTEST_PARALLEL)} past {QUICK_PARALLEL_MIN} tests)",
            run_tests,
        ),
    ]


def run_checks(steps: list[Step]) -> int:
    for name, run in steps:
        print(f"check: {name}", flush=True)
        if not run():
            print(f"check: failed at {name}")
            return 1
    print("check: all passed")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="The one check command (= CI).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--repo-data-only",
        action="store_true",
        help="run only the repo-data rule on the index (the pre-commit hook)",
    )
    mode.add_argument(
        "--quick",
        nargs="+",
        metavar="TEST_PATH",
        help="ruff, guard check and repo data on the repo, then pytest on only "
        "these test paths (same marker filter); not the gate",
    )
    args = parser.parse_args(argv)
    if args.repo_data_only:
        steps = [("repo data", repo_data)]
    elif args.quick:
        steps = quick_steps(args.quick)
    else:
        steps = STEPS
    sys.exit(run_checks(steps))


if __name__ == "__main__":
    main()
