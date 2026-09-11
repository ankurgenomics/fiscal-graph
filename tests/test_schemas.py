"""Unit tests for the Pydantic schemas.

No LLM calls -- these check the schemas reject bad shapes, not that a model
produces good ones.
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import RevenueExtraction, DateExtraction, ClassifiedDate, ClassifiedDates


def test_revenue_extraction_valid():
    r = RevenueExtraction(
        corp_income_tax_2024_billion=28.03,
        corp_income_tax_yoy_pct=-1.2,
        total_topups_2024_billion=20.352,
        operating_revenue_taxes=["Corporate Income Tax", "Personal Income Tax"],
        latest_actual_fiscal_position_billion=1.72,
    )
    assert r.corp_income_tax_2024_billion == 28.03
    assert len(r.operating_revenue_taxes) == 2


def test_revenue_extraction_rejects_missing_field():
    with pytest.raises(ValidationError):
        RevenueExtraction(corp_income_tax_2024_billion=28.03)


def test_revenue_extraction_rejects_wrong_type_for_float_field():
    with pytest.raises(ValidationError):
        RevenueExtraction(
            corp_income_tax_2024_billion="not a number",
            corp_income_tax_yoy_pct=-1.2,
            total_topups_2024_billion=20.352,
            operating_revenue_taxes=["Corporate Income Tax"],
            latest_actual_fiscal_position_billion=1.72,
        )


def test_classified_date_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ClassifiedDate(original_text="x", normalized_date="2024-01-01", status="Cancelled")


def test_classified_date_accepts_each_valid_status():
    for status in ("Expired", "Upcoming", "Ongoing"):
        d = ClassifiedDate(original_text="x", normalized_date="2024-01-01", status=status)
        assert d.status == status


def test_classified_dates_wraps_a_list():
    dates = ClassifiedDates(dates=[
        ClassifiedDate(original_text="a", normalized_date="2024-02-16", status="Upcoming"),
        ClassifiedDate(original_text="b", normalized_date="2008-02-15", status="Expired"),
    ])
    assert len(dates.dates) == 2


def test_date_extraction_requires_both_fields():
    with pytest.raises(ValidationError):
        DateExtraction(distribution_date_text="only one field given")
