# Seam 1 fixture PDFs

Slice M2 generates 3 **fake** B1-style PO PDFs here (fake internal numbers such as `2600001B`, fake addresses), plus their mutated copies (see `SPEC.md` → Testing Strategy).

**Never put the trial PDFs here.** The 3 trial POs (2609017B → pln_66935, 2609034B → pln_66938, 2610002B → pln_66940) are real B1 POs (16 Oct 2026, `docs/decisions.md`). They go in `private/pdfs/` with the other real POs (git-ignored, laptop only; used by `pytest -m real_data`).
