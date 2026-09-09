"""PDF parsing utilities.

Two extraction modes, chosen deliberately per page type (see PLAN.md section 0):
- get_prose_text: PyMuPDF, for narrative pages.
- get_table_text: pdfplumber table-extraction, for pages 8/16/20 — avoids the
  text-layer rendering artifact confirmed on page 8 (a stray garbage line
  interleaved with Table 1.1's real rows when read as raw text).
"""
import re
import pymupdf
import pdfplumber

# Page 8's text layer (Table 1.1) contains a confirmed rendering artifact: a stray
# line of comma-thousands-formatted integers ("22,376," / "23,480,570," / "22,915, 0")
# sandwiched between real rows, unrelated to any actual figure in the table (every
# real number in this document is formatted as $X.XX billion with 2 decimals, never
# comma-thousands). pdfplumber's extract_tables() does NOT detect this as a bordered
# table (page has no ruling lines), so it falls back to raw text and does NOT dodge
# this artifact — confirmed empirically, not just theorized. Stripped explicitly here.
_ARTIFACT_LINE = re.compile(r"^[\d,\.\s]+$")


def _strip_known_artifacts(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # matches lines like "22,376," or "23,480,570," or "22,915, 0" — comma-thousands
        # integers with no label, no decimal-billion formatting, no letters.
        if stripped and _ARTIFACT_LINE.match(stripped) and "," in stripped and "." not in stripped:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def get_prose_text(pdf_path: str, page_numbers: list[int]) -> str:
    """1-indexed page numbers, matching the printed page footer numbers."""
    doc = pymupdf.open(pdf_path)
    chunks = []
    for p in page_numbers:
        chunks.append(f"--- PAGE {p} ---\n{doc[p - 1].get_text()}")
    return "\n\n".join(chunks)


def get_table_text(pdf_path: str, page_number: int) -> str:
    """Extracts a page's tables as pipe-delimited rows (1-indexed page number).

    Falls back to raw text (artifact-stripped) if pdfplumber finds no bordered
    table — true for pages 8 and 16 in this document, which have no ruling lines.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        tables = page.extract_tables()
    if not tables:
        raw = pymupdf.open(pdf_path)[page_number - 1].get_text()
        return f"--- PAGE {page_number} (no bordered table detected, using cleaned raw text) ---\n" + \
            _strip_known_artifacts(raw)
    out = [f"--- PAGE {page_number} TABLE ---"]
    for table in tables:
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            out.append(" | ".join(cells))
    return "\n".join(out)


if __name__ == "__main__":
    PDF = "data/source_budget.pdf"
    print(get_prose_text(PDF, [5, 6]))
    print()
    print(get_table_text(PDF, 8))
    print()
    print(get_table_text(PDF, 16))
    print()
    print(get_table_text(PDF, 20))
