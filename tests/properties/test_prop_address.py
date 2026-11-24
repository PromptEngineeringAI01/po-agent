"""Properties of the address check (b1/address.py; SPEC -> MySys screen rules
-> Project address; decisions, 30 Oct, 2 Nov and 11 Nov 2026).

Expectations come from SPEC's rules on generated fake addresses
(b1_worlds.py), never from a copy of the parser.
"""

import string
from typing import NamedTuple

from b1_worlds import STATES, TAILS, Street, houses, lots, pdf_texts, streets, words
from hypothesis import assume, given
from hypothesis import strategies as st

from po_agent.b1.address import normalise, parse_project_address, verify_address
from po_agent.b1.models import SkipReason

MISMATCH = SkipReason.ADDRESS_MISMATCH
UNVERIFIABLE = SkipReason.ADDRESS_UNVERIFIABLE
LAYOUTS = st.sampled_from(["label_line", "under", "house_line"])
PROJECT_TAILS = st.sampled_from(["", " 6000", " 6000 WA", " WA", " WA 6000"])
# A non-ASCII letter: normalise() would turn it into a word break (2.5 review).
NON_ASCII_LETTERS = st.characters(min_codepoint=128, categories=["L"])
SAME = "same"


class Case(NamedTuple):
    """A project address and both readers' text of a PDF that holds it, in
    one of SPEC's layouts."""

    lot: str
    house: str | None
    street: Street
    tail: str  # the project's postcode and state
    plumber: str
    pypdf: str
    layout: str

    def project(
        self,
        lot: str | None = None,
        house: str | None = SAME,
        shown: list[str] | None = None,
        separator: str = " ",
        after_lot: str = "",
    ) -> str:
        """The project's Address string, with any part replaced."""
        house = self.house if house == SAME else house
        house_part = f" (#{house})" if house else ""
        rest = separator.join(self.street.shown if shown is None else shown)
        lot = self.lot if lot is None else lot
        return f"Lot {lot}{after_lot}{house_part} {rest}{self.tail}"


@st.composite
def matching(draw: st.DrawFn) -> Case:
    lot = draw(lots)
    layout = draw(LAYOUTS)
    house = draw(houses) if layout == "house_line" else draw(st.none() | houses)
    street = draw(streets())
    plumber, pypdf = pdf_texts(
        "9000001A", lot, house, " ".join(street.shown) + draw(TAILS), layout
    )
    return Case(lot, house, street, draw(PROJECT_TAILS), plumber, pypdf, layout)


def both(project: str, plumber: str, pypdf: str) -> tuple:
    """verify_address on both readers' text, as readers.check_address runs it."""
    return (
        verify_address(plumber, project),
        verify_address(pypdf, project, exact_line_under=True),
    )


# A1, A2: normalise


@given(st.text())
def test_normalise_is_idempotent(text):
    once = normalise(text)
    assert normalise(once) == once


@given(st.text())
def test_normalise_gives_lower_case_words_and_single_spaces(text):
    result = normalise(text)
    assert set(result) <= set(string.ascii_lowercase + string.digits + " ")
    assert result == " ".join(result.split())


# A5: the project address's shape


@given(
    lots,
    st.none() | houses,
    streets(),
    st.sampled_from(STATES),
    st.booleans(),
    PROJECT_TAILS,
)
def test_project_address_parses_into_lot_and_r(lot, house, street, state, mid, tail):
    """Lot <lot> [(#<house no>)] <street> <suburb> [<postcode>] [<state>],
    with any state word dropped wherever it sits (decisions, 11 Nov 2026)."""
    shown = list(street.shown)
    if mid:
        shown.insert(len(shown) - 1, state)
    house_part = f" (#{house})" if house else ""
    parsed = parse_project_address(f"Lot {lot}{house_part} {' '.join(shown)}{tail}")
    assert parsed is not None
    assert parsed.lot == lot.casefold()
    assert parsed.rest == " ".join(street.normalised)


