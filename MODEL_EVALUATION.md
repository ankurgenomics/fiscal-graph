# Model Evaluation

Eight models were evaluated against this pipeline's actual requirement: a schema-validated
financial extraction, returned reliably, within a bounded token budget. Claude Sonnet and Haiku
are the models used for the verified results in this repository, selected on that evidence.

## Method

Every part of this pipeline runs through one call site, `llm_config.get_llm(model, max_tokens,
temperature)`. Swapping models changes one string argument; no other code changes. This makes the
comparison a controlled test: identical prompts, identical Pydantic schemas, identical retry
logic, identical token budgets per model class, with only the model itself varied.

Three closed models (Sonnet, Haiku, Gemini) were run against the full pipeline. Five free
open-weight models, available through OpenRouter, were run against Part 1's structured
extraction. OpenRouter's free tier was queried directly, 19 models available at the time of
testing; DeepSeek, Llama, Qwen, and Mistral were not among them.

## Results

| Model | Class | Outcome | Detail |
|---|---|---|---|
| `google/gemma-4-31b-it:free` | Open-weight, free | Rate-limited | Shared free-tier capacity pool returned HTTP 429, independent of this pipeline's usage. |
| `nvidia/nemotron-3-super-120b-a12b:free` | Open-weight, free (reasoning) | No structured output | Spends its token budget on internal reasoning before emitting JSON; unbounded by design regardless of the budget given. |
| `nex-agi/nex-n2.5-pro:free` | Open-weight, free (reasoning) | No structured output | Same behavior: 7,703 of 8,000 tokens spent on reasoning before truncation. |
| `inclusionai/ling-3.0-flash-fin:free` | Open-weight, free (finance-tuned) | Not runnable | Backing provider does not support structured outputs for this model, independent of prompt or budget. |
| `liquid/lfm-2.5-2.6b:free` | Open-weight, free (2.6B params) | Ran, inconsistent results | Same question, three identical calls, three different numeric answers to a fact with one correct value in the source document. |
| `gemini-3.6-flash` (Google) | Closed API, direct | Correct on content | See Gemini below for the three measured differences from Sonnet/Haiku. |
| `claude-haiku-4-5` (Anthropic) | Closed API, direct | Correct on every field, every run | One interpretation difference from Sonnet on an inherently ambiguous field, a reading difference, not an error. |
| `claude-sonnet-5` (Anthropic) | Closed API, direct | Correct on every field, every run | Correct multi-agent routing after one prompt refinement. |

## Gemini

Every documented entry point (`run_all.py`, `part3_supervisor.py`, `api.py`) resolves its model
through `llm_config.primary_model()`, which reads the `MODEL_OVERRIDE` environment variable before
falling back to the Haiku/Sonnet default. Setting it runs the entire pipeline on a different model
with no code change:

```bash
MODEL_OVERRIDE=gemini-3.6-flash python run_all.py
```

Run this way, live, end to end:

| Part | Result | vs. the documented Haiku/Sonnet result |
|---|---|---|
| Part 1 | 4 of 5 fields exact. Fiscal position (the field with three candidate columns) correct. | Tax list count varied across separate runs (10, 11, and 12 items observed across different sessions); Sonnet and Haiku each hold one count consistently across repeats. |
| Part 2 | Exact match, character for character | No difference observed |
| Part 3, the 4 demo queries | 4 of 4 routed correctly | Matches Sonnet exactly; an over-routing case documented in an earlier version of this evaluation did not reproduce against the current `SUPERVISOR_PROMPT` |
| Part 3, held-out eval (8 queries never seen in the prompt) | 4 of 8 confirmed correct, zero failures observed; the remaining 4 were never reached | Cut short by the quota limitation below, not by any wrong answer |

Three measured differences from Sonnet/Haiku, unchanged from prior testing:

1. **Token budget.** Needs 6,000-8,000 tokens to reliably complete the schema, versus 3,000 for
   Sonnet and Haiku on the identical task.
2. **Run-to-run consistency.** The one field already documented as genuinely ambiguous
   (`operating_revenue_taxes`) is the only field where Gemini's answer changes between runs.
   Every other field, every run observed, has been correct.
3. **`temperature` handling.** Accepted without erroring, then silently ignored; the API reports
   this model "uses fixed sampling defaults."

**A fourth, operational limitation, confirmed directly**: Google's free-tier quota
(`generativelanguage.googleapis.com/generate_content_free_tier_requests`, 20 requests/day for this
model) is scoped **per Google Cloud project, not per API key**. Seven separate API keys were
created across testing; all seven drew from the same daily pool. A fresh key does not grant fresh
quota if it belongs to the same project as a key already in use that day. This is not a code
limitation, and does not apply to Anthropic's keys (Parts 1-3's default), but it is the practical
reason a full run against Gemini, including the held-out eval, could not be completed inside a
single day on the free tier.

## Failure categories

The free-tier results split into two categories:

**Contract failures.** The model cannot produce structured output at all, regardless of
prompting: `nemotron-3-super-120b` and `nex-n2.5-pro` spend an unbounded token budget on internal
reasoning before answering, and `ling-3.0-flash-fin`'s provider does not implement structured
outputs. No prompt or retry policy changes this.

**Capability failures.** The model returns a validly-shaped answer with wrong or unstable
content. `liquid/lfm-2.5-2.6b` is the one free model that reached this category rather than
failing outright.

A shared retry wrapper, doubled token budgets, and a few-shot worked example were applied
uniformly across every model before recording these results. The two contract-failure models are
unaffected by any of it, since the failure happens before the model produces an answer at all.

## Conclusion

Sonnet and Haiku returned zero wrong answers across every run of this pipeline. Gemini matched
them on accuracy with more tuning required to get there. Every free open-weight model tested
failed to reliably clear this pipeline's structured-output requirement. Sonnet and Haiku are used
for the verified results on that basis.
