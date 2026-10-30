"""Seam 1 with the real Claude reader (task 2.5, `-m live_claude`): every
seam-1 case through both real readers, laptop only, never in CI.

The fixtures are fake text (no PDF generator, decided at 2.1), so Claude gets
each case's text as a plain-text document; the real PDFs are read in the
real-PO seam (2.6). Prints per-field agreement (field names and counts only),
tokens, AUD cost and `false PROCEED: N`; fails if N > 0.
"""

import pytest
from seam1_cases import CASES, POOL, Seam1Case, pdf_bytes

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import decide, eligible_internal_no
from po_agent.b1.models import ClaudeReading, Proceed, Reading, Skip
from po_agent.b1.reader_claude import (
    ClaudeReader,
    reader_from_config,
    text_document,
)
from po_agent.core.config import load_config

pytestmark = pytest.mark.live_claude

FIELDS = tuple(ClaudeReading.model_fields)
BASE = next(case for case in CASES if case.id == "p1-clean")
# Cases whose expected skip comes from the stub's made-up Claude reading (a
# timeout, invalid JSON, a wrong PO, a reader fooled by injected text). Their
# PDF text is the clean p1 PO, so a real Claude may read it correctly: then
# p1's PROCEED is right, and the expected reading is p1's.
STUB_ONLY = {
    "claude-wrong-po",
    "claude-invalid-json",
    "claude-timeout",
    "injected-lot-claude-fooled",
}
PDF_BYTES = b"%PDF-stand-in"


def case_text(case: Seam1Case) -> str:
    if case.pdf in ("corrupt", "image-only"):
        return rules.text_layer(pdf_bytes(case.pdf))
    return case.pdf_text


def expected_reading(case: Seam1Case) -> Reading:
    return BASE.claude if case.id in STUB_ONLY else case.claude


def is_false_proceed(case: Seam1Case, result: Proceed) -> bool:
    expect = BASE.expect if case.id in STUB_ONLY else case.expect
    return (
        expect.result != "proceed"
        or result.pln != expect.pln
        or result.po_number != expect.po_number
    )


def run_case(
    case: Seam1Case, internal_no: str, reader: ClaudeReader
) -> tuple[Skip | Proceed, list[str]]:
    """decide() on the case with the real reader; Claude's raw replies."""
    text = case_text(case)
    replies: list[str] = []

    def read_claude() -> str:
        raw = reader.read(text_document(text), case.note.title, case.note.body)
        replies.append(raw)
        return raw

    result = decide(
        case.note,
        internal_no,
        text,
        PDF_BYTES,
        case.lookup,
        site=case.config.site,
        reader_mode="hybrid",
        duplicate_ignores_cancelled=case.config.duplicate_ignores_cancelled,
        read_claude=read_claude,
    )
    return result, replies


def test_seam1_live_claude_has_no_false_proceed() -> None:
    config = load_config("test")
    reader = reader_from_config(config)
    agree = dict.fromkeys(FIELDS, 0)
    read_count = 0
    false_proceeds = 0
    for case in CASES:
        internal_no = eligible_internal_no(case.pool_row, case.config.title_rule, POOL)
        if internal_no is None:
            continue
        result, replies = run_case(case, internal_no, reader)
        assert isinstance(result, Skip | Proceed)
        if isinstance(result, Proceed) and is_false_proceed(case, result):
            false_proceeds += 1
            print(f"false PROCEED on case {case.id}")
        for raw in replies:
            read_count += 1
            try:
                reading = ClaudeReading.model_validate_json(raw)
            except ValueError:
                continue  # counted as no agreement on any field
            expected = expected_reading(case)
            for field in FIELDS:
                agree[field] += getattr(reading, field) == getattr(expected, field)
    # Field names and counts only: never a value read from a PDF.
    for field in FIELDS:
        print(f"agree {field}: {agree[field]}/{read_count}")
    usage = reader.usage
    print(
        f"tokens in {usage.input_tokens} out {usage.output_tokens}, "
        f"cost AUD {reader.cost_aud:.4f} ({read_count} Claude reads)"
    )
    print(f"false PROCEED: {false_proceeds}")
    assert read_count > 0
    assert false_proceeds == 0
