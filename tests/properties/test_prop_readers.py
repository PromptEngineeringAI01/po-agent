"""Properties of the readers (b1/reader_rules.py, b1/readers.py; SPEC -> In
the MVP -> section 7, second reader; MySys screen rules -> Attachment).

Known and accepted (decisions, 9 Nov 2026): the PDF's PO number has no right
anchor, so `X/0481` reads as `X/048`; a B1 PDF never shows anything after
`/048`, so no generator here writes one.
"""

import string
from urllib.parse import urlencode

import pytest
from b1_worlds import ISSUER, any_internal_nos, internal_nos, proceed_worlds
from hypothesis import assume, given
from hypothesis import strategies as st

from po_agent.b1 import reader_rules as rules
from po_agent.b1.readers import PdfTexts, check_address, check_second_reader
from po_agent.core.errors import WriteNotStarted
from po_agent.core.models import SkipReason

PO_SHAPE = st.from_regex(r"[0-9A-Z]{1,10}/[0-9]{3}", fullmatch=True)
# File names as URLs carry them: anything printable, no surrogates.
NAMES = st.text(st.characters(exclude_categories=["Cs"]), min_size=1, max_size=30)


def po_line(po: str) -> str:
    return f"Purchase Order No {po}"


# B1: read_pdf on any text


@given(st.text(), st.text(), st.text())
def test_read_pdf_reads_any_text_without_raising(text, file_name, title):
    reading = rules.read_pdf(text, file_name, title)
    assert reading.po_number == "" or reading.po_number in text
    # The internal number is the PO's part before the slash (SPEC section 3).
    assert (reading.client_internal_no == "") == (reading.po_number == "")
    if reading.po_number:
        assert reading.po_number.startswith(reading.client_internal_no + "/")


# B2: exactly one PO number


@given(
    st.lists(st.text(string.ascii_letters + " \n", max_size=20), max_size=3), PO_SHAPE
)
def test_one_po_number_is_read_wherever_it_sits(noise, po):
    text = "\n".join([*noise, po_line(po), *noise])
    assert rules.read_pdf(text, "", "").po_number == po


@given(PO_SHAPE, PO_SHAPE)
def test_two_different_po_numbers_read_as_none(first, second):
    assume(first != second)
    text = f"{po_line(first)}\n{po_line(second)}"
    assert rules.read_pdf(text, "", "").po_number == ""


# B3: the file name's PO number


@given(
    any_internal_nos,
    st.sampled_from(["", "_1", "_12"]),
    st.sampled_from(["pdf", "PDF", "Pdf"]),
)
def test_the_file_names_po_number_round_trips(internal_no, copy, ext):
    """<internal no>_048[_n].pdf, any case of pdf (open question 10)."""
    name = f"{internal_no}_048{copy}.{ext}"
    assert rules.po_from_file_name(name) == f"{internal_no}/048"
    assert rules.read_pdf("", name, "").po_from_filename == f"{internal_no}/048"


@given(
    internal_nos,
    st.sampled_from(
        [
            "{x}_049.pdf",
            "{x}_048.pdf.exe",
            "copy of {x}_048.pdf",
            "{x}_048_.pdf",
            "{x}-048.pdf",
            "{l}_048.pdf",
            "{x}_048.docx",
        ]
    ),
)
def test_a_file_name_off_the_shape_has_no_po_number(internal_no, shape):
    name = shape.format(x=internal_no, l=internal_no.lower())
    assert rules.read_pdf("", name, "").po_from_filename == ""
    with pytest.raises(WriteNotStarted):
        rules.po_from_file_name(name)


# B4: the issuer


@given(
    st.lists(st.sampled_from(["", " ", "\t", "   "]), max_size=3), st.text(max_size=40)
)
def test_the_issuer_is_the_first_non_empty_line(blank_lines, rest):
    text = "\n".join([*blank_lines, f"  {ISSUER}  ", rest])
    assert rules.read_pdf(text, "", "").issuer == ISSUER


# B5: the one "Download document" link


@given(NAMES.map(lambda name: name + ".pdf") | NAMES.map(lambda name: name + ".PDF"))
def test_the_attachments_file_name_round_trips_through_its_url(name):
    href = "https://mysys.example/download?" + urlencode(
        {"user_note_id": "1", "file_name": name}
    )
    assert rules.pdf_file_name([href]) == name


@given(st.lists(NAMES, min_size=2, max_size=4))
def test_more_than_one_link_is_multiple_pdfs(names):
    hrefs = [
        "https://mysys.example/d?" + urlencode({"file_name": n + ".pdf"}) for n in names
    ]
    with pytest.raises(WriteNotStarted) as raised:
        rules.pdf_file_name(hrefs)
    assert raised.value.reason == "MULTIPLE_PDFS"


@given(NAMES.filter(lambda name: not name.lower().endswith(".pdf")))
def test_a_link_to_another_file_type_is_no_pdf(name):
    href = "https://mysys.example/d?" + urlencode({"file_name": name})
    for hrefs in ([href], []):
        with pytest.raises(WriteNotStarted) as raised:
            rules.pdf_file_name(hrefs)
        assert raised.value.reason == "NO_PDF"


# B6: the address check on both texts


@given(proceed_worlds())
def test_the_supplier_column_before_r_fails_pypdfs_exact_rule(world):
    """review, 2.5: pypdf reads the Supplier column apart, so on its text the
    line under a lone lot must be exactly R and a tail. pdfplumber's shared
    line, given as pypdf's text too, never passes: READERS_DISAGREE."""
    assume(world.layout != "label_line")
    texts = PdfTexts(plumber=world.plumber, pypdf=world.plumber, data=world.data)
    assert check_address(texts, world.address) is SkipReason.READERS_DISAGREE


# B7: the second reader


@given(proceed_worlds())
def test_the_same_text_from_both_readers_always_agrees(world):
    for text in (world.plumber, world.pypdf):
        texts = PdfTexts(plumber=text, pypdf=text, data=world.data)
        assert check_second_reader(texts) is None
