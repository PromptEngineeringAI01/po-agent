"""Claude Code PostToolUse hook for Edit/Write: ruff format, then ruff check --fix.

Only `.py` files. Lint that ruff can't fix is reported with exit 2, which is how
a PostToolUse hook shows its stderr to Claude (the edit has already happened;
https://code.claude.com/docs/en/hooks, "Exit code 2 behavior per event").
ruff runs from this interpreter's environment, so the project's pinned ruff and
its pyproject.toml settings apply (https://docs.astral.sh/ruff/configuration/).
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK = "format_python"


def ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        raw = (payload.get("tool_input") or {}).get("file_path") or ""
        path = Path(raw)
        if path.suffix.lower() != ".py" or not path.is_file():
            return
        formatted = ruff("format", "--quiet", str(path))
        linted = ruff("check", "--fix", "--quiet", str(path))
    except Exception as exc:
        sys.stderr.write(f"{HOOK}: hook error ({type(exc).__name__})\n")
        sys.exit(2)
    problems = [r.stdout + r.stderr for r in (formatted, linted) if r.returncode != 0]
    if problems:
        sys.stderr.write(f"{HOOK}: ruff left problems in {path}:\n" + "".join(problems))
        sys.exit(2)


if __name__ == "__main__":
    main()
