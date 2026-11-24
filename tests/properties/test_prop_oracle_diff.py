"""Differential tests for the multi-client refactor (tasks/plan.md Phase S):
the current B1 decision code against tests/oracle, frozen at main be84448.

A refactor that keeps B1's behaviour keeps both equal. When 9.1 adds the
Creator to the Proceed, its `test:` commit compares the shared fields and
`creator == "Perth Scheduling"` here.
"""

import b1_worlds
from b1_worlds import MUTATIONS, any_internal_nos, fresh_values, proceed_worlds
from hypothesis import assume, given
from hypothesis import strategies as st
from oracle import decision as old_decision
from oracle import models as old_models
from oracle import readers as old_readers

from po_agent.b1 import decision, models, readers

POOL = "Fake Agent Pool"


@given(
    proceed_worlds(),
    st.lists(st.sampled_from(sorted(MUTATIONS)), max_size=3),
    st.data(),
)
def test_decide_matches_the_frozen_b1_code(world, names, data):
    for name in names:
        if MUTATIONS[name].applies(world):
            world = MUTATIONS[name].apply(world, data.draw(fresh_values(world)))
    new = b1_worlds.outcome(world, models, readers, decision)
    old = b1_worlds.outcome(world, old_models, old_readers, old_decision)
    assert new == old


@given(
    st.text(max_size=60)
    | st.builds(lambda x, t: f"{t} {x}_048.pdf", any_internal_nos, st.text(max_size=20))
    | st.builds(
        lambda x, t: f"[B1 Homes] Order {x}/048 {t}",
        any_internal_nos,
        st.text(max_size=20),
    ),
    st.sampled_from(["---", " --- ", "pln_1"]),
    st.sampled_from([POOL, f" {POOL}", "A Person"]),
    st.sampled_from(["test-body-filename", "live-b1-title"]),
)
def test_step_0_eligibility_matches_the_frozen_b1_code(cell, project, assignee, rule):
    # The live rule now refuses a cell naming a second internal number (Joey,
    # 24 Nov 2026), unlike the frozen code: compare only cells without one.
    # test_prop_decision.py and seam 1 pin the new behaviour.
    if rule == "live-b1-title":
        assume("_048" not in cell and cell.count("/048") <= 1)
    new = decision.eligible_internal_no(
        models.NotePoolRow(
            note_id="1", subject_note=cell, project=project, assignee=assignee
        ),
        rule,
        POOL,
    )
    old = old_decision.eligible_internal_no(
        old_models.NotePoolRow(
            note_id="1", subject_note=cell, project=project, assignee=assignee
        ),
        rule,
        POOL,
    )
    assert new == old
