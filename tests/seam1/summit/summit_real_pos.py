"""Summit's real-PDF check (task 9.7) and real-PO seam (task 9.10): finding
the PDFs, the cases, the counts and the reports. A module of its own, so
the offline tests can run it on a fake folder.

Reads <private>/summit/pdfs/*.pdf and, when present,
<private>/summit/fixtures/cases.toml (S.0): one `[[case]]` per PDF.

- `pdf`: the PDF's file name in pdfs/ (its original name, which holds the PO).
- `expect_compaction`: does the PDF's item row say COMPACTION TEST (9.7).
- `note_title`, `note_body`: the Note window's title and body as shown.
- `original_assignee`: the Note's assignee before the agent takes it.
- `expect`: "PROCEED" or "SKIP"; `expect_reason`: "" for PROCEED, else the
  skip reason (a `SkipReason` value).
- `expect_pln`, `expect_creator`: PROCEED only, the project's pln and the
  Creator the task gets. The PO written is checked against the file name's.
- `[case.lookup]`, what MySys shows before this PO is booked: `more_pages`,
  `project_internal_no` (the project's Client Internal No.), every Projects
  search row (`[[case.lookup.search_rows]]`: `pln`, `client_ref_no`,
  `company`) and every row of the Tasks table
  (`[[case.lookup.project_tasks]]`: `task_no`, `name`, `status`,
  `task_creator`). Only a case decided before the lookup (a Note or PDF
  skip) may leave it out.

Two POs of one project: the later one's Tasks table shows the first one's
Compaction Test task, and it expects SKIP DUPLICATE_TASK (SPEC); two cases
expecting PROCEED on one pln are refused.

Everything read here is real data: only field names, counts, case ids
(summit-1, summit-2, ... in file order) and enum values leave this module.
"""

import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from real_pos import PRIVATE_DIR_ENV, _main_checkout_private

from po_agent.core.config import load_client
from po_agent.core.models import MySysLookup, NoteSnapshot, Skip, SkipReason
from po_agent.summit import reader_rules as rules
from po_agent.summit.decision import decide
from po_agent.summit.models import SummitProceed

CASES = Path("fixtures") / "cases.toml"
FIELDS = ("company", "po number", "compaction")
REPORT = pytest.StashKey[list[str]]()
SEAM_REPORT = pytest.StashKey[list[str]]()
# "<sender prefix>-123456_020_01.pdf" -> 123456/020/01 (the real names' shape).
_FILE_PO = re.compile(r"-([0-9]+)_([0-9]+)_([0-9]+)\.pdf", re.IGNORECASE)


def file_name_po(name: str) -> str:
    match = _FILE_PO.search(name)
    return "/".join(match.groups()) if match else ""


def find_summit_dir() -> Path | None:
    """<private>/summit with at least one PDF in pdfs/, else None."""
    env = os.environ.get(PRIVATE_DIR_ENV)
    private = Path(env) if env else _main_checkout_private()
    folder = None if private is None else private / "summit"
    if folder is not None and any((folder / "pdfs").glob("*.pdf")):
        return folder
    return None


def expected_compaction(folder: Path) -> dict[str, bool] | None:
    """Joey's expected compaction per file name; None without cases.toml."""
    cases = folder / CASES
    if not cases.is_file():
        return None
    raw = tomllib.loads(cases.read_text(encoding="utf-8")).get("case", [])
    return {c["pdf"]: c["expect_compaction"] for c in raw if "expect_compaction" in c}


@dataclass
class Counts:
    pdfs: int = 0
    agree: dict[str, int] = field(default_factory=lambda: dict.fromkeys(FIELDS, 0))
    po_as_file: int = 0
    compaction_yes: int = 0
    expected_given: int | None = None  # None: no cases.toml
    as_expected: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)


