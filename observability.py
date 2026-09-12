"""Structured local logging for LLM call sites.

This is not a tracing platform (no LangSmith/Phoenix integration -- that needs its
own account and API key, out of scope here). It's the minimum real thing: one log
line per named call, with elapsed time and outcome, so a run's latency and failure
rate are visible without re-reading the model's raw output. `timed_call` is a
context manager, used at each part's top-level entry point (see extract.py,
part2_pipeline.py, part3_supervisor.py).
"""
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("fiscal_graph")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


@contextmanager
def timed_call(name: str):
    """Logs `name` start, then one INFO line with elapsed seconds on success or one
    ERROR line with elapsed seconds and the exception on failure. Re-raises whatever
    the wrapped block raised; never swallows an error."""
    start = time.monotonic()
    logger.info("%s: start", name)
    try:
        yield
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("%s: failed after %.2fs (%s: %s)", name, elapsed, type(e).__name__, e)
        raise
    else:
        elapsed = time.monotonic() - start
        logger.info("%s: done in %.2fs", name, elapsed)
