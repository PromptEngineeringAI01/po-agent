"""Tests for scripts/guard_check.py, the AST build check (task 1.4).

Each case writes a small source tree to tmp_path and scans it. The code under
test is only ever a string here, so nothing in this file acts on a page.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUARD = "src/po_agent/mysys/guard.py"
DRIVER = "src/po_agent/mysys/driver.py"
ERRORS_SOURCE = (ROOT / "src/po_agent/core/errors.py").read_text(encoding="utf-8")


def _load_guard_check():
    # scripts/ isn't a package, so load the file directly.
    spec = importlib.util.spec_from_file_location(
        "guard_check", ROOT / "scripts" / "guard_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Loaded at import too, so the per-name tests below can parametrize over BANNED.
GUARD_CHECK = _load_guard_check()


@pytest.fixture(scope="module")
def guard_check():
    return GUARD_CHECK


def tree(root: Path, files: dict[str, str]) -> Path:
    """A source tree with the real core/errors.py plus `files`."""
    all_files = {"src/po_agent/core/errors.py": ERRORS_SOURCE, **files}
    for rel, source in all_files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


def scan(guard_check, root: Path, rel: str, source: str) -> list[str]:
    return guard_check.violations(tree(root, {rel: source}))


# --- banned page actions ----------------------------------------------------


@pytest.mark.parametrize(
    "source, name",
    [
        ("locator.check()\n", "check"),
        ("page.request.post('x')\n", "request"),
        ("api = context.request\n", "request"),
        ("getattr(x, 'click')()\n", "click"),
        ("page.keyboard.down('Shift')\n", "keyboard"),
        ("page.mouse.wheel(0, 1)\n", "mouse"),
        ("page.touchscreen\n", "touchscreen"),
        ("page.goto('https://example.invalid')\n", "goto"),
        ("page.evaluate('1')\n", "evaluate"),
        ("dialog.accept()\n", "accept"),
        ("page.route('**', handler)\n", "route"),
        ("context.tracing.start()\n", "tracing"),
        ("page.screenshot()\n", "screenshot"),
        ("f = locator.fill\n", "fill"),  # a reference, not only a call
    ],
)
@pytest.mark.parametrize(
    "rel",
    ["src/po_agent/mysys/booker.py", "scripts/tool.py", "tests/test_x.py"],
)
def test_banned_call_or_reference_fails_anywhere(
    tmp_path, guard_check, source, name, rel
):
    found = scan(guard_check, tmp_path, rel, source)

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:1:")
    assert name in found[0]


@pytest.mark.parametrize(
    "source",
    [
        "guard.vet('assign_note', scope, target)\n",
        "guard.act('assign_note', scope, target)\n",
        "download.delete()\n",
        "mock.patch('x')\n",
        "page.set_content('<p>x</p>')\n",
        "type(x)\n",
        "subprocess.run(['x'], check=True)\n",
        "locator.get_attribute('data-clicked')\n",
        "request.node\n",  # pytest's request fixture is a name, not an attribute
    ],
)
def test_allowed_code_passes(tmp_path, guard_check, source):
    assert scan(guard_check, tmp_path, "tests/test_x.py", source) == []


ACT = """\
class ActionGuard:
    def act(self, action, scope, target, value=None):
        element = self.vet(action, scope, target, value).element
        element.{call}
"""


@pytest.mark.parametrize(
    "call",
    [
        "click()",
        "fill(value)",
        "check()",
        "uncheck()",
        "select_option(label=value)",
        "set_input_files(value)",
        "press(value)",
        "hover(force=True)",
    ],
)
def test_action_methods_are_allowed_inside_guard_act(tmp_path, guard_check, call):
    assert scan(guard_check, tmp_path, GUARD, ACT.format(call=call)) == []


@pytest.mark.parametrize(
    "call", ["evaluate('1')", "type('x')", "dispatch_event('click')", "tap()"]
)
def test_other_banned_names_fail_even_inside_guard_act(tmp_path, guard_check, call):
    found = scan(guard_check, tmp_path, GUARD, ACT.format(call=call))

    assert len(found) == 1
    assert found[0].startswith(f"{GUARD}:4:")


def test_click_in_guard_py_outside_act_fails(tmp_path, guard_check):
    source = (
        "class ActionGuard:\n"
        "    def vet(self, action, scope, target, value=None):\n"
        "        target.click()\n"
    )

    found = scan(guard_check, tmp_path, GUARD, source)

    assert len(found) == 1
    assert found[0].startswith(f"{GUARD}:3:")


def test_click_in_an_act_outside_guard_py_fails(tmp_path, guard_check):
    rel = "src/po_agent/mysys/other.py"

    found = scan(guard_check, tmp_path, rel, ACT.format(call="click()"))

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:4:")


GO_HOME = """\
def go_home(page, base_url):
    page.{call}
