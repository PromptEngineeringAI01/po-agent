"""The supervised demo's deterministic checks (decisions, 27 Oct 2026).

Pure functions, no browser code: the attachment rule, the PDF checks, the
project match and the task rows (SPEC.md -> MySys screen rules). A failed
check raises a typed error with a fixed detail and a reason identifier; PDF
text, addresses and cell text never go into it.
"""

import io
import re
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

import pdfplumber

from po_agent.core.errors import PartialWrite, WriteNotStarted

COMPANY = "B1 Homes"
PO_SUFFIX = "048"
# <internal no>_048[_n].pdf, as in b1/decision.py (open question 10).
_FILE_NAME = re.compile(rf"([0-9A-Z]+)_{PO_SUFFIX}(?:_[0-9]+)?\.(?i:pdf)")
# "Purchase Order No 2609017B/048" (the trial PDFs).
_PDF_PO = re.compile(r"Purchase Order No\.?\s*:?\s*([0-9A-Z]+/[0-9]{3})")
# "(tsk_200001) | Compaction Test" plus the row's button texts, which
# inner text can run on without a break.
_TASK_HEADER = re.compile(
    r"\((tsk_[0-9]+)\) \| Compaction Test"
    r"(?:\s*(?:Undo Cancellation|Cancel|Un-Hold|Hold))*\s*"
)
CANCELLED = "Cancelled"


def pdf_file_name(hrefs: Sequence[str]) -> str:
    """The `file_name` of the one "Download document" link; it must end .pdf.

    None -> NO_PDF; more than one -> MULTIPLE_PDFS; a missing file_name or one
    not ending .pdf (any case) -> NO_PDF.
    """
    if len(hrefs) > 1:
        raise WriteNotStarted("attachment not as expected", reason="MULTIPLE_PDFS")
    if not hrefs:
        raise WriteNotStarted("attachment not as expected", reason="NO_PDF")
    # parse_qs URL-decodes the value.
    names = parse_qs(urlsplit(hrefs[0]).query).get("file_name", [])
    if len(names) != 1 or not names[0].lower().endswith(".pdf"):
        raise WriteNotStarted("attachment not as expected", reason="NO_PDF")
    return names[0]


def po_from_file_name(file_name: str) -> str:
    """2609017B_048_1.pdf -> 2609017B/048."""
    match = _FILE_NAME.fullmatch(file_name)
    if match is None:
        raise WriteNotStarted("file name not a PO", reason="NO_PDF")
    return f"{match.group(1)}/{PO_SUFFIX}"


def pdf_text(data: bytes) -> str:
    """Every page's text; anything pdfplumber can't read -> PDF_UNREADABLE."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:  # pdfminer raises many types; its message can quote the file
        raise WriteNotStarted("PDF not readable", reason="PDF_UNREADABLE") from None


def check_pdf(text: str, file_po: str, internal_no: str) -> str:
    """Step 4: the PDF names B1 Homes and COMPACTION, holds exactly one PO
    number, equal to the file name's, whose internal number is the Note's."""
    if COMPANY not in text:
        raise WriteNotStarted("PDF check failed", reason="NOT_B1_HOMES")
    if "COMPACTION" not in text:
        raise WriteNotStarted("PDF check failed", reason="NOT_COMPACTION")
    found = set(_PDF_PO.findall(text))
    if found != {file_po}:
        raise WriteNotStarted("PDF check failed", reason="PO_NUMBER_MISMATCH")
    if file_po.split("/")[0] != internal_no:
        raise WriteNotStarted("PDF check failed", reason="INTERNAL_NO_MISMATCH")
    return file_po


def same_internal_no(value: str, internal_no: str) -> bool:
    """Client Ref No. / Client Internal No. rule: trimmed, any case, equal to
    the internal number or to it plus /048 (SPEC.md -> Project search)."""
    wanted = internal_no.lower()
    return value.strip().lower() in (wanted, f"{wanted}/{PO_SUFFIX}")


def match_project(rows: Sequence[Mapping[str, str]], internal_no: str) -> str:
    """Step 5: the pln of the one B1 Homes row whose Client Ref No. matches."""
    plns = [
        row["Project No."].strip()
        for row in rows
        if row["Company"].strip() == COMPANY
        and same_internal_no(row["Client Ref No."], internal_no)
    ]
    if not plns:
        raise WriteNotStarted("project not found", reason="PROJECT_NOT_FOUND")
    if len(plns) > 1:
        raise WriteNotStarted("project ambiguous", reason="PROJECT_AMBIGUOUS")
    return plns[0]


def compaction_tasks(rows: Sequence[Sequence[str]]) -> dict[str, str]:
    """Task number -> Status cell for every "(tsk_...) | Compaction Test"
    header row. The details row right below it ends with the Status cell."""
    tasks = {}
    for index, cells in enumerate(rows):
        match = _TASK_HEADER.fullmatch(cells[0].strip()) if cells else None
        if match is None:
            continue
        if index + 1 >= len(rows) or len(rows[index + 1]) < 2:
            raise PartialWrite("task row not recognised", reason="TASK_ROW")
        tasks[match.group(1)] = rows[index + 1][-1].strip()
    return tasks


def live_tasks(tasks: Mapping[str, str]) -> list[str]:
    """Compaction Test tasks that aren't Cancelled (test site, row 07)."""
    return [task for task, status in tasks.items() if status != CANCELLED]


def new_task(before: set[str], after: Mapping[str, str]) -> str:
    """Step 6 read-back: exactly one Compaction Test task not seen before."""
    new = [task for task in after if task not in before]
    if len(new) != 1:
        raise PartialWrite("new task not found", reason="NO_NEW_TASK")
    return new[0]
