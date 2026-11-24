"""Claude Code PreToolUse hook for the browser tools and WebFetch.

Reads the tool call as JSON on stdin; exit 2 blocks it and stderr says why
(https://code.claude.com/docs/en/hooks, "Exit code output"). Anything that goes
wrong in here also exits 2, so the hook fails closed.

The rules (decisions, 24 Nov 2026, browser tools):

- Any MCP server named like chrome, browser or preview, except the built-in
  pane (`mcp__Claude_Browser__*`), is blocked whole. That is Claude in Chrome
  (Joey's own browser, signed in to live MySys and Outlook; CLAUDE.md Must
  never #2, #3, #4) under any spelling, and any other browser server.
- In the built-in pane only the tools named in PANE_TOOLS pass, so a tool
  added later is blocked until Joey lists it. javascript_tool, form_input and
  read_network_requests are not listed: page scripts, direct field values and
  network bodies are outside the 10 Nov live-lookup exception. Clicks and
  typing pass: the hook sees only a ref or a point, so it can't tell a search
  click from a write, and that exception needs them; its narrow list and Joey
  watching the pane stay the control.
- navigate and preview_start take only a web address (http, https, no
  scheme), "back" or "forward": a javascript:, data: or file: URL would run in
  the open page.
- No browser tool or WebFetch input may name a MySys host, live or test,
  however it is spelled (percent-encoded, any case, fullwidth or ideographic
  dots and letters, invisible format characters): Claude never opens MySys
  itself (Joey logs in; Must never #3), and seam 2 reaches the test site only
  through Playwright.
- `browser_batch` is checked item by item; a batch inside a batch is blocked.

It matches text, so it's a backstop, like guard_bash.py: an IP address for
MySys, for one, isn't caught.
"""

import json
import re
import sys
import unicodedata
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

HOOK = "guard_browser"
PANE_SERVER = "Claude_Browser"
WEBFETCH = "WebFetch"
BATCH = "browser_batch"
# The pane tools Claude may call: looking, reading, clicking and typing.
PANE_TOOLS = frozenset(
    {
        "browser_batch",
        "computer",
        "find",
        "get_page_text",
        "navigate",
        "preview_list",
        "preview_logs",
        "preview_start",
        "preview_stop",
        "read_console_messages",
        "read_page",
        "resize_window",
        "tabs_close",
        "tabs_context",
        "tabs_create",
        "tabs_select",
    }
)
URL_TOOLS = frozenset({"navigate", "preview_start"})
MCP_NAME = re.compile(r"mcp__(.+?)__(.+)")
BROWSER_SERVER = re.compile(r"chrome|browser|preview", re.IGNORECASE)
MYSYS = re.compile(r"mysys\.com\.au", re.IGNORECASE)
# Dots a browser's host parser reads as "." (after NFKC, which maps U+FF0E).
DOTS = str.maketrans({"。": ".", "｡": "."})


class Blocked(Exception):
    pass


def strings(value: Any) -> Iterator[str]:
    """Every string in a tool input, keys included, at any depth."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def plain(text: str) -> str:
    """Percent-decoded until it stops changing (at most 3 rounds), then
    NFKC, look-alike dots made ".", and format characters (soft hyphen,
    zero-width) dropped, as a browser does to a host name."""
    for _ in range(3):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    text = unicodedata.normalize("NFKC", text).translate(DOTS)
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def check_no_mysys(tool_input: Any) -> None:
    if any(MYSYS.search(plain(text)) for text in strings(tool_input)):
        raise Blocked(
            "a MySys address in a browser tool or WebFetch: Claude never opens "
            "MySys itself; Joey logs in (Must never #3)"
        )


def check_url(tool_input: Any) -> None:
    """A web address, "back" or "forward"; no url at all is fine too."""
    url = tool_input.get("url") if isinstance(tool_input, dict) else None
    if url is None:
        return
    if not isinstance(url, str):
        raise Blocked("a url that isn't text")
    lower = url.strip().lower()
    if lower in ("back", "forward") or lower.startswith(("http://", "https://")):
        return
    if ":" in url:
        raise Blocked("only http and https addresses: another scheme runs in the page")


def check_pane(name: str, tool_input: Any, in_batch: bool = False) -> None:
    if name not in PANE_TOOLS:
        raise Blocked(
            f"pane tool {name!r} isn't on guard_browser's list "
            "(scripts, field values and network bodies stay off it)"
        )
    if name in URL_TOOLS:
        check_url(tool_input)
    if name != BATCH:
        return
    if in_batch:
        raise Blocked("a browser_batch inside a browser_batch")
    actions = tool_input.get("actions") if isinstance(tool_input, dict) else None
    if not isinstance(actions, list):
        raise Blocked("a browser_batch without a list of actions")
    for item in actions:
        item_name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(item_name, str) or not item_name:
            raise Blocked("a browser_batch item without a tool name")
        if item_name.startswith("mcp__"):
            mcp = MCP_NAME.fullmatch(item_name)
            if not mcp or mcp.group(1) != PANE_SERVER:
                raise Blocked("another server's tool inside a browser_batch")
            item_name = mcp.group(2)
        check_pane(item_name, item.get("input"), in_batch=True)


def decide(payload: Any) -> None:
    """Returns to allow; raises Blocked."""
    if not isinstance(payload, dict):
        raise Blocked("the tool call isn't a JSON object")
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise Blocked("no tool name in the tool call")
    tool_input = payload.get("tool_input")
    if tool == WEBFETCH:
        check_no_mysys(tool_input)
        return
    mcp = MCP_NAME.fullmatch(tool)
    if not mcp:
        return
    server, name = mcp.groups()
    if server == PANE_SERVER:
        check_no_mysys(tool_input)
        check_pane(name, tool_input)
    elif BROWSER_SERVER.search(server):
        raise Blocked(
            f"browser server {server!r}: Claude in Chrome is Joey's own browser, "
            "signed in to live MySys and Outlook, and only the built-in pane "
            "is allowed (Must never #2, #3, #4)"
        )


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        decide(json.loads(sys.stdin.buffer.read().decode("utf-8")))
    except Blocked as exc:
        sys.stderr.write(f"{HOOK}: blocked - {exc}. Joey does this by hand.\n")
        sys.exit(2)
    except Exception as exc:  # fail closed
        sys.stderr.write(f"{HOOK}: blocked - hook error ({type(exc).__name__}).\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
