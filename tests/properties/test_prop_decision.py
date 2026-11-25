"""Properties of the decision engine (b1/decision.py, b1/models.py; SPEC -> In
the MVP; MySys screen rules -> Note Pool, Project search, Duplicate check).

The PROCEED worlds and the fault catalog are in b1_worlds.py. Every fault's
expected skip reason is SPEC's; the order of the checks is not restated
here: a combination of faults only has to skip.
"""

import b1_worlds
import pytest
from b1_worlds import (
    COMPANY,
    MUTATIONS,
    any_internal_nos,
    fresh_values,
    internal_nos,
    note_ids,
    plns,
    proceed_worlds,
    task_nos,
)
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from po_agent.b1 import decision, readers
from po_agent.b1.decision import check_duplicate, eligible_internal_no, match_project
from po_agent.b1.models import B1Proceed
from po_agent.core import models
from po_agent.core.models import (
    CompactionTask,
    NotePoolRow,
    SearchRow,
    Skip,
    SkipReason,
)

POOL = "Fake Agent Pool"
CURRENT = (models, readers, decision)
RULES = st.sampled_from(["test-body-filename", "live-b1-title"])
SPACES = st.sampled_from(["", " ", "  ", "\t"])
# Cell text around a file name: words and spaces, never a file name itself.
FILLER = st.text("abcdefghij XYZ,:", max_size=20).map(str.strip)


def run(world: b1_worlds.World) -> b1_worlds.Result:
    return b1_worlds.outcome(world, *CURRENT)


def eligible_cell(rule: str, internal_no: str, copy: str, before: str, after: str):
    if rule == "test-body-filename":
        return f"{before} {internal_no}_048{copy}.pdf {after}".strip()
    return f"[B1 Homes] Order {internal_no}/048 {after}".rstrip()


# C1, C2: step 0, which Notes are eligible


@given(RULES, any_internal_nos, st.sampled_from(["", "_1", "_23"]), FILLER, FILLER)
def test_an_eligible_cell_gives_back_its_internal_number(
    rule, internal_no, copy, before, after
):
    """Both title rules (SPEC -> In the MVP): the internal number round-trips."""
    row = NotePoolRow(
        note_id="1",
        subject_note=eligible_cell(rule, internal_no, copy, before, after),
        project="---",
        assignee=POOL,
    )
    assert eligible_internal_no(row, rule, POOL) == internal_no


@given(RULES, any_internal_nos, FILLER, SPACES, SPACES, SPACES)
def test_spaces_around_the_cells_never_change_eligibility(
    rule, internal_no, after, s1, s2, s3
):
    cell = eligible_cell(rule, internal_no, "", "", after)
    plain = NotePoolRow(note_id="1", subject_note=cell, project="---", assignee=POOL)
    padded = NotePoolRow(
        note_id="1",
        subject_note=f"{s1}{cell}{s2}",
        project=f"{s2}---{s3}",
        assignee=f"{s3}{POOL}{s1}",
    )
    assert eligible_internal_no(padded, rule, POOL) == eligible_internal_no(
        plain, rule, POOL
    )


@given(
    RULES,
    any_internal_nos,
    st.text(max_size=12).filter(lambda p: p.strip() != "---"),
    st.text(max_size=12).filter(lambda a: a.strip() != POOL),
    st.booleans(),
)
def test_a_linked_note_or_a_persons_note_is_never_eligible(
    rule, internal_no, project, assignee, linked
):
    """SPEC: the Project cell reads --- and the Assignee cell reads the pool,
    so a person's Note is never taken."""
    cell = eligible_cell(rule, internal_no, "", "", "")
    row = NotePoolRow(
        note_id="1",
        subject_note=cell,
        project=project if linked else "---",
        assignee=POOL if linked else assignee,
    )
    assert eligible_internal_no(row, rule, POOL) is None


@given(any_internal_nos, any_internal_nos, FILLER)
def test_two_internal_numbers_in_a_test_cell_are_not_eligible(first, second, between):
    """Anything uncertain is not eligible (decision.py, step 0)."""
    assume(first != second)
    cell = f"{first}_048.pdf {between} {second}_048_1.pdf"
    row = NotePoolRow(note_id="1", subject_note=cell, project="---", assignee=POOL)
    assert eligible_internal_no(row, "test-body-filename", POOL) is None