"""


@pytest.mark.parametrize("call", ["goto(base_url)", "reload()"])
def test_goto_and_reload_are_allowed_inside_driver_go_home(tmp_path, guard_check, call):
    assert scan(guard_check, tmp_path, DRIVER, GO_HOME.format(call=call)) == []


@pytest.mark.parametrize(
    "rel, source",
    [
        (DRIVER, "def open_note(page):\n    page.goto('x')\n"),
        (DRIVER, GO_HOME.format(call="click()")),
        ("src/po_agent/mysys/booker.py", GO_HOME.format(call="goto(base_url)")),
    ],
)
def test_goto_elsewhere_and_other_calls_in_go_home_fail(
    tmp_path, guard_check, rel, source
):
    assert len(scan(guard_check, tmp_path, rel, source)) == 1


def test_every_violation_is_reported(tmp_path, guard_check):
    source = "locator.check()\npage.goto('x')\ngetattr(x, 'evaluate')\n"

    found = scan(guard_check, tmp_path, "scripts/tool.py", source)

    assert [line.split(":")[1] for line in found] == ["1", "2", "3"]


# --- every banned name, one by one (audit N5) --------------------------------

# Written out here, not read from guard_check.BANNED: a name dropped from BANNED
# must fail these tests, and one added to BANNED is tested through the union.
BANNED_NAMES = frozenset(
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
        # Network and navigation
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
ALL_BANNED = sorted(BANNED_NAMES | GUARD_CHECK.BANNED)
# The only exemptions (scripts/guard_check.py EXEMPT), also written out here.
ACT_ALLOWED = frozenset(
    {
        "click",
        "fill",
        "check",
        "uncheck",
        "select_option",
        "set_input_files",
        "press",
        "hover",
    }
)
GO_HOME_ALLOWED = frozenset({"goto", "reload"})


@pytest.mark.parametrize(
    "template, label",
    [
        ("x.{name}\n", "{name}"),  # a reference
        ("x.{name}()\n", "{name}"),  # a call
        ("getattr(x, '{name}')\n", "getattr {name}"),
    ],
    ids=["reference", "call", "getattr"],
)
@pytest.mark.parametrize(
    "rel",
    ["src/po_agent/mysys/booker.py", "scripts/tool.py", "tests/test_x.py"],
)
@pytest.mark.parametrize("name", ALL_BANNED)
def test_every_banned_name_fails_anywhere(
    tmp_path, guard_check, name, rel, template, label
):
    found = scan(guard_check, tmp_path, rel, template.format(name=name))

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:1: {label.format(name=name)}: ")


@pytest.mark.parametrize("name", ALL_BANNED)
def test_inside_guard_act_only_the_eight_action_methods_pass(
    tmp_path, guard_check, name
):
    found = scan(guard_check, tmp_path, GUARD, ACT.format(call=f"{name}()"))

    if name in ACT_ALLOWED:
        assert found == []
    else:
        assert len(found) == 1
        assert found[0].startswith(f"{GUARD}:4: {name}: ")


VET = """\
class ActionGuard:
    def vet(self, action, scope, target, value=None):
        target.{call}
