"""The real-PO seam's cases, report and pytest wiring (task 2.6, S3).

Reads private/fixtures/cases.toml and private/pdfs/ (SPEC.md -> Testing
Strategy, real POs): each [[case]] holds pdf (the file name), note_title,
note_body, expect ("PROCEED" or "SKIP"), expect_reason, expect_pln (for
PROCEED) and [case.lookup] as MySys shows it (search_rows, more_pages,
project_internal_no, address, tasks). Optional: title_rule (default
test-body-filename) and site (default test), as config/test.toml.

Everything read here is real data: only field names, counts, enum values,
case ids and the trial POs' internal numbers leave this module. conftest.py
imports the fixtures and hooks below. (A module of its own, so the offline
tests can run it in a throwaway folder.)
"""

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from po_agent.b1 import reader_rules as rules
from po_agent.b1.address import job_address_line, normalise, verify_address
from po_agent.b1.decision import decide, eligible_internal_no
from po_agent.b1.models import (
    MySysLookup,
    NotePoolRow,
    NoteSnapshot,
    Proceed,
    Skip,
    SkipReason,
)
from po_agent.core.errors import WriteNotStarted

# The 3 trial POs (SPEC.md -> Trial conditions): internal numbers only.
TRIAL_INTERNAL_NOS = ("2609017B", "2609034B", "2610002B")
RECENT_REAL_POS = 3  # the 3 most recent real B1 /048 POs (SPEC.md, S3)
POOL = "Agent Pool"
PRIVATE_DIR_ENV = "SEAM1_PRIVATE_DIR"
CASES = Path("fixtures") / "cases.toml"
MYSYS_FIELDS = {"search_rows", "more_pages", "project_internal_no", "address"}
FIELDS = ("issuer", "compaction", "po number", "job address line", "address check")
_REPORT = pytest.StashKey[list[str]]()


class PrivateDirMissing(Exception):
    """`-m real_data` was selected, but there is no private/ folder."""


@dataclass
class CaseResult:
    """One case's outcome: no value from the PDF, Note or MySys, except the
    Proceed and the expected pln and PO number, which the report never prints."""

    case_id: str
    expect: str
    expect_reason: str
    expect_pln: str
    expect_po: str  # the PDF file name's PO number
    mysys_shape: bool
    result: Skip | Proceed | None = None
    untouched: bool = False  # step 0 left the Note alone
    agree: dict[str, bool] = field(default_factory=dict)

    @property
    def false_proceed(self) -> bool:
        if not isinstance(self.result, Proceed):
            return False
        return (
            self.expect != "PROCEED"
            or self.result.pln != self.expect_pln
            or self.result.po_number != self.expect_po
        )


# --- finding private/ ---


def _main_checkout_private() -> Path | None:
    """private/ in the main checkout (a worktree has none of its own)."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(common).parent / "private"


def find_private_dir() -> Path | None:
    """SEAM1_PRIVATE_DIR if set, else the main checkout's private/; None
    when that folder has no fixtures/cases.toml."""
    env = os.environ.get(PRIVATE_DIR_ENV)
    folder = Path(env) if env else _main_checkout_private()
    return folder if folder is not None and (folder / CASES).is_file() else None


def _selected_explicitly(markexpr: str) -> bool:
    """`-m` names real_data, not as `not real_data`."""
    return bool(re.search(r"(?<!not )\breal_data\b", " ".join(markexpr.split())))


@pytest.fixture(scope="session")
def real_po_dir(request: pytest.FixtureRequest) -> Path:
    """The private/ folder; skipped when absent, unless `-m real_data` was
    selected, where it is an error (green with nothing run never counts)."""
    folder = find_private_dir()
    if folder is not None:
        return folder
    message = f"private/ not found (set {PRIVATE_DIR_ENV} or use the laptop)"
    if _selected_explicitly(request.config.option.markexpr or ""):
        raise PrivateDirMissing(message)
    pytest.skip(message)


@pytest.fixture(scope="session")
def real_po_results(
    real_po_dir: Path, request: pytest.FixtureRequest
) -> list[CaseResult]:
    results = evaluate(real_po_dir)
    request.config.stash[_REPORT] = report_lines(results)
    return results


# --- the seam ---


def _file_name_po(file_name: str) -> str:
    """The file name's PO number, "" when the name isn't <no>_048[_n].pdf
    (decide() skips such a case like any other)."""
    try:
        return rules.po_from_file_name(file_name)
    except WriteNotStarted:
        return ""


def _case_ids(raw_cases: list[dict[str, Any]]) -> list[str]:
    ids, real = [], 0
    for raw in raw_cases:
        internal_no = _file_name_po(raw["pdf"]).split("/")[0]
        if internal_no in TRIAL_INTERNAL_NOS:
            ids.append(internal_no)
        else:
            real += 1
            ids.append(f"real-{real}")
    return ids


def _agreement(plumber: str, pypdf: str, address: str | None) -> dict[str, bool]:
    """Per field: do both readers' texts give the same thing (no values)."""
    a, b = rules.read_pdf(plumber, "", ""), rules.read_pdf(pypdf, "", "")
    line_a, line_b = job_address_line(plumber), job_address_line(pypdf)
    agree = {
        "issuer": a.issuer == b.issuer,
        "compaction": a.contains_compaction == b.contains_compaction,
        "po number": a.po_number == b.po_number,
        "job address line": (None if line_a is None else normalise(line_a))
        == (None if line_b is None else normalise(line_b)),
    }
    if address is not None:
        agree["address check"] = verify_address(plumber, address) == verify_address(
            pypdf, address, exact_line_under=True
        )
    return agree