@given(internal_nos, internal_nos)
def test_a_live_note_whose_attachment_is_another_number_skips(title_no, file_no):
    """The live title's number, a body naming no number and an attachment
    for another number: never PROCEED (Joey, 24 Nov 2026: pinned as a skip).
    The cell is eligible, and step 4 skips it (PO_MISMATCH). A body naming
    the other number is not eligible (the test below)."""
    assume(title_no != file_no)
    cell = f"[B1 Homes] Order {title_no}/048 Please find attached Purchase Order"
    row = NotePoolRow(note_id="1", subject_note=cell, project="---", assignee=POOL)
    internal_no = eligible_internal_no(row, "live-b1-title", POOL)
    assert internal_no == title_no
    if internal_no is not None:
        note = models.NoteSnapshot(
            note_id="1",
            title="",
            body="b",
            attachment_names=(f"{file_no}_048_1.pdf",),
            project_linked=False,
        )
        result = decision.check_note_and_pdf(
            note,
            internal_no,
            f"B1 Homes Pty Ltd\nCOMPACTION\nPurchase Order No {file_no}/048",
        )
        assert isinstance(result, Skip)
        assert result.reason is SkipReason.PO_MISMATCH


@example(title_no="9000001A", other_no="9000002A")  # the minimized counterexample
@given(internal_nos, internal_nos)
def test_a_live_cell_naming_a_second_po_is_not_eligible(title_no, other_no):
    """decision.py step 0: two different internal numbers in one cell are
    uncertain, so not eligible, on live as on the test rule."""
    assume(title_no != other_no)
    cell = (
        f"[B1 Homes] Order {title_no}/048 Please find attached Purchase Order"
        f" / Quotation file {other_no}_048_1.pdf"
    )
    row = NotePoolRow(note_id="1", subject_note=cell, project="---", assignee=POOL)
    assert eligible_internal_no(row, "live-b1-title", POOL) is None


# C3: the project match (SPEC -> Project search)


@st.composite
def search_results(draw):
    """Rows with one matching pln among noise, and the internal number."""
    x = draw(internal_nos)
    pln = draw(plns)
    matching = [
        SearchRow(
            pln=pln,
            client_ref_no=draw(SPACES)
            + draw(st.sampled_from([x, x.lower()]))
            + draw(SPACES),
            company=draw(SPACES) + COMPANY + draw(SPACES),
        )
        for _ in range(draw(st.integers(1, 3)))
    ]
    noise = draw(
        st.lists(
            st.builds(
                SearchRow,
                pln=plns.filter(lambda p: p != pln),
                client_ref_no=st.sampled_from(
                    [f"{x}/048", f"{x}/020", f"{x}0", "", "9"]
                ),
                company=st.just(COMPANY),
            )
            | st.builds(
                SearchRow,
                pln=plns,
                client_ref_no=st.just(x),
                company=st.sampled_from(["Other Homes Pty Ltd", "B1 Homes Group"]),
            ),
            max_size=4,
        )
    )
    rows = draw(st.permutations(matching + noise))
    return x, pln, tuple(rows)


@given(search_results(), st.sampled_from(["test", "live"]))
def test_the_one_matching_row_gives_its_pln_among_any_other_rows(results, site):
    """B1 Homes and Client Ref No. (trimmed, any case) = the bare internal
    number; other suffixes, numbers and companies are ignored; the same row
    twice counts once."""
    x, pln, rows = results
    assert match_project(rows, False, x, site) == pln


# C4: the duplicate check (SPEC -> Duplicate check, MVP strict)

TASKS = st.lists(
    st.builds(
        CompactionTask,
        task_no=task_nos,
        status=st.sampled_from(
            ["Cancelled", " Cancelled ", "New Project", "On-hold x", ""]
        ),
    ),
    max_size=4,
)


@given(TASKS, TASKS, st.booleans())
def test_more_tasks_never_turn_a_duplicate_into_a_pass(tasks, more, ignores):
    if isinstance(check_duplicate(tasks, ignores), Skip):
        assert isinstance(check_duplicate(tasks + more, ignores), Skip)


@given(TASKS)
def test_counting_cancelled_tasks_is_at_least_as_strict(tasks):
    """live (and the strict config) counts Cancelled ones too."""
    if isinstance(check_duplicate(tasks, True), Skip):
        assert isinstance(check_duplicate(tasks, False), Skip)


# C5-C7: decide() end to end


