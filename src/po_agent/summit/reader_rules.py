"""Summit's PDF rules on both code readers' text (task 9.7; SPEC.md ->
Client 2: Summit Home, Decision checks).

Pure functions, no browser code. The two readers are B1's (`b1/readers.py`,
task 8.3): pdfplumber's and pypdf's text of one PDF in a `PdfTexts`, ""
where a library reads none. This module reads Summit's three fields from
each text and applies SPEC's PDF rows in their order; the title's PO and
the company table are the decision engine's (task 9.9).

Patterns, pinned on the 11 real Summit PDFs as masked shapes:
- the company is the first non-empty line, trimmed;
- the PO is the `Purchase Order No:` value, three digit groups joined by
  `/`; a second page repeats it. No value, a malformed one or two
  different ones read as "" (open question 3: anything uncertain skips);
- COMPACTION TEST, in capitals, is the item row's description (Joey, 25 Nov
  2026: item line only), between the first line starting `DESCRIPTION` and
  the first totals line (`Total:` or `GST:`). An item row is a line that is
  exactly `COMPACTION TEST`, starts with it followed by the quantity
  (pdfplumber: "COMPACTION TEST 1.000 EA ..."), or ends with a price and the
  unit glued onto it (pypdf: "... 99.00EACOMPACTION TEST"). The phrase inside
  any other line (a note) never counts; an odd layout reads as not found.
"""

import re

from po_agent.b1.readers import PdfTexts, read
from po_agent.core.models import Frozen, Skip, SkipReason

__all__ = ["SummitReading", "agreement", "check_pdf", "read", "read_text"]

_PO_VALUE = re.compile(r"Purchase Order No:[ \t]*(\S*)")
_PO_SHAPE = re.compile(r"[0-9]+/[0-9]+/[0-9]+")
_ITEM_ROW = re.compile(
    r"COMPACTION TEST"  # the description alone on its line
    r"|COMPACTION TEST\s+[0-9].*"  # pdfplumber: then the quantity
    r"|.*[0-9]\.[0-9]{2}[A-Z]{1,4}COMPACTION TEST"  # pypdf: price, unit, it
)
_DESCRIPTION = "DESCRIPTION"
_TOTALS = ("Total:", "GST:")


class SummitReading(Frozen):
    """What one reader found in a Summit PDF; "" where nothing was found."""

    company: str
    po_number: str
    compaction: bool


def _po_number(text: str) -> str:
    values = set(_PO_VALUE.findall(text))
    if len(values) != 1:
        return ""
    value = values.pop()
    return value if _PO_SHAPE.fullmatch(value) else ""


def _compaction(lines: list[str]) -> bool:
    starts = [i for i, line in enumerate(lines) if line.startswith(_DESCRIPTION)]
    if not starts:
        return False
    for line in lines[starts[0] + 1 :]:
        if any(total in line for total in _TOTALS):
            return False
        if _ITEM_ROW.fullmatch(line):
            return True
    return False


def read_text(text: str) -> SummitReading:
    """One reader's text read with Summit's patterns."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return SummitReading(
        company=lines[0] if lines else "",
        po_number=_po_number(text),
        compaction=_compaction(lines),
    )


def agreement(texts: PdfTexts) -> dict[str, bool]:
    """Per field: do both readers find the same thing (no values)."""
    plumber, pypdf = read_text(texts.plumber), read_text(texts.pypdf)
    return {
        "company": plumber.company == pypdf.company,
        "po number": plumber.po_number == pypdf.po_number,
        "compaction": plumber.compaction == pypdf.compaction,
    }


def check_pdf(texts: PdfTexts) -> Skip | SummitReading:
    """SPEC's PDF rows in order: both readers give text (PDF_UNREADABLE);
    COMPACTION TEST under Description on both (neither -> NOT_COMPACTION);
    the three fields equal on both (READERS_DISAGREE); one well-formed PO
    (PO_MISMATCH). Else the reading both readers share."""
    if not texts.plumber.strip() or not texts.pypdf.strip():
        return Skip(reason=SkipReason.PDF_UNREADABLE)
    plumber, pypdf = read_text(texts.plumber), read_text(texts.pypdf)
    if not plumber.compaction and not pypdf.compaction:
        return Skip(reason=SkipReason.NOT_COMPACTION)
    if plumber != pypdf:
        return Skip(reason=SkipReason.READERS_DISAGREE)
    if not plumber.po_number:
        return Skip(reason=SkipReason.PO_MISMATCH)
    return plumber
