"""Golden-set regression check for Part 1 extraction.

Formalizes the check part1_extraction.ipynb already runs ad hoc into a reusable,
scriptable entry point: run the extraction, compare every field against a fixed
ground truth, exit non-zero on any hard mismatch. Not wired into CI, since it
calls a real LLM and needs an API key -- run it by hand after a prompt or schema
change to check for regressions, the same way the notebook's own check does.

Usage: python evaluate.py [--model MODEL_ID]
"""
import argparse
import sys

from extract import run_extraction
from llm_config import HAIKU_MODEL

# The 12-item reading (Haiku's) is the project's documented primary interpretation
# -- see README's Interpretation calls, row 6. Sonnet's 11-item reading (excluding
# "Statutory Boards' Contributions") is a documented, accepted alternate, not a
# regression, so a tax-list mismatch is reported separately from the other fields
# rather than folded into the same pass/fail count.
GROUND_TRUTH = {
    "corp_income_tax_2024_billion": 28.03,
    "corp_income_tax_yoy_pct": -1.2,
    "total_topups_2024_billion": 20.352,
    "latest_actual_fiscal_position_billion": -3.57,
}
GROUND_TRUTH_TAX_LIST = [
    "Corporate Income Tax", "Personal Income Tax", "Withholding Tax",
    "Statutory Boards' Contributions", "Assets Taxes",
    "Customs, Excise and Carbon Taxes", "Goods and Services Tax",
    "Motor Vehicle Taxes", "Vehicle Quota Premiums", "Betting Taxes",
    "Stamp Duty", "Other Taxes",
]
NUMERIC_TOLERANCE = 0.01


def run_golden_set_eval(model: str | None = None) -> tuple[bool, list[str]]:
    """Returns (all_hard_checks_passed, report_lines)."""
    model = model or HAIKU_MODEL
    result = run_extraction(model=model)
    extracted = result.model_dump()

    report = [f"Golden-set eval, model={model}", ""]
    all_passed = True

    for field, expected in GROUND_TRUTH.items():
        actual = extracted[field]
        passed = abs(actual - expected) < NUMERIC_TOLERANCE
        all_passed &= passed
        report.append(f"{'PASS' if passed else 'FAIL'}  {field}: got {actual}, expected {expected}")

    tax_match = set(extracted["operating_revenue_taxes"]) == set(GROUND_TRUTH_TAX_LIST)
    tag = "PASS" if tax_match else "DIFF (see README Interpretation calls, row 6)"
    report.append(
        f"{tag}  operating_revenue_taxes: got {sorted(extracted['operating_revenue_taxes'])}"
    )

    return all_passed, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="Model id, defaults to HAIKU_MODEL")
    args = parser.parse_args()

    passed, report = run_golden_set_eval(model=args.model)
    print("\n".join(report))
    sys.exit(0 if passed else 1)
