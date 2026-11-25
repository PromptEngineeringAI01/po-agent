"""Summit's own models (task 9.9; SPEC.md -> Client 2: Summit Home)."""

from typing import Self

from pydantic import Field, model_validator

from po_agent.core.models import Proceed

# Three groups of digits joined by "/" (fake example 123456/020/01).
PO_PATTERN = r"^[0-9]+/[0-9]+/[0-9]+$"


class SummitProceed(Proceed):
    """Summit's step 11: the shared `Proceed` with Summit's PO checked again,
    the Note's original assignee (the take's recheck and the return, 9.13)
    and, for a previous-task row, the previous task's number and Task
    Creator (W1's recheck, 9.14), so a malformed decision can't reach a
    write."""

    internal_no: str = Field(pattern=r"^[0-9]+$")  # the Client Ref No.
    po_number: str = Field(pattern=PO_PATTERN)
    pdf_file_name: str = Field(pattern=r"^.+\.(?i:pdf)$")
    original_assignee: str = Field(min_length=1)
    previous_task_no: str | None = Field(None, pattern=r"^tsk_[0-9]+$")
    previous_task_creator: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.po_number.split("/")[0] != self.internal_no:
            raise ValueError("internal_no is not the PO before its first /")
        if not self.original_assignee.strip():
            raise ValueError("blank original assignee")
        if self.creator.strip() in ("", "---"):
            raise ValueError("creator names nobody")
        if (self.previous_task_no is None) != (self.previous_task_creator is None):
            raise ValueError("previous task number and creator go together")
        if self.previous_task_creator not in (None, self.creator):
            raise ValueError("creator is not the previous task's Task Creator")
        return self
