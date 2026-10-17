"""Independent arithmetic and safe input boundaries for descriptive target groups."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.domain.cohort_comparison import cohort_plan, cohort_request, cohort_result
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult, WorkspaceScope
from execplus.domain.understanding import apply_definition
from test_patterns import prepared


def compare(rows, *, target="Ready", headers=("stage", "reading", "crop")):
    context, table = prepared(headers, rows)
    request = cohort_request(context, table, "stage", target)
    positions = [headers.index(name) for name in request["columns"]]
    result = QueryResult(
        uuid4(),
        tuple(request["columns"]),
        tuple(tuple(row[i] for i in positions) for row in rows),
        len(rows),
    )
    return cohort_result(result, request, "test-exact"), request


def test_comparison_is_record_weighted_with_exact_counts_means_and_medians():
    rows = [("Ready", Decimal("0.1"), "A")] * 10
    rows += [("Growing", Decimal("0.3"), "A")] * 5
    rows += [("Starting", Decimal("0.5"), "B")] * 15
    result, _ = compare(rows)
    metric = result["numeric"][0]
    assert metric["target_mean"] == "0.1"
    assert metric["other_mean"] == "0.45"  # Not unweighted mean 0.4.
    assert metric["other_median"] == "0.5"
    assert metric["difference"] == "-0.35"
    assert result["coverage"] == dict(
        source_rows=30, filtered_rows=30, target_rows=10, other_rows=20, missing_target_rows=0
    )
    assert result["categories"][0]["levels"] == [
        dict(value="A", target_count=10, other_count=5, target_share="1", other_share="0.25"),
        dict(value="B", target_count=0, other_count=15, target_share="0", other_share="0.75"),
    ]


def test_missing_target_is_not_other_and_missing_measure_is_not_zero():
    rows = [("Ready", 2, "A")] * 10 + [("Growing", 4, "B")] * 10
    rows += [(None, 999, "C"), ("Ready", None, "A")]
    result, _ = compare(rows)
    assert result["coverage"]["missing_target_rows"] == 1
    assert result["coverage"]["target_rows"] == 11
    assert result["numeric"][0]["target_count"] == 10
    assert result["numeric"][0]["target_mean"] == "2"
    assert result["numeric"][0]["other_mean"] == "4"


def test_equal_and_constant_values_remain_visible_without_forced_signals():
    result, _ = compare([("Ready", 7, "A")] * 10 + [("Growing", 7, "B")] * 10)
    assert result["numeric"][0]["difference"] == "0"
    assert result["numeric"][0]["standardized_difference"] is None
    assert result["numeric"][0]["status"] == "compared"


def test_sparse_groups_keep_counts_but_do_not_imply_a_reliable_mean():
    result, _ = compare([("Ready", 999, "A")] * 4 + [("Growing", 7, "B")] * 20)
    assert result["numeric"][0]["target_count"] == 4
    assert result["numeric"][0]["target_mean"] is None
    assert result["status"] == "insufficient_data"
    assert "snapshot alone cannot prescribe" in " ".join(result["next_steps"])


def test_existing_label_is_not_silently_replaced_with_hypothetical_success():
    context, table = prepared(("stage", "reading"), [("Ready", 2), ("Growing", 3)])
    with pytest.raises(ClarificationRequiredError, match="exact category"):
        cohort_request(context, table, "stage", "harvestable")
    with pytest.raises(ClarificationRequiredError, match="text category"):
        cohort_request(context, table, "reading", "2")


def test_units_exclusion_and_explicit_selection_keep_saved_meanings():
    context, table = prepared(("stage", "reading"), [("Ready", 2)] * 10 + [("Growing", 3)] * 10)
    definition = deepcopy(context.definition)
    definition["columns"][1]["unit"] = ""
    context = replace(
        context, definition=definition, view=apply_definition(context.view, definition)
    )
    request = cohort_request(context, table, "stage", "Ready")
    assert request["metrics"] == [] and "fixed unit" in request["exclusions"][0]["reason"]
    with pytest.raises(ClarificationRequiredError, match="fixed unit"):
        cohort_request(context, table, "stage", "Ready", ("reading",))


def test_projection_uses_authorized_named_columns_and_rejects_partial_population():
    context, table = prepared(("stage", "reading"), [("Ready", 2)] * 10 + [("Growing", 3)] * 10)
    request = cohort_request(context, table, "stage", "Ready")
    wid, did = uuid4(), uuid4()
    plan = cohort_plan(
        WorkspaceScope(wid, uuid4(), frozenset({"owner"}), frozenset({did})),
        did,
        context.view,
        request,
    )
    assert 'SELECT "stage", "reading"' in plan.sql and "LIMIT 10001" in plan.sql
    with pytest.raises(IngestionError, match="partial sample"):
        cohort_result(
            QueryResult(plan.query_id, tuple(request["columns"]), (("Ready", 2),) * 10001, 10001),
            request,
            "test",
        )


def test_large_decimal_means_do_not_pass_through_binary_float():
    number = Decimal("9007199254740993.125")
    result, _ = compare([("Ready", number, "A")] * 10 + [("Growing", number + 1, "B")] * 10)
    assert result["numeric"][0]["target_mean"] == str(number)
    assert result["numeric"][0]["difference"] == "-1"