@given(proceed_worlds())
def test_a_world_passing_every_check_proceeds_with_its_values(world):
    """SPEC section 2, every step passed: PROCEED with the Note's and the
    project's values, the lookup read once."""
    result = run(world)
    assert result.kind == "proceed", result
    assert result.lookups == 1
    assert result.value["note_id"] == world.note_id
    assert result.value["pln"] == world.pln
    assert result.value["po_number"] == f"{world.internal_no}/048"
    assert result.value["pdf_file_name"] == world.attachments[0]
    assert result.value["email_body"] == world.body
    assert result.value["pdf_bytes"] == world.data
    assert result.value["existing_task_nos"] == tuple(t for t, _ in world.tasks)


# Every fault runs every time (a sampled fault could go undrawn in the
# derandomized check), on a few worlds each.
@pytest.mark.parametrize("name", sorted(MUTATIONS))
@settings(max_examples=10)
@given(world=proceed_worlds(), data=st.data())
def test_each_single_fault_skips_with_its_spec_reason(name, world, data):
    mutation = MUTATIONS[name]
    assume(mutation.applies(world))
    fresh = data.draw(fresh_values(world))
    result = run(mutation.apply(world, fresh))
    assert (result.kind, result.value) == ("skip", mutation.reason)
    # The project is read in MySys only once the Note and PDF checks and the
    # second reader pass (task 8.3), and then only once.
    assert result.lookups == (0 if mutation.before_lookup else 1)


@given(
    proceed_worlds(),
    st.lists(st.sampled_from(sorted(MUTATIONS)), min_size=1, max_size=5),
    st.data(),
)
def test_adding_faults_never_turns_a_skip_into_proceed(world, names, data):
    """Monotonicity: any mix of faults skips; uncertainty never proceeds."""
    for name in names:
        mutation = MUTATIONS[name]
        if mutation.applies(world):
            world = mutation.apply(world, data.draw(fresh_values(world)))
    assert run(world).kind == "skip"


# D1: the Proceed refuses a malformed decision (models.py)


@st.composite
def proceeds(draw):
    x = draw(any_internal_nos)
    return {
        "note_id": draw(note_ids),
        "internal_no": x,
        "pln": draw(plns),
        "po_number": f"{x}/048",
        "email_body": "Please find attached",
        "pdf_file_name": f"{x}_048{draw(st.sampled_from(['', '_1']))}.pdf",
        "pdf_bytes": b"%PDF-",
        "existing_task_nos": tuple(draw(st.lists(task_nos, max_size=3))),
        "creator": "Perth Scheduling",
    }


@given(proceeds())
def test_a_well_formed_proceed_is_accepted(fields):
    assert B1Proceed(**fields).po_number == fields["po_number"]


@given(
    proceeds(),
    st.sampled_from(
        [
            ("internal_no", lambda v: v + "a"),
            ("internal_no", lambda v: v + "\n"),
            ("po_number", lambda v: v.replace("/048", "/049")),
            ("po_number", lambda v: "9" + v),
            ("po_number", lambda v: v + " "),
            ("pln", lambda v: v.upper()),
            ("pln", lambda v: v + "\n"),
            ("pdf_file_name", lambda v: v + ".exe"),
            ("pdf_file_name", lambda v: "copy " + v),
            ("email_body", lambda v: ""),
            ("pdf_bytes", lambda v: b""),
            ("existing_task_nos", lambda v: (*v, "TSK_1")),
            ("note_id", lambda v: ""),
            ("creator", lambda v: ""),
        ]
    ),
)
def test_a_near_miss_proceed_is_refused(fields, change):
    """Every value is checked again, so a malformed decision can't reach a
    write (models.py, Proceed)."""
    name, mutate = change
    with pytest.raises(ValidationError):
        B1Proceed(**{**fields, name: mutate(fields[name])})


def test_the_fault_catalog_covers_every_decide_skip_reason():
    """Every skip reason decide() can give has a fault in the catalog
    (PARTIAL_WRITE comes after Submit, never from decide; Summit's three
    come only from Summit's decide, task 9.9)."""
    covered = {mutation.reason for mutation in MUTATIONS.values()}
    summit_only = {"COMPANY_UNKNOWN", "COMPANY_MISMATCH", "CREATOR_UNKNOWN"}
    expected = {reason.value for reason in SkipReason} - {"PARTIAL_WRITE"}
    expected -= summit_only
    assert covered == expected
