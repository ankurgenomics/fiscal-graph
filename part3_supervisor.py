"""Part 3: Multi-Agent Supervisor.

Wires the Revenue Agent and Expenditure Agent (agents.py) under a LangGraph
supervisor. output_mode='full_history' is used deliberately (not the default
'last_message') so the trace retains sub-agents' actual tool calls, not just
their one-line final answers -- needed for the assignment's "clear trace of the
supervisor's decision-making process" requirement.
"""
from langgraph_supervisor import create_supervisor
from agents import build_revenue_agent, build_expenditure_agent
from llm_config import get_llm, SONNET_MODEL

SUPERVISOR_PROMPT = """You are a supervisor managing two specialized agents:
- revenue_agent: specializes in government revenue (taxes, collections).
- expenditure_agent: specializes in government spending (funds, expenditure figures).

For each user query, delegate to whichever agent(s) are relevant -- only the
agents actually needed to answer the question, not both by default. If the
query has both a revenue component and an expenditure component, delegate to
both and synthesize their responses into one comprehensive final answer that
directly addresses every part of the original question. Do not answer from
your own knowledge -- always delegate to the agents, who have access to the
source document."""


def build_supervisor(agent_model: str | None = None, supervisor_model: str | None = None):
    revenue_agent = build_revenue_agent(model=agent_model)
    expenditure_agent = build_expenditure_agent(model=agent_model)
    # temperature omitted (None): claude-sonnet-5 rejects the parameter entirely, even 0
    supervisor_llm = get_llm(model=supervisor_model or SONNET_MODEL, max_tokens=4096, temperature=None)

    graph = create_supervisor(
        agents=[revenue_agent, expenditure_agent],
        model=supervisor_llm,
        prompt=SUPERVISOR_PROMPT,
        output_mode="full_history",
    )
    return graph.compile()


def _extract_text(content) -> str:
    """Message content is sometimes a plain string, sometimes a list of content
    blocks (e.g. a 'thinking' block alongside a 'text' block, from extended
    thinking) -- extracts just the text regardless of shape."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return str(content)


def run_query(app, query: str):
    """Runs a query and returns (final_answer, trace_steps).

    output_mode='full_history' means each streamed step re-emits the ENTIRE
    accumulated message history so far, not just new deltas -- so we only keep
    the LAST step's message list (which already contains the complete, ordered
    history from question to final synthesis) rather than appending every step,
    which would duplicate every message once per step it appeared in.
    """
    final_state = None
    for step in app.stream({"messages": [{"role": "user", "content": query}]}):
        final_state = step

    last_node_output = list(final_state.values())[0]
    all_messages = last_node_output["messages"]

    trace_steps = []
    for m in all_messages:
        msg_type = type(m).__name__
        # skip raw tool-call-request AIMessages with no text content (the
        # ToolMessage right after already shows what the tool call did)
        content = getattr(m, "content", None)
        if msg_type == "AIMessage" and not content:
            continue
        trace_steps.append({
            "type": msg_type,
            "actor": getattr(m, "name", None) or "user",
            "content": content,
        })

    final_answer = _extract_text(all_messages[-1].content)
    return final_answer, trace_steps


def print_trace(trace_steps: list[dict]) -> None:
    for i, t in enumerate(trace_steps, 1):
        content = t["content"]
        if isinstance(content, list):  # tool-call content blocks
            preview = " | ".join(
                f"{c.get('type', '?')}: {str(c.get('text') or c.get('input') or c)[:120]}"
                for c in content if isinstance(c, dict)
            )
        else:
            preview = str(content)[:200]
        print(f"[{i}] {t['type']:<14} actor={t['actor']:<24} {preview}")


DEMO_QUERIES = {
    "Q1 (assignment's exact query, dual-agent)":
        "What are the key government revenue streams, and how will the Budget for the Future Energy Fund be supported?",
    "Q2 (revenue-only, tests selective routing)":
        "What is the largest single source of government revenue?",
    "Q3 (expenditure-only, tests selective routing)":
        "How much is being spent on the GST Voucher Fund top-up, and why?",
    "Q4 (second dual-agent query, different phrasing)":
        "What is the largest source of tax revenue, and separately, what specific purpose will the Future Energy Fund infrastructure spending serve according to the budget document?",
}


if __name__ == "__main__":
    import json
    app = build_supervisor()
    all_results = {}
    for label, query in DEMO_QUERIES.items():
        print(f"\n{'=' * 80}\n{label}\nQuery: {query}\n{'=' * 80}")
        answer, trace = run_query(app, query)
        print("\nTRACE:")
        print_trace(trace)
        print("\nAGENTS INVOKED:", sorted(set(t["actor"] for t in trace) - {"user", "supervisor"}))
        print("\nFINAL ANSWER:\n", answer)
        all_results[label] = {"query": query, "trace": trace, "final_answer": answer}

    with open("trace.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print("\nWrote trace.json with all 4 demo queries.")
