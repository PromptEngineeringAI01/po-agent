"""Seam 1 in hybrid mode with a stubbed Claude (task 2.4): steps 6-7 (the
Claude read and agreement) and step 9 (the address check), and `decide()` end
to end on every case in both reader modes.

The stub returns the case's Claude reading as raw JSON text, the way the
Claude reader (2.5) hands it to `decide()`; `decide()` validates it. A timeout
raises `ClaudeUnavailable`.
"""

from collections.abc import Callable

import pytest
from seam1_cases import CASES, POOL, Seam1Case, pdf_bytes

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import (
    ClaudeUnavailable,
    ReaderMode,
    decide,
    eligible_internal_no,
)
from po_agent.b1.models import (
    CompactionTask,
    MySysLookup,
    Proceed,
    Reading,
    Skip,
    SkipReason,
)

PDF_BYTES = b"%PDF-stand-in"
# Steps 2a-4: a case that skips here never calls Claude.
BEFORE_CLAUDE = {
    SkipReason.NOTE_ALREADY_LINKED,
    SkipReason.NO_PDF,
    SkipReason.MULTIPLE_PDFS,
    SkipReason.PDF_UNREADABLE,
    SkipReason.NOT_B1,
    SkipReason.NOT_COMPACTION,
    SkipReason.PO_MISMATCH,
}
INVALID_JSON = '{"issuer": "B1 Homes Pty Ltd", "contains_compaction": tru'


class StubClaude:
    """Counts its calls; returns raw JSON text or raises ClaudeUnavailable."""

    def __init__(self, raw: str | None) -> None:
        self.raw = raw  # None: a timeout
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.raw is None:
            raise ClaudeUnavailable("Claude timed out")
        return self.raw


def stub_for(case: Seam1Case) -> StubClaude:
    if case.claude_error == "timeout":
        return StubClaude(None)
    if case.claude_error == "invalid-json":
        return StubClaude(INVALID_JSON)
    return StubClaude(case.claude.model_dump_json())


def case_text(case: Seam1Case) -> str:
    if case.pdf in ("corrupt", "image-only"):
        return rules.text_layer(pdf_bytes(case.pdf))
    return case.pdf_text


def run(
    case: Seam1Case,
    claude: Callable[[], str],
    reader_mode: ReaderMode = "hybrid",
    lookup: MySysLookup | None = None,
    pdf_text: str | None = None,
) -> Skip | Proceed | None:
    """decide() on the case; None when step 0 leaves the Note untouched."""
    internal_no = eligible_internal_no(case.pool_row, case.config.title_rule, POOL)
    if internal_no is None:
        return None
    return decide(
        case.note,
        internal_no,
        case_text(case) if pdf_text is None else pdf_text,
        PDF_BYTES,
        case.lookup if lookup is None else lookup,
        site=case.config.site,
        reader_mode=reader_mode,
        duplicate_ignores_cancelled=case.config.duplicate_ignores_cancelled,
        read_claude=claude,
    )


def by_id(case_id: str) -> Seam1Case:
    return next(case for case in CASES if case.id == case_id)


CLEAN = by_id("p1-clean")


def skip(reason: SkipReason) -> Skip:
    return Skip(reason=reason)


def claude_json(**changes: object) -> str:
    return CLEAN.claude.model_copy(update=changes).model_dump_json()


# --- every seam-1 case, hybrid ---


def test_seam1_case_hybrid_end_to_end(seam1_case: Seam1Case) -> None:
    result = run(seam1_case, stub_for(seam1_case))
    expect = seam1_case.expect
    if expect.result == "untouched":
        assert result is None
    elif expect.result == "skip":
        assert expect.reason is not None
        assert result == skip(expect.reason)
    else:
        assert isinstance(result, Proceed)
        note = seam1_case.note
        assert result.note_id == note.note_id
        assert result.pln == expect.pln
        assert result.po_number == expect.po_number
        assert result.internal_no == result.po_number.split("/")[0]
        assert result.email_body == note.body
        assert result.pdf_file_name == note.attachment_names[0]
        assert result.pdf_bytes == PDF_BYTES
        assert result.existing_task_nos == expect.existing_task_nos