"""
# (file, source with {call}, line of the call): everywhere but act() in guard.py.
OUTSIDE_ACT = {
    "guard.py module level": (GUARD, "element.{call}\n", 1),
    "guard.py vet()": (GUARD, VET, 3),
    "act() in another file": ("src/po_agent/mysys/other.py", ACT, 4),
    "go_home() in driver.py": (DRIVER, GO_HOME, 2),
}


@pytest.mark.parametrize(
    "rel, source, line", OUTSIDE_ACT.values(), ids=list(OUTSIDE_ACT)
)
@pytest.mark.parametrize("name", sorted(ACT_ALLOWED))
def test_the_eight_action_methods_fail_outside_guard_act(
    tmp_path, guard_check, name, rel, source, line
):
    found = scan(guard_check, tmp_path, rel, source.format(call=f"{name}()"))

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:{line}: {name}: ")


@pytest.mark.parametrize("name", ALL_BANNED)
def test_inside_driver_go_home_only_goto_and_reload_pass(tmp_path, guard_check, name):
    found = scan(guard_check, tmp_path, DRIVER, GO_HOME.format(call=f"{name}()"))

    if name in GO_HOME_ALLOWED:
        assert found == []
    else:
        assert len(found) == 1
        assert found[0].startswith(f"{DRIVER}:2: {name}: ")


# (file, source with {call}, line of the call): everywhere but go_home() in driver.py.
OUTSIDE_GO_HOME = {
    "driver.py module level": (DRIVER, "page.{call}\n", 1),
    "driver.py open_note()": (DRIVER, "def open_note(page):\n    page.{call}\n", 2),
    "go_home() in another file": ("src/po_agent/mysys/booker.py", GO_HOME, 2),
    "act() in guard.py": (GUARD, ACT, 4),
}


@pytest.mark.parametrize(
    "rel, source, line", OUTSIDE_GO_HOME.values(), ids=list(OUTSIDE_GO_HOME)
)
@pytest.mark.parametrize("name", sorted(GO_HOME_ALLOWED))
def test_goto_and_reload_fail_outside_driver_go_home(
    tmp_path, guard_check, name, rel, source, line
):
    found = scan(guard_check, tmp_path, rel, source.format(call=f"{name}()"))

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:{line}: {name}: ")


# --- error details are fixed strings (1.5 review) ---------------------------


@pytest.mark.parametrize(
    "source",
    [
        "raise GuardRefusal(f'refused {name}')\n",
        "raise UnexpectedScreen(text)\n",
        "raise ConfigError('bad ' + name)\n",
        "raise ConfigError('bad %s' % name)\n",
        "raise ConfigError('bad {}'.format(name))\n",
        "raise ConfigError(detail=name)\n",
        "raise errors.PartialWrite(str(exc))\n",
        "error = AccuracyBreach(message)\n",
    ],
)
def test_error_detail_that_is_not_a_string_constant_fails_in_src(
    tmp_path, guard_check, source
):
    rel = "src/po_agent/b1/booker.py"

    found = scan(guard_check, tmp_path, rel, source)

    assert len(found) == 1
    assert found[0].startswith(f"{rel}:1:")


@pytest.mark.parametrize(
    "source",
    [
        "raise ConfigError('invalid config value', field=field) from None\n",
        "raise GuardRefusal('guard refused the action', action=a, reason=r)\n",
        "raise UnexpectedScreen(detail='Note window not found', note_id=n)\n",
        "raise ValueError(f'free text {x}')\n",  # not one of our typed errors
    ],
)
def test_fixed_error_detail_passes(tmp_path, guard_check, source):
    assert scan(guard_check, tmp_path, "src/po_agent/b1/booker.py", source) == []


def test_error_detail_rule_reads_the_classes_from_errors_py(tmp_path, guard_check):
    errors = ERRORS_SOURCE + "\n\nclass NewError(UnexpectedScreen):\n    pass\n"
    root = tree(tmp_path, {"src/po_agent/b1/booker.py": "raise NewError(text)\n"})
    (root / "src/po_agent/core/errors.py").write_text(errors, encoding="utf-8")

    assert len(guard_check.violations(root)) == 1


def test_error_detail_rule_applies_to_src_only(tmp_path, guard_check):
    source = "error = PartialWrite('read-back failed', step=page_text)\n"
    source += "error = PartialWrite(page_text)\n"

    assert scan(guard_check, tmp_path, "tests/test_x.py", source) == []


# --- the real repo and the command ------------------------------------------


def test_repo_passes(guard_check):
    assert guard_check.violations(ROOT) == []


def test_main_exits_1_and_names_the_violation(tmp_path):
    tree(tmp_path, {"scripts/tool.py": "page.goto('x')\n"})

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "guard_check.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "scripts/tool.py:1:" in result.stdout
    assert "goto" in result.stdout


def test_main_exits_0_on_the_repo():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "guard_check.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 0


# --- print only in core/output.py (task 1.6) ---------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "print('x')\n",
        "show = print\n",  # a reference, not only a call
        "import builtins\nbuiltins.print('x')\n",
    ],
)
def test_print_in_src_outside_output_py_fails(tmp_path, guard_check, source):
    found = scan(guard_check, tmp_path, "src/po_agent/cli.py", source)

    assert len(found) == 1
    assert "print" in found[0]


def test_print_in_output_py_passes(tmp_path, guard_check):
    source = "print('x')\n"

    assert scan(guard_check, tmp_path, "src/po_agent/core/output.py", source) == []


@pytest.mark.parametrize("rel", ["scripts/tool.py", "tests/test_x.py"])
def test_print_outside_src_passes(tmp_path, guard_check, rel):
    assert scan(guard_check, tmp_path, rel, "print('x')\n") == []
