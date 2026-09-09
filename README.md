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

## Part 2 — Tool Calling & Reasoning

### Approach

Pipeline (`part2_pipeline.py`): extract raw date text from pages 1 and 36 (LLM, structured
output via `schemas.DateExtraction`) → normalize to ISO 8601 using a **deterministic**
datetime tool → classify each date relative to reference date `2024-01-01` (LLM, structured
output via `schemas.ClassifiedDates`).

The datetime tool is implemented **once** (`tools/datetime_core.py`, using `python-dateutil`,
deliberately not LLM-based — once a raw date string is located, converting it to ISO is a
parsing problem, not a reasoning problem) and wrapped two ways so both are guaranteed to
never disagree:
- **`tools/datetime_mcp.py`** — a real local MCP server (`mcp>=2`; note this project's
  installed `mcp` package is v2.x, where `FastMCP` was renamed to `MCPServer` — the API is
  otherwise identical). Verified via the actual MCP protocol layer (`mcp.list_tools()` /
  `mcp.call_tool()`), not just imported as a plain function.
- **`tools/datetime_fallback.py`** — the same logic as a plain LangChain `@tool`, per the
  assignment's own fallback clause, used by `part2_pipeline.py`'s end-to-end run so the full
  pipeline doesn't require spinning up a separate MCP server process; the MCP path is verified
  independently in `part2_tools_reasoning.ipynb`.

### Verified results

| Original text | Normalized date | Status |
|---|---|---|
| "Distributed on Budget Day: 16 February 2024" | 2024-02-16 | **Upcoming** |
| "Estate Duty does not apply to a person who dies after 15 February 2008." | 2008-02-15 | **Expired** |

The first row matches the assignment's own sample output exactly. Both were confirmed on real
`claude-haiku-4-5-20251001`, run twice to confirm determinism (temperature=0).

### Assumption

The assignment's Part 2 task description says "normalize submission dates extracted **in Part
1**," but Part 1's task list has no date fields at all — the two dates to extract (page 1,
page 36) are only named here in Part 2, as if for the first time. Treated as a continuation
that extracts these two dates directly (using the same LLM-extraction pattern as Part 1),
rather than assuming Part 1 already produced them.

The estate-duty date (`2008-02-15`) is a policy-abolition cutoff, not an event/submission
date — genuinely ambiguous whether it should read as "Expired" (literal: the date has passed)
or "Ongoing" (the policy state it describes is still in effect today). We chose **Expired**,
the more literal reading of the field name.

### Bug found and fixed during development

The classification step initially returned `2024-02-16` as **Expired**, contradicting both
simple date arithmetic (2024-02-16 is after the reference date 2024-01-01) and the
assignment's own sample output, which explicitly labels this exact date "Upcoming." The model
had substituted its own knowledge of the real current date instead of strictly using the given
reference date as "today" for the exercise. Fixed by rewriting the classification system
prompt to explicitly forbid using real-world date knowledge, spell out the comparison rule
against the reference date, and include a worked example using this exact date — verified
correct across two repeated runs afterward.
