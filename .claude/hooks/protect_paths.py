"""Claude Code PreToolUse hook for Edit/Write: block or ask before risky paths.

Reads the tool call as JSON on stdin (https://code.claude.com/docs/en/hooks).
Exit 2 blocks, with stderr saying why; to ask, it prints the
`permissionDecision: "ask"` JSON and exits 0. Anything that goes wrong in here
also exits 2, so the hook fails closed.

Every path is resolved first (absolute, `..` collapsed, symlinks followed) and
then matched by whole folders, never as a string prefix, so `plans-evil/`
isn't inside `plans/`. Outside the repo, only three folders may be written
(decisions, 24 Oct 2026): `~/.claude/plans/`, this project's memory folder and
`<temp>/claude/`.
"""

import fnmatch
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePath

HOOK = "protect_paths"
BLOCKED_DIRS = {"secrets", "state", ".state"}  # at any depth
ASK_FILES = {"docs/macmini-setup.md", "scripts/macmini-run.sh"}


class Blocked(Exception):
    pass


def resolve(raw: str, base: str) -> Path:
    """Absolute, `..` collapsed, symlinks followed; the file needn't exist.
    https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.resolve
    """
    # On Windows the path arrives with backslashes; on macOS a backslash in a
    # path is almost certainly one too.
    return Path(base, raw.replace("\\", "/")).resolve()


def comparable(path: Path) -> PurePath:
    # normcase lowercases and uses `\` on Windows; it's a no-op elsewhere.
    return PurePath(os.path.normcase(path))


def inside(path: Path, folder: Path) -> bool:
    """Whole-folder containment on resolved paths.
    https://docs.python.org/3.12/library/pathlib.html#pathlib.PurePath.is_relative_to
    """
    return comparable(path).is_relative_to(comparable(folder))


def allowed_outside(project_raw: str) -> list[Path]:
    home = Path.home()
    # Claude Code names a project's folder after its path, with every
    # character that isn't a letter or digit replaced by "-".
    mangled = re.sub(r"[^A-Za-z0-9]", "-", project_raw)
    return [
        (home / ".claude" / "plans").resolve(),
        (home / ".claude" / "projects" / mangled / "memory").resolve(),
        # https://docs.python.org/3.12/library/tempfile.html#tempfile.gettempdir
        (Path(tempfile.gettempdir()) / "claude").resolve(),
    ]


def decide_in_repo(path: Path, project: Path) -> str | None:
    """'ask', or None to allow; raises Blocked."""
    parts = [p.lower() for p in path.relative_to(project).parts]
    rel = "/".join(parts)
    if ".claude" in parts:
        raise Blocked(".claude/ is changed only by Joey, by hand")
    if any(p.startswith(".env") for p in parts):
        raise Blocked(".env files hold secrets (Must never #5)")
    if BLOCKED_DIRS.intersection(parts[:-1]):
        raise Blocked("secrets/ and state/ never go in the repo (Must never #5, #6)")
    if fnmatch.fnmatchcase("/".join(parts[-2:]), "config/live*.toml"):
        raise Blocked("live config: the MVP is test site only (Must never #3)")
    if parts[:2] == [".github", "workflows"] or rel in ASK_FILES:
        return "ask-first file (tasks/plan.md, Cross-cutting rules)"
    if parts[:3] == ["tests", "seam1", "fixtures"] and path.exists():
        return "an existing seam-1 fixture (Must never #8)"
    return None


def decide(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        raise Blocked("no file path in the tool call")
    cwd = payload.get("cwd") or os.getcwd()
    project_raw = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    project = Path(project_raw).resolve()
    path = resolve(raw, cwd)
    if inside(path, project):
        return decide_in_repo(path, project)
    if any(inside(path, folder) for folder in allowed_outside(project_raw)):
        return None
    raise Blocked(f"{path} is outside the repo and the allowed folders")


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        reason = decide(payload)
    except Blocked as exc:
        sys.stderr.write(f"{HOOK}: blocked - {exc}. Joey does this by hand.\n")
        sys.exit(2)
    except Exception as exc:  # fail closed
        sys.stderr.write(f"{HOOK}: blocked - hook error ({type(exc).__name__}).\n")
        sys.exit(2)
    if reason:
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"{HOOK}: {reason}",
            }
        }
        sys.stdout.write(json.dumps(decision))


if __name__ == "__main__":
    main()
