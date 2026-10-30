"""Section 4, verify not extract: Claude extracts the site address, this code
verifies it (docs/specs/spec.md section 4; SPEC.md -> MySys screen rules ->
Project address).

Pure functions. Address text is untrusted page and PDF data: it never goes
into a return value other than these comparisons, or into run output.
"""

import re
from typing import NamedTuple

from po_agent.b1.models import Reading, SkipReason

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
# Lot <lot> [(#<house no>)] <street> <suburb> [<postcode>] [<state>]
_PROJECT = re.compile(
    r"\s*lot\s+([0-9a-z]+)\s*(?:\(\s*#[^)]*\))?(.*)", re.IGNORECASE | re.DOTALL
)
_JOB_ADDRESS = re.compile(r"Job Address\s*:", re.IGNORECASE)


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
    (no leading Lot, no lot, or nothing after the lot)."""
    match = _PROJECT.fullmatch(address)
    if match is None:
        return None
    rest = normalise(match.group(2)).split()
    if rest and rest[-1] in _STATES:
        rest.pop()
    if rest and _POSTCODE.fullmatch(rest[-1]):
        rest.pop()
    if not rest:
        return None
    return ProjectAddress(lot=match.group(1).casefold(), rest=" ".join(rest))


def _block_lines(pdf_text: str) -> tuple[str, str] | None:
    """The text after the one "Job Address:" label on its line, and the line
    under it ("" when there is none); None when the label is missing or
    appears more than once."""
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


def verify_address(
    claude: Reading, pdf_text: str, project_address: str
) -> SkipReason | None:
    """Step 9: None when Claude's lot, street and suburb pass, else the skip.

    First the PDF's Job Address block (decisions, 30 Oct 2026): the label
    line must start "Lot <lot>". If more follows on it, that rest must be
    exactly "<street> <suburb>" plus an optional tail (state, postcode, or
    both in either order); if nothing follows, the line under it must end
    with "<street> <suburb>" and an optional tail. Else ADDRESS_UNVERIFIABLE.
    Then the lot must equal the project's and street + suburb must equal R,
    else ADDRESS_MISMATCH.
    """
    lot = _words(claude.site_lot)
    if lot[:1] == ["lot"]:
        lot = lot[1:]
    street, suburb = normalise(claude.site_street), normalise(claude.site_suburb)
    lines = _block_lines(pdf_text)
    if len(lot) != 1 or not street or not suburb or lines is None:
        return SkipReason.ADDRESS_UNVERIFIABLE
    label_line, under = (normalise(line).split() for line in lines)
    head = normalise(f"lot {lot[0]}").split()
    address = f"{street} {suburb}".split()
    rest = label_line[len(head) :]
    if label_line[: len(head)] != head:
        return SkipReason.ADDRESS_UNVERIFIABLE
    if rest:
        found = rest[: len(address)] == address and _is_tail(rest[len(address) :])
    else:
        found = _ends_with_address(under, address)
    if not found:
        return SkipReason.ADDRESS_UNVERIFIABLE
    project = parse_project_address(project_address)
    if project is None:
        return SkipReason.ADDRESS_UNVERIFIABLE
    if lot[0] != project.lot or " ".join(address) != project.rest:
        return SkipReason.ADDRESS_MISMATCH
    return None
