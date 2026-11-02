# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Tests for the attachment download in mysys/driver.py (task 3.2).

Headless Chromium on a local fake of the test site's Note window, offline: no
site is touched. The fake follows docs/screen-map.md rows 02 and 05: each
"Download document" link carries the file name only in its URL's
`file_name`, and one click can fire the download twice. The fake's links
make their download in page JS (a Blob), so nothing leaves the test. The
browser writes downloads to a per-test folder, as the run's
`po-agent-dl-<run_id>` (D2). Values are fake. Tests never act on the page
themselves (guard_check.py).
"""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import Page, sync_playwright

from po_agent.core import runlog
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

NOTE_ID = "300001"
FILE = "2600001B_048_1.pdf"
FIRST = "%PDF-1.4 fake first"
SECOND = "%PDF-1.4 fake second"
CLOSE = '<div><span title="Close">close</span></div>'


@pytest.fixture
def downloads(tmp_path) -> Path:
    folder = tmp_path / "po-agent-dl-20261102T010203Z-abcd"
    folder.mkdir()
    return folder


@pytest.fixture
def page(downloads, monkeypatch) -> Iterator[Page]:
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(downloads_path=downloads)
        page = browser.new_context(accept_downloads=True).new_page()
        page.set_default_timeout(2000)
        yield page
        browser.close()


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


def note_page(*links: str | None, linked: bool = True) -> str:
    """The Note window with one "Download document" link per entry of
    `links` (its file_name, None for none). A click downloads two files at
    once, as the site can (row 05)."""
    rows = "".join(
        f'<div><span>{name or "file"}</span><a aria-label="Download document" href="'
        "https://testsite.invalid/index.php?task=get_note_file_content&amp;download=1"
        f"&amp;user_note_id=9{'' if name is None else '&amp;file_name=' + quote(name)}"
        f'" onclick="event.preventDefault(); save({(name or "file")!r}, {FIRST!r});'
        f' save({(name or "file")!r}, {SECOND!r})"><i class="fa fa-download">v</i></a></div>'
        for name in links
    )
    return f"""
<div><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div role="group" aria-label="Status buttons"><button disabled>Pending</button><button>Solved</button></div>
  {"<button>Link to Project</button>" if linked else ""}
  {rows}
</div>{CLOSE}</div>
<script>
function save(name, text) {{
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], {{type: 'application/pdf'}}));
  a.download = name;
  document.body.appendChild(a);
  a.click();
}}
</script>"""


def files(folder: Path) -> list[Path]:
    return [path for path in folder.rglob("*") if path.is_file()]


@pytest.mark.parametrize(
    "links, downloaded",
    [
        ((FILE,), FILE),
        (("2600001B_048_1.PDF",), "2600001B_048_1.PDF"),
        ((), None),
        ((FILE, "2600001B_048_2.pdf"), None),
        (("2600001B_048_1.docx",), None),
        ((None,), None),
    ],
    ids=["one-pdf", "upper-case-PDF", "none", "two", "not-a-pdf", "no-file_name"],
)
def test_clicks_only_when_there_is_exactly_one_pdf_link(
    page, guard, downloads, links, downloaded
):
    page.set_content(note_page(*links))
    window = driver.note_window(page, NOTE_ID)

    with driver.note_downloads(page, downloads):
        pdf = driver.download_pdf(guard, page, window)

    if downloaded is None:
        assert pdf is None
        assert guard.history == []  # counted before any click
    else:
        assert pdf == driver.Pdf(file_name=downloaded, data=FIRST.encode())
        assert [action for action, _ in guard.history] == ["download_attachment"]
    assert files(downloads) == []


def test_download_folder_empty_after_an_exception_mid_note(page, guard, downloads):
    # Downloaded (twice), then a later step finds a screen it doesn't know
    # (neither Link to Project nor a project button) and stops the Note.
    page.set_content(note_page(FILE, linked=False))
    window = driver.note_window(page, NOTE_ID)
    log = runlog.RunLog("20261102T010203Z-abcd", guard, directory=None)

    with pytest.raises(UnexpectedScreen):
        with driver.note_downloads(page, downloads):
            assert driver.download_pdf(guard, page, window) is not None
            driver.is_unlinked(window, log, NOTE_ID)

    assert files(downloads) == []
