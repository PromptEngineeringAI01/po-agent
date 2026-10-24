"""The one check command (= CI): `uv run scripts/check.py`.

Runs each step in order, stops on the first failure, and prints
"check: all passed" when every step passes. `--repo-data-only` runs just the
repo-data rule (the pre-commit hook).
"""

import argparse
import fnmatch
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"

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
    if fnmatch.fnmatchcase("/".join(parts[-2:]), LIVE_CONFIG):
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="The one check command (= CI).")
    parser.add_argument(
        "--repo-data-only",
        action="store_true",
        help="run only the repo-data rule on the index (the pre-commit hook)",
    )
    args = parser.parse_args(argv)
    steps = [("repo data", repo_data)] if args.repo_data_only else STEPS
    sys.exit(run_checks(steps))


if __name__ == "__main__":
    main()
