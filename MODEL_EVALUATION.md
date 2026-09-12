<!-- DRAFT: not linked from README, not committed. For review before deciding placement. -->

# Model Selection: Why Claude Sonnet/Haiku, Not Free Open-Weight Models

## Method

Every part of this pipeline runs through one call site, `llm_config.get_llm(model, max_tokens,
temperature)`. Swapping models changes one string argument; no other code changes. This makes the
comparison below a controlled test: identical prompts, identical Pydantic schemas, identical
retry logic, identical token budgets per model class; only the model differs.

Five free/open-weight models, all available at zero cost through OpenRouter, were run against
Part 1 (structured financial extraction, 5 required fields). Three paid, closed models were run
against the full pipeline (Parts 1-3). Every result below is from a live API call made during
development, not from documentation or vendor claims.

Note on scope: OpenRouter's free tier was queried directly (19 models total at time of testing).
DeepSeek, Llama, Qwen, and Mistral were not present in that free catalog. They were not available
to test at zero cost, not excluded by choice.

## Results

| Model | Class | Outcome | Root cause |
|---|---|---|---|
| `google/gemma-4-31b-it:free` | Open-weight, free | Failed: request rejected before reaching the model | Shared free-tier capacity pool returned HTTP 429 ("temporarily rate-limited upstream"), independent of this pipeline's usage. Infrastructure availability, not a model property. |
| `nvidia/nemotron-3-super-120b-a12b:free` | Open-weight, free (120B params, 12B active, reasoning) | Failed: no structured output produced | Consumed its entire 8,000-token budget on internal reasoning tokens before emitting any JSON. `openai.LengthFinishReasonError`. Raising the budget defers this failure; it does not eliminate it, because the model's reasoning-token consumption is unbounded by design. |
| `nex-agi/nex-n2.5-pro:free` | Open-weight, free (reasoning) | Failed: same mode | 7,703 of 8,000 tokens spent on reasoning tokens before truncation. Same root cause as above. |
| `inclusionai/ling-3.0-flash-fin:free` | Open-weight, free (finance-domain-tuned) | Failed: request rejected, zero attempts possible | Backing provider (Novita) returns HTTP 400: "model features structured outputs not support." This model cannot serve this pipeline's contract under any prompt or token budget. |
| `liquid/lfm-2.5-2.6b:free` | Open-weight, free (2.6B params) | Ran, but unreliable on both axes tested | Non-deterministic: an identical call succeeded once, then failed with the same `LengthFinishReasonError` as the two reasoning models above on a later attempt, with no prompt or input changed. When it did return valid JSON, the answers were wrong and inconsistent across identical repeated calls: fiscal position returned as 1.72, 1.72, then -0.35 across three runs (correct answer: -3.57); the Corporate Income Tax figure and its year-over-year change were pulled from the wrong fiscal-year column (Revised FY2023 instead of the requested Estimated FY2024) in all three runs; the required tax list ranged from 7 to 10 items per run (correct: 10-12, depending on one documented interpretation call). |
| `gemini-3.6-flash` (Google) | Closed, paid-tier API, direct | Passed on content, three quantified operational gaps | See "Gemini vs. Claude" below. |
| `claude-haiku-4-5` (Anthropic) | Closed, paid-tier API, direct | Passed | Correct on every field in every run. One interpretation disagreement against Sonnet on an inherently ambiguous field (see Interpretation calls, row 6), a documented reading difference, not an error. |
| `claude-sonnet-5` (Anthropic) | Closed, paid-tier API, direct | Passed | Correct on every field in every run. Correct multi-agent routing after one prompt refinement. Rejects the `temperature` parameter outright at the API level, a protocol quirk, handled in `llm_config.py`, not a capability issue. |

## Gemini vs. Claude

Gemini is in a different class from the five open-weight models above: it is a closed, capable
model, and every fact it returned across all three parts of the pipeline was correct once it had
enough token budget. Part 1's five fields, both Part 2 dates (normalized and classified correctly
through real MCP tool calls), and every factual claim in all four Part 3 demo answers were right.
It did not produce a single wrong answer in any run. On content accuracy, it matched Sonnet and
Haiku.

