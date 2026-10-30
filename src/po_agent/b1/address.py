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


def job_address_block(pdf_text: str) -> str | None:
    """The text after the one "Job Address:" label on its line, plus the line
    under it; None when the label is missing or appears more than once."""
    if len(_JOB_ADDRESS.findall(pdf_text)) != 1:
        return None
    lines = pdf_text.splitlines()
    for index, line in enumerate(lines):
        match = _JOB_ADDRESS.search(line)
        if match is not None:
            return "\n".join([line[match.end() :], *lines[index + 1 : index + 2]])
    return None  # the label spans a line break


def _contains(words: list[str], value: str) -> bool:
    """value's words appear as a run of whole words in words."""
    wanted = value.split()
    size = len(wanted)
    return any(words[i : i + size] == wanted for i in range(len(words) - size + 1))


def verify_address(
    claude: Reading, pdf_text: str, project_address: str
) -> SkipReason | None:
    """Step 9: None when Claude's lot, street and suburb pass, else the skip.

    First each value must be in the PDF's Job Address block (the lot as
    "Lot <lot>"), else ADDRESS_UNVERIFIABLE; then the lot must equal the
    project's and street + suburb must equal R, else ADDRESS_MISMATCH.
    """
    lot = _words(claude.site_lot)
    if lot[:1] == ["lot"]:
        lot = lot[1:]
    street, suburb = normalise(claude.site_street), normalise(claude.site_suburb)
    block = job_address_block(pdf_text)
    if len(lot) != 1 or not street or not suburb or block is None:
        return SkipReason.ADDRESS_UNVERIFIABLE
    words = normalise(block).split()
    if not all(
        _contains(words, value)
        for value in (normalise(f"lot {lot[0]}"), street, suburb)
    ):
        return SkipReason.ADDRESS_UNVERIFIABLE
    project = parse_project_address(project_address)
    if project is None:
        return SkipReason.ADDRESS_UNVERIFIABLE
    if lot[0] != project.lot or f"{street} {suburb}" != project.rest:
        return SkipReason.ADDRESS_MISMATCH
    return None
