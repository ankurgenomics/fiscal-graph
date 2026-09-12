"""Runs Part 1, Part 2, and Part 3 in sequence, printing each part's result.

python run_all.py
"""
import json

from extract import run_extraction, field_sources
from llm_config import HAIKU_MODEL
from part2_pipeline import run_pipeline_sync, to_sample_format
from part3_supervisor import build_supervisor, run_query, DEMO_QUERIES


def main():
    # Haiku explicitly: leaving model unset would fall through to DEV_MODEL,
    # the free OpenRouter model used only for zero-cost iteration, not the
    # model these parts' documented results are verified against.
    print("=" * 80)
    print("PART 1: Document Extraction")
    print("=" * 80)
    result1 = run_extraction(model=HAIKU_MODEL)
    print(result1.model_dump_json(indent=2))
    print("\nSource pages (fixed at code time, not model-reported):")
    print(json.dumps(field_sources(), indent=2))

    print("\n" + "=" * 80)
    print("PART 2: Tool Calling and Reasoning")
    print("=" * 80)
    result2 = run_pipeline_sync(model=HAIKU_MODEL)
    print(json.dumps(to_sample_format(result2), indent=2))

    print("\n" + "=" * 80)
    print("PART 3: Multi-Agent Supervisor")
    print("=" * 80)
    app = build_supervisor()
    for label, demo_query in DEMO_QUERIES.items():
        answer, trace = run_query(app, demo_query)
        agents = sorted(set(t["actor"] for t in trace) - {"user", "supervisor"})
        print(f"\n{label}")
        print(f"Agents invoked: {agents}")
        print(f"Answer: {answer[:300]}")


if __name__ == "__main__":
    main()