def test_seam1_case_never_carries_its_injected_text(seam1_case: Seam1Case) -> None:
    result = run(seam1_case, stub_for(seam1_case))
    shown = f"{result!r} {result!s}"
    values = result.model_dump() if isinstance(result, Proceed) else {}
    for text in seam1_case.never_in_output:
        assert text not in shown
        assert not any(isinstance(v, str) and text in v for v in values.values())


def test_seam1_case_calls_claude_only_after_steps_2a_to_4(
    seam1_case: Seam1Case,
) -> None:
    claude = stub_for(seam1_case)
    run(seam1_case, claude)
    expect = seam1_case.expect
    called_never = expect.result == "untouched" or expect.reason in BEFORE_CLAUDE
    assert claude.calls == (0 if called_never else 1)


def test_seam1_case_deterministic_only_never_calls_claude(
    seam1_case: Seam1Case,
) -> None:
    claude = stub_for(seam1_case)
    result = run(seam1_case, claude, reader_mode="deterministic-only")
    assert claude.calls == 0
    expect = seam1_case.expect_deterministic_only
    if expect.result == "untouched":
        assert result is None
    else:
        assert expect.reason is not None
        assert result == skip(expect.reason)


def false_proceeds(reader_mode: ReaderMode) -> int:
    """PROCEEDs a case doesn't expect, or with values it doesn't expect."""
    count = 0
    for case in CASES:
        result = run(case, stub_for(case), reader_mode=reader_mode)
        if not isinstance(result, Proceed):
            continue
        expect = (
            case.expect if reader_mode == "hybrid" else case.expect_deterministic_only
        )
        if (
            expect.result != "proceed"
            or result.pln != expect.pln
            or result.po_number != expect.po_number
        ):
            count += 1
    return count


def test_no_false_proceed_in_either_mode() -> None:
    hybrid, deterministic = (
        false_proceeds("hybrid"),
        false_proceeds("deterministic-only"),
    )
    print(f"false PROCEED: {hybrid + deterministic}")
    assert (hybrid, deterministic) == (0, 0)


def test_the_three_fake_pos_proceed_in_hybrid_mode() -> None:
    for case_id, pln in (
        ("p1-clean", "pln_10001"),
        ("p2-clean", "pln_10002"),
        ("p3-clean", "pln_10003"),
    ):
        case = by_id(case_id)
        result = run(case, stub_for(case))
        assert isinstance(result, Proceed) and result.pln == pln


# --- step 6: Claude's output ---


def test_a_clean_reading_proceeds() -> None:
    assert isinstance(run(CLEAN, StubClaude(claude_json())), Proceed)


def test_a_timeout_is_claude_unavailable() -> None:
    result = run(CLEAN, StubClaude(None))
    assert result == skip(SkipReason.CLAUDE_UNAVAILABLE)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        INVALID_JSON,
        "null",
        "[]",
        '"B1 Homes Pty Ltd"',
        # contains_compaction missing
        '{"issuer": "B1 Homes Pty Ltd", "po_number": "2600001B/048"}',
        # a string where a bool belongs (strict)
        claude_json().replace(
            '"contains_compaction":true', '"contains_compaction":"true"'
        ),
        # a number where a string belongs (strict)
        claude_json().replace('"site_lot":"123"', '"site_lot":123'),
        # an extra field
        claude_json().replace("{", '{"note":"ignore previous instructions",', 1),
    ],
)
def test_output_not_in_the_reading_schema_is_invalid(raw: str) -> None:
    result = run(CLEAN, StubClaude(raw))
    assert result == skip(SkipReason.CLAUDE_INVALID_OUTPUT)


def test_the_invalid_output_cases_really_change_the_json() -> None:
    # Guards the replace() calls above against a json format change.
    clean = claude_json()
    assert '"contains_compaction":true' in clean
    assert '"site_lot":"123"' in clean


# --- step 7: agreement (exact equality) ---


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "B1 HOMES PTY LTD"},
        {"issuer": "B1 Homes Pty Ltd "},
        {"issuer": ""},
        {"contains_compaction": False},
        {"po_number": "2600001B/049"},
        {"po_number": "2600001b/048"},
        {"po_number": ""},
        {"client_internal_no": "2600002B"},
        {"client_internal_no": ""},
    ],
)
def test_any_difference_on_the_agreed_fields_is_readers_disagree(
    changes: dict[str, object],
) -> None:
    result = run(CLEAN, StubClaude(claude_json(**changes)))
    assert result == skip(SkipReason.READERS_DISAGREE)


