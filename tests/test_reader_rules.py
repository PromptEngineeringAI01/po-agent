"""Tests for b1/reader_rules.py: the demo's deterministic checks (27 Oct 2026).

Pure functions on fake values: no browser, no real PDF. The real-PDF check
is in tests/seam1/test_real_pdf.py (real_data, laptop only).
"""

import pytest

from po_agent.b1 import reader_rules as rules
from po_agent.core.errors import PartialWrite, WriteNotStarted

LINK = (
    "index.php?option=com_cweb&controller=user_note&task=get_note_file_content"
    "&download=1&user_note_id=95&file_name={}"
)
# Fake PDF text in the shape of a B1 Homes PO (values fake).
PDF_TEXT = """B1 Homes Pty Ltd
Order Printed: 02 Oct 2026
Purchase Order No 2600001B/048
Supply: COMPACTION TEST Att: <person> Client:<client>
COMPACTION CERTIFICATE 1 each $85.00* $85.00"""


def reason(error: pytest.ExceptionInfo) -> str:
    return error.value.reason


# Attachment rule (SPEC.md -> Attachment and download)


def test_one_pdf_link_gives_its_file_name():
    assert rules.pdf_file_name([LINK.format("2600001B_048_1.pdf")]) == (
        "2600001B_048_1.pdf"
    )


def test_file_name_is_url_decoded_and_pdf_matches_any_case():
    assert rules.pdf_file_name([LINK.format("2600001B%5F048_1.PDF")]) == (
        "2600001B_048_1.PDF"
    )


@pytest.mark.parametrize(
    ("hrefs", "why"),
    [
        ([], "NO_PDF"),
        ([LINK.format("2600001B_048_1.docx")], "NO_PDF"),
        (["index.php?option=com_cweb&download=1"], "NO_PDF"),
        ([LINK.format("a.pdf"), LINK.format("b.pdf")], "MULTIPLE_PDFS"),
    ],
)
def test_anything_but_one_pdf_link_stops(hrefs, why):
    with pytest.raises(WriteNotStarted) as error:
        rules.pdf_file_name(hrefs)
    assert reason(error) == why


def test_po_number_comes_from_the_file_name():
    assert rules.po_from_file_name("2600001B_048_1.pdf") == "2600001B/048"
    assert rules.po_from_file_name("2600001B_048.PDF") == "2600001B/048"


@pytest.mark.parametrize("name", ["2600001B_049_1.pdf", "notes.pdf", "x_048_1.pdf"])
def test_a_file_name_not_shaped_like_a_po_stops(name):
    with pytest.raises(WriteNotStarted) as error:
        rules.po_from_file_name(name)
    assert reason(error) == "NO_PDF"


# PDF checks (step 4)


def test_pdf_that_matches_gives_its_po_number():
    assert rules.check_pdf(PDF_TEXT, "2600001B/048", "2600001B") == "2600001B/048"


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (PDF_TEXT.replace("B1 Homes", "Other Homes"), "NOT_B1"),
        ("Other Homes Pty Ltd\n" + PDF_TEXT, "NOT_B1"),  # issuer = first line
        (PDF_TEXT.replace("COMPACTION", "SURVEY"), "NOT_COMPACTION"),
        (PDF_TEXT.replace("2600001B/048", "2600002B/048"), "PO_MISMATCH"),
        (PDF_TEXT.replace("Purchase Order No", "Order"), "PO_MISMATCH"),
        (PDF_TEXT + "\nPurchase Order No 2600002B/048", "PO_MISMATCH"),
    ],
)
def test_pdf_that_does_not_match_stops(text, why):
    with pytest.raises(WriteNotStarted) as error:
        rules.check_pdf(text, "2600001B/048", "2600001B")
    assert reason(error) == why


def test_internal_number_must_equal_the_note_title():
    with pytest.raises(WriteNotStarted) as error:
        rules.check_pdf(PDF_TEXT, "2600001B/048", "2600009B")
    assert reason(error) == "PO_MISMATCH"


