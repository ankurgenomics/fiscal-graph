# HTX AI Engineering Take-Home

Extraction, tool-calling, and multi-agent analysis over Singapore's FY2024 Analysis of Revenue
and Expenditure (Ministry of Finance).

Source document: https://isomer-user-content.by.gov.sg/153/20f8e128-58fa-44ea-a109-f2dec3995271/fy2024_analysis_of_revenue_and_expenditure.pdf

Note: a plain `curl` or `requests` GET against that URL returns a 403 from CloudFront. It needs
a browser User-Agent header to fetch.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with one or both of:

- `OPENROUTER_API_KEY`: for any model on OpenRouter, including free-tier ones. Used here during
  development to iterate without cost. Set the `DEV_MODEL` env var to change which model that is
  (default: `google/gemma-4-31b-it:free`).
- `ANTHROPIC_API_KEY`: used automatically for the Haiku and Sonnet runs that produced the
  results documented below.

Only one is strictly required, depending on which model you run. `llm_config.py` is the single
factory both paths go through.

## How to run each part

Every notebook already contains executed output. You can read the results without running
anything. To re-run:

```bash
jupyter nbconvert --to notebook --execute --inplace part1_extraction.ipynb
jupyter nbconvert --to notebook --execute --inplace part2_tools_reasoning.ipynb
jupyter nbconvert --to notebook --execute --inplace part3_multiagent.ipynb
```

Or the underlying scripts:

```bash
python extract.py              # Part 1
python part2_pipeline.py       # Part 2
python part3_supervisor.py     # Part 3, runs all 4 demo queries, writes trace.json
```

## Repository structure

| File | Purpose |
|---|---|
| `parser.py` | PDF parsing. PyMuPDF for prose pages, pdfplumber table mode plus an artifact filter for tables. Used by all three parts. |
| `schemas.py` | Pydantic models for every structured output used across the three parts. |
| `llm_config.py` | LLM factory. Routes to OpenRouter for free dev models or direct Anthropic for Haiku/Sonnet, from one call site. |
| `extract.py` | Part 1 extraction. |
| `part1_extraction.ipynb` | Part 1 notebook, executed, with a verification table against ground truth. |
| `tools/datetime_core.py` | Part 2's date-normalization logic, deterministic. |
| `tools/datetime_mcp.py` | Part 2's local MCP server exposing that logic as a tool. |
| `tools/datetime_fallback.py` | Same tool as a plain LangChain `@tool`, used if MCP is unavailable. |
| `tools/mcp_client.py` | Connects to the MCP server as a subprocess and exposes it as a LangChain-bindable tool. |
| `part2_pipeline.py` | Part 2 pipeline: extraction, then tool-calling normalization (MCP primary), then classification. |
| `part2_tools_reasoning.ipynb` | Part 2 notebook, executed, with a synthetic robustness check for one branch not covered by real data. |
| `agents.py` | Part 3's Revenue Agent and Expenditure Agent. |
| `part3_supervisor.py` | Part 3 supervisor, trace capture, four demo queries. |
| `part3_multiagent.ipynb` | Part 3 notebook, executed, with an automated verification cell and a routing-pattern summary. |
| `trace.json` | Full captured trace for all four Part 3 demo queries. |
| `data/source_budget.pdf` | The source document, kept in the repo so the pipeline is reproducible without a fresh download. |

## System design

The three parts share one foundation:

```
source_budget.pdf
      |
 parser.py  (shared PDF parsing)
      |
      +----------------+----------------+
      |                |                |
   Part 1           Part 2           Part 3
extract.py     part2_pipeline.py   agents.py + part3_supervisor.py
5 structured   date extraction,    two agents (create_react_agent)
   fields      MCP tool calling,   over their own page scopes,
               classification      routed and synthesized by a
                                    supervisor (create_supervisor)
      |                |                |
      +----------------+----------------+
                        |
             llm_config.py (one LLM factory,
             used the same way by all three parts)
```

`parser.py`, `schemas.py`, and `llm_config.py` are built once, in Part 1, and reused unchanged
by Parts 2 and 3. Part 3's agent tools call the same `parser.py` functions Part 1 uses, just
scoped to different pages per agent. It's one pipeline from PDF to structured answers, not
three separate scripts.

