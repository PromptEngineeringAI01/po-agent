"""Shared Hypothesis generators for B1's property tests (tests/README.md).

Fake values only (CLAUDE.md Must never #6): internal numbers start with 9
(the trial and real B1 numbers start 26), words are random letters, plns and
task numbers are 9-prefixed, the supplier and builder lines are the seam-1
fakes' shapes.

`proceed_worlds()` is the targeted generator: random input almost never
passes every check, so it builds one consistent world from SPEC's rules (the
Note, both readers' text in the layouts SPEC -> Project address describes,
and the MySys lookup). `MUTATIONS` lists single faults, each with the skip
reason SPEC gives it and whether it stops before the project lookup.
`outcome()` runs `decide()` of any module set (the current code or
tests/oracle) on a world, so the decision and differential tests share it.
"""

import dataclasses
import string
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import NamedTuple

from hypothesis import strategies as st

COMPANY = "B1 Homes"  # SPEC -> Project search: Company B1 Homes
ISSUER = "B1 Homes Pty Ltd"  # the first line of every B1 PO (SPEC 2.2)
STATES = ("WA", "NSW", "VIC", "QLD", "SA", "TAS", "NT", "ACT")
# docs/specs/spec.md section 4's street types: (as written, normalised).
STREET_TYPES = (
    ("St", "street"),
    ("Street", "street"),
    ("Rd", "road"),
    ("Road", "road"),
    ("Ave", "avenue"),
    ("Avenue", "avenue"),
    ("Cres", "crescent"),
    ("Pde", "parade"),
    ("Ln", "lane"),
    ("Lane", "lane"),
    ("Way", "way"),
)
# The five tails SPEC allows after R: nothing, state, postcode, both orders.
TAILS = st.sampled_from(["", " WA", " 6000", " WA 6000", " 6000 WA"])

# A plain word: 5-9 letters, so never a state, a street-type abbreviation,
# "lot" or a postcode; never holding "job" or "address" (a second label).
words = st.from_regex(r"[A-Z][a-z]{4,8}", fullmatch=True).filter(
    lambda w: "job" not in w.lower() and "address" not in w.lower()
)
internal_nos = st.from_regex(r"9[0-9]{6}[A-Z]", fullmatch=True)
# Any shape the eligibility rule accepts: upper-case letters and digits.
any_internal_nos = st.text(string.digits + string.ascii_uppercase, min_size=1)
lots = st.from_regex(r"[1-9][0-9]{0,3}[A-Za-z]?", fullmatch=True)
houses = st.from_regex(r"[1-9][0-9]{0,2}[A-Za-z]?", fullmatch=True)
plns = st.integers(90000, 99999).map(lambda n: f"pln_{n}")
task_nos = st.integers(900000, 999999).map(lambda n: f"tsk_{n}")
note_ids = st.integers(1, 10**9).map(str)


class Street(NamedTuple):
    """R as the project writes it, and its words as SPEC normalises them."""

    shown: list[str]
    normalised: list[str]


@st.composite
def streets(draw: st.DrawFn) -> Street:
    """R: a street name, an optional street type, a suburb; at least two
    words (SPEC: R must hold a street and a suburb)."""
    name = draw(st.lists(words, min_size=1, max_size=2))
    kind = draw(st.none() | st.sampled_from(STREET_TYPES))
    suburb = draw(st.lists(words, min_size=1, max_size=2))
    shown = name + ([kind[0]] if kind else []) + suburb
    normalised = [w.lower() for w in name] + ([kind[1]] if kind else [])
    normalised += [w.lower() for w in suburb]
    return Street(shown, normalised)


@dataclass(frozen=True)
class World:
    """One Note, its PDF as both readers read it, and the MySys lookup."""

    internal_no: str
    note_id: str
    title: str
    body: str
    attachments: tuple[str, ...]
    linked: bool
    plumber: str
    pypdf: str
    data: bytes
    match_rows: tuple[tuple[str, str, str], ...]  # (pln, client ref, company)
    noise_rows: tuple[tuple[str, str, str], ...]
    order: tuple[int, ...]  # the rows' order on the page
    more_pages: bool
    project_internal_no: str
    project_prefix: str  # "Lot": the project address's leading word
    project_lot: str
    project_house: str | None
    project_rest: str  # R, maybe with a state inside, then postcode/state
    tasks: tuple[tuple[str, str], ...]  # (task no, status)
    site: str
    ignores_cancelled: bool
    # Fixed at generation (never mutated): what a PROCEED carries.
    pln: str
    pdf_lot: str
    layout: str

    @property
    def address(self) -> str:
        house = f" (#{self.project_house})" if self.project_house else ""
        return f"{self.project_prefix} {self.project_lot}{house} {self.project_rest}"

    @property
    def rows(self) -> tuple[tuple[str, str, str], ...]:
        rows = self.match_rows + self.noise_rows
        return (
            tuple(rows[i] for i in self.order if i < len(rows))
            + rows[len(self.order) :]
        )


