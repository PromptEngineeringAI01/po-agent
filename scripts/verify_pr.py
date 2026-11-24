"""The mechanical half of /verify-pr.

Run: `uv run scripts/verify_pr.py origin/<branch> --pr <n>`.

Audit fix #2 (24 Nov 2026): the rules in .claude/skills/verify-pr/SKILL.md
steps 2-4 that need no judgement, run as code, so the LLM verifier keeps only
the judgement calls. It diffs the ref (default HEAD) against its merge base
with origin/main (fetch first), like scripts/risk.py, and prints one line per
finding:

- FAIL: a commit not starting `test:` touches `tests/`, or a `test:` commit
  touches `src/`; a subject that isn't a Conventional Commit of type feat,
  fix, test, docs, chore or refactor (merge commits skipped); an em dash in
  an added line; in an added line, a Playwright action outside the guard,
  the live host outside its allowed files, or the Anthropic key's variable
  name outside tests/test_config_secrets.py; a PR body without Intent, What
  changed, Risk or Testing, or whose stated risk is below risk.py's.
- WARN: `uv.lock` or `pyproject.toml` changed (the PR must say Joey approved
  the dependency); no PR body given.
- REVIEW: a safety-sensitive file changed (the LLM reads its diff), or more
  than 400 lines changed.

The last line is `verify_pr: <n> fail, <n> warn`; exit 1 on any FAIL, 2 when
git or gh fails. The PR body comes from `gh pr view <n> --json body` with
`--pr`, or from a file with `--body-file`. Standard library, git and gh,
plus LIVE_HOST from po_agent.core.config.

The live host is never written here: it comes from LIVE_HOST in
po_agent.core.config (CLAUDE.md Must never #3). The Anthropic key's variable
name is built from parts, so this file never holds it whole.
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import risk

from po_agent.core.config import LIVE_HOST

TYPES = ("feat", "fix", "test", "docs", "chore", "refactor")
SUBJECT = re.compile(rf"^({'|'.join(TYPES)}): \S")
EM_DASH = chr(0x2014)  # never the character itself (CLAUDE.md)

GUARD = "src/po_agent/mysys/guard.py"
ACTIONS = ("click", "fill", "check", "set_input_files", "evaluate", "dispatch_event")
# Whole names only: `guard_check(` or `checked(` is not a Playwright action.
ACTION = re.compile(rf"\b({'|'.join(ACTIONS)})\(")
# The test host ends in the live host's name, so it is excluded, as in
# .claude/hooks/guard_bash.py.
LIVE = re.compile(rf"(?<!test-){re.escape(LIVE_HOST)}", re.IGNORECASE)
LIVE_HOST_FILES = (
    "src/po_agent/core/config.py",
    "config/live.toml",
    ".claude/hooks/guard_bash.py",
    "tests/test_hooks.py",
)
KEY_NAME = "ANTHROPIC" + "_API_KEY"
KEY_FILE = "tests/test_config_secrets.py"

DEPENDENCY_FILES = ("uv.lock", "pyproject.toml")
SECTIONS = ("Intent", "What changed", "Risk", "Testing")
HUNK = re.compile(r"@@ -\S+ \+(\d+)")

# verify-pr step 3: the files whose diff the LLM must read and judge.
SAFETY_FILES = (
    GUARD,
    "scripts/guard_check.py",
    "scripts/check.py",
    "config/test.toml",
    "docs/macmini-setup.md",
    "scripts/macmini-run.sh",
    "src/po_agent/b1/address.py",
)
SAFETY_PREFIXES = (".claude/", ".github/workflows/")
SAFETY_GLOBS = ("*.plist",)


class ToolError(Exception):
    """git or gh failed; the message says which command."""


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # a non-UTF-8 file in the diff must not crash it
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ToolError(f"{' '.join(args[:3])} failed: {exc}") from exc


def git(*args: str) -> str:
    return _run(["git", "-c", "core.quotepath=false", *args])


# --- commits ------------------------------------------------------------------


def commit_findings(ref: str) -> list[str]:
    """Rules 1 and 2, per commit in origin/main..ref."""
    findings = []
    log = git("log", "--reverse", "--format=%H%x00%P%x00%s", f"origin/main..{ref}")
    for row in log.splitlines():
        sha, parents, subject = row.split("\x00", 2)
        if len(parents.split()) > 1:
            continue  # a merge commit
        short = sha[:7]
        if not SUBJECT.match(subject):
            findings.append(
                f"FAIL: not a Conventional Commit ({', '.join(TYPES)}):"
                f" {short} {subject}"
            )
        is_test = subject.startswith("test:")
        files = git(
            "diff-tree", "-r", "--no-renames", "--no-commit-id", "--name-only", sha
        )
        for path in files.splitlines():
            if not is_test and path.startswith("tests/"):
                findings.append(
                    f"FAIL: tests/ changed outside a test: commit: {short} {path}"
                )
            if is_test and path.startswith("src/"):
                findings.append(f"FAIL: src/ changed in a test: commit: {short} {path}")
    return findings


# --- added lines --------------------------------------------------------------


def _hunk_start(line: str) -> int:
    match = HUNK.match(line)
    return int(match.group(1)) if match else 0


def added_lines(diff: str) -> Iterator[tuple[str, int, str]]:
    """(path, line number, text) for each added line of a `git diff -U0`."""
    path = ""
    number = 0
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_header = True
        elif in_header:
            if line.startswith("+++ "):
                target = line[4:]
                path = target[2:] if target.startswith("b/") else ""
            elif line.startswith("@@"):
                in_header = False
                number = _hunk_start(line)
        elif line.startswith("@@"):
            number = _hunk_start(line)
        elif line.startswith("+"):
            if path:
                yield path, number, line[1:]
            number += 1


def line_findings(diff: str) -> list[str]:
    """Rules 3 and 4, on added lines only (existing lines stay)."""
    findings = []
    for path, number, text in added_lines(diff):
        where = f"{path}:{number}"
        if EM_DASH in text:
            findings.append(f"FAIL: em dash in an added line: {where}")
        if path != GUARD and ACTION.search(text):
            findings.append(f"FAIL: Playwright action outside {GUARD}: {where}")
        if path not in LIVE_HOST_FILES and LIVE.search(text):
            findings.append(f"FAIL: live host outside its allowed files: {where}")
        if path != KEY_FILE and KEY_NAME in text:
            findings.append(f"FAIL: Anthropic key variable outside {KEY_FILE}: {where}")
    return findings


# --- changed files ------------------------------------------------------------


def is_safety_sensitive(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        path in SAFETY_FILES
        or path.startswith(SAFETY_PREFIXES)
        or any(fnmatch.fnmatchcase(name, glob) for glob in SAFETY_GLOBS)
    )


def file_findings(paths: list[str], lines: int) -> list[str]:
    """Rules 5 and 7."""
    findings = [
        f"WARN: dependency file changed (the PR must say Joey approved it): {path}"
        for path in paths
        if path in DEPENDENCY_FILES
    ]
    findings += [
        f"REVIEW: safety-sensitive file changed: {path}"
        for path in paths
        if is_safety_sensitive(path)
    ]
    if lines > risk.LARGE:
        findings.append(
            f"REVIEW: {lines} lines changed (over {risk.LARGE}); consider splitting"
            " the PR"
        )
    return findings


# --- the PR body --------------------------------------------------------------


def sections(body: str) -> dict[str, str]:
    """Each markdown heading's title (lowercased) and the text under it."""
    found: dict[str, str] = {}
    title = None
    for line in body.splitlines():
        heading = re.match(r"#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            title = heading.group(1).lower()
            found[title] = ""
        elif title is not None:
            found[title] += line + "\n"
    return found


def body_findings(body: str, computed: str) -> list[str]:
    """Rule 6: the four sections, and a stated risk no lower than computed."""
    found = sections(body)
    findings = [
        f"FAIL: PR body lacks the {name} section"
        for name in SECTIONS
        if name.lower() not in found
    ]
    if "risk" in found:
        level = re.search(r"\b(low|medium|high)\b", found["risk"], re.IGNORECASE)
        if not level:
            findings.append(
                "FAIL: the Risk section states no level (low, medium or high)"
            )
        else:
            stated = level.group(1).lower()
            if risk.LEVELS.index(stated) < risk.LEVELS.index(computed):
                findings.append(
                    f"FAIL: stated risk {stated} is below the computed {computed}"
                )
    return findings


def read_body(args: argparse.Namespace) -> str | None:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if args.pr:
        return _run(["gh", "pr", "view", str(args.pr), "--json", "body", "-q", ".body"])
    return None


# --- main ---------------------------------------------------------------------


def verify(ref: str, body: str | None) -> list[str]:
    numstat = git("diff", "--numstat", "--no-renames", f"origin/main...{ref}")
    paths, lines = risk.parse_numstat(numstat)
    diff = git("diff", "-U0", "--no-renames", "--no-color", f"origin/main...{ref}")
    findings = commit_findings(ref) + line_findings(diff)
    if body is None:
        findings.append("WARN: PR body not checked (give --pr or --body-file)")
    else:
        findings += body_findings(body, risk.assess(paths))
    return findings + file_findings(paths, lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The mechanical checks of /verify-pr on a PR branch."
    )
    parser.add_argument("ref", nargs="?", default="HEAD", help="e.g. origin/<branch>")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--pr", type=int, help="read the PR body with gh")
    source.add_argument("--body-file", help="read the PR body from this file")
    args = parser.parse_args(argv)
    try:
        findings = verify(args.ref, read_body(args))
    except (ToolError, OSError) as exc:
        print(f"verify_pr: {exc}")
        return 2
    for line in findings:
        print(line)
    fail = sum(line.startswith("FAIL:") for line in findings)
    warn = sum(line.startswith("WARN:") for line in findings)
    print(f"verify_pr: {fail} fail, {warn} warn")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
