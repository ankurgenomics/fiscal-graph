"""Unit tests for the PDF parsing layer, run against the actual source document.

No LLM calls -- these check that parsing pulls the right raw text out of known
pages, which is the thing an LLM call downstream depends on being correct.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import get_prose_text, get_table_text

PDF = str(Path(__file__).parent.parent / "data" / "source_budget.pdf")


def test_page_1_has_distribution_date():
    text = get_prose_text(PDF, [1])
    assert "16 February 2024" in text


def test_page_36_has_estate_duty_date():
    text = get_prose_text(PDF, [36])
    assert "15 February 2008" in text


def test_page_5_6_operating_revenue_heading_present():
    text = get_prose_text(PDF, [5, 6])
    assert "Operating Revenue" in text


def test_page_8_artifact_is_stripped():
    text = get_table_text(PDF, 8)
    # the confirmed rendering artifact -- must not appear in the cleaned output
    assert "22,376" not in text
    assert "23,480,570" not in text
    # the real NIRC figures on the same page must still be present
    assert "22.38" in text
    assert "23.48" in text


def test_page_8_fiscal_position_present():
    text = get_table_text(PDF, 8)
    # both candidate readings of "latest actual fiscal position" must be present:
    # Actual FY2022 (1.72) and Revised FY2023 (3.57), see README's interpretation table
    assert "1.72" in text
    assert "3.57" in text


def test_page_16_fy2024_cit_present():
    text = get_table_text(PDF, 16)
    assert "28.03" in text


def test_page_20_topups_table_present():
    text = get_table_text(PDF, 20)
    assert "20,352" in text
    assert "Future Energy Fund" in text
