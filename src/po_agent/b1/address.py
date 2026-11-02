"""Section 4, the address check: the project's address in MySys gives the lot
and street-and-suburb, and the PDF's Job Address block must hold them
(docs/specs/spec.md section 4; SPEC.md -> MySys screen rules -> Project
address; decisions, 2 Nov 2026).

Pure functions. Address text is untrusted page and PDF data: it never goes
into a return value other than these comparisons, or into run output.
"""

import re
from typing import NamedTuple

from po_agent.b1.models import SkipReason

# Section 4's street-type abbreviations, mapped to one form. Only these, until
# the real-PO seam shows a need for more (approved 2.4).
_STREET_TYPES = {
    "st": "street",
    "rd": "road",
    "ave": "avenue",
    "dr": "drive",
    "cres": "crescent",
    "ct": "court",
    "pl": "place",
    "bvd": "boulevard",
    "pde": "parade",
    "tce": "terrace",
    "cl": "close",
    "hwy": "highway",
    "ln": "lane",
}
_STATES = {"wa", "nsw", "vic", "qld", "sa", "tas", "nt", "act"}
_POSTCODE = re.compile(r"[0-9]{4}")
_NOT_WORD = re.compile(r"[^0-9a-z]+")
# Lot <lot> [(#<house no>)] <street> <suburb> [<postcode>] [<state>]; the lot
# is one word of letters and digits ("12-A" or "12/13" doesn't parse).
_PROJECT = re.compile(
    r"\s*lot\s+([0-9a-z]+)(?=\s|\(|$)\s*(?:\(\s*#[^)]*\))?(.*)",
    re.IGNORECASE | re.DOTALL,
)
# The label line's start: Lot <lot>, the lot one word of letters and digits.
_BLOCK_LOT = re.compile(r"\s*lot\s+([0-9a-z]+)(?=\s|$)(.*)", re.IGNORECASE)
_JOB_ADDRESS = re.compile(r"Job Address\s*:", re.IGNORECASE)
# Any spelling of the label ("Job  Address", "JobAddress", "Job Address -"),
# on case-folded text: a second one, however written, is never missed.
_ANY_LABEL = re.compile(r"job[^0-9a-z]*address")
# R must hold at least a street and a suburb (review, 2.5).
_MIN_REST_WORDS = 2


class ProjectAddress(NamedTuple):
    lot: str  # case-folded
    rest: str  # the street-and-suburb text R, normalised


def _words(text: str) -> list[str]:
    """Case-folded words; punctuation and whitespace are separators."""
    return _NOT_WORD.sub(" ", text.casefold()).split()


def normalise(text: str) -> str:
    """Case-fold, collapse whitespace and punctuation, map street types."""
    return " ".join(_STREET_TYPES.get(word, word) for word in _words(text))


def parse_project_address(address: str) -> ProjectAddress | None:
    """The project's lot and R, or None when the string lacks its shape
    (no leading Lot, no lot, or fewer than two words after the lot)."""
    match = _PROJECT.fullmatch(address)
    if match is None:
        return None
    rest = normalise(match.group(2)).split()
    if rest and rest[-1] in _STATES:
        rest.pop()
    if rest and _POSTCODE.fullmatch(rest[-1]):
        rest.pop()
    if len(rest) < _MIN_REST_WORDS:
        return None
    return ProjectAddress(lot=match.group(1).casefold(), rest=" ".join(rest))


def _block_lines(pdf_text: str) -> tuple[str, str] | None:
    """The text after the one "Job Address:" label on its line, and the line
    under it ("" when there is none); None when the label is missing or
    appears more than once, in any spelling."""
    if len(_ANY_LABEL.findall(pdf_text.casefold())) != 1:
        return None
    if len(_JOB_ADDRESS.findall(pdf_text)) != 1:
        return None
    lines = pdf_text.splitlines()
    for index, line in enumerate(lines):
        match = _JOB_ADDRESS.search(line)
        if match is not None:
            under = lines[index + 1] if index + 1 < len(lines) else ""
            return line[match.end() :], under
    return None  # the label spans a line break


def job_address_block(pdf_text: str) -> str | None:
    """The Job Address block: the label line's rest plus the line under it."""
    lines = _block_lines(pdf_text)
    return None if lines is None else "\n".join(part for part in lines if part)


def _ends_with_address(words: list[str], address: list[str]) -> bool:
    """words end with the address, then nothing, a state, a postcode, or a
    state and a postcode in either order."""
    for size in range(3):
        head, tail = words[: len(words) - size], words[len(words) - size :]
        if head[-len(address) :] == address and _is_tail(tail):
            return True
    return False


def _is_tail(words: list[str]) -> bool:
    states = [word in _STATES for word in words]
    postcodes = [bool(_POSTCODE.fullmatch(word)) for word in words]
    return (
        sum(states) <= 1
        and sum(postcodes) <= 1
        and all(
            state or postcode for state, postcode in zip(states, postcodes, strict=True)
        )
    )


def _is_address(words: list[str], address: list[str]) -> bool:
    """words are exactly the address, then nothing or a tail."""
    return words[: len(address)] == address and _is_tail(words[len(address) :])


def _non_ascii_letter(*texts: str) -> bool:
    """A letter normalise() would turn into a word break (review, 2.5)."""
    return any(char.isalpha() and not char.isascii() for text in texts for char in text)


def job_address_line(pdf_text: str) -> str | None:
    """The text after the one "Job Address:" label on its line; None when
    there isn't exactly one label on one line. The readers must agree on it."""
    lines = _block_lines(pdf_text)
    return None if lines is None else lines[0]


def verify_address(
    pdf_text: str, project_address: str, *, exact_line_under: bool = False
) -> SkipReason | None:
    """Step 9: None when the PDF's Job Address block holds the project's lot
    and R, else the skip (decisions, 30 Oct and 2 Nov 2026).

    The label line must start "Lot <lot>", the lot one word of letters and
    digits, equal to the project's. If more follows on it, that rest must be
    exactly R plus an optional tail (state, postcode, or both in either
    order); if nothing follows, the line under it must end with R and an
    optional tail. With exact_line_under (pypdf's text, which reads the
    Supplier column apart), that line must be exactly R and a tail.

    ADDRESS_UNVERIFIABLE when something can't be parsed: the project address
    (R of at least two words), no single label in any spelling, a label line
    not starting "Lot <lot>", a lone lot with nothing under it, or a non-ASCII
    letter in the project address or the block. ADDRESS_MISMATCH when both
    parse and the lot or R is not where the rule needs it.
    """
    project = parse_project_address(project_address)
    lines = _block_lines(pdf_text)
    if project is None or lines is None:
        return SkipReason.ADDRESS_UNVERIFIABLE
    label_line, under = lines
    match = _BLOCK_LOT.fullmatch(label_line)
    if match is None or _non_ascii_letter(project_address, label_line, under):
        return SkipReason.ADDRESS_UNVERIFIABLE
    rest, under_words = normalise(match.group(2)).split(), normalise(under).split()
    if not rest and not under_words:
        return SkipReason.ADDRESS_UNVERIFIABLE
    address = project.rest.split()
    if rest:
        found = _is_address(rest, address)
    elif exact_line_under:
        found = _is_address(under_words, address)
    else:
        found = _ends_with_address(under_words, address)
    if match.group(1).casefold() != project.lot or not found:
        return SkipReason.ADDRESS_MISMATCH
    return None
