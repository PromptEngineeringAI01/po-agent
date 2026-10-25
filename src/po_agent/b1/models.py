"""Decision-engine models (SPEC.md -> Code style: pydantic at every boundary)."""

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class NotePoolRow(BaseModel):
    """One Note Pool list row as read from the page, cells as shown.

    Cell text is untrusted page data: it never goes to run output.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    note_id: StrictStr = Field(min_length=1)  # the row's ID cell (row 05)
    subject_note: StrictStr  # title and body joined (row 01)
    project: StrictStr  # "---" when not linked
    assignee: StrictStr
