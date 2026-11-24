# Tests

How the suite is split and run: `SPEC.md` -> Testing Strategy; seam 2's run
order: `tests/seam2/README.md`. This file covers the property tests only.

## Property tests (Hypothesis)

`tests/properties/` holds the property-based tests (Joey approved the property
list and Hypothesis, 24 Nov 2026). They test only public pure functions and
take their expectations from SPEC, never from a copy of the production rule.
Generators use fake values only (CLAUDE.md Must never #6).

- `b1_worlds.py`: the shared generators. `proceed_worlds()` builds a whole
  consistent Note, both readers' text and the MySys lookup, the rare input
  that PROCEEDs; `MUTATIONS` is the catalog of single faults, each with the
  skip reason SPEC gives it.
- `tests/oracle/`: B1's pure modules frozen at main `be84448` for the
  differential tests of the multi-client refactor (tasks/plan.md Phase S).
  Never edit it (CLAUDE.md Must never #8); it is deleted in its own `test:`
  commit after checkpoint S-A, B1 seam 2 and the first watched B1 hourly run
  after the tag move.

### Profiles

Set in `tests/conftest.py`:

- `check` (default; `scripts/check.py` and CI): 60 examples per property,
  derandomized, so every run tries the same examples and a failure always
  reproduces; no example database.
- `thorough` (on demand): 2000 random examples per property, new ones each
  run, failures saved in `.hypothesis/` (git-ignored) and replayed first on
  the next run.

```powershell
uv run pytest tests/properties --hypothesis-profile=thorough
```

### Reproducing a failure

A failing property prints its minimized counterexample (the
`Falsifying example:` block) and, since `print_blob=True`, a line such as
`@reproduce_failure('6.170.17', b'...')`.

- Paste that decorator above the test's `@given` to replay exactly that
  example; remove it before committing (it is tied to the Hypothesis version).
- A `thorough` run saves the failure in `.hypothesis/` and replays it first
  on the next `thorough` run. To pin the random examples of a run, give it a
  seed:

```powershell
uv run pytest tests/properties --hypothesis-profile=thorough --hypothesis-seed=12345
```

- A `check` failure needs nothing extra: derandomized runs repeat it.

A property that finds a real bug is not fixed in the test task: its
counterexample becomes an `xfail(strict=True)` test and the fix is its own
task.
