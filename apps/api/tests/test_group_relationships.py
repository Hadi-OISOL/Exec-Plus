"""Use case: Independently verifies pooled and within-group statistical comparisons.

What it does: Checks numerical oracles, identical coverage, precision and governed eligibility.
"""

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
from statistics import correlation
from uuid import uuid4

import pytest

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.group_relationships import (
    group_relationship_plan,
    group_relationship_request,
    group_relationship_result,
)
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult, WorkspaceScope
from execplus.infrastructure.query.validation import validated_query
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics
from test_patterns import prepared


def fixture(rows):
    context, table = prepared(["left", "right", "group"], rows)
    return context, table, group_relationship_request(context, table, ("left", "right"), "group")


def analyze(rows, *, statistics=None):
    _, _, request = fixture(rows)
    value = QueryResult(uuid4(), ("left", "right", "group"), tuple(rows), len(rows))
    engine = ScipyPatternStatistics()
    return group_relationship_result(
        value, request, engine.engine_version, statistics or engine.correlations
    )


def independent_ranks(values):
    return [
        Fraction(1 + sum(other < value for other in values))
        + Fraction(sum(other == value for other in values) - 1, 2)
        for value in values
    ]


def oracle(rows):
    left, right = [row[0] for row in rows], [row[1] for row in rows]
    return dict(
        pearson=correlation(left, right),
        spearman=correlation(independent_ranks(left), independent_ranks(right)),
    )


def reversal(left_count=20, right_count=20):
    return [(i, 100 + i, "A") for i in range(left_count)] + [
        (100 + i, i, "B") for i in range(right_count)
    ]


@pytest.mark.parametrize("counts", [(20, 20), (20, 60), (37, 23)])
def test_simpson_direction_reversal_matches_independent_unweighted_row_oracle(counts):
    rows = reversal(*counts)
    result = analyze(rows)
    assert result["status"] == "compared"
    assert result["coverage"]["covered_rows"] == sum(counts)
    for method, expected in oracle(rows).items():
        assert float(result["pooled"]["statistics"][method]) == pytest.approx(expected, abs=5e-7)
        strong = expected <= -0.5
        assert result["pooled"]["directions"][method] == ("negative" if strong else "weak")
        assert result["comparisons"][method]["reversal_groups"] == (["A", "B"] if strong else [])
    assert result["comparisons"]["pearson"]["reversal_groups"] == ["A", "B"]
    for group in result["groups"]:
        assert group["statistics"] == {"pearson": "1.000000", "spearman": "1.000000"}
    assert "not causes" in " ".join(result["limitations"])


def test_symmetric_nonlinear_groups_honestly_show_weak_scores_without_reversal():
    result = analyze([(i, i * i, group) for group in ("A", "B") for i in range(-20, 21)])
    assert result["status"] == "compared"
    assert result["pooled"]["statistics"] == {"pearson": "0.000000", "spearman": "0.000000"}
    for compared in result["comparisons"].values():
        assert compared["weak_groups"] == ["A", "B"]
        assert compared["reversal_groups"] == []
    assert "nonlinear" in " ".join(result["limitations"])