def test_unreadable_pdf_bytes_stop():
    with pytest.raises(WriteNotStarted) as error:
        rules.pdf_text(b"not a pdf")
    assert reason(error) == "PDF_UNREADABLE"


# Project search (step 5)

HEADERS = ["Project No.", "Title", "Client Ref No.", "Date In", "Address", "Company"]


def project(pln: str, ref: str, company: str = "B1 Homes") -> dict[str, str]:
    return dict(
        zip(HEADERS, [pln, "", ref, "12 Oct 2026", "<address>", company], strict=True)
    )


def test_exactly_one_b1_row_with_the_client_ref_gives_its_pln():
    rows = [project("pln_10001", "2600001B"), project("pln_10002", "2600001BX")]
    assert rules.match_project(rows, "2600001B") == "pln_10001"


def test_client_ref_may_carry_the_048_suffix_and_any_case():
    rows = [project("pln_10001", " 2600001b/048 ")]
    assert rules.match_project(rows, "2600001B") == "pln_10001"


@pytest.mark.parametrize(
    ("rows", "why"),
    [
        ([], "PROJECT_NOT_FOUND"),
        ([project("pln_10001", "2600001B", "Other Homes")], "PROJECT_NOT_FOUND"),
        (
            [project("pln_10001", "2600001B"), project("pln_10002", "2600001B")],
            "PROJECT_AMBIGUOUS",
        ),
    ],
)
def test_no_or_two_matching_projects_stop(rows, why):
    with pytest.raises(WriteNotStarted) as error:
        rules.match_project(rows, "2600001B")
    assert reason(error) == why


def test_client_internal_no_follows_the_same_rule():
    assert rules.same_internal_no("2600001b/048", "2600001B")
    assert not rules.same_internal_no("2600001BX", "2600001B")


# Task rows (rows 07, 10, 12): each task is a header row, then a details row.

TASK_ROWS = [
    ["(tsk_200001) | Compaction Test\nUndo Cancellation"],
    ["Agent 1 (MySys Only)", "Perth Scheduling", "16 Oct 2026", "Cancelled"],
    [""],
    ["(tsk_200002) | Soil Classification\nCancel\nHold"],
    ["<user>", "<user>", "16 Oct 2026", "New Project"],
    ["(tsk_200003) | Compaction Test\nCancel\nUn-Hold"],
    ["Agent 1 (MySys Only)", "Perth Scheduling", "16 Oct 2026", "On-hold\nNotes:"],
]


def test_compaction_tasks_are_read_with_their_status():
    assert rules.compaction_tasks(TASK_ROWS) == {
        "tsk_200001": "Cancelled",
        "tsk_200003": "On-hold\nNotes:",
    }


def test_a_header_row_without_a_details_row_is_unexpected():
    with pytest.raises(PartialWrite):
        rules.compaction_tasks([["(tsk_200001) | Compaction Test\nCancel\nHold"]])


def test_live_tasks_leave_out_cancelled_ones():
    assert rules.live_tasks(rules.compaction_tasks(TASK_ROWS)) == ["tsk_200003"]


def test_new_task_is_the_one_id_not_seen_before():
    after = {"tsk_200001": "Cancelled", "tsk_200004": "New Project"}
    assert rules.new_task({"tsk_200001"}, after) == "tsk_200004"


@pytest.mark.parametrize(
    "after",
    [
        {"tsk_200001": "Cancelled"},
        {"tsk_200001": "x", "tsk_200004": "New Project", "tsk_200005": "New Project"},
    ],
)
def test_no_new_task_or_two_is_a_partial_write(after):
    with pytest.raises(PartialWrite):
        rules.new_task({"tsk_200001"}, after)


def test_a_duplicated_row_counts_as_one_project():
    rows = [project("pln_10001", "2600001B"), project("pln_10001", "2600001B")]
    assert rules.match_project(rows, "2600001B") == "pln_10001"
