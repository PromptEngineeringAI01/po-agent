"""Claude Code PreToolUse hook for Bash: block commands that break a Must-never rule.

Reads the tool call as JSON on stdin; exit 2 blocks it and stderr says why
(https://code.claude.com/docs/en/hooks, "Exit code output"). Anything that goes
wrong in here also exits 2, so the hook fails closed.

It matches text, so it's a backstop: the action guard, the repo-data check and
gitleaks are the main controls (docs/workflow.md, Appendix A).

This file and tests/test_hooks.py are the only places the live host may appear
(CLAUDE.md Must never #3; decisions, 16 Oct 2026, D4).
"""

import json
import re
import shlex
import subprocess
import sys

HOOK = "guard_bash"
TEST_ORIGIN = "https://test-prompt.mysys.com.au"

# Rules checked against the whole command text: (rule, why, pattern).
TEXT_RULES = [
    (
        "live site",
        "the MVP is test site only (Must never #3)",
        # Appendix A's pattern; hostnames ignore case, so the match does too.
        re.compile(r"(?<!test-)prompt\.mysys\.com\.au", re.IGNORECASE),
    ),
    (
        "Anthropic key",
        "secrets never go in a command (Must never #5)",
        re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ),
    (
        "environment dump",
        "it can print secrets (Must never #5)",
        re.compile(
            r"\bprintenv\b"
            r"|/proc/[^\s/]+/environ"
            r"|PO_AGENT_"
            r"|\bexport\s+-p\b"
            r"|\bdeclare\s+-x\b"
            r"|\bos\.environ\b"
            r"|\benv:",  # PowerShell's env: drive and $env:NAME
            re.IGNORECASE,
        ),
    ),
    (
        "gh pr merge",
        "Joey merges (Must never #9)",
        re.compile(r"\bgh\s+pr\s+merge\b"),
    ),
]

# Tokens made only of these end a simple command (`;`, `&&`, `|`, `(`, ...).
SEPARATOR_CHARS = set(";&|()`")
PLAYWRIGHT_OBSERVE = {
    "snapshot",
    "screenshot",
    "find",
    "generate-locator",
    "tab-list",
    "list",
    "close",  # closes the CLI's own browser, not a MySys control
    "--version",
    "--help",
}
REAL_DATA_DIRS = {"private", "state", ".state", "logs"}
TOOLS = {"Bash", "PowerShell"}
# Programs that run the command after them: `npx playwright-cli ...`.
WRAPPERS = {"npx", "uvx", "env", "sudo", "xargs", "command", "exec", "time", "nohup"}
SHELLS = {"bash", "sh", "zsh", "dash"}
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
CONTINUATION = re.compile(r"\\\r?\n")
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?")
SHELL_WORD = re.compile(r"\b(bash|sh|zsh|dash|pwsh|powershell)\b", re.IGNORECASE)
MAX_DEPTH = 3  # how deep `bash -c "..."` inside `bash -c "..."` is checked


class Blocked(Exception):
    def __init__(self, rule: str, why: str):
        super().__init__(f"{rule}: {why}")


def line_tokens(line: str) -> list[str]:
    """Shell words of one line, quotes respected, backslashes kept (Windows
    paths); `;`, `&`, `|`, `(`, `)` and backticks come out as their own tokens.
    https://docs.python.org/3.12/library/shlex.html#shlex.shlex.punctuation_chars
    """
    lexer = shlex.shlex(line, posix=True, punctuation_chars="();<>|&`")
    lexer.whitespace_split = True
    lexer.escape = ""
    try:
        return list(lexer)
    except ValueError:  # unbalanced quotes: split on separators and spaces
        return re.sub(r"([;&|()`])", r" \1 ", line).split()


def simple_commands(command: str) -> list[list[str]]:
    """The command's simple commands, one list of words each.

    A backslash-newline continues the line. A heredoc's body is text (a
    commit message, say) and is skipped, unless a shell on that line reads it.
    """
    found: list[list[str]] = []
    heredoc_end = None
    for line in CONTINUATION.sub(" ", command).splitlines():
        if heredoc_end is not None:
            if line.strip() == heredoc_end:
                heredoc_end = None
            continue
        start = HEREDOC.search(line)
        if start and not SHELL_WORD.search(line):
            heredoc_end = start.group(1)
        words: list[str] = []
        for token in line_tokens(line):
            if set(token) <= SEPARATOR_CHARS:
                found.append(words)
                words = []
            else:
                words.append(token)
        found.append(words)
    return [words for words in found if words]


def program(word: str) -> str:
    """`/usr/bin/git` and `git.exe` are both `git`."""
    name = re.split(r"[\\/]", word)[-1].lower()
    return name.removesuffix(".exe")


def is_bare(words: list[str], name: str) -> bool:
    """`name` with no arguments, apart from a redirect."""
    return program(words[0]) == name and (len(words) == 1 or words[1][0] in "<>")


def unwrap(words: list[str]) -> list[str]:
    """Drop leading `VAR=value`s and wrappers (`npx`, `sudo`, `uv run`), with
    their options, so the program that really runs comes first."""
    while words:
        first = program(words[0])
        if ASSIGNMENT.match(words[0]) or first in WRAPPERS:
            words = words[1:]
        elif first == "uv" and words[1:2] == ["run"]:
            words = words[2:]
        else:
            return words
        while words and words[0].startswith("-"):
            words = words[1:]
    return words


