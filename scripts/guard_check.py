"""Build check: only the guard acts on the page (CLAUDE.md Must never #1).

`uv run python scripts/guard_check.py [root]` scans the .py files under src/,
scripts/ and tests/ (AST, not text) and exits 1, one "<path>:<line>: ..." line
per finding, on:

- an attribute (a call or a reference) named like a page action, script,
  dialog, network, navigation or disk call, or keyboard/mouse/touchscreen
  (tasks/plan.md task 1.4), or `getattr(x, "<that name>")`. Exceptions: the
  six action methods inside `act()` in src/po_agent/mysys/guard.py, and
  `goto`/`reload` inside `go_home()` in src/po_agent/mysys/driver.py. A name
  that clashes with other code is fixed by renaming that code, never a waiver.
- in src/, a typed error (a PoAgentError subclass in core/errors.py) whose
  detail isn't a plain string constant: details are fixed strings, never page
  text (1.5 review).
- in src/, `print` (a call or a reference, bare or as an attribute) outside
  src/po_agent/core/output.py, the only printer of the stdout contract (1.6).

Known gaps (code review is the control): operator.methodcaller, page JS via
wait_for_function, record_har_path= keyword arguments, force=True in act().
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ("src", "scripts", "tests")
ERRORS = "src/po_agent/core/errors.py"
BASE_ERROR = "PoAgentError"
OUTPUT = "src/po_agent/core/output.py"

BANNED = frozenset(
    {
        # Page actions
        "click",
        "dblclick",
        "tap",
        "fill",
        "clear",
        "type",
        "press",
        "press_sequentially",
        "check",
        "uncheck",
        "set_checked",
        "select_option",
        "select_text",
        "set_input_files",
        "set_files",
        "hover",
        "focus",
        "drag_to",
        "drag_and_drop",
        "dispatch_event",
        # Scripts and dialogs
        "evaluate",
        "evaluate_handle",
        "evaluate_all",
        "add_init_script",
        "add_script_tag",
        "expose_function",
        "expose_binding",
        "accept",
        "dismiss",
        # Network and navigation; `request` is the APIRequestContext attribute
        "route",
        "route_from_har",
        "request",
        "goto",
        "reload",
        "go_back",
        "go_forward",
        # Disk
        "storage_state",
        "tracing",
        "screenshot",
        "record_video_dir",
        "record_har_path",
        # Raw input devices
        "keyboard",
        "mouse",
        "touchscreen",
    }
)
# (file, enclosing function) -> the banned names allowed there.
EXEMPT = {
    ("src/po_agent/mysys/guard.py", "act"): frozenset(
        {
            "click",
            "fill",
            "check",
            "uncheck",
            "select_option",
            "set_input_files",
            "press",  # Enter on two search boxes only (28 Oct 2026)
        }
    ),
    ("src/po_agent/mysys/driver.py", "go_home"): frozenset({"goto", "reload"}),
}


def error_classes(root: Path) -> frozenset[str]:
    """PoAgentError and every class in core/errors.py that derives from it."""
    path = root / ERRORS
    if not path.is_file():
        return frozenset()
    found = {BASE_ERROR}
    classes = [
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ClassDef)
    ]
    grew = True
    while grew:
        grew = False
        for node in classes:
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            if node.name not in found and bases & found:
                found.add(node.name)
                grew = True
    return frozenset(found)


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _detail(call: ast.Call) -> ast.expr | None:
    if call.args:
        return call.args[0]
    return next((kw.value for kw in call.keywords if kw.arg == "detail"), None)


def _is_fixed_string(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def scan_file(rel: str, source: str, errors: frozenset[str]) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{rel}:{exc.lineno}: cannot parse"]
    found: list[str] = []
    check_errors = rel.startswith("src/")
    check_print = check_errors and rel != OUTPUT

    def visit(node: ast.AST, allowed: frozenset[str]) -> None:
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Attribute) and node.attr in BANNED - allowed:
            found.append(f"{rel}:{line}: {node.attr}: page action outside the guard")
        if check_print and (
            (isinstance(node, ast.Name) and node.id == "print")
            or (isinstance(node, ast.Attribute) and node.attr == "print")
        ):
            found.append(f"{rel}:{line}: print: only core/output.py prints")
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in BANNED
            ):
                name = node.args[1].value
                found.append(f"{rel}:{line}: getattr {name}: page action by name")
            name = _call_name(node)
            if check_errors and name in errors and not _is_fixed_string(_detail(node)):
                found.append(
                    f"{rel}:{line}: {name}: error detail must be a fixed string"
                )
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            allowed = allowed | EXEMPT.get((rel, node.name), frozenset())
        for child in ast.iter_child_nodes(node):
            visit(child, allowed)

    visit(tree, frozenset())
    return sorted(found, key=lambda line: int(line.split(":")[1]))


def violations(root: Path) -> list[str]:
    """One "<path>:<line>: <name>: <why>" line per finding under `root`."""
    errors = error_classes(root)
    found: list[str] = []
    for folder in SCANNED:
        for path in sorted((root / folder).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            found += scan_file(rel, path.read_text(encoding="utf-8"), errors)
    return found


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else ROOT
    found = violations(root)
    for line in found:
        print(line)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
