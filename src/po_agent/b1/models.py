"""B1's decision-engine models (SPEC.md -> Code style: pydantic at every
boundary). The shared ones are in `core/models.py` (ADR-003 decision 2)."""

from typing import Self

from pydantic import Field, model_validator

from po_agent.core.models import Frozen, Proceed


class Reading(Frozen):
    """What a reader found in the PDF (section 3). Empty means not found.

    No reader extracts the address: the project's address in MySys gives the
    values the PDF is checked against (decisions, 2 Nov 2026).
    """

    issuer: str = ""
    contains_compaction: bool
    po_number: str = ""
    client_internal_no: str = ""


class DeterministicReading(Reading):
    """The deterministic reading also carries the file name's and, on live,
    the title's PO number (section 3)."""

    po_from_filename: str = ""
    po_from_title: str | None = None  # live title rule only


class B1Proceed(Proceed):
    """B1's step 11: the shared `Proceed` with B1's /048 PO and file name
    checked again, so a malformed B1 decision can't reach a write."""

    internal_no: str = Field(pattern=r"^[0-9A-Z]+$")
    po_number: str = Field(pattern=r"^[0-9A-Z]+/048$")
    pdf_file_name: str = Field(pattern=r"^[0-9A-Z]+_048(_[0-9]+)?\.(?i:pdf)$")

    @model_validator(mode="after")
    def _po_is_this_internal_numbers(self) -> Self:
        if self.po_number != f"{self.internal_no}/048":
            raise ValueError("po_number is not this internal number's /048 PO")
        return self
