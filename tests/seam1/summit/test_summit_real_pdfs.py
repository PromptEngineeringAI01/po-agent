"""Summit's readers on Joey's real Summit POs (task 9.7; laptop only).

`-m real_data`: reads private/summit/pdfs/ in the main checkout (or under
SEAM1_PRIVATE_DIR), never in CI. On each PDF both readers agree on all three
fields, the PDF's PO equals its file name's (a reader cross-check only:
decide() compares the title's PO, SPEC), and the compaction finding equals
Joey's expected value where private/summit/fixtures/cases.toml gives one
(`[[case]]` with `pdf` and `expect_compaction`, S.0). Output is counts only,
never a value; a failure shows the test name and exception type only (the
real_data scrub in tests/seam1/real_pos.py).
"""

import os
import re
import tomllib
from pathlib import Path

import pytest
from real_pos import PRIVATE_DIR_ENV, _main_checkout_private, _selected_explicitly

from po_agent.core.models import Skip, SkipReason
from po_agent.summit import reader_rules as rules

# "<sender prefix>-123456_020_01.pdf" -> 123456/020/01 (the 11 real names'
# shape, fake digits here).
_FILE_PO = re.compile(r"-([0-9]+)_([0-9]+)_([0-9]+)\.pdf", re.IGNORECASE)


def _file_name_po(name: str) -> str:
    match = _FILE_PO.search(name)
    return "/".join(match.groups()) if match else ""


@pytest.fixture(scope="session")
def summit_private(request: pytest.FixtureRequest) -> Path:
    env = os.environ.get(PRIVATE_DIR_ENV)
    private = Path(env) if env else _main_checkout_private()
    folder = None if private is None else private / "summit"
    if folder is not None and any((folder / "pdfs").glob("*.pdf")):
        return folder
    message = (
        f"private/summit/pdfs/ not found (set {PRIVATE_DIR_ENV} or use the laptop)"
    )
    if _selected_explicitly(request.config.option.markexpr or ""):
        raise FileNotFoundError(message)
    pytest.skip(message)


def _expected_compaction(folder: Path) -> dict[str, bool]:
    cases = folder / "fixtures" / "cases.toml"
    if not cases.is_file():
        return {}
    raw = tomllib.loads(cases.read_text(encoding="utf-8")).get("case", [])
    return {c["pdf"]: c["expect_compaction"] for c in raw if "expect_compaction" in c}


@pytest.mark.real_data
def test_the_real_summit_pdfs_read_alike_on_both_readers(summit_private: Path) -> None:
    pdfs = sorted((summit_private / "pdfs").glob("*.pdf"))
    expected = _expected_compaction(summit_private)
    fields = {"company": 0, "po number": 0, "compaction": 0}
    po_as_file = compaction_yes = as_expected = given = 0
    outcomes: dict[str, int] = {}
    for pdf in pdfs:
        texts = rules.read(pdf.read_bytes())
        for name, same in rules.agreement(texts).items():
            fields[name] += same
        result = rules.check_pdf(texts)
        outcome = result.reason.value if isinstance(result, Skip) else "READING"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        plumber = rules.read_text(texts.plumber)
        po_as_file += plumber.po_number == _file_name_po(pdf.name) != ""
        compaction_yes += plumber.compaction
        if pdf.name in expected:
            given += 1
            as_expected += plumber.compaction == expected[pdf.name]
    print(f"summit pdfs: {len(pdfs)}")
    for name, agree in fields.items():
        print(f"field {name}: agree {agree}, disagree {len(pdfs) - agree}")
    print(f"po equals file name: {po_as_file} of {len(pdfs)}")
    print(f"compaction: yes {compaction_yes}, no {len(pdfs) - compaction_yes}")
    print(f"compaction as expected: {as_expected} of {given} given (S.0)")
    print("outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())))
    assert pdfs
    assert all(agree == len(pdfs) for agree in fields.values())
    assert po_as_file == len(pdfs)
    assert as_expected == given
    assert set(outcomes) <= {"READING", SkipReason.NOT_COMPACTION.value}
