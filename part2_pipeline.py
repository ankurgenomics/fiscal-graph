"""Part 2: Data Extraction + Datetime Tool, then Reasoning over Normalised Dates.

Pipeline: extract raw date text (LLM, structured output) -> normalize to ISO
(deterministic tool, via MCP-wrapped or plain-function fallback) -> classify
each date vs. reference date 2024-01-01 (LLM, structured output).
"""
from langchain_core.prompts import ChatPromptTemplate
from parser import get_prose_text
from schemas import DateExtraction, ClassifiedDates
from llm_config import get_llm
from tools.datetime_fallback import normalize_date

PDF = "data/source_budget.pdf"
REFERENCE_DATE = "2024-01-01"

EXTRACTION_SYSTEM_PROMPT = """Extract the exact raw text stating each requested date \
from the given page excerpts. Copy the sentence/phrase verbatim, do not paraphrase."""

CLASSIFICATION_SYSTEM_PROMPT = f"""You are given a list of dates, each with its \
original source text and its normalized ISO date. Classify each one relative to \
the reference date {REFERENCE_DATE} — treat {REFERENCE_DATE} as "today" for this \
task. Do NOT use your own knowledge of the real current date; the only "today" \
that matters here is {REFERENCE_DATE}.

Rules (apply by simple string/date comparison against {REFERENCE_DATE}):
- normalized_date > {REFERENCE_DATE} -> Upcoming (the date is in the future \
relative to {REFERENCE_DATE})
- normalized_date < {REFERENCE_DATE} -> Expired (the date has already passed \
relative to {REFERENCE_DATE})
- the source text describes an ongoing period/state rather than a single past/future \
point (e.g. a range that includes {REFERENCE_DATE}) -> Ongoing

Worked example: normalized_date "2024-02-16" is AFTER reference date {REFERENCE_DATE} \
(Feb comes after Jan in the same year 2024), so its status is Upcoming, not Expired.

Return one classified entry per input date, preserving the original_text and \
normalized_date exactly as given."""


def extract_raw_dates(model: str | None = None, max_tokens: int = 1024) -> DateExtraction:
    llm = get_llm(model=model, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(DateExtraction)
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human", "{context}"),
    ])
    chain = prompt | structured_llm
    context = get_prose_text(PDF, [1, 36])
    return chain.invoke({"context": context})


def classify_dates(normalized: list[dict], model: str | None = None, max_tokens: int = 1024) -> ClassifiedDates:
    llm = get_llm(model=model, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(ClassifiedDates)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CLASSIFICATION_SYSTEM_PROMPT),
        ("human", "{dates}"),
    ])
    chain = prompt | structured_llm
    return chain.invoke({"dates": normalized})


def run_pipeline(model: str | None = None, max_tokens: int = 1024) -> ClassifiedDates:
    raw = extract_raw_dates(model=model, max_tokens=max_tokens)

    normalized = [
        {
            "original_text": raw.distribution_date_text,
            "normalized_date": normalize_date.invoke({"raw_text": raw.distribution_date_text}),
        },
        {
            "original_text": raw.estate_duty_date_text,
            "normalized_date": normalize_date.invoke({"raw_text": raw.estate_duty_date_text}),
        },
    ]

    return classify_dates(normalized, model=model, max_tokens=max_tokens)


if __name__ == "__main__":
    result = run_pipeline()
    print(result.model_dump_json(indent=2))
