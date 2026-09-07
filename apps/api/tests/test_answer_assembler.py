"""Use case: Verifies the numerical-evidence boundary.

What it does: Proves metrics originate from matching execution and lineage.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.application.services.answers import AnswerAssembler
from execplus.domain.errors import UnverifiedAnswerError
from execplus.domain.models import CalculationLineage, QueryResult


def make_evidence() -> tuple[QueryResult, CalculationLineage]:
    query_id = uuid4()
    workspace_id = uuid4()
    dataset_id = uuid4()
    result = QueryResult(
        query_id=query_id,
        columns=("total_revenue",),
        rows=((Decimal("18432.50"),),),
        records_analyzed=240,
    )
    lineage = CalculationLineage(
        query_id=query_id,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        dataset_name="sales.csv",
        records_analyzed=240,
        metric="Revenue",
        aggregation="SUM",
        grouping=(),
        filters=(),
        sql="SELECT SUM(revenue) AS total_revenue FROM authorized_dataset",
    )
    return result, lineage


def test_assembles_metric_from_executed_cell() -> None:
    result, lineage = make_evidence()

    answer = AnswerAssembler().assemble_metric(
        label="Total revenue",
        column="total_revenue",
        result=result,
        lineage=lineage,
    )

    assert answer.value == Decimal("18432.50")
    assert answer.lineage == lineage


def test_rejects_lineage_from_another_query() -> None:
    result, lineage = make_evidence()
    mismatched_result = QueryResult(
        query_id=uuid4(),
        columns=result.columns,
        rows=result.rows,
        records_analyzed=result.records_analyzed,
    )

    with pytest.raises(UnverifiedAnswerError, match="different queries"):
        AnswerAssembler().assemble_metric(
            label="Total revenue",
            column="total_revenue",
            result=mismatched_result,
            lineage=lineage,
        )


def test_rejects_non_numeric_executed_cell() -> None:
    result, lineage = make_evidence()
    text_result = QueryResult(
        query_id=result.query_id,
        columns=("total_revenue",),
        rows=(("unknown",),),
        records_analyzed=result.records_analyzed,
    )

    with pytest.raises(UnverifiedAnswerError, match="not numeric"):
        AnswerAssembler().assemble_metric(
            label="Total revenue",
            column="total_revenue",
            result=text_result,
            lineage=lineage,
        )


@pytest.mark.parametrize("value", [True, None, float("nan"), float("inf"), Decimal("NaN")])
def test_rejects_unusable_numbers(value):
    result, lineage = make_evidence()
    invalid = QueryResult(result.query_id, result.columns, ((value,),), result.records_analyzed)
    with pytest.raises(UnverifiedAnswerError):
        AnswerAssembler().assemble_metric("Metric", "total_revenue", invalid, lineage)


def test_rejects_negative_row_index():
    result, lineage = make_evidence()
    with pytest.raises(UnverifiedAnswerError):
        AnswerAssembler().assemble_metric("Metric", "total_revenue", result, lineage, -1)