def _decide(
    raw: dict[str, Any], case_id: str, plumber: str, pypdf: str, data: bytes
) -> Skip | Proceed | None:
    """decide() on the case; None when step 0 leaves the Note untouched."""
    note = NoteSnapshot(
        note_id=case_id,
        title=raw["note_title"],
        body=raw["note_body"],
        attachment_names=(raw["pdf"],),
        project_linked=False,
    )
    row = NotePoolRow(
        note_id=case_id,
        subject_note=f"{note.title} {note.body}",
        project="---",
        assignee=POOL,
    )
    internal_no = eligible_internal_no(
        row, raw.get("title_rule", "test-body-filename"), POOL
    )
    if internal_no is None:
        return None
    lookup = raw["lookup"]
    return decide(
        note,
        internal_no,
        plumber,
        pypdf,
        data,
        MySysLookup.model_validate(
            {
                **lookup,
                "search_rows": tuple(lookup["search_rows"]),
                "tasks": tuple(lookup.get("tasks", ())),
            }
        ),
        site=raw.get("site", "test"),
        duplicate_ignores_cancelled=True,  # config/test.toml
    )


def _expectation(raw: dict[str, Any], case_id: str) -> tuple[str, str]:
    """expect and expect_reason, which the report prints: PROCEED with no
    reason, or SKIP with a SkipReason; anything else fails with a fixed
    message that prints no value (review, 2.6)."""
    expect, reason = raw.get("expect"), raw.get("expect_reason", "")
    if (expect == "PROCEED" and reason == "") or (
        expect == "SKIP" and reason in set(SkipReason)
    ):
        return expect, reason
    raise ValueError(f"case {case_id}: expect or expect_reason not valid")


def evaluate(folder: Path) -> list[CaseResult]:
    """Every case through both readers and, when its lookup is in the MySys
    shape, decide(). A missing PDF raises FileNotFoundError, an expectation
    that isn't an enum value ValueError."""
    raw_cases = tomllib.loads((folder / CASES).read_text(encoding="utf-8"))["case"]
    results = []
    for raw, case_id in zip(raw_cases, _case_ids(raw_cases), strict=True):
        expect, expect_reason = _expectation(raw, case_id)
        data = (folder / "pdfs" / raw["pdf"]).read_bytes()
        plumber, pypdf = rules.text_layer(data), rules.pypdf_text_layer(data)
        mysys_shape = MYSYS_FIELDS <= set(raw["lookup"])
        address = raw["lookup"]["address"] if mysys_shape else None
        result = CaseResult(
            case_id=case_id,
            expect=expect,
            expect_reason=expect_reason,
            expect_pln=raw.get("expect_pln", ""),
            expect_po=_file_name_po(raw["pdf"]),
            mysys_shape=mysys_shape,
            agree=_agreement(plumber, pypdf, address),
        )
        if mysys_shape:
            result.result = _decide(raw, case_id, plumber, pypdf, data)
            result.untouched = result.result is None
        results.append(result)
    return results


def false_proceeds(results: list[CaseResult]) -> int:
    return sum(r.false_proceed for r in results)


def _outcome(result: CaseResult) -> str:
    if not result.mysys_shape:
        return "not decided (lookup not in the MySys shape)"
    if result.untouched:
        outcome = "untouched (not eligible at step 0)"
    elif isinstance(result.result, Skip):
        outcome = f"SKIP {result.result.reason}"
    else:
        outcome = "PROCEED"
    expected = result.expect
    if result.expect == "SKIP" and result.expect_reason:
        expected = f"SKIP {result.expect_reason}"
    return f"{outcome} (expected {expected})"


def report_lines(results: list[CaseResult]) -> list[str]:
    """The stdout contract: field names, counts, coverage, an outcome per
    case id and false PROCEED. Never a value."""
    trial = [r.case_id for r in results if r.case_id in TRIAL_INTERNAL_NOS]
    missing = [no for no in TRIAL_INTERNAL_NOS if no not in trial]
    recent = len(results) - len(trial)
    lines = [
        f"cases: {len(results)} (recent real {recent} of {RECENT_REAL_POS}, "
        f"trial {len(trial)} of {len(TRIAL_INTERNAL_NOS)}"
        + (f"; trial missing: {', '.join(missing)})" if missing else ")")
    ]
    for name in FIELDS:
        seen = [r.agree[name] for r in results if name in r.agree]
        lines.append(
            f"field {name}: agree {sum(seen)}, disagree {len(seen) - sum(seen)}"
        )
    lines += [f"case {r.case_id}: {_outcome(r)}" for r in results]
    decided = [r for r in results if r.mysys_shape]
    clean = [r for r in decided if r.expect == "PROCEED"]
    proceeded = sum(isinstance(r.result, Proceed) for r in clean)
    lines += [
        f"decided: {len(decided)} of {len(results)}",
        f"coverage: {proceeded} of {len(clean)} clean POs PROCEED",
        f"false PROCEED: {false_proceeds(results)}",
    ]
    return lines


# --- pytest hooks (conftest.py imports them) ---


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """1.8's failure-report scrub (tests/seam2/conftest.py), for real_data:
    a failure shows the test name and exception type only (Must never #6)."""
    # https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport
    report = yield
    if report.failed and item.get_closest_marker("real_data"):
        kind = call.excinfo.typename if call.excinfo else "Failure"
        report.longrepr = f"{item.nodeid}: {kind}"
        report.sections = []
    return report


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the real-PO report once, after the run, without -s."""
    lines = config.stash.get(_REPORT, None)
    if lines:
        terminalreporter.section("real-PO seam")
        for line in lines:
            terminalreporter.write_line(line)
