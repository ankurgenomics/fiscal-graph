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
        description="List of TAX names only, mentioned in the 'Operating Revenue' "
        "section (narrative and/or table), e.g. 'Corporate Income Tax', 'Personal "
        "Income Tax', etc. The table version of this section also includes 'Fees "
        "and Charges' and 'Others' under the same header — EXCLUDE both, neither "
        "is a tax. Names only, no figures."
    )
    latest_actual_fiscal_position_billion: float = Field(
        description="The 'OVERALL FISCAL POSITION' row's value in page 8's "
        "'Revised FY2023' column — the most recent fiscal year with real, "
        "collected data behind it rather than a forward projection. Use "
        "'Revised FY2023' specifically, NOT 'Actual FY2022' (a year older) "
        "and NOT 'Estimated FY2023' (the original forecast, since revised). "
        "Page 16's 'Estimated FY2024' does not qualify either, since it is "
        "still a forecast, not realized data."
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
