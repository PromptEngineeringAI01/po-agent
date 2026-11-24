---
name: test-driven-development
description: Drives development with tests using the red-green-refactor loop. Use when implementing any logic, fixing any bug, or changing any behavior. Use when you need to prove that code works, when a bug report arrives, or when you're about to modify existing functionality. Use when asked to add tests to a function, fix a bug in it or change its behavior, even when the request does not mention tests. The skill writes the failing test first and changes the function second, never the change alone.
---

<!-- From addyosmani/agent-skills@8c99fa3 (v0.6.17, MIT, see LICENSE), skills/test-driven-development. Vendored 24 Nov 2026 so the build loop doesn't follow the plugin's auto-updates. Adapted for PO Agent: Python/pytest examples and uv commands instead of TypeScript/npm; the repo's test: commit rule; dropped the Chrome DevTools section (MySys is driven only through the guard) and links to files not vendored. -->

# Test-Driven Development

**CLAUDE.md wins over anything here.** In this repo: the failing test goes in its own `test:` commit before the `feat:` or `fix:` commit; a test, fixture or expected result is never edited to make it pass (Must never #8); test rules in `docs/workflow.md` (Production build loop step 3) and the task brief add to this skill.

## Overview

Write a failing test before writing the code that makes it pass. For bug fixes, reproduce the bug with a test before attempting a fix. Tests are proof - "seems right" is not done.

## When to Use

- Implementing any new logic or behavior
- Fixing any bug (the Prove-It Pattern)
- Modifying existing functionality
- Adding edge case handling
- Any change that could break existing behavior

**When NOT to use:** Pure configuration changes, documentation updates, or static content changes that have no behavioral impact.

## This Repo's Commands

- Focused test while looping: `uv run pytest <test file or node id>`, or `uv run scripts/check.py --quick <test paths>` (the `/quick-check` skill)
- Full gate before completion: `uv run scripts/check.py` (healthy: last line "check: all passed")
- Seam 2 touches the MySys test site: never run it by path or in a loop; follow `SPEC.md` -> Commands and the task brief.

Tests live under `tests/`, named `test_*.py`; follow the neighbouring tests' patterns. Never assume another stack's default command.

## The TDD Cycle

```
    RED                GREEN              REFACTOR
 Write a test    Write minimal code    Clean up the
 that fails  ──→  to make it pass  ──→  implementation  ──→  (repeat)
      │                  │                    │
      ▼                  ▼                    ▼
   Test FAILS        Test PASSES         Tests still PASS
```

The examples below use illustrative names, not this repo's API.

### Step 1: RED - Write a Failing Test

Write the test first. It must fail, and for the expected reason (the behaviour is missing, not a typo or an import error). A test that passes immediately proves nothing. Commit it as `test:`.

```python
# RED: fails because parse_po_number doesn't exist yet
def test_parse_po_number_reads_the_048_suffix():
    assert parse_po_number("PO 12345/048") == "12345/048"
```

### Step 2: GREEN - Make It Pass

Write the minimum code to make the test pass. Don't over-engineer:

```python
# GREEN: minimal implementation
def parse_po_number(text: str) -> str | None:
    match = re.search(r"\b\d+/048\b", text)
    return match.group(0) if match else None
```

### Step 3: REFACTOR - Clean Up

With tests green, improve the code without changing behavior: extract shared logic, improve naming, remove duplication. Run the tests after every refactor step.

## The Prove-It Pattern (Bug Fixes)

When a bug is reported, **do not start by trying to fix it.** Start by writing a test that reproduces it.

```
Bug report arrives
       │
       ▼
  Write a test that demonstrates the bug
       │
       ▼
  Test FAILS (confirming the bug exists)  → commit as test:
       │
       ▼
  Implement the fix                        → commit as fix:
       │
       ▼
  Test PASSES (proving the fix works)
       │
       ▼
  Run the full check (no regressions)
```

If the cause isn't obvious, use the `diagnosing-bugs` skill.

## The Test Pyramid

Most tests should be small and fast, with progressively fewer at higher levels:

| Size | Constraints | Speed | Example here |
|------|------------|-------|---------|
| **Small** | Single process, no I/O, no network | Milliseconds | Address rules, decision engine, parsers |
| **Medium** | Localhost only, no external services | Seconds | Seam 1 on generated fake PDFs, driver tests against fake pages |
| **Large** | External services | Minutes | Seam 2 on the MySys test site (serial, watched) |

```
Is it pure logic with no side effects?        → small test
Does it cross a boundary (PDF, file system)?   → medium test
Is it a critical flow that must work in MySys? → seam 2, critical paths only
```

## Writing Good Tests

### Test State, Not Interactions

Assert on the *outcome* of an operation, not on which methods were called internally. Tests that verify call sequences break on refactor even when behaviour is unchanged.

```python
# Good: tests what the function returns
def test_decide_skips_when_readers_disagree():
    assert decide(readers_disagree_po).action == "SKIP"

# Bad: tests how it works inside
def test_decide_calls_compare(mocker):
    spy = mocker.spy(engine, "_compare")
    decide(readers_disagree_po)
    spy.assert_called_once()
```

### DAMP Over DRY in Tests

A test should read like a specification: each test tells a complete story without tracing shared helpers. Duplication in tests is fine when it makes each test independently understandable.

### Prefer Real Implementations Over Mocks

```
Preference order (most to least preferred):
1. Real implementation  → highest confidence
2. Fake                 → in-memory stand-in (e.g. a fake MySys page)
3. Stub                 → returns canned data
4. Mock (interaction)   → verifies calls; use sparingly
```

Never mock our own code; fakes only at the edges (MySys pages, the clock), as the seams already do. For crash or rollback behaviour, exercise the real boundary: an injected exception is not process termination.

### Arrange-Act-Assert, One Concept per Test, Descriptive Names

```python
def test_address_check_fails_on_a_different_street_number():
    # Arrange
    pdf, mysys = "12 Smith St", "14 Smith St"
    # Act
    result = addresses_match(pdf, mysys)
    # Assert
    assert result is False
```

Name tests so the list reads like the spec (`test_skips_when_...`, `test_rejects_...`), never `test_works` or `test_3`. Use `pytest.mark.parametrize` for a rule's in, out and boundary cases rather than one test that asserts everything.

## Test Anti-Patterns to Avoid

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Testing implementation details | Breaks on refactor with behaviour unchanged | Test inputs and outputs |
| Tautological expected value | Computed the way the code computes it, so it can't fail | Write the value out from `SPEC.md` or the plan |
| Flaky tests (timing, order) | Erode trust in the suite | Deterministic assertions; isolate state (xdist runs in parallel) |
| Testing framework code | Tests third-party behaviour | Only test our code |
| No test isolation | Pass alone, fail together | Each test sets up its own state (`tmp_path`, fixtures) |
| Mocking everything | Pass while production breaks | Real > fake > stub > mock |

## When to Use Subagents for Testing

For a complex bug fix, a sub-agent can write the reproduction test without knowing the fix; the main agent checks it fails, fixes, and checks it passes.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll write tests after the code works" | You won't. And tests written after the fact test implementation, not behavior. |
| "This is too simple to test" | Simple code gets complicated. The test documents the expected behavior. |
| "I tested it manually" | Manual testing doesn't persist. Tomorrow's change might break it with no way to know. |
| "Let me run the tests again just to be extra sure" | After a clean run, repeating the same command adds nothing unless the code has changed since. |

## Red Flags

- Writing code without any corresponding tests
- Tests that pass on the first run (they may not be testing what you think)
- "All tests pass" but no tests were actually run
- Bug fixes without reproduction tests
- A test changed after its `test:` commit (`git diff <test commit>..HEAD -- tests/` must be empty)
- Skipping or deselecting tests to make the suite pass
- Running the same test command twice in a row without any intervening code change

## Verification

After completing any implementation:

- [ ] Every new behavior has a corresponding test, committed as `test:` before the code
- [ ] `uv run scripts/check.py` ends with "check: all passed"
- [ ] Bug fixes include a reproduction test that failed before the fix
- [ ] Test names describe the behavior being verified
- [ ] No tests were skipped, disabled or edited to pass
