"""Plain LangChain @tool fallback — works standalone with zero MCP client setup,
per the assignment's own fallback clause. Wraps the same datetime_core logic
used by the MCP server, so both paths are guaranteed to agree.
"""
from langchain_core.tools import tool
from tools.datetime_core import normalize_date as _normalize_date


@tool
def normalize_date(raw_text: str) -> str:
    """Normalizes a date found in raw_text to ISO 8601 (YYYY-MM-DD)."""
    return _normalize_date(raw_text)