def _spaces(draw: st.DrawFn, text: str) -> str:
    """The cell as MySys may show it: stray spaces around it."""
    return (
        draw(st.sampled_from(["", " ", "  "]))
        + text
        + draw(st.sampled_from(["", " ", "  "]))
    )


def _any_case(draw: st.DrawFn, text: str) -> str:
    return "".join(c.lower() if draw(st.booleans()) else c.upper() for c in text)


def pdf_texts(
    internal_no: str, lot: str, house: str | None, rest: str, layout: str
) -> tuple[str, str]:
    """pdfplumber's and pypdf's text of one fake B1 PO, after the seam-1
    fakes (tests/seam1/fixtures/cases.toml): pdfplumber's Job Address block
    shares its lines with the Supplier column, pypdf reads them apart."""
    head = (
        f"{ISSUER}\n1 Builder Way\nFakeville WA 6999 Page 1 of 1\n"
        "Order Date: 05 Jan 2026\nA.B.N 00 000 000 000\n"
        f"Purchase Order No {internal_no}/048\nDelivery Date:\n"
    )
    foot = (
        "Order Type: COMPACTION TEST Job: Sample Job Stage:Earthworks\n"
        "Ref Description Quantity Price @ Amount\n"
        "COMPACTION Compaction test 1 each $10.00* $10.00\nTotal $11.00\n"
    )
    supplier = "Supplier: Example Compaction Pty Ltd"
    unit = "Unit 1, 2 Supplier Road Supplierton WA"
    if layout == "label_line":
        plumber = f"{supplier} Job Address: Lot {lot} {rest}\n{unit}\n"
        pypdf = f"{supplier}\n{unit}\nJob Address: Lot {lot} {rest}\nSupervisor:\n"
    elif layout == "under":
        plumber = f"{supplier} Job Address: Lot {lot}\n{unit} {rest}\n"
        pypdf = f"{supplier}\n{unit}\nJob Address: Lot {lot}\n{rest}\nSupervisor:\n"
    else:  # house_line: the house number on its own line (decisions, 11 Nov)
        plumber = (
            f"{supplier} Job Address: Lot {lot}\n{unit} ({house})\n"
            f"Supplierton WA 6998 {rest}\n"
        )
        pypdf = (
            f"{supplier}\n{unit}\nJob Address: Lot {lot}\n({house})\n{rest}\n"
            "Supervisor:\n"
        )
    return head + plumber + foot, head + pypdf + foot


@st.composite
def proceed_worlds(draw: st.DrawFn) -> World:
    """A world every SPEC check passes: decide() must PROCEED on it."""
    x = draw(internal_nos)
    lot = draw(lots)
    layout = draw(st.sampled_from(["label_line", "under", "house_line"]))
    house = draw(houses) if layout == "house_line" else draw(st.none() | houses)
    street = draw(streets())
    pdf_rest = " ".join(street.shown) + draw(TAILS)
    # The project's own R: maybe a state after the street (decisions, 11
    # Nov 2026), street types spelt either way, then postcode and state.
    shown = list(street.shown)
    if draw(st.booleans()):
        shown.insert(len(shown) - 1, draw(st.sampled_from(STATES)))
    project_rest = " ".join(shown) + draw(
        st.sampled_from(["", " 6000", " 6000 WA", " WA"])
    )
    plumber, pypdf = pdf_texts(x, lot, house, pdf_rest, layout)
    suffix = draw(st.sampled_from(["", "_1", "_2"]))
    file_name = f"{x}_048{suffix}.{draw(st.sampled_from(['pdf', 'PDF']))}"
    title = draw(st.sampled_from(["", f"[B1 Homes] Order {x}/048"]))
    pln = draw(plns)
    copies = draw(st.integers(1, 3))  # the same row listed more than once
    match_rows = tuple(
        (pln, _spaces(draw, _any_case(draw, x)), _spaces(draw, COMPANY))
        for _ in range(copies)
    )
    other_no = draw(internal_nos.filter(lambda n: n != x))
    noise_choices = [
        (draw(plns), x, "Other Homes Pty Ltd"),  # another company
        (draw(plns), f"{x}/048", COMPANY),  # another suffix (SPEC)
        (draw(plns), f"{x}/020", COMPANY),
        (draw(plns), other_no, COMPANY),  # another number
        (draw(plns), "", COMPANY),
    ]
    noise_rows = tuple(draw(st.lists(st.sampled_from(noise_choices), max_size=4)))
    count = len(match_rows) + len(noise_rows)
    order = tuple(draw(st.permutations(range(count))))
    ignores = draw(st.booleans())
    cancelled = (
        draw(st.lists(st.tuples(task_nos, st.just(" Cancelled ")), max_size=2))
        if ignores
        else []
    )
    return World(
        internal_no=x,
        note_id=draw(note_ids),
        title=title,
        body=f"Please find attached Purchase Order / Quotation file {file_name}",
        attachments=(file_name,),
        linked=False,
        plumber=plumber,
        pypdf=pypdf,
        data=b"%PDF-" + draw(st.binary(min_size=1, max_size=8)),
        match_rows=match_rows,
        noise_rows=noise_rows,
        order=order,
        more_pages=False,
        project_internal_no=_spaces(draw, _any_case(draw, x)),
        project_prefix="Lot",
        project_lot=_any_case(draw, lot),
        project_house=house,
        project_rest=project_rest,
        tasks=tuple(cancelled),
        site=draw(st.sampled_from(["test", "live"])),
        ignores_cancelled=ignores,
        pln=pln,
        pdf_lot=lot,
        layout=layout,
    )