def nested_command(words: list[str]) -> str | None:
    """The command a shell is given as text: `bash -c "..."`, `cmd /c ...`,
    `powershell -Command ...`, `eval ...`."""
    first, rest = program(words[0]), words[1:]
    for i, word in enumerate(rest):
        lower = word.lower()
        if first in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", word):
            return " ".join(rest[i + 1 : i + 2])
        if first == "cmd" and lower in ("/c", "/k"):
            return " ".join(rest[i + 1 :])
        if first in ("powershell", "pwsh") and lower in ("-c", "-command"):
            return " ".join(rest[i + 1 :])
    if first == "eval":
        return " ".join(rest)
    return None


def check_playwright(words: list[str]) -> None:
    if program(words[0]) != "playwright-cli":
        return
    sub = words[1] if len(words) > 1 else ""
    if sub in PLAYWRIGHT_OBSERVE:
        return
    if sub == "open":
        check_playwright_open(words[2:])
        return
    raise Blocked(
        f"playwright-cli {sub}".strip(),
        "only observe commands are allowed (Must never #1)",
    )


def check_playwright_open(args: list[str]) -> None:
    if any(a.startswith(("--persistent", "--profile")) for a in args):
        raise Blocked("playwright-cli open", "no persistent profile (it saves state)")
    urls = [a for a in args if "://" in a]
    test_urls = [u for u in urls if u == TEST_ORIGIN or u.startswith(TEST_ORIGIN + "/")]
    if not test_urls or len(test_urls) != len(urls):
        raise Blocked("playwright-cli open", "only the test-site URL may be opened")


def git_args(words: list[str], verbs: tuple[str, ...]) -> tuple[str, list[str]] | None:
    """(verb, args after it) if `words` is `git [opts] <verb> ...`."""
    if program(words[0]) != "git":
        return None
    i = 1
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in ("-C", "-c") else 1  # these take a value
    if i < len(words) and words[i] in verbs:
        return words[i], words[i + 1 :]
    return None


def current_branch(cwd: str | None) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=cwd or None,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def check_push(args: list[str], cwd: str | None) -> None:
    flags = [a for a in args if a.startswith("-")]
    positional = [a for a in args if not a.startswith("-")]
    for flag in flags:
        short_force = not flag.startswith("--") and "f" in flag[1:]
        if flag.startswith("--force") or short_force:
            raise Blocked("force push", "never force-push (Must never #9)")
        if flag in ("--all", "--mirror"):
            raise Blocked("push to main", f"{flag} pushes main too (Must never #9)")
    # positional[0] is the remote; the rest are refspecs.
    for refspec in positional[1:]:
        if refspec.startswith("+"):
            raise Blocked("force push", "a + refspec forces (Must never #9)")
        source, _, dest = refspec.partition(":")
        target = dest or source
        if target in ("HEAD", "@"):
            target = current_branch(cwd)
            if target is None:
                raise Blocked(
                    "push to main", "HEAD on an unknown branch (Must never #9)"
                )
        if target in ("main", "refs/heads/main"):
            raise Blocked("push to main", "never push to main (Must never #9)")
    if len(positional) <= 1:
        branch = current_branch(cwd)
        if branch is None or branch == "main":
            raise Blocked(
                "push to main",
                "a bare push from main (or an unknown branch) (Must never #9)",
            )


def check_rm(words: list[str]) -> None:
    if program(words[0]) != "rm":
        return
    letters = "".join(
        w[1:] for w in words if w.startswith("-") and not w.startswith("--")
    )
    recursive = "r" in letters.lower() or "--recursive" in words
    force = "f" in letters or "--force" in words
    if recursive and force:
        raise Blocked("rm -rf", "delete by hand if it's really needed")


def check_stage(args: list[str]) -> None:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-m", "--message", "-F", "--file", "-C", "-c"):
            skip_next = True  # the next word is a message or a file, not a path
            continue
        parts = [p for p in re.split(r"[\\/]", arg.lower()) if p]
        if any(p in REAL_DATA_DIRS or p.startswith(".env") for p in parts):
            raise Blocked(
                "staging real data or secrets",
                f"{arg} never goes in git (Must never #5, #6)",
            )


def check(command: str, cwd: str | None, depth: int = 0) -> None:
    for rule, why, pattern in TEXT_RULES:
        if pattern.search(command):
            raise Blocked(rule, why)
    for words in simple_commands(command):
        if is_bare(words, "env") or is_bare(words, "set"):
            raise Blocked(
                f"bare {words[0]}", "it prints every variable (Must never #5)"
            )
        words = unwrap(words)
        if not words:
            continue
        inner = nested_command(words)
        if inner is not None:
            if depth >= MAX_DEPTH:
                raise Blocked("nested command", "too deeply nested to check")
            check(inner, cwd, depth + 1)
            continue
        check_playwright(words)
        check_rm(words)
        push = git_args(words, ("push",))
        if push:
            check_push(push[1], cwd)
        stage = git_args(words, ("add", "commit"))
        if stage:
            check_stage(stage[1])


def block(message: str) -> None:
    sys.stderr.write(
        f"{HOOK}: blocked - {message}. Joey does this by hand, outside Claude Code.\n"
    )
    sys.exit(2)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        tool = payload.get("tool_name")
        if tool not in TOOLS:
            raise Blocked("unexpected tool", f"{tool!r} isn't Bash or PowerShell")
        command = payload["tool_input"]["command"]
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not text")
        check(command, payload.get("cwd"))
    except Blocked as exc:
        block(str(exc))
    except Exception as exc:  # fail closed
        block(f"hook error ({type(exc).__name__}), so the command is not run")


if __name__ == "__main__":
    main()
