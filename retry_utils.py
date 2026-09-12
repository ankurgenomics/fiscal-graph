"""Generic retry helper for structured-output LLM calls.

Model-agnostic and schema-agnostic on purpose: it retries the exact same call
unchanged, never inspecting which model or which field failed. See README.md's
"Cross-model behavior" section for the two distinct failure shapes this has
actually caught in live runs, both from free/weaker models under a strict
schema contract, neither ever seen from Sonnet/Haiku:

- OutputParserException: Gemini silently omitted a required schema field under
  a tight max_tokens budget.
- openai.LengthFinishReasonError: an OpenRouter free model (liquid/lfm-2.5-2.6b)
  non-deterministically spent its entire token budget on a hidden "reasoning"
  phase before emitting any JSON -- same call, same prompt, succeeded cleanly
  moments earlier and failed this way the next time.

A model that succeeds on the first try pays no extra cost; a model that
occasionally doesn't gets one more attempt before the error propagates.
"""
from langchain_core.exceptions import OutputParserException
from openai import LengthFinishReasonError

_RETRYABLE_ERRORS = (OutputParserException, LengthFinishReasonError)


def invoke_with_retry(chain, input_dict: dict, max_retries: int = 1):
    """Invoke a `prompt | structured_llm` chain, retrying on a retryable
    structured-output failure (see module docstring for which ones).

    Raises the final error if every attempt fails.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return chain.invoke(input_dict)
        except _RETRYABLE_ERRORS as e:
            last_error = e
    raise last_error
