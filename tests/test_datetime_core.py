"""Unit tests for the deterministic date-normalization logic.

No LLM calls, no API keys needed -- normalize_date is plain string parsing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.datetime_core import normalize_date


def test_distribution_date():
    assert normalize_date("Distributed on Budget Day: 16 February 2024") == "2024-02-16"


def test_estate_duty_date():
    result = normalize_date("Estate Duty does not apply to a person who dies after 15 February 2008.")
    assert result == "2008-02-15"


def test_date_embedded_in_longer_sentence():
    result = normalize_date("The report, published on 1 January 2020, covers last year.")
    assert result == "2020-01-01"


def test_iso_input_stays_iso():
    assert normalize_date("2024-02-16") == "2024-02-16"