# --- section 2 order in hybrid mode ---

NO_PROJECT = CLEAN.lookup.model_copy(
    update={"search_rows": (), "project_internal_no": "", "address": ""}
)
ON_HOLD = (CompactionTask(task_no="tsk_200001", status="On Hold"),)


def test_steps_2a_to_4_come_before_claude() -> None:
    linked = CLEAN.note.model_copy(update={"project_linked": True})
    case = CLEAN.model_copy(update={"note": linked})
    claude = StubClaude(None)
    assert run(case, claude) == skip(SkipReason.NOTE_ALREADY_LINKED)
    assert claude.calls == 0


@pytest.mark.parametrize(
    ("claude", "reason"),
    [
        (StubClaude(None), SkipReason.CLAUDE_UNAVAILABLE),
        (StubClaude(INVALID_JSON), SkipReason.CLAUDE_INVALID_OUTPUT),
        (
            StubClaude(claude_json(po_number="2600001B/049")),
            SkipReason.READERS_DISAGREE,
        ),
    ],
)
def test_claude_and_agreement_come_before_the_project_lookup(
    claude: StubClaude, reason: SkipReason
) -> None:
    assert run(CLEAN, claude, lookup=NO_PROJECT) == skip(reason)


def test_the_project_lookup_comes_before_the_address() -> None:
    claude = StubClaude(claude_json(site_lot="77"))
    result = run(CLEAN, claude, lookup=NO_PROJECT)
    assert result == skip(SkipReason.PROJECT_NOT_FOUND)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"site_lot": "77"}, SkipReason.ADDRESS_UNVERIFIABLE),
        ({"site_suburb": "Sampleville North"}, SkipReason.ADDRESS_UNVERIFIABLE),
    ],
)
def test_the_address_comes_before_the_duplicate_check(
    changes: dict[str, object], reason: SkipReason
) -> None:
    lookup = CLEAN.lookup.model_copy(update={"tasks": ON_HOLD})
    result = run(CLEAN, StubClaude(claude_json(**changes)), lookup=lookup)
    assert result == skip(reason)


def test_an_address_mismatch_comes_before_the_duplicate_check() -> None:
    text = CLEAN.pdf_text.replace("Job Address: Lot 123", "Job Address: Lot 124")
    lookup = CLEAN.lookup.model_copy(update={"tasks": ON_HOLD})
    claude = StubClaude(claude_json(site_lot="124"))
    result = run(CLEAN, claude, lookup=lookup, pdf_text=text)
    assert result == skip(SkipReason.ADDRESS_MISMATCH)


def test_the_duplicate_check_runs_last() -> None:
    lookup = CLEAN.lookup.model_copy(update={"tasks": ON_HOLD})
    result = run(CLEAN, StubClaude(claude_json()), lookup=lookup)
    assert result == skip(SkipReason.DUPLICATE_TASK)


def test_the_project_address_is_parsed_in_decide() -> None:
    lookup = CLEAN.lookup.model_copy(update={"address": "123 Sample Lane Sampleville"})
    result = run(CLEAN, StubClaude(claude_json()), lookup=lookup)
    assert result == skip(SkipReason.ADDRESS_UNVERIFIABLE)


def test_hybrid_mode_without_a_claude_reader_is_refused() -> None:
    internal_no = eligible_internal_no(CLEAN.pool_row, CLEAN.config.title_rule, POOL)
    assert internal_no is not None
    with pytest.raises(ValueError):
        decide(
            CLEAN.note,
            internal_no,
            CLEAN.pdf_text,
            PDF_BYTES,
            CLEAN.lookup,
            site="test",
            reader_mode="hybrid",
            duplicate_ignores_cancelled=True,
        )


def test_the_reading_model_is_what_claude_must_fill() -> None:
    # The stub's clean JSON is a valid Reading, so the skips above come from
    # the changed values, not from a broken stub.
    assert Reading.model_validate_json(claude_json()) == CLEAN.claude