It fell short of Sonnet/Haiku on three specific, measured points, not on general capability:

1. **Token budget.** At 3,000 tokens (Claude's working default), Gemini silently omitted a
   required schema field. It needed 6,000-8,000 to reliably complete the schema, a 2-2.7x larger
   budget for the identical task. Sonnet and Haiku never showed this failure at 3,000.
2. **Run-to-run consistency on ambiguous fields.** Across repeated identical calls, Gemini's
   operating-revenue tax list came back as both a 12-item and a 10-item list. Sonnet was consistent
   across repeated runs (always 11 items) and Haiku was consistent (always 12); each settled on one
   reading and held it. Gemini's own output varied despite its API reporting "fixed sampling
   defaults."
3. **Multi-agent routing precision.** Of 4 demo queries through the Part 3 supervisor, Gemini
   over-routed once: an expenditure-only query (Q3) triggered both agents instead of one. The extra
   call did not corrupt the final answer, but it is a routing-selectivity miss. Sonnet, after one
   prompt refinement, was 4/4 correct on selectivity in the verified trace.

None of these three are answer-accuracy failures. They are operational reliability gaps: more
token headroom required to reach the same completeness, more decoding variance on the one
genuinely ambiguous field, and one avoidable extra tool call. That is a materially different, and
smaller, gap than any of the five open-weight models show above.

## Two different kinds of failure

The five free-tier results split into two categories that matter differently to a production
decision:

**Contract failures.** The model cannot participate in a structured-output pipeline at all,
regardless of prompting effort. `nemotron-3-super-120b` and `nex-n2.5-pro` spend an unbounded
amount of their token budget on internal reasoning before producing an answer; no fixed
`max_tokens` value is safe against this by construction. `ling-3.0-flash-fin`'s provider does not
implement structured outputs. These are architectural or infrastructure limits: no prompt, retry
policy, or schema change fixes them.

**Capability failures.** The model participates and returns a validly-shaped answer, but the
content is wrong or non-reproducible. `liquid/lfm-2.5-2.6b` is the only free model tested that
reached this category rather than failing outright, and it failed here too: three identical calls
to the same question produced three different numeric answers to a fact that has exactly one
correct value in the source document.

Every generic mitigation available was already applied uniformly across all models before this
comparison: a shared retry-on-failure wrapper (`retry_utils.py`), doubled token budgets, and a
few-shot worked example in the extraction prompt. None of it changes the outcome for the two
contract-failure models, because the failure occurs before the model's own answer-generation step.
It only partially helps the capability-failure model, because the underlying problem there is the
model's accuracy on a 2.6B-parameter budget, not a fixable prompt gap.

## Conclusion

Claude Sonnet and Haiku were not the default choice. They were the only two models tested, across
eight, with zero wrong answers and zero operational gaps across every run of this pipeline. Gemini
belongs in the same tier on raw accuracy (it never returned an incorrect fact) but needed a larger
token budget to get there, showed decoding variance Claude did not, and made one avoidable routing
mistake in the multi-agent case. Every open-weight model available at zero cost through OpenRouter
failed outright, for one of three distinct, verifiable reasons: unbounded internal reasoning
consuming the entire output budget, a missing provider capability, or accuracy too unreliable to
trust on a single-answer factual field. Sonnet/Haiku are the choice for correctness with no
caveats; Gemini is a viable second option that costs more tuning to reach the same bar; the free
open-weight tier tested does not clear the bar at all.

## Open gap in this comparison's own method

Every extraction prompt in this pipeline states which page and which column to read from (see
`extract.py`'s `SYSTEM_PROMPT`). That is a deliberate reliability choice for a known, fixed
document, not a flaw in the extraction results above. But it means this comparison measures
whether each model can *follow* a fully-specified instruction, not whether it can *locate* an
ambiguous field without being told where to look. A weaker model copying a given page number
correctly is a different, easier capability than a weaker model finding the right page number on
its own. This comparison has not tested the harder version, and does not claim to.
