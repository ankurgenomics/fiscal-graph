"""Part 2: Data Extraction + Datetime Tool, then Reasoning over Normalised Dates.

Pipeline: extract raw date text (LLM, structured output) -> normalize to ISO via
REAL LLM-driven tool calling (.bind_tools()), routed through the local MCP server
as primary (per the assignment's literal preference order), falling back to the
plain function only if the MCP connection itself fails -> classify each date vs.
reference date 2024-01-01 (LLM, structured output).
"""
import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from parser import get_prose_text
from schemas import DateExtraction, ClassifiedDates
from llm_config import get_llm
from tools.datetime_fallback import normalize_date as _fallback_normalize_date
from tools.mcp_client import get_mcp_normalize_tool

PDF = "data/source_budget.pdf"
REFERENCE_DATE = "2024-01-01"

EXTRACTION_SYSTEM_PROMPT = """Extract the exact raw text stating each requested date \
from the given page excerpts. Copy the sentence/phrase verbatim, do not paraphrase."""

TOOL_CALLING_SYSTEM_PROMPT = """You have access to a normalize_date tool that converts \
a date mentioned in raw text into ISO 8601 (YYYY-MM-DD) format. Call the tool with the \
exact raw text given to you, so it can locate and normalize the date within it."""

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


def _unwrap_tool_result(result) -> str:
    """MCP tool results come back as a list of content blocks
    ([{'type': 'text', 'text': '2024-02-16', ...}]); the plain fallback tool
    returns the plain string directly. Normalize both to a plain string so
    downstream code doesn't care which path ran."""
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict) and block.get("type") == "text":
                return block["text"]
        raise ValueError(f"Could not extract text from MCP tool result: {result!r}")
    return result


async def _get_normalize_tool():
    """MCP is the assignment's stated primary path; the plain function is
    explicitly a fallback for when MCP 'is not able to be implemented' — since we
    have a working MCP server, route through it by default. The except clause is
    scoped ONLY to the MCP connection/tool-loading call, not any downstream logic,
    so a real bug elsewhere can't be silently misattributed to 'MCP unavailable'.
    """
    try:
        tool = await get_mcp_normalize_tool()
        return tool, "mcp"
    except Exception as e:
        print(f"[normalize_dates_via_tool_calling] MCP unavailable ({e!r}), using fallback tool.")
        return _fallback_normalize_date, "fallback"


async def normalize_dates_via_tool_calling_async(
    raw_texts: list[str], model: str | None = None, max_tokens: int = 512
) -> list[str]:
    """Real function/tool calling: the LLM decides to call normalize_date with its own
    extracted arguments (via .bind_tools()), rather than Python invoking the tool
    directly. Single-turn per date — the tool's ISO output is the final answer needed
    at this step, no further model reasoning required on the result.

    Returns the plain list of normalized ISO dates — this is the assignment's literal
    Step 1 deliverable ("your final output for this step should be a list of these
    normalized dates"), returned/printed on its own before classification consumes it.
    """
    llm = get_llm(model=model, max_tokens=max_tokens)
    tool, source = await _get_normalize_tool()
    llm_with_tools = llm.bind_tools([tool])
    print(f"[normalize_dates_via_tool_calling] tool source: {source}")

    normalized_dates = []
    for raw_text in raw_texts:
        messages = [
            SystemMessage(content=TOOL_CALLING_SYSTEM_PROMPT),
            HumanMessage(content=raw_text),
        ]
        ai_msg = llm_with_tools.invoke(messages)
        if not ai_msg.tool_calls:
            raise RuntimeError(f"Model did not call normalize_date for: {raw_text!r}")
        tool_call = ai_msg.tool_calls[0]
        raw_result = await tool.ainvoke(tool_call["args"]) if source == "mcp" else tool.invoke(tool_call["args"])
        normalized_dates.append(_unwrap_tool_result(raw_result))
    return normalized_dates



def classify_dates(normalized: list[dict], model: str | None = None, max_tokens: int = 1024) -> ClassifiedDates:
    llm = get_llm(model=model, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(ClassifiedDates)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CLASSIFICATION_SYSTEM_PROMPT),
        ("human", "{dates}"),
    ])
    chain = prompt | structured_llm
    return chain.invoke({"dates": normalized})


async def run_pipeline(model: str | None = None, max_tokens: int = 1024) -> ClassifiedDates:
    """Async — call with `await run_pipeline(...)` in a notebook (Jupyter already
    runs an event loop; asyncio.run() would fail there). For scripts/CLI use, call
    run_pipeline_sync(...) instead."""
    raw = extract_raw_dates(model=model, max_tokens=max_tokens)
    raw_texts = [raw.distribution_date_text, raw.estate_duty_date_text]

    # Step 1 output, per the assignment's literal wording: "a list of these normalized dates"
    normalized_dates = await normalize_dates_via_tool_calling_async(raw_texts, model=model, max_tokens=512)
    print("Step 1 output (list of normalized dates):", normalized_dates)

    paired = [
        {"original_text": t, "normalized_date": d}
        for t, d in zip(raw_texts, normalized_dates)
    ]
    return classify_dates(paired, model=model, max_tokens=max_tokens)


def run_pipeline_sync(model: str | None = None, max_tokens: int = 1024) -> ClassifiedDates:
    """Sync entry point for scripts/CLI use — do not call this from a notebook cell."""
    return asyncio.run(run_pipeline(model=model, max_tokens=max_tokens))


if __name__ == "__main__":
    result = run_pipeline_sync()
    print(result.model_dump_json(indent=2))
