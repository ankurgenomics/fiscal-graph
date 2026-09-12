"""Unit tests for extract.py's field-to-source-page citation mapping.

No LLM calls -- these check the mapping itself, not that a model cites correctly
(citations here are fixed at code time, not model-reported; see extract.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extract import field_sources, FIELD_SOURCE_PAGES
from schemas import RevenueExtraction


def test_every_schema_field_has_a_citation():
    schema_fields = set(RevenueExtraction.model_fields)
    cited_fields = set(FIELD_SOURCE_PAGES)
    assert schema_fields == cited_fields, (
        f"Mismatch between RevenueExtraction fields and FIELD_SOURCE_PAGES: "
        f"missing citations for {schema_fields - cited_fields}, "
        f"stale citations for {cited_fields - schema_fields}"
    )


def test_every_citation_is_a_nonempty_list_of_page_numbers():
    for field, pages in FIELD_SOURCE_PAGES.items():
        assert isinstance(pages, list) and pages, f"{field} has no source pages"
        assert all(isinstance(p, int) and p > 0 for p in pages), f"{field} has a bad page number"


def test_field_sources_returns_a_copy_not_the_original():
    result = field_sources()
    result["corp_income_tax_2024_billion"] = [999]
    assert FIELD_SOURCE_PAGES["corp_income_tax_2024_billion"] == [16]
