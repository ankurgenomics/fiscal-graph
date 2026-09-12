"""Discovery-vs-constrained extraction comparison for Part 1.

extract.py's SYSTEM_PROMPT names the exact page and column for the two fields
this repo documents as ambiguous (latest_actual_fiscal_position_billion,
corp_income_tax_2024_billion / corp_income_tax_yoy_pct). That is a deliberate
reliability choice for a known document, but it also means the constrained
prompt tests whether a model can follow a fully-specified instruction, not
whether it can locate the right figure unaided.

This script runs the same five fields through a second, discovery prompt that
gives the same page excerpts but never says which page or column to use for
the ambiguous fields, and compares both against the same ground truth.

Usage: python eval_discovery.py [--model MODEL_ID] [--repeats N]
"""
import argparse
import json

from extract import run_extraction, build_context, SYSTEM_PROMPT
from llm_config import HAIKU_MODEL
from evaluate import GROUND_TRUTH, GROUND_TRUTH_TAX_LIST, NUMERIC_TOLERANCE

DISCOVERY_SYSTEM_PROMPT = """You are extracting structured financial data from Singapore's \
FY2024 Analysis of Revenue and Expenditure. You will be given several excerpts, each labeled \
with its source page number. Figures in parentheses, e.g. (1.2), are negative: -1.2.

Extract the value that best answers each field's description from the given context, using \
your own judgment about which figures and which page are the correct ones. Every field in the \
schema is required."""


def _check(extracted: dict) -> dict:
    results = {}
    for field, expected in GROUND_TRUTH.items():
        actual = extracted[field]
        results[field] = {
            "got": actual,
            "expected": expected,
            "match": abs(actual - expected) < NUMERIC_TOLERANCE,
        }
    tax_match = set(extracted["operating_revenue_taxes"]) == set(GROUND_TRUTH_TAX_LIST)
    results["operating_revenue_taxes"] = {
        "got": sorted(extracted["operating_revenue_taxes"]),
        "expected": sorted(GROUND_TRUTH_TAX_LIST),
        "match": tax_match,
    }
    return results


def run_condition(label: str, system_prompt: str, model: str, repeats: int) -> list[dict]:
    print(f"\n=== {label} (model={model}, repeats={repeats}) ===")
    runs = []
    for i in range(repeats):
        result = run_extraction(model=model, system_prompt=system_prompt)
        checked = _check(result.model_dump())
        runs.append(checked)
        n_correct = sum(1 for v in checked.values() if v["match"])
        print(f"  run {i + 1}: {n_correct}/{len(checked)} fields correct")
        for field, v in checked.items():
            if not v["match"]:
                print(f"    MISS {field}: got {v['got']}, expected {v['expected']}")
    return runs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=HAIKU_MODEL)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    all_results = {
        "constrained": run_condition("Constrained (current SYSTEM_PROMPT)", SYSTEM_PROMPT, args.model, 1),
        "discovery": run_condition("Discovery (no page/column hints)", DISCOVERY_SYSTEM_PROMPT, args.model, args.repeats),
    }
    with open("eval_discovery_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print("\nWrote eval_discovery_results.json")
