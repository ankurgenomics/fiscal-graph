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

Gemini matched Sonnet and Haiku on content: every fact it returned across all three parts, once
given enough token budget, was correct. It differed on three measured, specific points:

1. **Token budget.** Needed 6,000-8,000 tokens to reliably complete the schema, versus 3,000 for
   Sonnet and Haiku on the identical task.
2. **Run-to-run consistency.** Its operating-revenue tax list varied between a 12-item and a
   10-item answer across repeated identical calls. Sonnet and Haiku each held one reading
   consistently across repeats.
3. **Routing precision.** Over-routed once across four Part 3 demo queries, calling both agents
   where one was relevant. The final answer was still correct.

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
