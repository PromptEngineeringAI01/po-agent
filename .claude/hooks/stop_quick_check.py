"""Claude Code Stop hook: the quick check on uncommitted Python changes.

Reads the Stop input as JSON on stdin (https://code.claude.com/docs/en/hooks).
Exit 2 on a Stop hook keeps Claude working, with stderr as the reason; exit 0
lets it stop. It passes at once when `stop_hook_active` is true (Claude is
already continuing because of this hook, so it never loops) or when no
uncommitted `.py` file changed (nothing changed, or a docs-only turn).

Otherwise it maps the changed files to test paths the way /quick-check does
and runs `uv run scripts/check.py --quick <paths>` in the session's checkout:
ruff, mypy, guard check, repo data, then only those tests. check.py always
applies its marker filter, so a seam-2 file never logs in to the test site.
No test maps: it passes, since format_python already lints each edit and the
full check still runs before every PR.

Anything that goes wrong in here also exits 2, so it fails closed; the
`stop_hook_active` check stops that from looping.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HOOK = "stop_quick_check"
TIMEOUT = 900  # seconds; mypy plus a few test files take well under this
TAIL = 60  # lines of check output shown to Claude on failure


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    ).stdout


def changed_py(root: Path) -> list[str]:
    """Uncommitted `.py` files that still exist, as repo-relative paths."""
    entries = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    parts = entries.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # -z puts the old path of a rename or copy next
        if path.endswith(".py") and (root / path).is_file():
            paths.append(path)
    return paths


def importers(root: Path, pattern: str) -> set[str]:
    regex = re.compile(pattern)
    return {
        p.relative_to(root).as_posix()
        for p in (root / "tests").rglob("test_*.py")
        if regex.search(p.read_text(encoding="utf-8", errors="replace"))
    }


def by_name(root: Path, folder: str, stem: str) -> set[str]:
    return {
        p.relative_to(root).as_posix() for p in (root / folder).glob(f"test_{stem}*.py")
    }


def test_paths(root: Path, changed: list[str]) -> list[str]:
    """The test files that cover the changed files (/quick-check, Which tests)."""
    tests: set[str] = set()
    for path in changed:
        parts = path.split("/")
        name = Path(path).stem
        if parts[0] == "tests" and name.startswith("test_"):
            tests.add(path)
        elif parts[0] == "tests" and name == "conftest":
            tests.add("/".join(parts[:-1]))
        elif parts[:2] == ["tests", "fakes"]:
            tests |= importers(root, r"\bfakes\b")
        elif parts[:2] == ["src", "po_agent"] and len(parts) >= 3:
            pkg = ".".join(parts[1:-1])  # po_agent or po_agent.<pkg>
            if name == "__init__":
                tests |= importers(root, rf"\b{re.escape(pkg)}\b")
            else:
                mod = re.escape(name)
                tests |= {
                    p.relative_to(root).as_posix()
                    for p in (root / "tests").rglob(f"test_{name}*.py")
                }
                tests |= importers(
                    root,
                    rf"{re.escape(pkg)}\.{mod}\b"
                    rf"|from {re.escape(pkg)} import .*\b{mod}\b",
                )
        elif parts[0] == "scripts" and len(parts) == 2:
            tests |= by_name(root, "tests", name)
        elif parts[:2] == [".claude", "hooks"]:
            tests.add("tests/test_hooks.py")
    return sorted(t for t in tests if (root / t).exists())


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if payload.get("stop_hook_active") is True:
            return
        start = Path(payload.get("cwd") or ".")
        root = Path(git(start, "rev-parse", "--show-toplevel").strip())
        changed = changed_py(root)
        if not changed:
            return
        tests = test_paths(root, changed)
        if not tests:
            return
        result = subprocess.run(
            ["uv", "run", "scripts/check.py", "--quick", *tests],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
    except Exception as exc:  # fail closed
        sys.stderr.write(f"{HOOK}: hook error ({type(exc).__name__}: {exc})\n")
        sys.exit(2)
    if result.returncode != 0:
        # uv's own notes go to stderr; put them first so the check's
        # failure line ends the tail.
        tail = (result.stderr + result.stdout).splitlines()[-TAIL:]
        sys.stderr.write(
            f"{HOOK}: `uv run scripts/check.py --quick {' '.join(tests)}` failed. "
            "Fix the cause before ending the turn:\n" + "\n".join(tail) + "\n"
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
