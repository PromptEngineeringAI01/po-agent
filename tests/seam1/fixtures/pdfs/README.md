# Seam 1 fixture PDFs

**This folder holds no PDF** (Joey, 29 Oct 2026: no fake-PDF generator). Seam 1's 3 fake B1-style POs are text in `../cases.toml`; the corrupt and image-only PDFs are built inside the tests. `tests/seam1/test_cases.py` fails on any PDF here.

**Never put the trial PDFs here.** The 3 trial POs (2609017B → pln_66935, 2609034B → pln_66938, 2610002B → pln_66940) are real B1 POs (16 Oct 2026, `docs/decisions.md`). They go in `private/pdfs/` with the other real POs (git-ignored, laptop only; used by `pytest -m real_data`).
