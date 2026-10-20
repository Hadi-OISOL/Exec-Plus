"""Use case: Independently checks measured pattern statistics and semantic limits.

What it does: Uses known mathematical fixtures and confirmed definitions to verify evidence.
"""

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from statistics import correlation
from uuid import uuid4

import pytest

from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import QueryResult
from execplus.domain.patterns import pattern_request, pattern_result
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import apply_definition, infer_definition
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics


def configured(headers, rows, metrics, *, units=None, rules=()):
    table = TableData(tuple(headers), tuple(tuple(str(value) for value in row) for row in rows))
    metadata = profile(table)
    definition = infer_definition(metadata)
    definition["grain"] = "record"
    definition["metrics"] = list(rules)
    for column in definition["columns"]:
        column["role"] = "metric" if column["name"] in metrics else "dimension"
        column["meaning"] = "Reviewed observation"
        if column["name"] in metrics:
            column["unit"] = (units or {}).get(column["name"], "units")
    view = apply_definition(dataset_view(metadata), definition)
    view = replace(view, sources=({"understanding_id": str(uuid4())},))
    return DescriptionContext(
        "Fictional observations", metadata, view, definition, "confirmed"
    ), table


def analyze(context, table, selected=()):
    request = pattern_request(context, table, selected)
    rows = tuple(
        tuple(
            Decimal(row[table.headers.index(name)])
            if name in request["metrics"]
            else row[table.headers.index(name)]
            for name in request["columns"]
        )
        for row in table.rows
    )
    result = QueryResult(uuid4(), tuple(request["columns"]), rows, len(rows))
    engine = ScipyPatternStatistics()
    return request, pattern_result(
        result, request, engine.engine_version, engine.correlations, engine.categorical_association
    )


def average_ranks(values):
    return [
        Fraction(1 + sum(other < value for other in values))
        + Fraction(sum(other == value for other in values) - 1, 2)
        for value in values
    ]


@pytest.mark.parametrize("direction", [1, -1])
def test_known_linear_coefficient_preserves_exact_large_observations(direction):
    base = 10**30
    context, table = configured(
        ("reading", "outcome"),
        [(base + index, direction * index) for index in range(20)],
        {"reading", "outcome"},
    )
    _, result = analyze(context, table)
    finding = next(item for item in result["findings"] if item["type"] == "numeric_relationship")
    assert Decimal(finding["statistics"]["pearson"]) == direction
    assert Decimal(finding["statistics"]["spearman"]) == direction
    axis = "x" if finding["chart"]["x"] == "reading" else "y"
    assert finding["chart"]["points"][1][axis] == str(base + 1)
    assert finding["support"] == 20


def test_tied_rank_coefficient_matches_independent_fraction_reference():
    left = [index // 3 for index in range(30)]
    right = [index // 4 for index in range(30)]
    expected = correlation(average_ranks(left), average_ranks(right))
    context, table = configured(("left", "right"), zip(left, right, strict=True), {"left", "right"})
    _, result = analyze(context, table)
    finding = next(item for item in result["findings"] if item["type"] == "numeric_relationship")
    assert float(finding["statistics"]["spearman"]) == pytest.approx(expected, abs=0.0000005)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [(((10, 0), (0, 10)), 1.0), (((10, 10), (10, 10)), 0.0), (((30, 10), (10, 30)), 0.5)],
)
def test_binary_category_association_matches_independent_determinant(counts, expected):
    (a, b), (c, d) = counts
    independent = abs(a * d - b * c) / ((a + b) * (c + d) * (a + c) * (b + d)) ** 0.5
    value = ScipyPatternStatistics().categorical_association(counts)
    assert value == pytest.approx(expected)
    assert value == pytest.approx(independent)


def test_constant_and_empty_marginal_statistics_do_not_become_zero_evidence():
    engine = ScipyPatternStatistics()
    assert (
        engine.correlations((1.0,) * 20, tuple(range(20)), (10.5,) * 20, tuple(range(20))) is None
    )
    assert engine.categorical_association(((0, 0), (2, 3))) is None


def test_confirmed_metric_name_does_not_override_its_meaning():
    context, table = configured(
        ("code_quality", "successful_runs"),
        [(index, index * 2) for index in range(20)],
        {"code_quality", "successful_runs"},
        units={"code_quality": "percent", "successful_runs": "runs"},
    )
    request, result = analyze(context, table)
    assert "code_quality" in request["metrics"]
    assert any(item["type"] == "numeric_relationship" for item in result["findings"])


def test_group_mean_cannot_replace_an_explicit_confirmed_total():
    context, table = configured(
        ("group", "amount", "volume"),
        [("A" if index < 20 else "B", index, index * 2) for index in range(40)],
        {"amount", "volume"},
        rules=({"column": "amount", "aggregation": "sum", "filters": []},),
    )
    request, result = analyze(context, table)
    assert "amount" in request["metrics"]
    assert "amount" not in request["group_metrics"]
    assert not any(
        item["type"] == "group_difference" and "amount" in item["columns"]
        for item in result["findings"]
    )
    assert any(item["type"] == "numeric_relationship" for item in result["findings"])


def test_sparse_groups_remain_excluded_from_average_and_coverage():
    context, table = configured(
        ("group", "measurement"),
        [("A", 10)] * 20 + [("B", 30)] * 20 + [("Rare", 1_000_000)] * 4,
        {"measurement"},
    )
    _, result = analyze(context, table)
    finding = next(item for item in result["findings"] if item["type"] == "group_difference")
    assert finding["support"] == 40
    assert finding["excluded"] == 4
    assert finding["chart"]["points"] == [
        {"x": "A", "y": "10", "count": 20},
        {"x": "B", "y": "30", "count": 20},
    ]


def test_partial_field_units_still_allow_confirmed_farm_comparisons():
    context, table = configured(
        ("Soil_Moisture", "Temperature_C", "Rainfall_mm", "Sunlight_Hours", "Soil_Type"),
        [
            (index, index, index * 2, 10 + index, "Clay" if index < 50 else "Sand")
            for index in range(100)
        ],
        {"Soil_Moisture", "Temperature_C", "Rainfall_mm", "Sunlight_Hours"},
        units={
            "Soil_Moisture": "",
            "Temperature_C": "C",
            "Rainfall_mm": "mm",
            "Sunlight_Hours": "hours",
        },
    )
    request, result = analyze(context, table)
    assert request["metrics"] == ["Rainfall_mm", "Sunlight_Hours", "Temperature_C"]
    assert result["findings"]
    assert any(item["column"] == "Soil_Moisture" for item in result["exclusions"])
    assert all("Soil_Moisture" not in item["columns"] for item in result["findings"])


def test_weak_comparison_is_useful_without_becoming_a_claimed_strong_pattern():
    left = list(range(40))
    right = [(index * 17) % 40 for index in left]
    expected = correlation(left, right)
    assert abs(expected) < 0.5
    context, table = configured(
        ("reading", "outcome"), zip(left, right, strict=True), {"reading", "outcome"}
    )
    _, result = analyze(context, table)
    assert result["status"] == "no_strong_patterns"
    assert result["findings"] == []
    assert len(result["exploratory"]) == 1
    comparison = result["exploratory"][0]
    assert comparison["strength"] == "weak"
    assert comparison["support"] == 40
    assert float(comparison["statistics"]["pearson"]) == pytest.approx(expected, abs=0.0000005)
    assert "tend to" not in comparison["summary"]