def test_same_direction_and_tied_ranks_match_independent_reference():
    rows = [(i // 3, i // 4, group) for group in ("A", "B") for i in range(30)]
    result = analyze(rows)
    for method, expected in oracle(rows).items():
        assert float(result["pooled"]["statistics"][method]) == pytest.approx(expected, abs=5e-7)
        assert result["comparisons"][method]["same_direction_groups"] == ["A", "B"]
    assert sum(group["complete_pairs"] for group in result["groups"]) == 60


def test_coverage_exclusions_are_disjoint_and_pool_uses_exactly_eligible_group_rows():
    covered = reversal(25, 35)
    rows = (
        covered
        + [(i, 10_000 * i, "Sparse") for i in range(19)]
        + [(7, i, "Constant") for i in range(20)]
        + [(None, 1, "A"), (2, None, "Sparse"), (None, None, "Constant")]
        + [(None, None, None), (100000, -100000, None)]
    )
    result = analyze(rows)
    coverage = result["coverage"]
    assert coverage == dict(
        source_rows=104,
        filtered_rows=104,
        covered_rows=60,
        excluded_rows=44,
        missing_category_rows=2,
        missing_pair_rows=3,
        sparse_group_rows=19,
        constant_group_rows=20,
        unstable_group_rows=0,
        observed_groups=4,
        eligible_groups=2,
    )
    assert result["pooled"]["support"] == 60
    assert {point["group"] for point in result["pooled"]["chart"]["points"]} == {"A", "B"}
    for method, expected in oracle(covered).items():
        assert float(result["pooled"]["statistics"][method]) == pytest.approx(expected, abs=5e-7)
    groups = {group["label"]: group for group in result["groups"]}
    assert groups["Sparse"]["status"] == "sparse"
    assert groups["Constant"]["status"] == "constant"
    assert groups["A"]["excluded_pairs"] == 1


@pytest.mark.parametrize("other_count", [0, 1, 19])
def test_requires_two_eligible_groups_instead_of_falling_back_to_pooled(other_count):
    # A missing category leaves the declared category nonconstant when no B pair exists.
    rows = [*reversal(20, other_count), (None, None, "Unreviewable")]
    result = analyze(rows)
    assert result["status"] == "insufficient_data" and result["pooled"] is None
    assert "two usable groups" in result["reason"]
    assert result["coverage"]["eligible_groups"] == 1
    assert all(not value["reversal_groups"] for value in result["comparisons"].values())


def test_all_constant_groups_have_explicit_coverage_without_false_zero_coefficient():
    result = analyze([(1, 2, "A")] * 20 + [(3, 4, "B")] * 20)
    assert result["status"] == "insufficient_data"
    assert result["coverage"]["constant_group_rows"] == 40
    assert result["coverage"]["covered_rows"] == 0
    assert all(group["statistics"] is None for group in result["groups"])


def test_unstable_group_is_explicitly_excluded_without_changing_other_groups():
    engine = ScipyPatternStatistics()

    def correlations(left, right, left_ranks, right_ranks):
        return (
            None if len(left) == 22 else engine.correlations(left, right, left_ranks, right_ranks)
        )

    result = analyze(reversal() + [(i, i * 2, "C") for i in range(22)], statistics=correlations)
    assert result["coverage"]["unstable_group_rows"] == 22
    assert result["pooled"]["support"] == 40
    assert result["groups"][-1]["status"] == "unstable"


def test_unavailable_pooled_statistic_does_not_become_a_compared_claim():
    engine = ScipyPatternStatistics()

    def correlations(left, right, left_ranks, right_ranks):
        return (
            None if len(left) == 40 else engine.correlations(left, right, left_ranks, right_ranks)
        )

    result = analyze(reversal(), statistics=correlations)
    assert result["coverage"]["eligible_groups"] == 2
    assert result["status"] == "insufficient_data" and result["pooled"] is None
    assert "pooled relationship" in result["reason"]


def test_exact_large_offsets_keep_decimal_values_and_rank_order():
    with localcontext() as precision:
        precision.prec = 128
        rows = [
            (Decimal("1e30") + Decimal(i) / 1000, i, group)
            for group in ("A", "B")
            for i in range(20)
        ]
    result = analyze(rows)
    assert result["pooled"]["statistics"] == {"pearson": "1.000000", "spearman": "1.000000"}
    assert result["pooled"]["chart"]["points"][2]["x"] == "1000000000000000000000000000000.001"
    assert json.loads(json.dumps(result)) == result


def test_float_collapse_withholds_pearson_without_discarding_valid_spearman_groups():
    with localcontext() as precision:
        precision.prec = 128
        values = [Decimal(0), *(Decimal("1e30") + Decimal(i) / 1000 for i in range(19))]
    rows = [(value, i, group) for group in ("A", "B") for i, value in enumerate(values)]
    result = analyze(rows)
    assert result["coverage"]["covered_rows"] == 40
    for group in result["groups"]:
        assert group["statistics"] == {"pearson": None, "spearman": "1.000000"}
        assert group["directions"]["pearson"] == "unavailable"
    assert result["pooled"]["statistics"] == {"pearson": None, "spearman": "1.000000"}
    assert result["comparisons"]["pearson"]["unavailable_groups"] == ["A", "B"]
    assert result["comparisons"]["spearman"]["same_direction_groups"] == ["A", "B"]


def test_plot_is_bounded_without_sampling_statistical_population():
    rows = [(i, i * 2, group) for group in ("A", "B") for i in range(300)]
    result = analyze(rows)
    assert result["pooled"]["support"] == 600
    assert len(result["pooled"]["chart"]["points"]) == 200
    assert result["pooled"]["statistics"]["pearson"] == "1.000000"
    assert "200" in " ".join(result["pooled"]["notes"])


def test_typed_category_keys_do_not_merge_equal_rendered_values():
    _, _, request = fixture(reversal())
    rows = tuple((i, i * 2, group) for group in (1, "1", True, "True") for i in range(20))
    engine = ScipyPatternStatistics()
    result = group_relationship_result(
        QueryResult(uuid4(), ("left", "right", "group"), rows, 80),
        request,
        engine.engine_version,
        engine.correlations,
    )
    assert result["coverage"]["observed_groups"] == 4
    assert len({group["id"] for group in result["groups"]}) == 4
    assert {group["label"] for group in result["groups"]} == {
        "1 (int)",
        "1 (str)",
        "True (bool)",
        "True (str)",
    }
    assert len({group["value"]["type"] for group in result["groups"]}) == 3


@pytest.mark.parametrize("mutation", ["version", "columns", "row_shape"])
def test_projection_shape_and_version_cannot_change_silently(mutation):
    _, _, request = fixture(reversal())
    value = QueryResult(uuid4(), ("left", "right", "group"), tuple(reversal()), 40)
    if mutation == "version":
        request["version"] = "unknown-version"
    elif mutation == "columns":
        value = replace(value, columns=("right", "left", "group"))
    else:
        value = replace(value, rows=((1, 2),))
    engine = ScipyPatternStatistics()
    with pytest.raises(IngestionError, match="declared fields"):
        group_relationship_result(value, request, engine.engine_version, engine.correlations)


def test_complete_population_guard_refuses_more_than_ten_thousand_rows():
    with pytest.raises(IngestionError, match="no partial sample"):
        analyze([(i, i * 2, "A" if i < 5000 else "B") for i in range(10001)])


def test_more_than_twelve_groups_are_refused_before_and_after_projection():
    rows = [(i, i * 2, f"G{group}") for group in range(13) for i in range(20)]
    with pytest.raises(ClarificationRequiredError, match="twelve categories"):
        fixture(rows)
    _, _, request = fixture(reversal())
    engine = ScipyPatternStatistics()
    with pytest.raises(IngestionError, match="twelve observed"):
        group_relationship_result(
            QueryResult(uuid4(), ("left", "right", "group"), tuple(rows), len(rows)),
            request,
            engine.engine_version,
            engine.correlations,
        )


@pytest.mark.parametrize(
    "selected,group_by",
    [
        (("left",), "group"),
        (("left", "left"), "group"),
        (("left", "right"), "left"),
        (("left", "right", "group"), "group"),
        (("left", "right"), "unknown"),
        (("left", "group"), "right"),
    ],
)
def test_explicit_two_measure_and_separate_category_contract(selected, group_by):
    context, table, _ = fixture(reversal())
    with pytest.raises(IngestionError):
        group_relationship_request(context, table, selected, group_by)


def test_saved_units_roles_and_confirmation_remain_authoritative():
    context, table, _ = fixture(reversal())
    with pytest.raises(ClarificationRequiredError, match="Confirm what"):
        group_relationship_request(
            replace(context, state="needs_review"), table, ("left", "right"), "group"
        )
    context.definition["columns"][0]["unit"] = ""
    with pytest.raises(ClarificationRequiredError, match="fixed unit"):
        group_relationship_request(context, table, ("left", "right"), "group")
    context.definition["columns"][0]["unit"] = "units"
    context.definition["columns"][0]["role"] = "identifier"
    with pytest.raises(ClarificationRequiredError, match="Identifiers"):
        group_relationship_request(context, table, ("left", "right"), "group")


def test_matching_required_filters_remain_parameterized_and_no_mean_replaces_saved_total():
    context, table, _ = fixture(reversal())
    rule = dict(
        column="left",
        aggregation="sum",
        filters=[dict(column="group", operator="ne", value="Private")],
    )
    context.definition["metrics"] = [rule]
    with pytest.raises(ClarificationRequiredError, match="different required filters"):
        group_relationship_request(context, table, ("left", "right"), "group")
    other = deepcopy(rule)
    other["column"] = "right"
    context.definition["metrics"].append(other)
    request = group_relationship_request(context, table, ("left", "right"), "group")
    wid, did, actor = uuid4(), uuid4(), uuid4()
    plan = group_relationship_plan(
        WorkspaceScope(wid, actor, frozenset({"owner"}), frozenset({did})),
        did,
        context.view,
        request,
    )
    assert plan.params == ("Private",) and "Private" not in plan.sql
    assert "SUM" not in plan.sql and "AVG" not in plan.sql
    validated_query(plan.sql, {"dataset"}, len(plan.params))


@pytest.mark.parametrize("scores", [(float("nan"), 0.5), (0.5, 2.0)])
def test_invalid_statistics_cannot_be_published(scores):
    with pytest.raises(IngestionError, match="reliably"):
        analyze(reversal(), statistics=lambda *args: scores)
