"""Part 1: structured extraction of the 5 required fields.

Deliberately feeds page 16 (not the literally-cited page 5) for the CIT/YoY
fields — page 5 is FY2023 narrative; page 16's Table 2.1 is the actual
Estimated FY2024 vs Revised FY2023 comparison. See README.md's
"Interpretation calls" table, row 2.
"""
from langchain_core.prompts import ChatPromptTemplate
from parser import get_prose_text, get_table_text
from schemas import RevenueExtraction
from llm_config import get_llm

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
figure is still an estimate."""


def build_context() -> str:
    parts = [
        get_prose_text(PDF, [5, 6]),  # Operating Revenue narrative -> tax list
        get_table_text(PDF, 8),  # Table 1.1 -> Latest Actual Fiscal Position
        get_table_text(PDF, 16),  # Table 2.1 -> CIT 2024 + YoY (FY2024 column)
        get_table_text(PDF, 20),  # Table 2.4 -> Total top-ups 2024
    ]
    return "\n\n".join(parts)


def run_extraction(
    model: str | None = None, max_tokens: int = 3000, temperature: float | None = 0
) -> RevenueExtraction:
    llm = get_llm(model=model, max_tokens=max_tokens, temperature=temperature)
    structured_llm = llm.with_structured_output(RevenueExtraction)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{context}"),
    ])
    chain = prompt | structured_llm
    return chain.invoke({"context": build_context()})


if __name__ == "__main__":
    result = run_extraction()
    print(result.model_dump_json(indent=2))
