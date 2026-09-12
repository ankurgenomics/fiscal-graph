"""Part 1: structured extraction of the 5 required fields.

Deliberately feeds page 16 (not the literally-cited page 5) for the CIT/YoY
fields — page 5 is FY2023 narrative; page 16's Table 2.1 is the actual
Estimated FY2024 vs Revised FY2023 comparison. See README.md's
"Interpretation calls" table, row 2.
"""
import math
from collections import Counter
from langchain_core.prompts import ChatPromptTemplate
from parser import get_prose_text, get_table_text
from schemas import RevenueExtraction
from llm_config import get_llm
from retry_utils import invoke_with_retry

PDF = "data/source_budget.pdf"

SYSTEM_PROMPT = """You are extracting structured financial data from Singapore's \
FY2024 Analysis of Revenue and Expenditure. You will be given several excerpts, \
each labeled with its source page number. Pay close attention to which fiscal \
year column each figure belongs to — the document contains both 'Revised FY2023' \
and 'Estimated FY2024' columns side by side in its tables, and these are \
different numbers. Only use 'Estimated FY2024' / 'FY2024' figures for any field \
asking about 2024. Figures in parentheses, e.g. (1.2), are negative: -1.2.

Note: both page 8 and page 16 contain a row named 'OVERALL FISCAL POSITION' \
with different values in each — these are two different tables comparing \
different fiscal year pairs. For the 'latest_actual_fiscal_position_billion' \
field specifically, use PAGE 8's table only, and within page 8, the 'Revised \
FY2023' column — the most recent fiscal year backed by real collected data, \
not a forecast. This is NOT the 'Actual' column (that is FY2022, a year \
older) and NOT 'Estimated FY2023' (the original forecast, superseded by the \
revision). Ignore page 16 entirely for this field, since its only FY2024 \
figure is still an estimate.

Worked example for operating_revenue_taxes: if a table lists "Corporate Income \
Tax: $28.03", "Personal Income Tax: $17.55", "Fees and Charges: $4.12", and \
"Others: $1.02" all under the same "OPERATING REVENUE" header, the correct list \
is ["Corporate Income Tax", "Personal Income Tax"] -- Fees and Charges and \
Others are excluded because neither is a tax, even though both appear under the \
same section header as the real tax rows.

Every field in the schema is required. If a value is genuinely unclear from the \
given context, give your best-supported reading based on the rules above rather \
than omitting the field."""


def build_context() -> str:
    parts = [
        get_prose_text(PDF, [5, 6]),  # Operating Revenue narrative -> tax list
        get_table_text(PDF, 8),  # Table 1.1 -> Latest Actual Fiscal Position
        get_table_text(PDF, 16),  # Table 2.1 -> CIT 2024 + YoY (FY2024 column)
        get_table_text(PDF, 20),  # Table 2.4 -> Total top-ups 2024
    ]
    return "\n\n".join(parts)


def run_extraction(
    model: str | None = None, max_tokens: int = 8000, temperature: float | None = 0
) -> RevenueExtraction:
    llm = get_llm(model=model, max_tokens=max_tokens, temperature=temperature)
    structured_llm = llm.with_structured_output(RevenueExtraction)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{context}"),
    ])
    chain = prompt | structured_llm
    return invoke_with_retry(chain, {"context": build_context()})


SELF_CHECK_SYSTEM_PROMPT = """You are reviewing a draft structured extraction against its \
source context. If every field is present, correctly sourced, and consistent with the rules \
below, return it unchanged. If any field is missing, wrong, or unsupported by the context, \
correct it.

- 'Estimated FY2024' / 'FY2024' figures only for any field asking about 2024, never 'Revised \
FY2023'.
- latest_actual_fiscal_position_billion: page 8's 'Revised FY2023' column specifically.
- operating_revenue_taxes: tax names only -- exclude 'Fees and Charges' and 'Others'.

Return the complete, corrected object."""


def self_check_extraction(
    result: RevenueExtraction,
    context: str,
    model: str | None = None,
    temperature: float | None = 0,
    max_tokens: int = 8000,
) -> RevenueExtraction:
    """Second-pass self-refine: hands the draft result back to the model alongside the
    original source context and asks it to verify or correct itself. Generic -- it isn't
    scoped to any one model's known failure mode, so it also catches mistakes a strong
    model makes, not just the ones already observed on weaker ones. Opt-in: costs one
    extra LLM call, so it is never invoked by run_extraction() itself."""
    llm = get_llm(model=model, max_tokens=max_tokens, temperature=temperature)
    structured_llm = llm.with_structured_output(RevenueExtraction)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SELF_CHECK_SYSTEM_PROMPT),
        ("human", "Source context:\n{context}\n\nDraft answer to review:\n{draft}"),
    ])
    chain = prompt | structured_llm
    return invoke_with_retry(
        chain, {"context": context, "draft": result.model_dump_json()}
    )


def run_extraction_verified(model: str | None = None, **kwargs) -> RevenueExtraction:
    """run_extraction() followed by one self_check_extraction() pass. Opt-in wrapper --
    doubles the LLM calls for one extraction, so it is not the default entry point."""
    result = run_extraction(model=model, **kwargs)
    return self_check_extraction(result, build_context(), model=model)


def run_extraction_consistent(
    n: int = 3, model: str | None = None, **kwargs
) -> tuple[RevenueExtraction, list[str]]:
    """Self-consistency voting: runs run_extraction() n times and merges the results.
    Scalar fields take the value most runs agreed on. operating_revenue_taxes -- the one
    field with a documented interpretation split (see README's Cross-model behavior
    section) -- keeps any item that appeared in at least half the runs, and disagreements
    are returned alongside the result instead of silently discarded. Opt-in: costs n LLM
    calls instead of 1, so it is not the default entry point.

    Returns (result, disagreement_notes).
    """
    runs = [run_extraction(model=model, **kwargs) for _ in range(n)]
    notes = []

    def majority_scalar(field: str):
        values = [getattr(r, field) for r in runs]
        value, count = Counter(values).most_common(1)[0]
        if count < n:
            notes.append(f"{field}: split across runs {values}, took majority {value!r}")
        return value

    tax_lists = [set(r.operating_revenue_taxes) for r in runs]
    item_counts = Counter(item for taxes in tax_lists for item in taxes)
    threshold = math.ceil(n / 2)
    merged_taxes = [item for item, count in item_counts.items() if count >= threshold]
    contested = [item for item, count in item_counts.items() if 0 < count < n]
    if contested:
        notes.append(f"operating_revenue_taxes: contested items {contested}")

    merged = RevenueExtraction(
        corp_income_tax_2024_billion=majority_scalar("corp_income_tax_2024_billion"),
        corp_income_tax_yoy_pct=majority_scalar("corp_income_tax_yoy_pct"),
        total_topups_2024_billion=majority_scalar("total_topups_2024_billion"),
        operating_revenue_taxes=merged_taxes,
        latest_actual_fiscal_position_billion=majority_scalar(
            "latest_actual_fiscal_position_billion"
        ),
    )
    return merged, notes


if __name__ == "__main__":
    result = run_extraction()
    print(result.model_dump_json(indent=2))
