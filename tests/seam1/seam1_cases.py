"""Seam-1 decision cases from fixtures/cases.toml (task 2.1).

Each case merges its base fake PO with its own overrides and is validated
through the b1 models, so a malformed case fails at collection. conftest.py
runs a test that takes a `seam1_case` argument once per case. (A module of
its own: tests/seam2 has a conftest too, so `import conftest` is ambiguous.)
"""

import copy
import tomllib
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from po_agent.b1.decision import TitleRule
from po_agent.b1.models import (
    MySysLookup,
    NotePoolRow,
    NoteSnapshot,
    Reading,
    SkipReason,
)

CASES_FILE = Path(__file__).parent / "fixtures" / "cases.toml"
POOL = "Agent Pool"

# Every row of docs/specs/spec.md -> Seam 1 table and of SPEC.md -> Testing
# Strategy's extra cases, plus the screen rules' project checks. Each must be
# covered by at least one case.
COVERAGE = {
    # spec table
    "fake-pos-test-config": "3 POs, test-site config -> PROCEED",
    "live-title-config": "same 3, live-style titles -> PROCEED",
    "live-title-missing-tag": "live title missing [B1 Homes]",
    "live-title-po-differs": "live title PO differs from the PDF PO",
    "issuer-not-b1": "issuer not B1 Homes Pty Ltd -> NOT_B1",
    "compaction-removed": "COMPACTION removed -> NOT_COMPACTION",
    "file-name-023": "file name _023 -> not eligible",
    "pdf-po-023": "PDF PO /023 -> PO_MISMATCH",
    "pdf-po-not-file-name": "PDF PO differs from file name -> PO_MISMATCH",
    "lot-changed": "lot changed -> ADDRESS_MISMATCH",
    "street-changed": "street changed -> ADDRESS_MISMATCH",
    "suburb-changed": "suburb changed -> ADDRESS_MISMATCH",
    "street-abbreviation": "Street <-> St -> PROCEED",
    "case-change": "case changes -> PROCEED",
    "postcode-state-removed": "postcode and state removed -> PROCEED",
    "address-split": "address split across the PDF -> ADDRESS_UNVERIFIABLE",
    "project-not-found": "internal no not in MySys -> PROJECT_NOT_FOUND",
    "project-ambiguous": "two matching projects -> PROJECT_AMBIGUOUS",
    "duplicate-same-po": "Compaction Test with the same PO -> DUPLICATE_TASK",
    "no-pdf": "no attachment -> NO_PDF",
    "two-pdfs": "two attachments -> MULTIPLE_PDFS",
    "image-only-pdf": "image-only PDF -> PDF_UNREADABLE",
    "corrupt-pdf": "corrupt PDF -> PDF_UNREADABLE",
    "injected-text": "injected text never PROCEEDs with its value",
    "claude-lot-elsewhere": "Claude's lot from elsewhere in the PDF -> skip",
    "claude-wrong-po": "Claude's PO wrong -> READERS_DISAGREE",
    "claude-invalid-json": "Claude invalid JSON -> CLAUDE_INVALID_OUTPUT",
    "claude-timeout": "Claude timeout -> CLAUDE_UNAVAILABLE",
    # SPEC.md extras
    "cancelled-task-test": "Cancelled task, test config -> PROCEED",
    "cancelled-task-strict": "Cancelled task, not ignored -> DUPLICATE_TASK",
    "task-other-po": "task for another PO -> DUPLICATE_TASK",
    "other-suffix-rows": "other-suffix rows plus one match -> PROCEED",
    "company-not-b1": "matching row, other Company -> PROJECT_NOT_FOUND",
    "house-no-postcode-state": "(#n), postcode and state -> PROCEED",
    "lot-with-letter": "lot 12A -> PROCEED",
    "different-lot-letter": "different lot letter -> ADDRESS_MISMATCH",
    "note-already-linked": "Note already linked -> NOTE_ALREADY_LINKED",
    "test-note-live-title-po-differs": "test Note, live title PO differs",
    # SPEC.md -> MySys screen rules -> Project search, and section 4
    "more-pages": "a second results page -> PROJECT_AMBIGUOUS",
    "project-internal-no-differs": "project window internal no -> UNEXPECTED_SCREEN",
    "spec-address-example": "section 4's must-pass address example",
}


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseConfig(_Closed):
    site: Literal["test", "live"] = "test"
    title_rule: TitleRule = "test-body-filename"
    duplicate_ignores_cancelled: bool = True


class Expect(_Closed):
    result: Literal["proceed", "skip", "untouched"]
    reason: SkipReason | None = None
    pln: str | None = None
    po_number: str | None = None
    existing_task_nos: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _fields_fit_the_result(self) -> Self:
        proceed_values = (self.pln, self.po_number)
        if self.result == "proceed":
            ok = self.reason is None and None not in proceed_values
        elif self.result == "skip":
            ok = self.reason is not None and proceed_values == (None, None)
        else:
            ok = self.reason is None and proceed_values == (None, None)
        if not ok or (self.existing_task_nos and self.result != "proceed"):
            raise ValueError(f"expect fields don't fit result {self.result!r}")
        return self


class Seam1Case(_Closed):
    id: str
    covers: tuple[str, ...]
    config: CaseConfig = CaseConfig()
    note: NoteSnapshot
    # "text": pdf_text is the PDF's text layer (lean fakes; no PDF file).
    pdf: Literal["text", "none", "image-only", "corrupt"]
    pdf_text: str
    lookup: MySysLookup
    claude: Reading
    claude_error: Literal["invalid-json", "timeout"] | None = None
    never_in_output: tuple[str, ...] = ()
    expect: Expect
    expect_deterministic_only: Expect

    @property
    def pool_row(self) -> NotePoolRow:
        """The Note Pool list row (step 0): unlinked, in the pool."""
        return NotePoolRow(
            note_id=self.note.note_id,
            subject_note=f"{self.note.title} {self.note.body}",
            project="---",
            assignee=POOL,
        )


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _tuples(value: Any) -> Any:
    """TOML arrays -> tuples, for the strict models' tuple fields."""
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


def _build(raw: dict[str, Any], bases: dict[str, Any]) -> Seam1Case:
    raw = dict(raw)
    data = _merge(bases[raw.pop("base")], raw)
    text = data["pdf_text"].lstrip("\n")
    for old, new in data.pop("pdf_replace", []):
        if old not in text:
            raise ValueError(f"case {data['id']}: pdf_replace text not in base")
        text = text.replace(old, new)
    data["pdf_text"] = text
    return Seam1Case.model_validate(_tuples(data))


def load_cases(path: Path = CASES_FILE) -> list[Seam1Case]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [_build(case, raw["po"]) for case in raw["case"]]


CASES = load_cases()


def _image_only_pdf() -> bytes:
    """One page showing a 1x1 grey image and no text: no text layer."""
    pixel = b"\x80"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200]"
        b" /Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1"
        b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\nstream\n"
        + pixel
        + b"\nendstream",
    ]
    content = b"q 100 0 0 100 50 50 cm /Im1 Do Q"
    objects.append(
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def pdf_bytes(kind: str) -> bytes:
    """PDF bytes for the two cases that need them (Joey, 29 Oct 2026: no
    generator, standard library only, no committed .pdf files). Text cases
    use their pdf_text."""
    if kind == "corrupt":
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R\ntruncated"
    if kind == "image-only":
        return _image_only_pdf()
    raise ValueError(f"no PDF bytes for kind {kind!r}")
