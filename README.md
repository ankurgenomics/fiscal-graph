# HTX AI Engineering Take-Home

AI-powered extraction, tool-calling/reasoning, and multi-agent analysis of Singapore's
**FY2024 Analysis of Revenue and Expenditure** (Ministry of Finance).

Source document: https://isomer-user-content.by.gov.sg/153/20f8e128-58fa-44ea-a109-f2dec3995271/fy2024_analysis_of_revenue_and_expenditure.pdf
(fetched via a browser User-Agent header — a bare `curl`/`requests` GET is blocked with a
403 by the CloudFront distribution serving this file).

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then fill in your key(s), see below
```

### API keys

This project is **model-agnostic**: `llm_config.py` is the single LLM factory used by every
part. It supports two providers:

- **OpenRouter** (`OPENROUTER_API_KEY`) — for any model on OpenRouter's catalog, including
  free-tier models (used here for zero-cost development iteration). Set `DEV_MODEL` env var
  to override the default (`google/gemma-4-31b-it:free`).
- **Direct Anthropic** (`ANTHROPIC_API_KEY`) — used automatically whenever `HAIKU_MODEL` or
  `SONNET_MODEL` (from `llm_config.py`) is requested, for the final verified runs.

Only one is strictly required depending on which models you run; both are supported so you
can iterate for free and only spend real credit on confirmed final runs.

## Part 1 — Document Extraction & Prompt Engineering

### Parsing approach and justification

Two extraction modes are used deliberately, per page content type — not a single blanket
approach:

- **`pymupdf` (`parser.get_prose_text`)** for narrative/prose pages. Fast, robust text-layer
  extraction with correct reading order; the natural choice for pages that are paragraphs of
  text (e.g. pages 5-6, 18).
- **`pdfplumber` (`parser.get_table_text`)** for pages centered on tabular data (pages 8, 16,
  20). `pdfplumber` was chosen over a raw text dump for tables because it can detect and
  extract bordered tables cell-by-cell, which is more robust to column misalignment than
  reconstructing table structure from a flat text stream.

**A concrete finding drove a correction to this plan mid-build**: `pdfplumber.extract_tables()`
returns *no* tables on pages 8 and 16 — this document's tables have no ruling/border lines,
so pdfplumber can't detect them as bordered tables. It silently falls back to raw text on
those two pages. This matters because **page 8's raw text layer contains a genuine rendering
artifact**: a stray line of comma-thousands-formatted integers (`22,376,` / `23,480,570,` /
`22,915, 0`) sitting between two real table rows, unrelated to any actual figure in the
document (every real figure here is formatted `$X.XX billion`, never comma-thousands). A naive
text-dump extractor would hand this garbage straight to the LLM. `get_table_text` handles this
with a targeted, documented regex filter (`_strip_known_artifacts`) that strips lines matching
this specific artifact pattern from the raw-text fallback path — verified to remove the
artifact while leaving every real figure on the page untouched. Page 20 *does* have a real
bordered table and is extracted via pdfplumber's native table mode, no fallback needed.

### Extraction methodology

`extract.py` builds one combined context (pages 5-6 prose + pages 8/16/20 table-mode) and
extracts all 5 required fields in a single structured-output call via
`schemas.RevenueExtraction` (a Pydantic model), using LangChain's `.with_structured_output()`.
The system prompt explicitly warns the model that the source document contains both
"Revised FY2023" and "Estimated FY2024" columns side by side in its tables, and that these are
different numbers — this instruction was necessary, not decorative (see Known limitations).

### Verified results (against manually cross-checked source figures)

| Field | Extracted value | Source |
|---|---|---|
| Corporate Income Tax 2024 | $28.03 billion | Table 2.1, page 16 |
| YoY % diff, CIT 2024 | -1.2% | Table 2.1, page 16 |
| Total top-ups 2024 | $20.352 billion | Table 2.4, page 20 |
| Operating Revenue taxes | 12-item list (see below) | Pages 5-6 |
| Latest Actual Fiscal Position | $1.72 billion | Table 1.1, page 8 |

**Important finding, worth stating plainly**: the assignment brief cites **page 5** for the
Corporate Income Tax 2024 and YoY fields. Page 5 is actually the "Update on Financial Year
2023" section — the figures there ($28.38B, +17.0%) are **Revised FY2023** data, not FY2024.
The correct FY2024 estimates ($28.03B, -1.2%) are on **page 16**, Table 2.1. This was confirmed
by manually reading the source PDF, not assumed. The extraction pipeline is built to pull from
the correct page regardless of the cited page number.

### Assumptions

1. **Units**: the assignment specifies `float` for the CIT and top-ups fields but not a unit.
   Both are expressed in **$ billion**, matching the source document's own primary reporting
   unit (its tables are titled "$billion"; the top-ups table is in $ million and was converted).
2. **"Operating Revenue" tax list scope**: this field could reasonably mean either (a) the tax
   names called out in the narrative prose under the "1.2 Operating Revenue" heading (pages
   5-6) — 12 items — or (b) every line item under the "OPERATING REVENUE" header in Table 1.1
   (page 8), which additionally includes "Fees and Charges" and "Others" (14 items, and not
   all of those are strictly *taxes*). **We chose interpretation (a)**, the narrative's tax
   list, since the field is literally named "list of taxes" and "Fees and Charges"/"Others"
   are not taxes. This was empirically observed to be ambiguous during development — one dev
   run returned the 14-item table version before this scope was pinned down explicitly.
3. **Estate-duty-adjacent ambiguity does not apply to Part 1** (see Part 2 docs once written)
   but is noted here for consistency of documentation practice going forward.

### Known limitations

- The fix that gets `latest_actual_fiscal_position_billion` correct has two parts: (1) a
  **generalizable** rule in the schema description — "Actual" is a specific column label, not
  "whichever year is most recent" — and (2) a **document-specific, hardcoded** instruction in
  the system prompt pointing the model at page 8 specifically and telling it to ignore page 16.
  Part (2) was necessary because both pages 8 and 16 contain a row literally named
  `OVERALL FISCAL POSITION`, and part (1) alone was insufficient to resolve the collision on
  the model tested. **This hardcoded page pointer is brittle**: it works for this specific
  document but would need to be redesigned (e.g. via a retrieval step that identifies which
  page a field's ground-truth table actually lives on, rather than assuming a fixed page
  number) if applied to a different fiscal year's report with a different table layout.
- Development iteration used a free OpenRouter model (`google/gemma-4-31b-it:free`) for
  fast, zero-cost debugging; the final numbers above are from a real `claude-haiku-4-5-20251001`
  run, not the free dev model, to avoid depending on flaky free-tier availability for the
  numbers that actually matter.
