"""Use case: Builds governed, bounded time-series evidence for basic forecasts.

What it does: Validates declared coverage and creates replayable calendar aggregate queries.
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    DatasetView,
    MetricRequest,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request


def coverage(request: dict[str, Any]) -> tuple[date, date]:
    if request.get("coverage_confirmed") is not True:
        raise IngestionError(
            "coverage_required", "Confirm that the declared periods contain complete data.", 422
        )
    try:
        start = date.fromisoformat(request["coverage_start"])
        end = date.fromisoformat(request["coverage_end"])
    except (KeyError, TypeError, ValueError):
        raise IngestionError(
            "invalid_coverage", "Provide valid complete-coverage dates.", 422
        ) from None
    if start > end or end >= date.today() or (end - start).days > 36_600:
        raise IngestionError(
            "invalid_coverage",
            "Use an ordered historical coverage window ending before today.",
            422,
        )
    frequency = request.get("frequency")
    if frequency not in {"daily", "monthly"}:
        raise IngestionError("invalid_frequency", "Choose daily or monthly periods.", 422)
    if frequency == "monthly" and (start.day != 1 or end.day != monthrange(end.year, end.month)[1]):
        raise IngestionError(
            "incomplete_period", "Monthly forecasts require whole calendar months.", 422
        )
    count = (
        (end - start).days + 1
        if frequency == "daily"
        else ((end.year - start.year) * 12 + end.month - start.month + 1)
    )
    if count > 1200:
        raise IngestionError("forecast_limit", "Use at most 1,200 complete periods.", 422)
    return start, end


def series_request(raw: dict[str, Any], table: TableData, view: DatasetView) -> MetricRequest:
    start, end = coverage(raw)
    name = raw["time_column"]
    column = view.column(name)
    if not column or name not in view.dimensions or column.type != "date":
        raise IngestionError(
            "date_required", "Choose a confirmed date column in YYYY-MM-DD format.", 422
        )
    if any(not row[table.headers.index(name)].strip() for row in table.rows):
        raise IngestionError(
            "missing_dates", "Resolve missing dates before forecasting this source.", 422
        )
    filters = raw.get("filters", [])
    if len(filters) > 18 or any(item.get("column") == name for item in filters):
        raise IngestionError(
            "invalid_forecast_filter",
            "Use up to 18 filters; coverage controls the date window.",
            422,
        )
    method = validated_method(
        dict(
            kind="metric",
            column=raw["metric"],
            aggregation=raw["aggregation"],
            group_by=[name],
            filters=[
                *filters,
                dict(column=name, operator="gte", value=start.isoformat()),
                dict(column=name, operator="lte", value=end.isoformat()),
            ],
        ),
        view,
    )
    request = governed_request(view, table, method_request(method))
    if (view.definition or {}).get("grain") == "inventory_snapshot" and raw[
        "frequency"
    ] == "monthly":
        raise IngestionError(
            "snapshot_period",
            "Use daily inventory snapshots; monthly stock aggregation needs a separate method.",
            422,
        )
    declared_time_filters = [item for item in request.filters if item.column == name]
    if len(declared_time_filters) != 2:
        raise IngestionError(
            "metric_period_conflict",
            "The confirmed metric has its own date filter. Review its meaning before forecasting.",
            422,
        )
    return request


def series_plan(
    scope: WorkspaceScope,
    did: UUID,
    view: DatasetView,
    request: MetricRequest,
    frequency: str,
    kind: str,
) -> QueryPlan:
    time_column = quote_identifier(request.group_by[0])
    metric = quote_identifier(request.metric)
    unit = "day" if frequency == "daily" else "month"
    period = f"DATE_TRUNC(?, {time_column})"
    alias = "__forecast_period"
    while view.column(alias) is not None:
        alias += "_"
    grouped = quote_identifier(alias)
    aggregation = request.aggregation.value.upper() if kind == "value" else "COUNT"
    operand = "?" if kind == "samples" else metric
    clauses, parameters = build_where(view, request.filters)
    sql = (
        f'SELECT {period} AS {grouped}, {aggregation}({operand}) AS "__value" '
        'FROM "dataset" WHERE '
        + " AND ".join(clauses)
        + f" GROUP BY {grouped} ORDER BY {grouped} LIMIT 1201"
    )
    validate_read_only(sql)
    return QueryPlan(
        uuid4(),
        scope.workspace_id,
        did,
        "Forecast calendar evidence",
        sql,
        (unit, *((1,) if kind == "samples" else ()), *parameters),
    )


def series_values(
    results: list[QueryResult], request: dict[str, Any], *, allow_missing: bool = False
) -> tuple[tuple[date, Decimal], ...]:
    start, end = coverage(request)
    if len(results) != 3 or any(len(result.rows) > 1200 for result in results):
        raise IngestionError("forecast_limit", "Use at most 1,200 complete periods.", 422)
    values: list[dict[date, Any]] = []
    for result in results:
        converted = {}
        if len(result.columns) != 2:
            raise IngestionError("invalid_series", "The time-series evidence is malformed.", 422)
        for row in result.rows:
            if len(row) != 2:
                raise IngestionError(
                    "invalid_series", "The time-series evidence is malformed.", 422
                )
            period, value = row
            if isinstance(period, datetime):
                if period.hour or period.minute or period.second or period.microsecond:
                    raise IngestionError(
                        "invalid_series", "The time-series period is not a calendar boundary.", 422
                    )
                period = period.date()
            if not isinstance(period, date):
                raise IngestionError(
                    "invalid_series", "The time series contains an invalid date.", 422
                )
            if period in converted:
                raise IngestionError(
                    "invalid_series", "The time series contains duplicate periods.", 422
                )
            converted[period] = value
        values.append(converted)
    actual, present, samples = values
    if set(actual) != set(present) or set(actual) != set(samples):
        raise IngestionError(
            "invalid_series", "The time-series evidence has inconsistent periods.", 422
        )
    if any(type(value) is not int or value < 1 for value in samples.values()) or any(
        type(value) is not int or value < 0 for value in present.values()
    ):
        raise IngestionError(
            "invalid_series", "The time-series evidence contains invalid record counts.", 422
        )
    if any(present[key] != value for key, value in samples.items()):
        raise IngestionError(
            "missing_measure",
            "Resolve missing measure values within the selected periods before forecasting.",
            422,
        )
    expected: list[date] = []
    cursor = start
    while cursor <= end:
        expected.append(cursor)
        cursor = (
            cursor + timedelta(days=1)
            if request["frequency"] == "daily"
            else (date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1))
        )
    if not set(actual).issubset(expected):
        raise IngestionError(
            "invalid_series", "The time-series evidence is outside the declared periods.", 422
        )
    if not allow_missing and set(expected) != set(actual):
        raise IngestionError(
            "missing_periods",
            "Some complete periods have no records. Supply those periods; absence is not zero.",
            422,
        )
    output = []
    for period in expected:
        if period not in actual:
            continue
        value = actual[period]
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise IngestionError(
                "invalid_series", "The time series must contain exact finite numbers.", 422
            )
        number = Decimal(value)
        if not number.is_finite():
            raise IngestionError(
                "invalid_series", "The time series must contain finite numbers.", 422
            )
        output.append((period, number))
    return tuple(output)
