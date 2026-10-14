"""Use case: Checks measured exploratory patterns against independent known fixtures.

What it does: Exercises support, precision, missingness, governance and honest empty results.
"""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult, WorkspaceScope
from execplus.domain.patterns import pattern_plan, pattern_request, pattern_result
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import apply_definition, infer_definition
from execplus.infrastructure.query.validation import validated_query
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics


def prepared(headers, rows):
    table = TableData(
        tuple(headers),
        tuple(tuple("" if value is None else str(value) for value in row) for row in rows),
    )
    observed = profile(table)
    definition = infer_definition(observed)
    definition["grain"] = "record"
    for column in definition["columns"]:
        if column["role"] == "metric":
            column["unit"] = "units"
    view = apply_definition(dataset_view(observed), definition)
    view = replace(view, sources=({"understanding_id": str(uuid4())},))
    return DescriptionContext("Independent fixture", observed, view, definition, "confirmed"), table


def calculate(headers, rows, *, selected=()):
    context, table = prepared(headers, rows)
    request = pattern_request(context, table, selected)
    positions = [headers.index(name) for name in request["columns"]]
    result = QueryResult(
        uuid4(),
        tuple(request["columns"]),
        tuple(tuple(row[index] for index in positions) for row in rows),
        len(rows),
    )
    engine = ScipyPatternStatistics()
    return pattern_result(
        result, request, engine.engine_version, engine.correlations, engine.categorical_association
    )


def numeric(result):
    return [item for item in result["findings"] if item["type"] == "numeric_relationship"]


@pytest.mark.parametrize("sign", [1, -1])
def test_exact_linear_relationship_and_direction(sign):
    result = calculate(["amount", "reading"], [(i, sign * i * 3) for i in range(1, 41)])
    finding = numeric(result)[0]
    assert finding["statistics"] == {"pearson": f"{sign}.000000", "spearman": f"{sign}.000000"}
    assert finding["support"] == 40 and finding["excluded"] == 0
    assert "almost perfect" in " ".join(finding["notes"])
    assert "same rows" in " ".join(finding["notes"])


def test_exact_large_offset_and_decimal_rank_order_survive_float_boundary():
    with localcontext() as context:
        context.prec = 128
        values = [Decimal("1e30") + Decimal(i) / 1000 for i in range(40)]
    result = calculate(
        ["amount", "reading"], [(value, index) for index, value in enumerate(values)]
    )
    assert numeric(result)[0]["statistics"] == {"pearson": "1.000000", "spearman": "1.000000"}
    assert numeric(result)[0]["chart"]["points"][1]["x"] == "1000000000000000000000000000000.001"


def test_precision_collapse_omits_pearson_but_keeps_exact_ranks():
    with localcontext() as context:
        context.prec = 128
        values = [Decimal(0), *(Decimal("1e30") + Decimal(i) / 1000 for i in range(39))]
    result = calculate(
        ["amount", "reading"], [(value, index) for index, value in enumerate(values)]
    )
    scores = numeric(result)[0]["statistics"]
    assert scores["pearson"] is None and scores["spearman"] == "1.000000"
    assert "merge distinct" in " ".join(numeric(result)[0]["notes"])


def test_tied_rank_and_duplicate_frequencies_preserved():
    rows = [(1, 10)] * 10 + [(2, 20)] * 5 + [(3, 30)] * 15
    result = calculate(["amount", "reading"], rows)
    assert numeric(result)[0]["statistics"]["spearman"] == "1.000000"
    assert numeric(result)[0]["support"] == 30
    assert len(numeric(result)[0]["chart"]["points"]) == 30


def test_missing_pairs_excluded_without_filling_zero():
    result = calculate(
        ["amount", "reading"], [(i, i * 3) for i in range(30)] + [(None, 100), (40, None)]
    )
    finding = numeric(result)[0]
    assert finding["support"] == 30 and finding["excluded"] == 2
    assert finding["statistics"]["spearman"] == "1.000000"


def test_no_forced_pattern_for_symmetric_nonlinear_data():
    result = calculate(["amount", "reading"], [(i, i * i) for i in range(-20, 21)])
    assert result["status"] == "no_strong_patterns"
    assert result["findings"] == [] and result["coverage"]["suppressed_candidates"] == 1
    assert "nonlinear" in " ".join(result["limitations"])


def test_small_sample_has_explicit_no_findings():
    result = calculate(["amount", "reading"], [(i, i * 3) for i in range(19)])
    assert result["status"] == "insufficient_data" and result["findings"] == []


def test_constant_fields_and_identifiers_are_excluded_before_search():
    rows = [(i, 7, i * 2, i * 4) for i in range(30)]
    result = calculate(["id", "fixed", "amount", "reading"], rows)
    assert {item["column"] for item in result["exclusions"]} == {"id", "fixed"}
    assert result["coverage"]["eligible_columns"] == 2


