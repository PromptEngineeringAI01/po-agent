"""The demo's PDF checks on the real 2609017B trial PDF (laptop only).

`-m real_data`: reads private/pdfs/ in the main checkout, never in CI. It
asserts on booleans only, so no PDF text reaches the test output.
"""

from pathlib import Path

import pytest

from po_agent.b1 import reader_rules as rules

PDF = Path(r"C:\Users\JoeyWu\po-agent\private\pdfs\2609017B_048_1.pdf")


@pytest.mark.real_data
def test_the_real_2609017B_pdf_passes_the_demo_checks():
    if not PDF.is_file():
        pytest.skip("trial PDF not on this machine")
    text = rules.pdf_text(PDF.read_bytes())
    po = rules.po_from_file_name(PDF.name)
    assert (rules.check_pdf(text, po, "2609017B") == "2609017B/048") is True