@given(lots, words, PROJECT_TAILS)
def test_project_r_of_one_word_does_not_parse(lot, word, tail):
    """R must hold at least a street and a suburb (review, 2.5)."""
    assert parse_project_address(f"Lot {lot} {word}{tail}") is None


# A6, A3, A4: SPEC's layouts verify, whatever the spelling


@given(matching())
def test_each_spec_layout_verifies_on_both_readers(case):
    assert both(case.project(), case.plumber, case.pypdf) == (None, None)


@given(matching(), st.sampled_from([str.upper, str.lower, str.swapcase]))
def test_letter_case_never_changes_the_result(case, change):
    changed = (change(case.project()), change(case.plumber), change(case.pypdf))
    assert both(*changed) == (None, None)


@given(matching(), st.sampled_from([", ", " / ", " - ", "  ", "\t", "; "]))
def test_punctuation_between_the_words_of_r_is_a_separator(case, separator):
    project = case.project(separator=separator)
    assert both(project, case.plumber, case.pypdf) == (None, None)


@given(matching(), st.data())
def test_a_street_type_spelt_the_other_way_still_verifies(case, data):
    """SPEC section 4: the project may write Street where the PDF has St."""
    swap = {"St": "Street", "Street": "St", "Rd": "Road", "Road": "Rd"}
    swap |= {"Ave": "Avenue", "Avenue": "Ave", "Ln": "Lane", "Lane": "Ln"}
    shown = [swap.get(word, word) for word in case.street.shown]
    assume(shown != case.street.shown)
    assert both(case.project(shown=shown), case.plumber, case.pypdf) == (None, None)


# A7, A8: near misses never verify


@given(matching(), st.sampled_from(["A", "0", "1", "B"]), st.booleans())
def test_a_lot_differing_only_at_its_end_is_a_mismatch(case, extra, drop):
    """12 vs 12A vs 120 vs 1: SPEC compares the lot as a case-folded word."""
    other = case.lot[:-1] if drop and len(case.lot) > 1 else case.lot + extra
    assume(other.casefold() != case.lot.casefold())
    project = case.project(lot=other)
    assert both(project, case.plumber, case.pypdf) == (MISMATCH, MISMATCH)


@given(matching(), words, st.data())
def test_one_changed_word_of_r_never_verifies(case, other, data):
    index = data.draw(st.integers(0, len(case.street.shown) - 1))
    assume(normalise(other) != normalise(case.street.shown[index]))
    assume(other.lower() not in case.plumber.lower())
    shown = list(case.street.shown)
    shown[index] = other
    assert None not in both(case.project(shown=shown), case.plumber, case.pypdf)


@given(matching(), words, st.data())
def test_an_extra_word_in_r_never_verifies(case, extra, data):
    assume(extra.lower() not in case.plumber.lower())
    shown = list(case.street.shown)
    shown.insert(data.draw(st.integers(0, len(shown))), extra)
    assert None not in both(case.project(shown=shown), case.plumber, case.pypdf)


@given(matching(), st.booleans())
def test_the_house_number_line_needs_the_projects_house_number(case, drop):
    """decisions, 11 Nov 2026: a project without one, or with another, is
    ADDRESS_MISMATCH."""
    assume(case.layout == "house_line")
    project = case.project(house=None if drop else f"{case.house}0")
    assert both(project, case.plumber, case.pypdf) == (MISMATCH, MISMATCH)


# A9: the tail


@given(lots, streets(), st.sampled_from(["under", "label_line"]), st.data())
def test_a_tail_of_two_states_or_two_postcodes_is_a_mismatch(lot, street, layout, data):
    tail = data.draw(st.sampled_from([" WA NSW", " 6000 6001", " WA 6000 6001"]))
    rest = " ".join(street.shown) + tail
    plumber, pypdf = pdf_texts("9000001A", lot, None, rest, layout)
    project = f"Lot {lot} {' '.join(street.shown)}"
    assert both(project, plumber, pypdf) == (MISMATCH, MISMATCH)


# A10, A11: what can't be read is ADDRESS_UNVERIFIABLE