def tally_folder(folder: Path) -> Counts:
    expected = expected_compaction(folder)
    counts = Counts(expected_given=None if expected is None else 0)
    for pdf in sorted((folder / "pdfs").glob("*.pdf")):
        texts = rules.read(pdf.read_bytes())
        counts.pdfs += 1
        for name, same in rules.agreement(texts).items():
            counts.agree[name] += same
        result = rules.check_pdf(texts)
        outcome = result.reason.value if isinstance(result, Skip) else "READING"
        counts.outcomes[outcome] = counts.outcomes.get(outcome, 0) + 1
        plumber = rules.read_text(texts.plumber)
        pypdf = rules.read_text(texts.pypdf)
        wanted = file_name_po(pdf.name)
        counts.po_as_file += (
            wanted != "" and plumber.po_number == wanted == pypdf.po_number
        )
        counts.compaction_yes += plumber.compaction
        if expected is not None and pdf.name in expected:
            counts.expected_given += 1
            counts.as_expected += plumber.compaction == expected[pdf.name]
    return counts


def report_lines(counts: Counts) -> list[str]:
    """Field names and counts only, never a value."""
    lines = [f"summit pdfs: {counts.pdfs}"]
    lines += [
        f"field {name}: agree {agree}, disagree {counts.pdfs - agree}"
        for name, agree in counts.agree.items()
    ]
    lines.append(f"po equals file name: {counts.po_as_file} of {counts.pdfs}")
    lines.append(
        f"compaction: yes {counts.compaction_yes},"
        f" no {counts.pdfs - counts.compaction_yes}"
    )
    if counts.expected_given is None:
        lines.append("compaction as expected: no cases.toml yet (S.0)")
    else:
        lines.append(
            f"compaction as expected: {counts.as_expected} of {counts.expected_given}"
            f" given, {counts.pdfs} PDFs"
        )
    lines.append(
        "outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.outcomes.items()))
    )
    return lines


# --- the real-PO seam (task 9.10) ---


@dataclass
class CaseResult:
    """One case's outcome. The expected pln and creator and the Proceed are
    real values: the report never prints them."""

    case_id: str
    expect: str
    expect_reason: str
    expect_pln: str
    expect_creator: str
    expect_po: str  # the file name's PO
    agree: dict[str, bool]
    result: Skip | SummitProceed

    @property
    def false_proceed(self) -> bool:
        if not isinstance(self.result, SummitProceed):
            return False
        return (
            self.expect != "PROCEED"
            or self.result.pln != self.expect_pln
            or self.result.creator != self.expect_creator
            or self.result.po_number != self.expect_po
        )

    @property
    def as_expected(self) -> bool:
        if isinstance(self.result, Skip):
            return self.expect == "SKIP" and self.result.reason == self.expect_reason
        return self.expect == "PROCEED" and not self.false_proceed


@dataclass
class SeamRun:
    cases: list[CaseResult]
    pdfs_without_case: int


def _expectation(raw: dict[str, Any], case_id: str) -> tuple[str, str]:
    """expect and expect_reason, which the report prints: PROCEED with no
    reason and with a pln and a creator, or SKIP with a SkipReason. Anything
    else fails with a fixed message that prints no value."""
    expect, reason = raw.get("expect"), raw.get("expect_reason", "")
    proceed = (
        expect == "PROCEED"
        and reason == ""
        and bool(raw.get("expect_pln"))
        and bool(raw.get("expect_creator"))
    )
    if proceed or (expect == "SKIP" and reason in set(SkipReason)):
        return str(expect), reason
    raise ValueError(f"case {case_id}: expected result not valid")


def _one_booking_per_project(cases: list[CaseResult]) -> None:
    """SPEC: a project's second PO skips DUPLICATE_TASK once the first is
    booked, so no two cases may expect PROCEED on one pln."""
    first: dict[str, str] = {}
    for case in cases:
        if case.expect != "PROCEED":
            continue
        if case.expect_pln in first:
            raise ValueError(
                f"cases {first[case.expect_pln]} and {case.case_id}:"
                " both expect PROCEED on one project"
            )
        first[case.expect_pln] = case.case_id


