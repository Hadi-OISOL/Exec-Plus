"""Use case: Verifies deterministic KPI matching and explanation against a dataset view.

What it does: Proves the KPI catalog only matches datasets carrying the required tag,
and that every match explains why it applies.
"""

from execplus.domain.kpi_library import LIBRARY, KpiDomain, compatible_kpis, kpi_by_id
from execplus.domain.semantics import dataset_view


def finance_view():
    return dataset_view(
        {
            "columns": [
                {"name": "date", "type": "date", "role": "dimension", "semantic_tags": ["date"]},
                {
                    "name": "category",
                    "type": "text",
                    "role": "dimension",
                    "semantic_tags": [],
                },
                {
                    "name": "revenue",
                    "type": "decimal",
                    "role": "metric",
                    "semantic_tags": ["revenue"],
                },
                {"name": "cost", "type": "decimal", "role": "metric", "semantic_tags": ["cost"]},
            ]
        }
    )


def hr_view():
    return dataset_view(
        {
            "columns": [
                {
                    "name": "department",
                    "type": "text",
                    "role": "dimension",
                    "semantic_tags": [],
                },
                {
                    "name": "headcount",
                    "type": "integer",
                    "role": "metric",
                    "semantic_tags": ["headcount"],
                },
            ]
        }
    )


def test_library_ids_are_unique_and_versioned():
    ids = [definition.id for definition in LIBRARY]
    assert len(ids) == len(set(ids))
    assert all(definition.version >= 1 for definition in LIBRARY)


def test_kpi_by_id_resolves_known_and_unknown_ids():
    assert kpi_by_id("finance.total_revenue") is not None
    assert kpi_by_id("not.a.kpi") is None


def test_compatible_kpis_matches_only_finance_definitions_for_finance_dataset():
    matches = compatible_kpis(finance_view())
    matched_ids = {match.definition.id for match in matches}
    assert matched_ids == {"finance.total_revenue", "finance.total_cost"}
    assert all(match.definition.domain == KpiDomain.FINANCE for match in matches)


def test_compatible_kpis_explains_why_each_match_applies():
    matches = compatible_kpis(finance_view())
    revenue_match = next(
        match for match in matches if match.definition.id == "finance.total_revenue"
    )
    assert revenue_match.column == "revenue"
    assert "revenue" in revenue_match.explanation
    assert "Total revenue" in revenue_match.explanation


def test_compatible_kpis_is_deterministic():
    first = compatible_kpis(finance_view())
    second = compatible_kpis(finance_view())
    assert first == second


def test_hr_dataset_only_matches_hr_definitions():
    matches = compatible_kpis(hr_view())
    matched_ids = {match.definition.id for match in matches}
    assert matched_ids == {"hr.total_headcount"}


def test_dataset_without_any_tagged_metric_matches_nothing():
    empty = dataset_view(
        {"columns": [{"name": "notes", "type": "text", "role": "dimension"}]}
    )
    assert compatible_kpis(empty) == ()
