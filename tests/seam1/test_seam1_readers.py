"""Seam 1, the two code readers as one value (task 8.3; decisions, 2 Nov 2026).

`readers.read()` turns the PDF bytes into one `PdfTexts`: pdfplumber's text,
pypdf's text (each "" when its library reads none) and the bytes. The value
takes keywords only, so the two texts can't be swapped by position, and its
repr shows no PDF text. `readers.agreement()` is the per-field agreement the
second reader and the real-PO seam both use.
"""

import pytest
from po_agent.b1.readers import PdfTexts
from seam1_cases import pdf_bytes, text_pdf

from po_agent.b1 import reader_rules as rules
from po_agent.b1 import readers

LINES = [
    "B1 Homes Pty Ltd",
    "Purchase Order No 2600001B/048",
    "Job Address: Lot 123",
    "Sample Lane Sampleville WA",
    "Order Type: COMPACTION TEST",
]
FIELDS = ["issuer", "compaction", "po number", "job address line"]


def test_read_gives_both_texts_and_the_bytes() -> None:
    data = text_pdf(LINES)
    assert readers.read(data) == PdfTexts(
        plumber=rules.text_layer(data), pypdf=rules.pypdf_text_layer(data), data=data
    )


@pytest.mark.parametrize("kind", ["corrupt", "image-only"])
def test_a_pdf_neither_library_reads_gives_empty_texts(kind: str) -> None:
    texts = readers.read(pdf_bytes(kind))
    assert (texts.plumber.strip(), texts.pypdf.strip()) == ("", "")


def test_the_texts_take_keywords_only_and_show_no_pdf_text() -> None:
    with pytest.raises(TypeError):
        PdfTexts("plumber text", "pypdf text", b"%PDF")  # type: ignore[misc]
    texts = PdfTexts(plumber="Lot 123 plumber", pypdf="Lot 123 pypdf", data=b"%PDF")
    assert "Lot 123" not in f"{texts!r} {texts!s}"


def test_agreement_is_per_field() -> None:
    text = "\n".join(LINES)
    same = PdfTexts(plumber=text, pypdf=text, data=b"")
    assert readers.agreement(same) == dict.fromkeys(FIELDS, True)
    other = PdfTexts(plumber=text, pypdf=text.replace("/048", "/049"), data=b"")
    assert readers.agreement(other) == {
        **dict.fromkeys(FIELDS, True),
        "po number": False,
    }


def test_agreement_with_an_address_adds_the_address_check() -> None:
    plumber = "\n".join(LINES)
    pypdf = plumber.replace("Sample Lane", "North Sample Lane")
    texts = PdfTexts(plumber=plumber, pypdf=pypdf, data=b"")
    address = "Lot 123 (#45) Sample Lane Sampleville 6000 WA"
    # pypdf's line under the label must be exactly the address.
    assert readers.agreement(texts, address) == {
        **dict.fromkeys(FIELDS, True),
        "address check": False,
    }
