"""Part 3: Revenue Agent and Expenditure Agent.

Each agent gets a single no-argument tool returning its pre-scoped page context
(reusing parser.py, same pattern as Parts 1-2), not a generic full-document search
tool — deliberate proportionality: this is a 37-page document with a known, fixed
page-to-topic mapping (the same pages verified in Part 1, see README.md), so
embedding-based RAG would be over-engineering relative to what this part is
actually graded on: the supervisor's routing and synthesis behavior, not
retrieval sophistication.
"""
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from parser import get_prose_text, get_table_text
from llm_config import get_llm, HAIKU_MODEL

PDF = "data/source_budget.pdf"


@tool
def revenue_context() -> str:
    """Returns source document context on government revenue: Operating Revenue
    narrative, its FY2023 breakdown chart, and the FY2024 Table 2.1 figures."""
    return "\n\n".join([
        get_prose_text(PDF, [5, 6]),
        get_prose_text(PDF, [9]),
        get_table_text(PDF, 16),
    ])


@tool
def expenditure_context() -> str:
    """Returns source document context on government expenditure: Total Expenditure
    narrative, spending-by-ministry chart, Special Transfers/Fund top-up narrative
    (including the Future Energy Fund's purpose), and the Table 2.4 top-ups table."""
    return "\n\n".join([
        get_prose_text(PDF, [14]),
        get_prose_text(PDF, [17]),
        get_prose_text(PDF, [18]),
        get_table_text(PDF, 20),
    ])


REVENUE_AGENT_PROMPT = """You are the Revenue Agent. You specialize in identifying \
and extracting information on government revenue: tax categories, collection \
amounts, and revenue trends. Use your revenue_context tool to answer questions \
about government revenue. Cite specific figures from the context, do not estimate \
or invent numbers."""

EXPENDITURE_AGENT_PROMPT = """You are the Expenditure Agent. You specialize in \
finding and analyzing information on government spending, including specific funds \
and sums to the correct figure. Use your expenditure_context tool to answer \
questions about government expenditure and fund allocations. Cite specific figures \
from the context, do not estimate or invent numbers."""


def build_revenue_agent(model: str | None = None, temperature: float | None = 0):
    llm = get_llm(model=model or HAIKU_MODEL, max_tokens=2048, temperature=temperature)
    return create_react_agent(
        model=llm,
        tools=[revenue_context],
        prompt=REVENUE_AGENT_PROMPT,
        name="revenue_agent",
    )


def build_expenditure_agent(model: str | None = None, temperature: float | None = 0):
    llm = get_llm(model=model or HAIKU_MODEL, max_tokens=2048, temperature=temperature)
    return create_react_agent(
        model=llm,
        tools=[expenditure_context],
        prompt=EXPENDITURE_AGENT_PROMPT,
        name="expenditure_agent",
    )
