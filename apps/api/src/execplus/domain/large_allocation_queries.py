"""Use case: Projects a complete governed action population for larger allocations.

What it does: Enforces one identical population, fixed units and a 51-row overflow sentinel.
"""

from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import fail
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    DatasetView,
    MetricFilter,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request, preferred_aggregation


def large_allocation_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> tuple[QueryPlan, dict[str, str]]:
    names = [
        raw["cost_column"],
        raw["benefit_column"],
        *(item["column"] for item in raw.get("resources", [])),
    ]
    entity = raw["entity_column"]
    columns = (view.definition or {}).get("columns", [])
    meaning = next((column for column in columns if column["name"] == entity), None)
    if not meaning or meaning["role"] not in {"identifier", "dimension"}:
        fail("candidate_identity_required", "Choose a confirmed candidate identifier or category.")
    if len(set([entity, *names])) != len(names) + 1:
        fail(
            "distinct_columns_required", "Choose distinct identifier, benefit and resource columns."
        )
    units: dict[str, str] = {}
    filters: tuple[MetricFilter, ...] | None = None
    for name in names:
        method = validated_method(
            dict(
                kind="metric",
                column=name,
                aggregation=preferred_aggregation(view, name).value,
                filters=raw["filters"],
                group_by=[],
                order=[],
            ),
            view,
        )
        request = governed_request(view, table, method_request(method))
        if filters is not None and set(filters) != set(request.filters):
            fail(
                "allocation_population_mismatch",
                "All action measures must use the same required population filters.",
            )
        filters = request.filters
        definition = next(column for column in columns if column["name"] == name)
        unit = definition["currency"] or definition["unit"]
        if not unit or definition["unit_column"]:
            fail("fixed_unit_required", "Confirm a fixed unit for every action measure.")
        units[name] = unit
    where, parameters = build_where(view, filters or ())
    sql = f'SELECT {", ".join(quote_identifier(name) for name in [entity, *names])} FROM "dataset"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {quote_identifier(entity)} LIMIT 51"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(),
        scope.workspace_id,
        did,
        "Registered multi-resource allocation",
        sql,
        tuple(parameters),
    ), units
