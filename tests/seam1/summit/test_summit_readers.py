"""Summit's two code readers (task 9.7; SPEC.md -> Client 2: Summit Home,
Decision checks; tasks/plan.md 9.7).

`summit.reader_rules.check_pdf()` takes both readers' text of one PDF (B1's
`PdfTexts`, task 8.3) and gives Summit's reading - the company line at the
top, the one `Purchase Order No:` value (three digit groups joined by `/`),
whether `COMPACTION TEST` stands under the Description header - or a skip,
in SPEC's order: a reader reads no text -> PDF_UNREADABLE; neither finds
COMPACTION TEST -> NOT_COMPACTION; the readers differ on a field ->
READERS_DISAGREE; no single well-formed PO value -> PO_MISMATCH (open
question 3: anything uncertain skips). Fake values only (reader_cases.toml).
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest
from seam1_cases import pdf_bytes, text_pdf

from po_agent.b1.readers import PdfTexts
from po_agent.core.models import Skip, SkipReason
from po_agent.summit import reader_rules as rules
from po_agent.summit.reader_rules import SummitReading

CASES_FILE = Path(__file__).parent / "reader_cases.toml"
_RAW = tomllib.loads(CASES_FILE.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = _RAW["case"]


def _replaced(text: str, pairs: list[list[str]]) -> str:
    for old, new in pairs:
        assert old in text, f"replace target not in the text: {old!r}"
        text = text.replace(old, new)
    return text


def texts_of(case: dict[str, Any]) -> PdfTexts:
    """The case's two texts: [po] with its replacements applied."""
    plumber = _replaced(_RAW["po"]["plumber"], case.get("pdf_replace", []))
    pypdf = _replaced(_RAW["po"]["pypdf"], case.get("pdf_replace", []))
    plumber = _replaced(plumber, case.get("plumber_replace", []))
    pypdf = _replaced(pypdf, case.get("pypdf_replace", []))
    empty = case.get("empty")
    return PdfTexts(
        plumber="" if empty == "plumber" else plumber,
        pypdf="" if empty == "pypdf" else pypdf,
        data=b"",
    )


def expected(case: dict[str, Any]) -> Skip | SummitReading:
    if "expect_skip" in case:
        return Skip(reason=SkipReason(case["expect_skip"]))
    return SummitReading(
        company=case["expect_company"],
        po_number=case["expect_po"],
        compaction=case["expect_compaction"],
    )


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_summit_reader_case(case: dict[str, Any]) -> None:
    assert rules.check_pdf(texts_of(case)) == expected(case)


@pytest.mark.parametrize("kind", ["corrupt", "image-only"])
def test_bytes_no_reader_can_read_are_pdf_unreadable(kind: str) -> None:
    texts = rules.read(pdf_bytes(kind))
    assert rules.check_pdf(texts) == Skip(reason=SkipReason.PDF_UNREADABLE)


def test_a_text_pdf_reads_alike_on_both_real_readers() -> None:
    data = text_pdf(
        [
            "Summit Homes Group",
            "Purchase Order No: 123456/020/01",
            "DESCRIPTION Supplier Code Quantity Unit Unit Price Total",
            "COMPACTION TEST 1.000 EA 99.00 99.00",
            "Sub Total: $99.00",
        ]
    )
    texts = rules.read(data)
    assert rules.agreement(texts) == {
        "company": True,
        "po number": True,
        "compaction": True,
    }
    assert rules.check_pdf(texts) == SummitReading(
        company="Summit Homes Group", po_number="123456/020/01", compaction=True
    )


def test_agreement_names_the_field_the_readers_differ_on() -> None:
    case = next(c for c in CASES if c["id"] == "readers-disagree-po")
    assert rules.agreement(texts_of(case)) == {
        "company": True,
        "po number": False,
        "compaction": True,
    }
