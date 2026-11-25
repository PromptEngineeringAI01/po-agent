"""`mysys/` and `core/` are client-free (tasks 9.2 and 9.4; ADR-003 decisions
2-3; SPEC.md -> Client 2: What is shared): no module under
src/po_agent/mysys/ imports a client package (`po_agent.b1`,
`po_agent.summit`) or holds one of B1's literals, and no module under
src/po_agent/core/ but `demo.py` (B1's demo, kept as is) imports one. Client
values come in as arguments: the Note Pool filters, the project match rule,
the body rule and the `Proceed`; `core/run.py` asks the client interface
(`core/client.py`). An AST scan, as tests/test_models.py's Proceed scan, for
direct imports; a fresh interpreter for an indirect one (a shared module
importing something that imports a client)."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "po_agent"
MYSYS = SRC / "mysys"
CORE = SRC / "core"
# B1's demo stays B1's (SPEC.md keeps `demo` as is; plan 9.4).
CORE_EXCEPT = ("demo.py",)
CLIENTS = ("po_agent.b1", "po_agent.summit")
B1_LITERALS = ("Perth Scheduling", "/048", "B1 Homes")


def _is_client(module: str) -> bool:
    return any(module == c or module.startswith(f"{c}.") for c in CLIENTS)


def client_imports(tree: ast.AST, package: str = "po_agent.mysys") -> list[str]:
    """Every client package a module imports: `import po_agent.b1...`,
    `from po_agent.b1... import`, `from po_agent import b1`, a relative
    `from ..b1 import` (mysys/ and core/ sit one below po_agent), or a module
    path named in a string (importlib)."""
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
                base = ".".join(p for p in (package, node.module) if p)
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


def core_modules() -> dict[str, ast.AST]:
    return {
        path.relative_to(CORE).as_posix(): ast.parse(path.read_text("utf-8"))
        for path in sorted(CORE.rglob("*.py"))
        if path.relative_to(CORE).as_posix() not in CORE_EXCEPT
    }


def shared_module_names() -> list[str]:
    """Every module under mysys/ and core/ but the demo, as import names."""
    names = [f"po_agent.mysys.{n.removesuffix('.py')}" for n in mysys_modules()]
    names += [f"po_agent.core.{n.removesuffix('.py')}" for n in core_modules()]
    return [n.removesuffix(".__init__") for n in names]


def test_the_booker_is_a_mysys_module() -> None:
    # The scan covers W1-W5: both clients run the one booker (ADR-003 C).
    assert {"booker.py", "booking.py", "driver.py", "guard.py"} <= set(mysys_modules())


def test_no_mysys_module_imports_a_client_package() -> None:
    found = {name: client_imports(tree) for name, tree in mysys_modules().items()}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_no_mysys_module_holds_a_b1_literal() -> None:
    found = {name: b1_literals(tree) for name, tree in mysys_modules().items()}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_the_core_scan_covers_the_run_loop_and_its_controls() -> None:
    # Plan 9.4: run.py, controls.py and trace.py by name; demo.py left out.
    assert {"run.py", "controls.py", "trace.py", "client.py"} <= set(core_modules())
    assert "demo.py" not in core_modules()


def test_no_core_module_imports_a_client_package() -> None:
    found = {
        name: client_imports(tree, "po_agent.core")
        for name, tree in core_modules().items()
    }
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_no_shared_module_pulls_in_a_client_package_on_import() -> None:
    # The indirect path the AST scan can't see (9.2 review): importing every
    # mysys/ and core/ module but the demo, in a fresh interpreter, loads no
    # client package.
    code = "\n".join(
        [
            "import importlib, sys",
            "for name in sys.argv[1:]:",
            "    importlib.import_module(name)",
            "clients = (['po_agent', 'b1'], ['po_agent', 'summit'])",
            "print(' '.join(m for m in sys.modules if m.split('.')[:2] in clients))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code, *shared_module_names()],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.split() == []


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
    ("source", "imports"),
    [
        ("from ..b1.decision import decide", True),
        ("from ..summit import client", True),
        ("from .client import Client", False),
        ("from . import controls", False),
        ("from ..mysys import driver", False),
    ],
)
def test_the_import_scan_resolves_core_s_relative_imports(
    source: str, imports: bool
) -> None:
    assert bool(client_imports(ast.parse(source), "po_agent.core")) is imports


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