class Fresh(NamedTuple):
    """New values a mutation brings in, each different from the world's."""

    other_no: str
    other_lot: str
    other_word: str
    pln: str
    task: str


@st.composite
def fresh_values(draw: st.DrawFn, world: World) -> Fresh:
    return Fresh(
        other_no=draw(internal_nos.filter(lambda n: n != world.internal_no)),
        other_lot=draw(
            lots.filter(lambda lot: lot.casefold() != world.pdf_lot.casefold())
        ),
        other_word=draw(words.filter(lambda w: w not in world.project_rest)),
        pln=draw(plns.filter(lambda p: p != world.pln)),
        task=draw(task_nos),
    )


def _both(world: World, old: str, new: str) -> World:
    """A change to the PDF itself: both readers read it."""
    return dataclasses.replace(
        world,
        plumber=world.plumber.replace(old, new),
        pypdf=world.pypdf.replace(old, new),
    )


def _pypdf(world: World, old: str, new: str) -> World:
    """pypdf reads the PDF differently from pdfplumber."""
    return dataclasses.replace(world, pypdf=world.pypdf.replace(old, new))


def _first_word(rest: str) -> str:
    return rest.split()[0]


class Mutation(NamedTuple):
    apply: Callable[[World, Fresh], World]
    reason: str  # SPEC's skip reason when this is the only fault
    before_lookup: bool  # stops before the project read in MySys (8.3)
    applies: Callable[[World], bool] = lambda world: True