Two external APIs are used, both behind `llm_config.get_llm()`: OpenRouter's OpenAI-compatible
endpoint for free development models, and Anthropic's Messages API directly for the Haiku and
Sonnet runs whose results are documented below. Nothing else is called at runtime. The source
PDF is fetched once, manually, into `data/` rather than re-downloaded on every run.

## Dependencies

| Library | Why it's here |
|---|---|
| `pymupdf` | Text-layer extraction for prose pages. Fast, correct reading order. |
| `pdfplumber` | Table-aware extraction for tabular pages. Detects bordered tables cell by cell instead of reconstructing structure from a flat text dump (see the page 8 artifact finding under Part 1). |
| `langchain`, `langchain-openai` | Structured output and tool binding, used the same way in all three parts. `langchain-openai`'s `ChatOpenAI` is what actually talks to OpenRouter. |
| `langchain-anthropic` | Direct Anthropic access for the Haiku/Sonnet runs. |
| `pydantic` | Every schema in `schemas.py` is a Pydantic model, which is what makes structured output type-checked instead of parsed from raw JSON strings. |
| `langgraph`, `langgraph-supervisor` | Part 3's agent framework: `create_react_agent` for the two sub-agents, `create_supervisor` for routing and synthesis. |
| `mcp` (pinned `<2.0.0,>=1.24.0`) | The local MCP server for Part 2's datetime tool. Pinned below v2 because `langchain-mcp-adapters` requires it (see Part 2's bug notes). |
| `langchain-mcp-adapters` | Turns the MCP server into a tool an LLM can call through `.bind_tools()`, instead of Python code calling it directly. |
| `python-dateutil` | Deterministic date parsing for `tools/datetime_core.py`. Not LLM-based, on purpose: once a date string is located, converting it to ISO format is parsing, not reasoning. |
| `python-dotenv` | Loads `.env` so API keys stay out of source and out of git. |
| `jupyter` | Runs the three notebook deliverables. |

## Part 1 — Document Extraction & Prompt Engineering

### Parsing approach

Two extraction modes, chosen by page content, not one blanket approach:

- `pymupdf` (`parser.get_prose_text`) for narrative pages, such as 5-6 and 18.
- `pdfplumber` (`parser.get_table_text`) for pages centered on tables: 8, 16, 20.

pdfplumber was chosen for tables specifically because it can detect a bordered table and pull
it out cell by cell, which holds up better than reconstructing a table's structure from a flat
text stream. That distinction mattered in practice. Page 8's raw text layer contains a stray
line, `22,376,` / `23,480,570,` / `22,915, 0`, sitting between two real rows of Table 1.1.
It's a rendering artifact, not real data; every genuine figure in this document is formatted as
`$X.XX billion`, never comma-thousands. A plain text dump hands this straight to the model.
`get_table_text` filters it out with a regex scoped to that exact pattern, verified to remove
the artifact while leaving every real number on the page untouched.

pdfplumber's own table detector, as it turns out, finds no bordered table at all on pages 8 or
16 (this document's tables have no ruling lines), so it silently falls back to raw text on
both. That's where the artifact filter above actually does its work. Page 20 does have a
detectable bordered table and goes through pdfplumber's native table extraction.

### Extraction

`extract.py` builds one combined context from pages 5-6 (prose) and 8, 16, 20 (table mode),
then extracts all five required fields in a single call using
`.with_structured_output(RevenueExtraction)`. The system prompt warns explicitly that the
source document has both a "Revised FY2023" and an "Estimated FY2024" column side by side in
its tables, and that these are different numbers.

### Results

| Field | Value | Source |
|---|---|---|
| Corporate Income Tax 2024 | $28.03 billion | Table 2.1, page 16 |
| YoY % change, CIT 2024 | -1.2% | Table 2.1, page 16 |
| Total top-ups 2024 | $20.352 billion | Table 2.4, page 20 |
| Operating Revenue taxes | 12-item list, matches source exactly | Pages 5-6 |
| Latest Actual Fiscal Position | $1.72 billion | Table 1.1, page 8 |

Confirmed on `claude-haiku-4-5-20251001`.

One finding is worth stating plainly: the task brief cites page 5 for the Corporate Income Tax
2024 figure and its YoY change. Page 5 is the "Update on Financial Year 2023" section. Its
figures ($28.38 billion, +17.0%) are Revised FY2023, not FY2024. The correct FY2024 estimates,
$28.03 billion and -1.2%, are on page 16, Table 2.1. That was confirmed by reading the source
PDF directly, not assumed. The pipeline pulls from the correct page regardless of which page
the brief names.

### Assumptions

1. **Units.** The task specifies `float` for the CIT and top-ups fields but no unit. Both are
   reported in $ billion, matching the document's own primary unit (its tables are titled
   "$billion"; the top-ups table itself is in $ million and was converted).
