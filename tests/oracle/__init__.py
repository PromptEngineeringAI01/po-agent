"""B1's pure decision code, frozen as the oracle for the multi-client refactor.

A copy of `src/po_agent/b1/{models,reader_rules,address,readers,decision}.py`
at main `be84448` (24 Nov 2026), word for word except the import lines,
which point here (Joey, 24 Nov 2026: the oracle lands before task 9.1 moves
anything). `tests/properties/test_prop_oracle_diff.py` compares the current
code with it on generated inputs, so Phase S's refactor (tasks/plan.md 9.1,
9.2, 9.4) is checked old against new.

Never edit these files (CLAUDE.md Must never #8). They are deleted in their
own `test:` commit after checkpoint S-A, B1 seam 2 on the test site and the
first watched B1 hourly run after the tag move.
"""