def test_group_difference_retains_exact_means_counts_and_exclusions():
    rows = (
        [("A", Decimal("0.1"))] * 10
        + [("B", Decimal("0.3"))] * 10
        + [("Tiny", Decimal("100"))] * 4
        + [("A", None)]
    )
    result = calculate(["group", "amount"], rows)
    finding = result["findings"][0]
    assert finding["type"] == "group_difference"
    assert finding["statistics"]["eta_squared"] == "1.000000"
    assert finding["support"] == 20 and finding["excluded"] == 5
    assert finding["chart"]["points"] == [
        {"x": "A", "y": "0.1", "count": 10},
        {"x": "B", "y": "0.3", "count": 10},
    ]


def test_categories_report_exact_cooccurrence_and_cramers_v():
    rows = [("A", "Dry")] * 15 + [("A", "Wet")] * 5 + [("B", "Dry")] * 5 + [("B", "Wet")] * 15
    result = calculate(["group", "condition"], rows)
    finding = result["findings"][0]
    assert finding["type"] == "category_association"
    assert finding["statistics"]["cramers_v"] == "0.500000"
    assert sum(point["count"] for point in finding["chart"]["points"]) == 40
    assert finding["support"] == 40


def test_independent_categories_are_not_a_discovery():
    rows = [(x, y) for x in ("A", "B") for y in ("Dry", "Wet")] * 10
    result = calculate(["group", "condition"], rows)
    assert result["findings"] == []
    assert result["status"] == "no_strong_patterns"


def test_single_named_field_focus_compares_it_with_available_fields():
    result = calculate(
        ["amount", "reading", "other"],
        [(i, i * 2, i * 4) for i in range(40)],
        selected=("reading",),
    )
    assert result["coverage"]["checked_candidates"] == 2
    assert all("reading" in finding["columns"] for finding in result["findings"])


def test_scatter_limit_discloses_full_score_and_bounded_plot():
    result = calculate(["amount", "reading"], [(i, i * 2) for i in range(250)])
    finding = numeric(result)[0]
    assert finding["support"] == 250 and len(finding["chart"]["points"]) == 200
    assert "Scores use every complete pair" in " ".join(finding["notes"])


def test_full_projection_refuses_over_limit_instead_of_analysing_first_rows():
    with pytest.raises(IngestionError, match="no partial sample"):
        calculate(["amount", "reading"], [(i, i * 2) for i in range(10001)])


def test_unconfirmed_meaning_and_unknown_units_request_clear_inputs():
    context, table = prepared(["amount", "reading"], [(i, i * 2) for i in range(30)])
    with pytest.raises(ClarificationRequiredError, match="Confirm what"):
        pattern_request(replace(context, state="needs_review"), table)
    context.definition["columns"][0]["unit"] = ""
    with pytest.raises(ClarificationRequiredError, match="fixed unit"):
        pattern_request(context, table, ("amount", "reading"))


def test_required_filters_must_match_and_query_stays_parameter_bound():
    context, table = prepared(
        ["group", "amount", "reading", "other"],
        [("A" if i < 20 else "B", i, i * 2, i * 4) for i in range(40)],
    )
    context.definition["metrics"] = [
        dict(
            name="Amount",
            column="amount",
            aggregation="sum",
            filters=[dict(column="group", operator="eq", value="A")],
        )
    ]
    request = pattern_request(context, table)
    assert "amount" not in request["metrics"]
    assert "different records" in next(
        item["reason"] for item in request["exclusions"] if item["column"] == "amount"
    )
    with pytest.raises(ClarificationRequiredError, match="different required filters"):
        pattern_request(context, table, ("amount", "reading"))
    focused = pattern_request(context, table, ("amount",))
    wid, did, actor = uuid4(), uuid4(), uuid4()
    plan = pattern_plan(
        WorkspaceScope(wid, actor, frozenset({"owner"}), frozenset({did})),
        did,
        context.view,
        focused,
    )
    assert plan.params == ("A",) and "'A'" not in plan.sql
    validated_query(plan.sql, {"dataset"}, len(plan.params))


def test_cap_and_top_findings_are_explicit_and_reproducible():
    headers = [f"value_{index}" for index in range(10)]
    rows = [tuple(row * (index + 1) for index in range(10)) for row in range(30)]
    result = calculate(headers, rows)
    assert result["coverage"]["eligible_columns"] == 8
    assert result["coverage"]["checked_candidates"] == 28
    assert len(result["findings"]) == 6
    assert result["coverage"]["omitted_findings"] == 22
    assert result == calculate(headers, rows)


def test_engine_rejects_bad_or_constant_inputs():
    engine = ScipyPatternStatistics()
    assert engine.correlations((1.0,) * 20, (2.0,) * 20, (1.0,) * 20, (2.0,) * 20) is None
    assert engine.categorical_association(((0, 0), (4, 5))) is None


def test_changed_projection_is_refused():
    context, table = prepared(["amount", "reading"], [(i, i * 2) for i in range(30)])
    request = pattern_request(context, table)
    engine = ScipyPatternStatistics()
    value = QueryResult(uuid4(), ("wrong", "reading"), ((1, 2),) * 30, 30)
    with pytest.raises(IngestionError, match="declared fields"):
        pattern_result(
            value,
            deepcopy(request),
            engine.engine_version,
            engine.correlations,
            engine.categorical_association,
        )