2. **Scope of "taxes mentioned in the Operating Revenue section."** This could mean the tax
   names called out in the narrative under "1.2 Operating Revenue" on pages 5-6 (12 items), or
   every line under the "OPERATING REVENUE" header in Table 1.1 on page 8, which adds "Fees and
   Charges" and "Others" (14 items, and neither of those two is actually a tax). The narrative
   reading was used, since the field is named "list of taxes" and those two items aren't taxes.
   This ambiguity showed up in practice: one early test run against a different page window
   returned the 14-item version before the scope was pinned down.

### Known limitations

- Getting `latest_actual_fiscal_position_billion` right took two separate fixes: a general rule
  in the schema description ("Actual" is a specific column label, not "whichever year is most
  recent"), and a page-8-only instruction in the system prompt, because both pages 8 and 16
  contain a row literally named `OVERALL FISCAL POSITION` and the general rule alone wasn't
  enough to resolve the collision on the model tested. The page-8 pointer is specific to this
  document. Point it at a different fiscal year's report with a different table layout and it
  would need to be redesigned, probably with a retrieval step that finds which page a field's
  answer actually lives on rather than assuming a fixed page number.
- Development used a free OpenRouter model for fast iteration. The numbers above are from a
  real Haiku run, not the free model, so the results that matter don't depend on a free tier
  staying available.

## Part 2 — Tool Calling & Reasoning

### Approach

`part2_pipeline.py`: extract the raw date text from pages 1 and 36, normalize it to ISO 8601
through a real tool call, then classify each date against the reference date `2024-01-01`.

The normalization logic lives in one place, `tools/datetime_core.py`, using `python-dateutil`.
This is not LLM-based on purpose. Once a date string is located, turning it into ISO format is
parsing, not reasoning. Two wrappers sit on top of that one implementation, so they can't drift
apart from each other:

- `tools/datetime_mcp.py`: a real local MCP server. `mcp` is pinned below v2 because
  `langchain-mcp-adapters` requires it; installing that package silently downgraded an unpinned
  `mcp>=2` install and broke the v2 API this file briefly used before the constraint was found.
- `tools/datetime_fallback.py`: the same logic as a plain LangChain `@tool`, used only if the
  MCP connection itself fails.

The running pipeline goes through MCP first, not the fallback, matching the task's own wording:
"via local MCP... if you are not able to implement a local MCP, you may define as a function."
`part2_pipeline.py`'s `_get_normalize_tool()` connects to the server as a real subprocess, binds
its tool to the LLM with `.bind_tools()`, and lets the model decide to call it with arguments it
extracted itself. That's the actual difference between this and Python code calling a function
directly: the model is the one deciding to invoke the tool. Every run prints which path,
`mcp` or `fallback`, actually executed.

One environment detail to flag directly: from a plain Python process, the MCP path runs and is
confirmed (`tool source: mcp`). Inside the Jupyter kernel used to execute
`part2_tools_reasoning.ipynb`, the same connection fails with `UnsupportedOperation('fileno')`,
because Jupyter replaces stdin/stdout with objects that don't expose the file descriptors the
stdio transport needs. The fallback runs instead, automatically, with the same result. Both
paths are exercised and verified separately. This is the fallback doing its job, not a failure
being hidden.

### Results

| Text | Normalized | Status |
|---|---|---|
| "Distributed on Budget Day: 16 February 2024" | 2024-02-16 | Upcoming |
| "Estate Duty does not apply to a person who dies after 15 February 2008." | 2008-02-15 | Expired |

The first row matches the task's own sample output exactly. Both confirmed on real Haiku, run
twice to check for determinism (temperature 0).

### Assumptions

The task description says to normalize "submission dates extracted in Part 1," but Part 1 has
no date fields at all. The two dates named here appear for the first time in Part 2, and are treated
as a continuation that extracts these two dates directly, using the same pattern built for
Part 1, rather than assuming Part 1 already produced them.

The estate duty date is a policy cutoff, not a submission date. Against the reference date, a
literal reading says Expired (the date has passed); an alternative reading says Ongoing (the
policy state it describes is still in effect). Expired was used, as the more literal reading of
the field.

### Bugs found along the way

1. The classification step first returned `2024-02-16` as Expired, which contradicts both plain
   date arithmetic and the task's own sample output, which labels this exact date Upcoming. The
   model had substituted its own sense of the current date instead of treating the reference
   date as "today" for this exercise. Fixed by rewriting the system prompt to rule that out
   explicitly, spell out the comparison, and include this date as a worked example.
2. A closer read of the assignment text turned up two things the first working version had
   missed: no genuine function calling (the tool was called from Python glue code between two
   LLM calls, not by the model itself), and the literal Step 1 deliverable, "a list of these
   normalized dates," was never printed as its own output. Both fixed as described above.
3. Installing `langchain-mcp-adapters` silently downgraded `mcp` from an unpinned 2.2.0 to
   1.30.0, breaking the v2 API `tools/datetime_mcp.py` had briefly switched to. Found by
   comparing the installed version before and after, not guessed at. Reverted to the v1
   `FastMCP` API and pinned the version constraint in `requirements.txt`.
4. The printed final output was `{"dates": [...]}`, wrapped in an object because
   structured-output APIs require an object root schema. The task's own sample output is a bare
   array. `to_sample_format()` unwraps it for display only; the schema itself is unchanged.

### One branch tested synthetically

Both real dates are single points in time, so neither exercises the third classification state,
Ongoing, which describes a period spanning the reference date. `part2_tools_reasoning.ipynb`
includes one clearly labeled synthetic case, a constructed period that does span the reference
date, to confirm the branch works. It's marked `[SYNTHETIC, not document-derived]` and isn't
part of the graded output above.

## Part 3 — Multi-Agent Supervisor

### Architecture

Two agents, built with `create_react_agent`:

- **Revenue Agent**: one tool, `revenue_context()`, returning pages 5-6, 9, and 16.
- **Expenditure Agent**: one tool, `expenditure_context()`, returning pages 14, 17, 18, and 20.
  Page 18 matters specifically: it's the narrative that explains why the Future Energy Fund
  exists, not just the table row that gives its dollar amount.

`part3_supervisor.py` wires both agents under `create_supervisor(agents=[...], model=...,
prompt=..., output_mode="full_history")`. `output_mode="full_history"` is not the default; the
default, `"last_message"`, would only keep each agent's final one-line answer and lose the tool
calls that make the trace worth reading. `create_supervisor()` returns an uncompiled graph;
`.compile()` is called before use.

Both sub-agents run on Haiku. The supervisor's routing and final synthesis run on Sonnet, since
that step is where the actual decision-making happens, and it's what this part is graded on.

### Assumptions

1. **Tool design.** Each agent's tool returns a fixed, pre-scoped block of page text rather than
   searching the full document with an embedding index. The source is 37 pages with a page
   mapping already established in Part 1, and this part is graded on how the supervisor routes
   and synthesizes, not on retrieval sophistication. Building a retrieval layer here would be
   solving a problem the task doesn't actually pose.
2. **Selective routing.** The supervisor is prompted to delegate only to the agent or agents an
   individual query actually needs, not both by default. That's a design choice, checked
   behaviorally below rather than just asserted.
3. **Which pages belong to which agent** is an interpretive call the task doesn't make for you.
   Pages were assigned by their dominant topic: revenue narrative and tables to Revenue Agent,
   expenditure and fund top-ups to Expenditure Agent. Table 2.1 (page 16) and Table 2.4 (page
   20) both list the Future Energy Fund as a line item, since the source document nests
   expenditure figures inside a broader budget summary table. That overlap produced the finding
   below.
4. **"Key government revenue streams"** has no fixed count or cutoff in the query itself.
   Revenue Agent reports every line item visible in its context rather than picking an arbitrary
   top-N.

### Results

Trace-verified: read from the actual sequence of agents invoked, not inferred from whether the
final answer sounded right.

| Query | Agents invoked |
|---|---|
| The task's exact query (dual-agent) | Revenue Agent, Expenditure Agent |
| Revenue-only ("largest single source of revenue?") | Revenue Agent only |
| Expenditure-only ("GST Voucher Fund top-up?") | Expenditure Agent only |
| A second dual-agent query, different phrasing | Revenue Agent, Expenditure Agent |

The revenue-only and expenditure-only rows show the supervisor isn't reflexively calling both
agents on every query. The two dual-agent rows show collaboration isn't a one-off. The task's
exact query gets the Future Energy Fund figure right: $5.0 billion, sourced to "invest in
critical infrastructure for the energy transition," the actual wording from page 18. It also
names revenue streams that match Part 1's verified 12-item list, with nothing invented.

### A finding worth keeping in

The second dual-agent query was originally phrased as a comparison between total revenue and
the Future Energy Fund's spending commitment. Run that way, the supervisor answered using only
Revenue Agent. This wasn't a routing bug. Revenue Agent's page 16 happens to list the fund's dollar
figure too, so the supervisor judged the second agent unnecessary. The answer was numerically
correct but hedged the fund's purpose ("likely supporting energy transition... initiatives")
instead of citing the actual reason, which lives only in Expenditure Agent's page-18 context
and was never reached. The query was rewritten to ask for something only Expenditure Agent has,
which brought both agents back into play and replaced the hedge with the verbatim source quote.
Left in here because it says something real about agent design: overlapping context between
agents can produce an answer that still looks fine while quietly skipping collaboration.

### Bugs found along the way

1. The Sonnet model rejects the `temperature` parameter outright. Haiku accepts it, Sonnet
   returns a 400 with "temperature is deprecated for this model." `llm_config.get_llm()` made
   `temperature` optional; passing `None` now omits it from the request entirely.
2. `output_mode="full_history"` re-sends the entire accumulated message history on every
   streamed step, not just the new part. Appending each step's messages produced a trace with
   over fifty entries, most of them duplicates. Technically complete, not remotely clear. Fixed
   by reading only the final stream step, which already holds the full ordered history.
3. The final answer's content is sometimes a list of content blocks instead of a plain string,
   when the model's response includes an extended-thinking block. This is not consistent run to
   run. Earlier tests happened to get plain strings before a later run exposed it with an
   `AttributeError`. `_extract_text()` now handles both shapes.

## Known limitations and open items

A consolidated list, pulled together from the sections above and from decisions made along the
way that a reader shouldn't have to hunt for:

- No embedding-based retrieval anywhere in the pipeline. Every part uses fixed, pre-scoped page
  text. Given a 37-page document with a known page-to-topic mapping that was a reasonable scope
  decision, but it means none of this would scale to a much longer or less-structured source
  without redesign.
- The Part 1 fix for `latest_actual_fiscal_position_billion` includes a hardcoded pointer to
  page 8. It works for this document and would need to be redesigned for a different one.
- The Part 2 "Ongoing" classification branch is verified with a synthetic example, not real
  document data. There's no naturally occurring date range in the source that spans the
  reference date.
- The MCP tool-calling path in Part 2 doesn't run inside a Jupyter kernel specifically, due to a
  `fileno()` limitation in how Jupyter replaces stdio streams. It falls back automatically and
  correctly, and both paths are verified separately, but the notebook run and the plain-script
  run don't take the identical code path.
- Two judgment calls in Part 1 and Part 2, the Operating Revenue tax list scope and the estate
  duty date's Expired/Ongoing classification, don't have a single correct answer. Both are
  documented above with the reasoning behind the choice made.
- Page-to-agent scoping in Part 3 is an interpretive choice, not something the task specifies.
- This README and the three notebooks are the record of what was built and verified. The task's
  own step of emailing the repository link to the review contacts is not part of this repository
  and was not done as part of building it.
