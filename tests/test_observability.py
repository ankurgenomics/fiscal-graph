"""Unit tests for the structured logging wrapper.

No LLM calls -- timed_call wraps arbitrary code, tested here with plain functions.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from observability import timed_call


def test_logs_start_and_done_on_success(caplog):
    with caplog.at_level("INFO", logger="fiscal_graph"):
        with timed_call("test_op"):
            pass
    messages = [r.message for r in caplog.records]
    assert any("test_op: start" in m for m in messages)
    assert any("test_op: done in" in m for m in messages)


def test_logs_failure_and_reraises(caplog):
    with caplog.at_level("INFO", logger="fiscal_graph"):
        with pytest.raises(ValueError):
            with timed_call("test_op_fail"):
                raise ValueError("boom")
    messages = [r.message for r in caplog.records]
    assert any("test_op_fail: failed after" in m and "boom" in m for m in messages)
