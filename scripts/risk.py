"""A PR's risk level, computed from the files it changes: `uv run scripts/risk.py`.

The table is docs/workflow.md, Production build loop step 5 (decisions,
19 Nov 2026, risk is computed). The highest file wins:

- high: `src/po_agent/mysys/` (the guard and every MySys write), the booker,
  the readers and decision engine, the address rules, `scripts/guard_check.py`,
  `scripts/check.py` (= CI), `scripts/risk.py` and `scripts/verify_pr.py` (the
  scripts that grade a PR, so a PR can't loosen them unseen), `.claude/hooks/`,
  `.claude/settings*.json` and `.github/workflows/`;
- medium: any other file under `src/` or `scripts/`;
- low: everything else (docs, tests, skills, tasks).

It diffs HEAD (or the ref given, e.g. `uv run scripts/risk.py origin/<branch>`)
against its merge base with origin/main (fetch first), prints
`risk: <level>` and the file that set it, and a warning when the PR changes
more than 400 lines. A stated risk lower than this one is an Important
finding in /verify-pr. Standard library and git only.
"""

import fnmatch
import subprocess
import sys
from collections.abc import Callable, Iterable

LEVELS = ("low", "medium", "high")
LARGE = 400  # changed lines (added + deleted) above which the PR is hard to review

HIGH_PREFIXES = (
    "src/po_agent/mysys/",
    ".claude/hooks/",
    ".github/workflows/",
)
HIGH_FILES = (
    "src/po_agent/b1/booker.py",
    "src/po_agent/b1/reader_rules.py",
    "src/po_agent/b1/readers.py",
    "src/po_agent/b1/decision.py",
    "src/po_agent/b1/address.py",
    "scripts/guard_check.py",
    "scripts/check.py",
    "scripts/risk.py",
    "scripts/verify_pr.py",
)
HIGH_GLOBS = (".claude/settings*.json",)
MEDIUM_PREFIXES = ("src/", "scripts/")


def classify(path: str) -> str:
    """The risk level of one changed file (a repo-relative path, `/` separated)."""
    path = path.replace("\\", "/")
    if (
        path.startswith(HIGH_PREFIXES)
        or path in HIGH_FILES
        or any(fnmatch.fnmatchcase(path, glob) for glob in HIGH_GLOBS)
    ):
        return "high"
    if path.startswith(MEDIUM_PREFIXES):
        return "medium"
    return "low"


def assess(paths: Iterable[str]) -> str:
    """The PR's level: its highest file's; no files is low."""
    return max((classify(p) for p in paths), key=LEVELS.index, default="low")


def parse_numstat(text: str) -> tuple[list[str], int]:
    """Paths and total changed lines from `git diff --numstat` (binary counts 0)."""
    paths: list[str] = []
    lines = 0
    for row in text.splitlines():
        if not row.strip():
            continue
        added, deleted, path = row.split("\t", 2)
        paths.append(path)
        lines += sum(int(n) for n in (added, deleted) if n.isdigit())
    return paths, lines


def _run_git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def main(
    argv: list[str] | None = None, run_git: Callable[[list[str]], str] = _run_git
) -> int:
    head = argv[0] if argv else "HEAD"
    # --no-renames: a move shows both paths, so moving a file out of a high
    # folder is still high.
    try:
        numstat = run_git(
            ["diff", "--numstat", "--no-renames", f"origin/main...{head}"]
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"risk: unknown (git diff failed: {exc})")
        return 2
    paths, lines = parse_numstat(numstat)
    level = assess(paths)
    print(f"risk: {level}")
    if paths:
        top = [p for p in paths if classify(p) == level]
        more = f" (+{len(top) - 1} more)" if len(top) > 1 else ""
        print(f"why: {top[0]}{more}")
    else:
        print("why: no changes against origin/main")
    if lines > LARGE:
        print(
            f"warning: {lines} lines changed (over {LARGE}); consider splitting the PR"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
