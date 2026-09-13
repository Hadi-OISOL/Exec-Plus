"""Use case: Interprets a model's proposed question classification and query plan.

What it does: Treats a language model's JSON response as untrusted input, validating
every proposed metric, dimension, and filter against the dataset's semantic view
before it can ever reach the query engine.
"""

import json
from dataclasses import dataclass
from typing import Any

from execplus.domain.models import QuestionKind
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
)

_AGGREGATIONS = {item.value for item in AggregationKind}
_OPERATORS = {item.value for item in FilterOperator}
_UNINTERPRETABLE = "The model response could not be interpreted."


@dataclass(frozen=True, slots=True)
class RoutedIntent:
    kind: QuestionKind
    request: MetricRequest | None = None
    options: tuple[str, ...] = ()
    message: str = ""


def _unsupported(message: str) -> RoutedIntent:
    return RoutedIntent(QuestionKind.UNSUPPORTED, message=message)


def _parse_filters(raw: Any, view: DatasetView) -> tuple[MetricFilter, ...] | None:
    if not isinstance(raw, list):
        return None
    filters = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        column, operator, value = item.get("column"), item.get("operator"), item.get("value")
        if (
            not isinstance(column, str)
            or view.column(column) is None
            or operator not in _OPERATORS
            or not isinstance(value, str | int | float | bool)
        ):
            return None
        filters.append(MetricFilter(column, FilterOperator(operator), value))
    return tuple(filters)


def _parse_numerical(payload: dict[str, Any], view: DatasetView) -> RoutedIntent:
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        return _unsupported("The model did not propose a usable query plan.")
    metric = plan.get("metric")
    aggregation = plan.get("aggregation")
    group_by = plan.get("group_by") or []
    if (
        not isinstance(metric, str)
        or metric not in view.metrics
        or aggregation not in _AGGREGATIONS
        or not isinstance(group_by, list)
        or not all(isinstance(name, str) and name in view.dimensions for name in group_by)
    ):
        return _unsupported("The model proposed an unsupported metric or dimension.")
    filters = _parse_filters(plan.get("filters") or [], view)
    if filters is None:
        return _unsupported("The model proposed an invalid filter.")
    request = MetricRequest(
        metric=metric,
        aggregation=AggregationKind(aggregation),
        group_by=tuple(group_by),
        filters=filters,
    )
    return RoutedIntent(QuestionKind.NUMERICAL, request=request)


def route_response(raw: str, view: DatasetView) -> RoutedIntent:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _unsupported(_UNINTERPRETABLE)
    if not isinstance(payload, dict):
        return _unsupported(_UNINTERPRETABLE)

    try:
        kind = QuestionKind(payload.get("kind"))
    except ValueError:
        return _unsupported(_UNINTERPRETABLE)

    if kind == QuestionKind.NUMERICAL:
        return _parse_numerical(payload, view)
    if kind == QuestionKind.AMBIGUOUS:
        options = payload.get("options")
        clean = tuple(str(option) for option in options) if isinstance(options, list) else ()
        message = str(payload.get("message") or "This question is ambiguous.")
        return RoutedIntent(QuestionKind.AMBIGUOUS, options=clean, message=message)
    if kind == QuestionKind.TEXTUAL:
        message = str(
            payload.get("message")
            or "This looks like a question needing a text answer, which isn't supported yet."
        )
        return RoutedIntent(QuestionKind.TEXTUAL, message=message)
    fallback = payload.get("message") or "This question is outside the supported scope."
    return _unsupported(str(fallback))
