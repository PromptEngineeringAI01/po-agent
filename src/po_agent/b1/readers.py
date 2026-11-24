"""The two code readers as one value (decisions, 2 Nov 2026; task 8.3).

Pure functions, no browser code. `read()` turns the PDF bytes into one
`PdfTexts`: pdfplumber's text and pypdf's text, each "" when its library
reads none, plus the bytes. This module owns the two-readers rule: the
per-field agreement (issuer, COMPACTION, PO number, Job Address label line)
and the address check on both texts, exact under the label on pypdf's.
"""

from pydantic import BaseModel, ConfigDict, Field

from po_agent.b1 import reader_rules as rules
from po_agent.b1.address import job_address_line, normalise, verify_address
from po_agent.core.models import Skip, SkipReason


class PdfTexts(BaseModel):
    """One PDF as both readers read it. Keywords only, so the two texts
    can't be swapped by position; PDF text is untrusted and never shown."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plumber: str = Field(repr=False)  # pdfplumber's text layer
    pypdf: str = Field(repr=False)  # pypdf's text layer
    data: bytes = Field(repr=False)


def read(data: bytes) -> PdfTexts:
    """Both readers' text of the PDF bytes, "" where a library reads none."""
    return PdfTexts(
        plumber=rules.text_layer(data), pypdf=rules.pypdf_text_layer(data), data=data
    )


def _label_line(text: str) -> str | None:
    line = job_address_line(text)
    return None if line is None else normalise(line)


def check_address(texts: PdfTexts, project_address: str) -> SkipReason | None:
    """Step 9 on both texts: verify_address's result, or READERS_DISAGREE
    when the texts give different results. pypdf reads the Supplier column
    apart, so its line under the label must be exactly the address
    (review, 2.5)."""
    plumber = verify_address(texts.plumber, project_address)
    pypdf = verify_address(texts.pypdf, project_address, exact_line_under=True)
    if pypdf != plumber:
        return SkipReason.READERS_DISAGREE
    return plumber


def agreement(texts: PdfTexts, address: str | None = None) -> dict[str, bool]:
    """Per field: do both texts give the same thing (no values). With the
    project's address, also whether the address check agrees."""
    plumber = rules.read_pdf(texts.plumber, "", "")
    pypdf = rules.read_pdf(texts.pypdf, "", "")
    agree = {
        "issuer": pypdf.issuer == plumber.issuer,
        "compaction": pypdf.contains_compaction == plumber.contains_compaction,
        "po number": pypdf.po_number == plumber.po_number,
        "job address line": _label_line(texts.pypdf) == _label_line(texts.plumber),
    }
    if address is not None:
        agree["address check"] = (
            check_address(texts, address) is not SkipReason.READERS_DISAGREE
        )
    return agree


def check_second_reader(texts: PdfTexts) -> Skip | None:
    """The second code reader: pypdf's text must read as pdfplumber's. No
    pypdf text -> PDF_UNREADABLE. The issuer, COMPACTION, the PO number and
    the Job Address label line (normalised) must be equal, else
    READERS_DISAGREE. The line under the label is not compared: pypdf reads
    the Supplier column apart from it, and check_address runs on both texts
    instead."""
    if not texts.pypdf.strip():
        return Skip(reason=SkipReason.PDF_UNREADABLE)
    if not all(agreement(texts).values()):
        return Skip(reason=SkipReason.READERS_DISAGREE)
    return None
