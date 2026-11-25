"""`mysys/` is client-free (task 9.2; ADR-003 decision 3; SPEC.md -> Client 2:
What is shared): no module under src/po_agent/mysys/ imports a client package
(`po_agent.b1`, `po_agent.summit`) or holds one of B1's literals. Client
values come in as arguments: the Note Pool filters, the project match rule,
the body rule and the `Proceed`. An AST scan, as tests/test_models.py's
Proceed scan."""

import ast
from pathlib import Path

import pytest

MYSYS = Path(__file__).resolve().parent.parent / "src" / "po_agent" / "mysys"
CLIENTS = ("po_agent.b1", "po_agent.summit")
B1_LITERALS = ("Perth Scheduling", "/048", "B1 Homes")


def _is_client(module: str) -> bool:
    return any(module == c or module.startswith(f"{c}.") for c in CLIENTS)


def client_imports(tree: ast.AST) -> list[str]:
    """Every client package a module imports: `import po_agent.b1...`,
    `from po_agent.b1... import`, `from po_agent import b1`, a relative
    `from ..b1 import` (mysys/ sits one below po_agent), or a module path
    named in a string (importlib)."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if _is_client(a.name)]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            elif node.level == 2:
                base = ".".join(p for p in ("po_agent", node.module) if p)
            else:
                base = ".".join(p for p in ("po_agent.mysys", node.module) if p)
            names = [f"{base}.{a.name}" for a in node.names]
            found += [n for n in (base, *names) if _is_client(n)][:1]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found += [c for c in CLIENTS if c in node.value]
    return found


def b1_literals(tree: ast.AST) -> list[str]:
    """Every listed B1 literal in a string constant (docstrings and f-string
    parts too), any case."""
    return [
        literal
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for literal in B1_LITERALS
        if literal.casefold() in node.value.casefold()
    ]


def mysys_modules() -> dict[str, ast.AST]:
    return {
        path.relative_to(MYSYS).as_posix(): ast.parse(path.read_text("utf-8"))
        for path in sorted(MYSYS.rglob("*.py"))
    }


def test_the_booker_is_a_mysys_module() -> None:
    # The scan covers W1-W5: both clients run the one booker (ADR-003 C).
    assert {"booker.py", "booking.py", "driver.py", "guard.py"} <= set(mysys_modules())


def test_no_mysys_module_imports_a_client_package() -> None:
    found = {name: client_imports(tree) for name, tree in mysys_modules().items()}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_no_mysys_module_holds_a_b1_literal() -> None:
    found = {name: b1_literals(tree) for name, tree in mysys_modules().items()}
    assert {name: hits for name, hits in found.items() if hits} == {}


@pytest.mark.parametrize(
    ("source", "imports"),
    [
        ("import po_agent.b1.decision", True),
        ("import po_agent.summit as s", True),
        ("from po_agent.b1 import reader_rules as rules", True),
        ("from po_agent.b1.decision import Site", True),
        ("from po_agent import b1", True),
        ("from po_agent import core, summit", True),
        ("from ..b1 import decision", True),
        ("from .. import b1", True),
        ("importlib.import_module('po_agent.b1.decision')", True),
        ("from po_agent.core.models import Proceed", False),
        ("from po_agent.mysys import driver", False),
        ("from . import guard", False),
        ("from .. import core", False),
        ("import po_agent.b10", False),
        ("from po_agent import b1x", False),
    ],
)
def test_the_import_scan_sees_every_way_to_import_a_client(
    source: str, imports: bool
) -> None:
    assert bool(client_imports(ast.parse(source))) is imports


@pytest.mark.parametrize(
    ("source", "holds"),
    [
        ('CREATOR = "Perth Scheduling"', True),
        ('"""Order 2600001B/048, the title."""', True),
        ('title = f"[B1 Homes] Order {internal_no}"', True),
        ('company = "b1 homes"', True),
        ('task = "Compaction Test"', False),
        ("# B1 Homes in a comment is not a value", False),
        ('pool = "Agent Pool"', False),
    ],
)
def test_the_literal_scan_sees_b1_s_values(source: str, holds: bool) -> None:
    assert bool(b1_literals(ast.parse(source))) is holds
