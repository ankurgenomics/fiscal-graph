"""Shared date-normalization logic, deliberately deterministic (not LLM-based) —
once a raw date string is located in the document, converting "16 February 2024"
to "2024-02-16" is a parsing problem, not a reasoning problem. Both the MCP tool
and the plain-function fallback wrap this single implementation, so there is no
risk of the two paths silently disagreeing.
"""
from dateutil import parser as dateutil_parser


def normalize_date(raw_text: str) -> str:
    """Extracts and normalizes a date found anywhere in raw_text to ISO YYYY-MM-DD."""
    dt = dateutil_parser.parse(raw_text, fuzzy=True)
    return dt.date().isoformat()
