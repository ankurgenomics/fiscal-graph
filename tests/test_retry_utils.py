"""Unit tests for the generic structured-output retry helper.

No LLM calls -- a fake chain stands in for a real `prompt | structured_llm`
chain, so these check the retry/give-up logic itself, not any model's behavior.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.exceptions import OutputParserException
from openai import LengthFinishReasonError

sys.path.insert(0, str(Path(__file__).parent.parent))

from retry_utils import invoke_with_retry


class _FakeChain:
    """Raises `error_cls` on its first `fail_times` invocations, then returns
    `success_value`. Records how many times invoke() was called."""

    def __init__(self, fail_times: int, success_value="ok", error_cls=OutputParserException):
        self.fail_times = fail_times
        self.success_value = success_value
        self.error_cls = error_cls
        self.calls = 0

    def invoke(self, input_dict):
        self.calls += 1
        if self.calls <= self.fail_times:
            if self.error_cls is LengthFinishReasonError:
                raise self.error_cls(completion=MagicMock())
            raise self.error_cls("simulated missing required field")
        return self.success_value


def test_succeeds_first_try_without_retrying():
    chain = _FakeChain(fail_times=0)
    result = invoke_with_retry(chain, {"context": "x"})
    assert result == "ok"
    assert chain.calls == 1


def test_recovers_after_one_failure_with_default_retry():
    chain = _FakeChain(fail_times=1)
    result = invoke_with_retry(chain, {"context": "x"})
    assert result == "ok"
    assert chain.calls == 2


def test_raises_after_exhausting_retries():
    chain = _FakeChain(fail_times=5)
    with pytest.raises(OutputParserException):
        invoke_with_retry(chain, {"context": "x"}, max_retries=1)
    assert chain.calls == 2  # 1 initial attempt + 1 retry, then gives up


def test_max_retries_zero_means_no_retry():
    chain = _FakeChain(fail_times=1)
    with pytest.raises(OutputParserException):
        invoke_with_retry(chain, {"context": "x"}, max_retries=0)
    assert chain.calls == 1


def test_recovers_from_length_finish_reason_error():
    """Observed live from an OpenRouter free model that non-deterministically
    exhausted its token budget on hidden reasoning tokens before emitting JSON."""
    chain = _FakeChain(fail_times=1, error_cls=LengthFinishReasonError)
    result = invoke_with_retry(chain, {"context": "x"})
    assert result == "ok"
    assert chain.calls == 2
