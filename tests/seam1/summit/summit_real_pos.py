"""Summit's real-PDF check: finding the PDFs, the counts and the report
(task 9.7; review, 9.7). A module of its own, so the offline tests can run
it on a fake folder.

Reads <private>/summit/pdfs/*.pdf and, when present,
<private>/summit/fixtures/cases.toml: each `[[case]]` with `pdf` (the file
name) and `expect_compaction` (Joey's expected value, S.0). Everything read
here is real data: only field names and counts leave this module.
"""

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from real_pos import PRIVATE_DIR_ENV, _main_checkout_private

from po_agent.core.models import Skip
from po_agent.summit import reader_rules as rules

CASES = Path("fixtures") / "cases.toml"
FIELDS = ("company", "po number", "compaction")
REPORT = pytest.StashKey[list[str]]()
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
