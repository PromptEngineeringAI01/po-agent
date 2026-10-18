"""The one check command (= CI): `uv run scripts/check.py`.

Runs each step in order, stops on the first failure, and prints
"check: all passed" when every step passes.
"""

import fnmatch
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"

# Folder names that must never be tracked, at any depth (as in .gitignore).
BANNED_DIRS = {"private", "logs", "state", ".state", "traces", ".playwright-cli"}
PDF_FIXTURES = "tests/seam1/fixtures/pdfs/"
CAPTURE_PATTERNS = ("*trace*.zip", "*.har", "*.webm")

Step = tuple[str, Callable[[], bool]]


def classify(path: str) -> str | None:
    """Why a tracked path breaks the repo-data rule, or None if it's allowed."""
    parts = path.split("/")
    for part in parts[:-1]:
        if part in BANNED_DIRS:
            return f"under {part}/"
    lower = path.lower()
    if lower.endswith(".pdf") and not lower.startswith(PDF_FIXTURES):
        return f"PDF outside {PDF_FIXTURES}"
    name = parts[-1].lower()
    for pattern in CAPTURE_PATTERNS:
        if fnmatch.fnmatchcase(name, pattern):
            return f"trace or capture file ({pattern})"
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


STEPS: list[Step] = [
    ("ruff format --check .", command("ruff", "format", "--check", ".")),
    ("ruff check .", command("ruff", "check", ".")),
    ("repo data", repo_data),
    (
        f'pytest tests -m "{PYTEST_MARKERS}"',
        command("pytest", "tests", "-m", PYTEST_MARKERS),
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


def main() -> None:
    sys.exit(run_checks(STEPS))


if __name__ == "__main__":
    main()
