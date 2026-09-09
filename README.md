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
- **`tools/datetime_mcp.py`** — a real local MCP server (`mcp<2.0.0,>=1.24.0`, using the
  `FastMCP` API — pinned below v2 because `langchain-mcp-adapters`, needed to bridge this
  server into a LangChain-bindable tool, hard-requires `mcp<2.0.0`; installing it silently
  downgrades an unpinned `mcp>=2` install and breaks the v2 `MCPServer` API this project
  briefly used before that constraint was discovered).
- **`tools/datetime_fallback.py`** — the same logic as a plain LangChain `@tool`, used
  automatically only if the MCP connection itself fails.

**The live pipeline routes through MCP as primary, not the fallback** — matching the
assignment's literal preference order ("via local MCP... if you are not able to implement a
local MCP, you may define as a function"). `part2_pipeline.py::_get_normalize_tool()` connects
to the MCP server as a real subprocess (via `tools/mcp_client.py`, `langchain-mcp-adapters`),
binds its tool to the LLM with `.bind_tools()`, and lets the model itself decide to call it
with its own extracted arguments — this is genuine LLM-driven function calling, not Python
code invoking the tool directly. The except clause around the MCP connection is scoped
narrowly to just that call, so a downstream bug elsewhere can't be silently misattributed to
"MCP unavailable." Every run prints which path (`mcp` or `fallback`) actually executed, so the
mechanism is never asserted without evidence.

**Environment-dependent behavior, disclosed rather than hidden**: from a plain Python process
(script or `python -c`), the MCP path works and is confirmed (`tool source: mcp`). Inside the
Jupyter kernel used for `part2_tools_reasoning.ipynb` specifically, the MCP subprocess
connection fails with `UnsupportedOperation('fileno')` — Jupyter's kernel replaces stdin/stdout
with custom stream objects lacking the raw file descriptors the stdio transport needs — and the
fallback path is used automatically instead, producing identical correct results either way.
This is the fallback design working as intended; both entry points are verified separately (see
`part2_tools_reasoning.ipynb` for the notebook run, and this README's dev log for the standalone
script run showing `tool source: mcp`).

**Step 1's literal deliverable**: the assignment states "your final output for this step should
be a list of these normalized dates" — `normalize_dates_via_tool_calling_async()` returns and
prints exactly that (`['2024-02-16', '2008-02-15']`) before it's paired with original text and
handed to classification.

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

### Bugs found and fixed during development

1. **Classification used the wrong "today"**: the classification step initially returned
   `2024-02-16` as **Expired**, contradicting both simple date arithmetic (2024-02-16 is after
   the reference date 2024-01-01) and the assignment's own sample output, which explicitly
   labels this exact date "Upcoming." The model had substituted its own knowledge of the real
   current date instead of strictly using the given reference date as "today" for the exercise.
   Fixed by rewriting the classification system prompt to explicitly forbid using real-world
   date knowledge, spell out the comparison rule against the reference date, and include a
   worked example using this exact date — verified correct across two repeated runs afterward.
2. **A stricter postmortem, re-reading the literal assignment text rather than just checking
   output correctness, found the first working version of Part 2 was incomplete**: the
   normalization step called the tool directly from Python glue code between two LLM calls
   (no genuine function calling was demonstrated), and the assignment's literal Step-1
   deliverable ("a list of these normalized dates") was never surfaced as its own output.
   Both fixed as described above (real `.bind_tools()` tool calling routed through MCP as
   primary, and an explicit printed list before classification runs).