def _lookup(raw: dict[str, Any], case_id: str) -> Callable[[], MySysLookup]:
    """The case's MySys lookup as decide() calls it; a case without one
    fails only if decide() gets that far."""

    def found() -> MySysLookup:
        lookup = raw.get("lookup")
        if lookup is None:
            raise ValueError(f"case {case_id}: decide() needs its [case.lookup]")
        return MySysLookup.model_validate(
            {
                "more_pages": lookup["more_pages"],
                "project_internal_no": lookup["project_internal_no"],
                "search_rows": tuple(lookup.get("search_rows", ())),
                "project_tasks": tuple(lookup.get("project_tasks", ())),
            }
        )

    return found


def evaluate_cases(folder: Path) -> SeamRun:
    """Every case through both readers and decide() with the committed
    creator table. A missing PDF raises FileNotFoundError; an expected
    result that isn't valid, or a lookup decide() needs and the case lacks,
    ValueError."""
    raw_cases = tomllib.loads((folder / CASES).read_text(encoding="utf-8"))["case"]
    companies = load_client("summit", "live").company
    cases = []
    for number, raw in enumerate(raw_cases, start=1):
        case_id = f"summit-{number}"
        expect, expect_reason = _expectation(raw, case_id)
        texts = rules.read((folder / "pdfs" / raw["pdf"]).read_bytes())
        note = NoteSnapshot(
            note_id=case_id,
            title=raw["note_title"],
            body=raw["note_body"],
            attachment_names=(raw["pdf"],),
            project_linked=False,
        )
        result = decide(
            note,
            raw["original_assignee"],
            texts,
            _lookup(raw, case_id),
            companies=companies,
        )
        cases.append(
            CaseResult(
                case_id=case_id,
                expect=expect,
                expect_reason=expect_reason,
                expect_pln=raw.get("expect_pln", ""),
                expect_creator=raw.get("expect_creator", ""),
                expect_po=file_name_po(raw["pdf"]),
                agree=rules.agreement(texts),
                result=result,
            )
        )
    _one_booking_per_project(cases)
    named = {raw["pdf"] for raw in raw_cases}
    without = [pdf for pdf in (folder / "pdfs").glob("*.pdf") if pdf.name not in named]
    return SeamRun(cases=cases, pdfs_without_case=len(without))


def false_proceeds(cases: list[CaseResult]) -> int:
    return sum(case.false_proceed for case in cases)


def _outcome(case: CaseResult) -> str:
    if isinstance(case.result, Skip):
        outcome = f"SKIP {case.result.reason}"
    else:
        outcome = "PROCEED"
    expected = f"SKIP {case.expect_reason}" if case.expect == "SKIP" else "PROCEED"
    flag = " - false PROCEED" if case.false_proceed else ""
    return f"{outcome} (expected {expected}){flag}"


def seam_report_lines(run: SeamRun) -> list[str]:
    """The stdout contract: field names, counts, an outcome per case id,
    coverage and false PROCEED. Never a value."""
    cases = run.cases
    lines = [
        f"summit cases: {len(cases)}, PDFs without a case: {run.pdfs_without_case}"
    ]
    for name in FIELDS:
        agree = sum(case.agree[name] for case in cases)
        lines.append(f"field {name}: agree {agree}, disagree {len(cases) - agree}")
    lines += [f"case {case.case_id}: {_outcome(case)}" for case in cases]
    clean = [case for case in cases if case.expect == "PROCEED"]
    proceeded = sum(isinstance(case.result, SummitProceed) for case in clean)
    lines += [
        f"as expected: {sum(case.as_expected for case in cases)} of {len(cases)}",
        f"coverage: {proceeded} of {len(clean)} clean POs PROCEED",
        f"false PROCEED: {false_proceeds(cases)}",
    ]
    return lines
