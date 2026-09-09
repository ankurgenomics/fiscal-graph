from typing import Literal
from pydantic import BaseModel, Field


class RevenueExtraction(BaseModel):
    corp_income_tax_2024_billion: float = Field(
        description="Corporate Income Tax, Estimated FY2024, in $ billion. "
        "This is the 'Estimated FY2024' column, NOT the 'Revised FY2023' column."
    )
    corp_income_tax_yoy_pct: float = Field(
        description="YoY %change for Corporate Income Tax, Estimated FY2024 vs "
        "Revised FY2023 (the '%change' column next to the FY2024 figure). "
        "Negative values are shown in parentheses in the source, e.g. (1.2) means -1.2."
    )
    total_topups_2024_billion: float = Field(
        description="Total amount of Top-ups to Endowment and Trust Funds, "
        "Estimated FY2024, in $ billion (source table is in $ million — convert)."
    )
    operating_revenue_taxes: list[str] = Field(
        description="List of all tax/revenue line-item names mentioned in the "
        "'Operating Revenue' section (narrative and/or table), e.g. 'Corporate "
        "Income Tax', 'Personal Income Tax', etc. Names only, no figures."
    )
    latest_actual_fiscal_position_billion: float = Field(
        description="The 'OVERALL FISCAL POSITION' row's value in the column "
        "literally labeled 'Actual'. IMPORTANT: 'Actual' is a specific column "
        "header, distinct from 'Estimated' and 'Revised' columns. Do NOT pick "
        "an Estimated or Revised figure just because it belongs to a more "
        "recent fiscal year — a newer year's Estimated/Revised figure is NOT "
        "'Actual' data. Find the column header spelled 'Actual' specifically, "
        "even if it corresponds to an older fiscal year than other columns shown."
    )


class DateExtraction(BaseModel):
    distribution_date_text: str = Field(
        description="The exact raw sentence/phrase from page 1 stating the "
        "document's distribution date (e.g. 'Distributed on Budget Day: ...')."
    )
    estate_duty_date_text: str = Field(
        description="The exact raw sentence/phrase from page 36 (Glossary, "
        "'Assets Taxes' / Estate Duty entry) stating the date after which "
        "Estate Duty no longer applies."
    )


class ClassifiedDate(BaseModel):
    original_text: str
    normalized_date: str = Field(description="ISO 8601 YYYY-MM-DD")
    status: Literal["Expired", "Upcoming", "Ongoing"]


class ClassifiedDates(BaseModel):
    dates: list[ClassifiedDate]