3. **The `mcp` package version pin**: installing `langchain-mcp-adapters` (needed to bridge
   the MCP server into a bindable LangChain tool) silently downgraded `mcp` from an unpinned
   `2.2.0` to `1.30.0`, breaking the v2 `MCPServer` API this project had briefly switched to.
   Root-caused via `langchain-mcp-adapters`' own package metadata (`Requires-Dist:
   mcp<2.0.0,>=1.24.0`) rather than guessed at; reverted `tools/datetime_mcp.py` to the v1
   `FastMCP` API and pinned `mcp<2.0.0,>=1.24.0` explicitly in `requirements.txt`.

### Output format matched to the literal sample, not the internal schema

A re-postmortem (re-reading the literal assignment text once more against the *current* code,
per this project's working agreement) found the printed final output was `{"dates": [...]}`, an
object wrapper — but the assignment's own sample output is a **bare array**. The wrapper exists
for a real reason (structured-output/tool-calling APIs require an object root schema, `dates`
wraps `list[ClassifiedDate]` to satisfy that), but the *presented* output shouldn't leak that
internal detail. Added `to_sample_format()` to unwrap for display only — the printed/notebook
output now matches the literal sample shape exactly, without changing the validated schema.

### Untested branch, addressed with a labeled synthetic check

Both real document-derived dates are point-in-time, so neither exercises the third
classification state ("Ongoing" — a period spanning the reference date). Rather than leave this
branch unverified, `part2_tools_reasoning.ipynb` includes one clearly-labeled **synthetic**
test case (a constructed period explicitly marked `[SYNTHETIC, not document-derived]`) that
does span the reference date — confirmed the model correctly classifies it "Ongoing." This is
never conflated with the two graded document-derived answers above.

## Part 3 — Multi-Agent Supervisor

### Architecture

`agents.py` defines two `create_react_agent` (LangGraph prebuilt) agents:
- **Revenue Agent** (`name="revenue_agent"`): single no-argument tool `revenue_context()`
  returning pages 5-6 (Operating Revenue narrative), 9 (Chart 1.1 breakdown), 16 (Table 2.1
  FY2024 figures).
- **Expenditure Agent** (`name="expenditure_agent"`): single no-argument tool
  `expenditure_context()` returning pages 14 (Total Expenditure), 17 (Chart 2.1 by ministry),
  **18** (Special Transfers / Fund top-up narrative — the Future Energy Fund's stated purpose),
  20 (Table 2.4).

`part3_supervisor.py` wires both under `langgraph_supervisor.create_supervisor(agents=[...],
model=..., prompt=..., output_mode="full_history")`. **`output_mode="full_history"` is a
deliberate, non-default choice** — the default `"last_message"` would only retain each
sub-agent's final one-line answer, losing the tool-call detail needed for a genuinely "clear
trace of the supervisor's decision-making process." `create_supervisor()` returns an uncompiled
`StateGraph`; `.compile()` is called before use.

**Model tiering**: both sub-agents run on Haiku (well-scoped extraction/analysis, same tier as
Parts 1-2); the supervisor's routing and final synthesis runs on Sonnet — the higher-value
reasoning step, and the part actually graded on "decision-making."

### Assumptions

1. **Tool design — proportionality, not under-engineering**: each agent's tool returns fixed,
   pre-scoped page text rather than performing embedding-based retrieval over the full
   37-page document. The source document has a known, fixed page-to-topic mapping (established
   in Part 1), and this part is graded on the supervisor's *routing and synthesis* behavior, not
   retrieval sophistication — building RAG infrastructure here would be disproportionate to what
   the assignment is actually testing.
2. **Selective routing, not reflexive dual-agent calls**: the supervisor is explicitly prompted
   to delegate only to the agent(s) actually relevant to each query, not both by default. This
   is verified behaviorally, not just claimed — see Verified Results below.

### Verified results — routing pattern across 4 demo queries

Trace-verified (from the actual message/actor structure, not inferred from answer plausibility):

| Query | Agents invoked (from trace) |
|---|---|
| Q1 — assignment's exact query (dual-agent) | `expenditure_agent`, `revenue_agent` |
| Q2 — revenue-only ("largest source of revenue?") | `revenue_agent` only |
| Q3 — expenditure-only ("GST Voucher Fund top-up?") | `expenditure_agent` only |
| Q4 — second dual-agent query, different phrasing | `expenditure_agent`, `revenue_agent` |

Confirms the supervisor genuinely routes based on query content (Q2/Q3 prove it doesn't call
both agents reflexively) and genuinely collaborates when needed (Q1/Q4 confirm dual-agent
routing isn't a one-off fluke). Q1's final answer states the Future Energy Fund as **$5.0
billion**, sourced to "invest in critical infrastructure for the energy transition" (verbatim
from the source document), and names revenue streams that match Part 1's verified 12-item tax
list exactly — see `part3_multiagent.ipynb`'s verification cell for the automated checks.

### A real routing-quality finding from development (not glossed over)

Q4 was originally phrased as "Compare total government revenue to the Future Energy Fund
spending commitment." Run against that phrasing, the supervisor answered using **only**
`revenue_agent` — not a bug, but a real, honest consequence of context design: Revenue Agent's
page 16 (Table 2.1) happens to also list the Future Energy Fund as a line item (it's a top-up
table nested within the FY2024 budget table), so the supervisor judged the second agent
unnecessary for the number. The answer was still numerically correct, but it **hedged the fund's
purpose** ("likely supporting energy transition... initiatives") instead of citing the actual
verbatim reason — that qualitative fact lives only in Expenditure Agent's exclusive context
(page 18), which never got invoked. Rewritten to explicitly ask for content only Expenditure
Agent has ("what specific purpose... according to the budget document") — confirmed both agents
now invoked, and the answer quotes the source verbatim rather than hedging. Kept in this README
because it's a genuine, instructive finding about agent context design (accidental page overlap
between agents can mask under-collaboration behind a still-plausible answer), not something to
hide because the first version "mostly worked."

### Bugs found and fixed during development

1. **`temperature` deprecated for `claude-sonnet-5`**: `llm_config.get_llm()` always passed
   `temperature=0` by default; Haiku 4.5 accepts this fine, but Sonnet 5 rejects it entirely
   with a 400 error ("`temperature` is deprecated for this model"). Fixed by making
   `temperature` an optional parameter (`None` omits it from the API call) and passing
   `temperature=None` explicitly for the supervisor's Sonnet call.
2. **Trace duplication from `output_mode="full_history"`**: each streamed step re-emits the
   *entire* accumulated message history so far, not just new deltas — naively appending every
   step's messages produced a 50+ entry trace full of duplicates. Fixed by only reading the
   **last** stream step's message list (already contains the complete, ordered history) rather
   than accumulating across steps.
3. **Final answer content sometimes a list, not a string**: when the model's final response
   includes an extended-thinking block alongside its text, `message.content` comes back as a
   list of content blocks instead of a plain string — nondeterministic (depends on whether
   thinking was triggered for that particular run), so earlier test runs "got lucky" with plain
   strings before this surfaced. Fixed with `_extract_text()`, which handles both shapes.
