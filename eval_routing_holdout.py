"""Held-out routing eval for Part 3's supervisor.

SUPERVISOR_PROMPT's own worked examples use "Skills Development Fund" and
"National Productivity Fund"; the four DEMO_QUERIES in part3_supervisor.py use
"GST Voucher Fund" and "Future Energy Fund". None of those four fund names
appear in any query below, and none of these queries appear anywhere in
SUPERVISOR_PROMPT. This is what makes this a genuine test of whether routing
generalizes, rather than a repeat of queries the supervisor has already seen.

Usage: python eval_routing_holdout.py
"""
import json

from part3_supervisor import build_supervisor, run_query

HELD_OUT_QUERIES = {
    "R1 (revenue-only)": (
        "What is the total Operating Revenue collected in FY2024?",
        {"revenue_agent"},
    ),
    "R2 (revenue-only)": (
        "How much did Personal Income Tax bring in this year, and how does that "
        "compare to last year?",
        {"revenue_agent"},
    ),
    "E1 (expenditure-only)": (
        "How much is allocated to the Public Transport Fund, and what will it be used for?",
        {"expenditure_agent"},
    ),
    "E2 (expenditure-only)": (
        "What is the purpose of the Legal Aid Fund top-up?",
        {"expenditure_agent"},
    ),
    "E3 (expenditure-only)": (
        "How much is the Financial Sector Development Fund receiving this year?",
        {"expenditure_agent"},
    ),
    "D1 (dual)": (
        "What is the largest source of tax revenue, and how much is being added "
        "to the National Research Fund?",
        {"revenue_agent", "expenditure_agent"},
    ),
    "D2 (dual)": (
        "Summarize government revenue streams and explain the purpose of the "
        "Edusave Endowment Fund top-up.",
        {"revenue_agent", "expenditure_agent"},
    ),
    "D3 (dual)": (
        "How much GST revenue was collected, and what is the Majulah Package Fund for?",
        {"revenue_agent", "expenditure_agent"},
    ),
}


AGENT_NAMES = {"revenue_agent", "expenditure_agent"}


if __name__ == "__main__":
    app = build_supervisor()
    results = {}
    correct = 0
    for label, (query, expected) in HELD_OUT_QUERIES.items():
        answer, trace = run_query(app, query)
        # trace actors include tool/transfer names (e.g. revenue_context,
        # transfer_to_revenue_agent) alongside the real agent names -- filter
        # down to just the two real agents before comparing.
        raw_actors = set(t["actor"] for t in trace) - {"user", "supervisor"}
        actual = raw_actors & AGENT_NAMES
        match = actual == expected
        correct += match
        print(f"{'PASS' if match else 'FAIL'}  {label}: expected {sorted(expected)}, got {sorted(actual)}")
        results[label] = {
            "query": query,
            "expected_agents": sorted(expected),
            "actual_agents": sorted(actual),
            "match": match,
            "answer": answer,
        }

    print(f"\n{correct}/{len(HELD_OUT_QUERIES)} correct on held-out routing")
    with open("eval_routing_holdout_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote eval_routing_holdout_results.json")