@given(matching(), NON_ASCII_LETTERS, st.data())
def test_a_non_ascii_letter_in_the_project_address_is_unverifiable(case, letter, data):
    project = case.project()
    at = data.draw(st.integers(0, len(project)))
    changed = project[:at] + letter + project[at:]
    assert both(changed, case.plumber, case.pypdf) == (UNVERIFIABLE, UNVERIFIABLE)


@given(matching(), NON_ASCII_LETTERS, st.data())
def test_a_non_ascii_letter_in_the_label_line_is_unverifiable(case, letter, data):
    """The block starts after the label: on pdfplumber's text the Supplier
    column sits before it on the same line, and is not the block (SPEC)."""
    for text, exact in ((case.plumber, False), (case.pypdf, True)):
        start = text.index("Job Address:") + len("Job Address:")
        at = data.draw(st.integers(start, text.index("\n", start)))
        changed = text[:at] + letter + text[at:]
        result = verify_address(changed, case.project(), exact_line_under=exact)
        assert result == UNVERIFIABLE


@given(
    matching(),
    st.sampled_from(
        ["Job Address:", "Job  Address", "JobAddress", "JOB ADDRESS -", "job-address"]
    ),
    st.booleans(),
)
def test_a_second_label_in_any_spelling_is_unverifiable(case, label, first):
    extra = f"{label} Lot 1 Other Place"
    for text, exact in ((case.plumber, False), (case.pypdf, True)):
        changed = f"{extra}\n{text}" if first else f"{text}\n{extra}"
        result = verify_address(changed, case.project(), exact_line_under=exact)
        assert result == UNVERIFIABLE


# Edges SPEC doesn't settle, pinned as a skip with any reason (Joey, 24 Nov
# 2026). Loosening one is a behaviour change: its own test: commit and a
# docs/decisions.md entry.


@given(matching(), st.sampled_from([",", ".", ";", ":", "-"]))
def test_punctuation_right_after_the_lot_is_never_verified(case, mark):
    project = case.project(after_lot=mark)
    assert None not in both(project, case.plumber, case.pypdf)
    lot_line = f"Job Address: Lot {case.lot}"
    plumber = case.plumber.replace(lot_line, lot_line + mark)
    pypdf = case.pypdf.replace(lot_line, lot_line + mark)
    assert None not in both(case.project(), plumber, pypdf)


@given(lots, houses, streets(), TAILS)
def test_a_house_number_on_the_pdfs_label_line_is_never_verified(
    lot, house, street, tail
):
    rest = f"(#{house}) {' '.join(street.shown)}{tail}"
    plumber, pypdf = pdf_texts("9000001A", lot, None, rest, "label_line")
    project = f"Lot {lot} (#{house}) {' '.join(street.shown)}"
    assert None not in both(project, plumber, pypdf)


# A12, A13: any input


@given(st.text(), st.text(), st.booleans())
def test_any_input_gives_one_of_three_results(pdf_text, project, exact):
    assert verify_address(pdf_text, project, exact_line_under=exact) in (
        None,
        MISMATCH,
        UNVERIFIABLE,
    )


EDITS = st.lists(
    st.tuples(st.integers(0, 10**4), st.sampled_from(["", "x", " ", "\n", "9", "("])),
    min_size=1,
    max_size=4,
)


@given(matching(), EDITS, st.booleans())
def test_whenever_it_verifies_the_lot_and_r_are_in_the_text(case, edits, exact):
    """Safety: random edits to the PDF text ("" deletes a character), and
    whenever the check still passes, the text holds `lot <lot>` and R's
    words in a row."""
    text = case.pypdf if exact else case.plumber
    for at, insert in edits:
        at %= len(text) + 1
        text = text[:at] + insert + text[at + (0 if insert else 1) :]
    if verify_address(text, case.project(), exact_line_under=exact) is None:
        parsed = parse_project_address(case.project())
        assert parsed is not None
        flat = f" {normalise(text)} "
        assert f" lot {parsed.lot} " in flat
        assert f" {parsed.rest} " in flat