R = dataclasses.replace
MUTATIONS: dict[str, Mutation] = {
    # Steps 2a-4 (SPEC -> In the MVP; docs/specs/spec.md section 2-3).
    "note_linked": Mutation(
        lambda w, f: R(w, linked=True), "NOTE_ALREADY_LINKED", True
    ),
    "second_attachment": Mutation(
        lambda w, f: R(w, attachments=(*w.attachments, "other.pdf")),
        "MULTIPLE_PDFS",
        True,
    ),
    "no_attachment": Mutation(lambda w, f: R(w, attachments=()), "NO_PDF", True),
    "not_a_pdf": Mutation(
        lambda w, f: R(w, attachments=(f"{w.internal_no}_048.docx",)), "NO_PDF", True
    ),
    "no_pdfplumber_text": Mutation(
        lambda w, f: R(w, plumber=" \n"), "PDF_UNREADABLE", True
    ),
    "not_b1": Mutation(
        lambda w, f: _both(w, ISSUER, "B2 Homes Pty Ltd"), "NOT_B1", True
    ),
    "not_compaction": Mutation(
        lambda w, f: _both(w, "COMPACTION", "EXCAVATION"), "NOT_COMPACTION", True
    ),
    "pdf_po_other": Mutation(
        lambda w, f: _both(w, f"No {w.internal_no}/048", f"No {f.other_no}/048"),
        "PO_MISMATCH",
        True,
    ),
    "second_po": Mutation(
        lambda w, f: _both(
            w, "Delivery Date:", f"Purchase Order No {f.other_no}/048\nDelivery Date:"
        ),
        "PO_MISMATCH",
        True,
    ),
    "file_other": Mutation(
        lambda w, f: R(w, attachments=(f"{f.other_no}_048.pdf",)), "PO_MISMATCH", True
    ),
    "title_other": Mutation(
        lambda w, f: R(w, title=f"[B1 Homes] Order {f.other_no}/048"),
        "PO_MISMATCH",
        True,
    ),
    # The second reader (decisions, 2 Nov 2026).
    "no_pypdf_text": Mutation(lambda w, f: R(w, pypdf=""), "PDF_UNREADABLE", True),
    "pypdf_issuer": Mutation(
        lambda w, f: _pypdf(w, ISSUER, "B2 Homes Pty Ltd"), "READERS_DISAGREE", True
    ),
    "pypdf_po": Mutation(
        lambda w, f: _pypdf(w, f"No {w.internal_no}/048", f"No {f.other_no}/048"),
        "READERS_DISAGREE",
        True,
    ),
    "pypdf_no_compaction": Mutation(
        lambda w, f: _pypdf(w, "COMPACTION", "EXCAVATION"), "READERS_DISAGREE", True
    ),
    "pypdf_label_lot": Mutation(
        lambda w, f: _pypdf(
            w, f"Job Address: Lot {w.pdf_lot}", f"Job Address: Lot {f.other_lot}"
        ),
        "READERS_DISAGREE",
        True,
    ),
    # Step 8: the project search (SPEC -> Project search).
    "no_project": Mutation(
        lambda w, f: R(w, match_rows=()), "PROJECT_NOT_FOUND", False
    ),
    "other_company": Mutation(
        lambda w, f: R(
            w,
            match_rows=tuple((p, r, "Other Homes Pty Ltd") for p, r, _ in w.match_rows),
        ),
        "PROJECT_NOT_FOUND",
        False,
    ),
    "second_match": Mutation(
        lambda w, f: R(
            w,
            match_rows=w.match_rows
            + tuple((f.pln, r, c) for _, r, c in w.match_rows[:1]),
        ),
        "PROJECT_AMBIGUOUS",
        False,
    ),
    "more_pages": Mutation(
        lambda w, f: R(w, more_pages=True), "PROJECT_AMBIGUOUS", False
    ),
    "project_internal_no": Mutation(
        lambda w, f: R(w, project_internal_no=f.other_no), "UNEXPECTED_SCREEN", False
    ),
    # Step 9: the address check (SPEC -> Project address).
    "project_lot": Mutation(
        lambda w, f: R(w, project_lot=f.other_lot), "ADDRESS_MISMATCH", False
    ),
    "project_word": Mutation(
        lambda w, f: R(
            w,
            project_rest=w.project_rest.replace(
                _first_word(w.project_rest), f.other_word, 1
            ),
        ),
        "ADDRESS_MISMATCH",
        False,
    ),
    "project_no_lot": Mutation(
        lambda w, f: R(w, project_prefix="Block"), "ADDRESS_UNVERIFIABLE", False
    ),
    "second_label": Mutation(
        lambda w, f: _both(w, "Delivery Date:", "Delivery Date:\nJob Address: Lot 1"),
        "ADDRESS_UNVERIFIABLE",
        False,
    ),
    "project_house_other": Mutation(
        lambda w, f: R(w, project_house=f"{w.project_house}0"),
        "ADDRESS_MISMATCH",
        False,
        lambda w: w.layout == "house_line",
    ),
    "project_no_house": Mutation(
        lambda w, f: R(w, project_house=None),
        "ADDRESS_MISMATCH",
        False,
        lambda w: w.layout == "house_line",
    ),
    # Step 10: the duplicate check (SPEC -> Duplicate check).
    "live_task": Mutation(
        lambda w, f: R(w, tasks=(*w.tasks, (f.task, "New Project"))),
        "DUPLICATE_TASK",
        False,
    ),
    "cancelled_task_counted": Mutation(
        lambda w, f: R(
            w, tasks=(*w.tasks, (f.task, "Cancelled")), ignores_cancelled=False
        ),
        "DUPLICATE_TASK",
        False,
    ),
}


class Result(NamedTuple):
    """decide()'s result as plain values, and how often it read MySys."""

    kind: str  # "skip" or "proceed"
    value: str | dict  # the skip reason, or the Proceed's fields
    lookups: int


def outcome(
    world: World, models: ModuleType, readers: ModuleType, decision: ModuleType
) -> Result:
    """decide() of the given modules (the current code or tests/oracle)."""
    calls: list[int] = []

    def lookup():  # the project read in MySys, faked (step 8)
        calls.append(1)
        return models.MySysLookup(
            search_rows=tuple(
                models.SearchRow(pln=p, client_ref_no=r, company=c)
                for p, r, c in world.rows
            ),
            more_pages=world.more_pages,
            project_internal_no=world.project_internal_no,
            address=world.address,
            tasks=tuple(
                models.CompactionTask(task_no=t, status=s) for t, s in world.tasks
            ),
        )

    note = models.NoteSnapshot(
        note_id=world.note_id,
        title=world.title,
        body=world.body,
        attachment_names=world.attachments,
        project_linked=world.linked,
    )
    texts = readers.PdfTexts(plumber=world.plumber, pypdf=world.pypdf, data=world.data)
    result = decision.decide(
        note,
        world.internal_no,
        texts,
        lookup,
        site=world.site,
        duplicate_ignores_cancelled=world.ignores_cancelled,
    )
    if isinstance(result, models.Skip):
        return Result("skip", result.reason.value, len(calls))
    return Result("proceed", result.model_dump(), len(calls))
