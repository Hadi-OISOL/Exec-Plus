"""Use case: Verifies typed list ingestion for bounded exact query execution.

What it does: Checks row alignment, decimal boundaries, null batches and concurrent isolation.
"""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.domain.errors import QueryDataError
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import (
    AggregationKind,
    MetricRequest,
    RowRequest,
    dataset_view,
    plan_query,
    plan_rows,
)
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [1, 2, 500, 10000])
async def test_typed_column_batches_keep_nulls_types_row_alignment_and_bound_values(batch_size):
    table = TableData(
        ("amount", "count", "enabled", "date", "label", "empty"),
        (
            ("", "", "", "", " first ", ""),
            (
                "0.000000000000000000000000001",
                "9223372036854775807",
                "true",
                "2026-01-01",
                "O'Reilly",
                "",
            ),
            ("1.5", "-9223372036854775808", "false", "2026-01-02", '"; DROP TABLE dataset; --', ""),
            ("-0.000000000000000000000000001", "0", "true", "2026-01-03", "last\nline", ""),
        ),
    )
    view = dataset_view(profile(table))
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    plan = plan_rows(scope, did, view, RowRequest(), row_limit=100)
    result = await DuckDBQueryExecutor(5, 64, batch_size).execute(plan, scope, table, view)
    assert result.rows == (
        (None, None, None, None, "first", None),
        (Decimal("1e-27"), 9223372036854775807, True, date(2026, 1, 1), "O'Reilly", None),
        (
            Decimal("1.5"),
            -9223372036854775808,
            False,
            date(2026, 1, 2),
            '"; DROP TABLE dataset; --',
            None,
        ),
        (Decimal("-1e-27"), 0, True, date(2026, 1, 3), "last\nline", None),
    )
    assert result.records_analyzed == result.matched_records == 4
    assert result.rows[1][0].as_tuple().exponent == -27


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values,expected",
    [
        (("1e-38", "2e-38", "0"), Decimal("3e-38")),
        (
            ("99999999999999999999999999.999999999999", "-0.000000000001"),
            Decimal("99999999999999999999999999.999999999998"),
        ),
    ],
)
async def test_list_binding_never_falls_back_to_binary_float_for_38_digit_values(values, expected):
    table = TableData(("amount",), tuple((value,) for value in values))
    view = dataset_view(profile(table))
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    plan = plan_query(scope, did, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10)
    result = await DuckDBQueryExecutor(5, 64).execute(plan, scope, table, view)
    assert result.rows[0][0].as_tuple() == expected.as_tuple()


@pytest.mark.asyncio
async def test_bad_value_in_later_batch_is_reported_before_any_answer_can_escape():
    table = TableData(("amount",), (("0.1",), ("0.2",), ("0.3",), ("private-invalid",)))
    view = dataset_view(profile(table))
    did = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    plan = plan_query(scope, did, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10)
    with pytest.raises(QueryDataError, match='Column "amount", data row 4') as error:
        await DuckDBQueryExecutor(5, 64, 2).execute(plan, scope, table, view)
    assert "private-invalid" not in str(error.value)


@pytest.mark.asyncio
async def test_eight_concurrent_bounded_loads_keep_distinct_workspace_results():
    async def run(index):
        value = f"0.{index:012d}"
        table = TableData(("amount",), tuple((value,) for _ in range(1200)))
        view = dataset_view(profile(table))
        did = uuid4()
        scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
        plan = plan_query(
            scope, did, view, MetricRequest("amount", AggregationKind.SUM), row_limit=10
        )
        result = await DuckDBQueryExecutor(10, 64).execute(plan, scope, table, view)
        assert result.rows == ((Decimal(value) * 1200,),)
        assert result.records_analyzed == 1200
        return result.query_id

    ids = await asyncio.gather(*(run(index) for index in range(1, 9)))
    assert len(set(ids)) == 8
