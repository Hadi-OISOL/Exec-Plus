"""Use case: Selects useful first explorations without requiring business setup.

What it does: Ranks bounded descriptive questions and renders findings from executed evidence.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.semantics import AggregationKind, MetricRequest

VERSION = "discovery-v1"


@dataclass(frozen=True)
class DiscoveryStep:
    metric: str
    aggregation: AggregationKind
    distribution: bool = False

    def request(self) -> MetricRequest:
        return MetricRequest(self.metric, self.aggregation)


@dataclass(frozen=True)
class DiscoveryFinding:
    id: str
    title: str
    text: str
    kind: str
    metric: str
    aggregation: str
    question: str
    result: QueryResult
    lineage: CalculationLineage


def name_words(name: str) -> set[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return set(re.findall(r"[a-z]+", separated.lower()))


def _candidate(context: DescriptionContext, column: dict[str, Any]) -> bool:
    name = column["name"]
    if name not in context.view.metrics or column["type_conflicts"]:
        return False
    if column["missing"] == context.profile["row_count"]:
        return False
    if context.state == "confirmed":
        return True
    words = name_words(name)
    return not words & {
        "id",
        "code",
        "sku",
        "zip",
        "postal",
        "year",
        "month",
        "day",
        "rating",
        "likert",
    }


def discovery_steps(context: DescriptionContext) -> tuple[DiscoveryStep, ...]:
    columns = context.profile["columns"]
    priority = {"revenue", "sales", "amount", "quantity", "balance", "cost", "stock", "value"}
    candidates = sorted(
        (column for column in columns if _candidate(context, column)),
        key=lambda column: (
            not bool(name_words(column["name"]) & priority),
            -column["distinct_count"],
            column["name"],
        ),
    )[:2]
    metrics = {entry["column"]: entry for entry in (context.definition or {}).get("metrics", [])}
    steps: list[DiscoveryStep] = []
    for column in candidates:
        name = column["name"]
        aggregates: tuple[AggregationKind, ...]
        if name in metrics and context.state == "confirmed":
            aggregates = (AggregationKind(metrics[name]["aggregation"]),)
        else:
            aggregates = (AggregationKind.MIN, AggregationKind.MAX, AggregationKind.AVG)
        steps.extend(DiscoveryStep(name, aggregate) for aggregate in aggregates)
    dimensions = sorted(
        (
            column
            for column in columns
            if column["name"] in context.view.dimensions
            and column["type"] in {"text", "boolean", "integer"}
            and 2 <= column["distinct_count"] <= 30
            and not name_words(column["name"]) & {"id", "code", "sku", "zip", "postal"}
            and not (
                (semantic := context.view.column(column["name"])) and "identifier" in semantic.tags
            )
            and not column["type_conflicts"]
        ),
        key=lambda column: (
            not bool(name_words(column["name"]) & {"category", "country", "city", "status", "job"}),
            column["distinct_count"],
            column["name"],
        ),
    )
    if dimensions:
        steps.append(DiscoveryStep(dimensions[0]["name"], AggregationKind.COUNT, True))
    return tuple(steps)


def discovery_quality(context: DescriptionContext) -> list[dict[str, str]]:
    labels = {
        "missing_values": "empty cells",
        "duplicate_rows": "repeated rows",
        "type_conflicts": "cells with inconsistent types",
        "invalid_dates": "unrecognized dates",
    }
    result = [
        {
            "code": check["code"],
            "text": f"{check['count']} {labels.get(check['code'], check['code'])}.",
            "action": check["explanation"],
        }
        for check in context.profile["quality_checks"]
        if check["count"]
    ]
    if not result:
        result.append(
            {
                "code": "basic_checks",
                "text": "Basic structure and completeness checks passed.",
                "action": "Basic checks cannot confirm business meaning or source accuracy.",
            }
        )
    return result


def readable_number(value: object) -> str:
    if isinstance(value, Decimal):
        rendered = format(value, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    return str(value)


def discovery_finding(
    context: DescriptionContext,
    step: DiscoveryStep,
    result: QueryResult,
    lineage: CalculationLineage,
) -> DiscoveryFinding:
    name, aggregate = step.metric, step.aggregation.value
    if step.distribution:
        largest = max(row[-1] for row in result.rows if isinstance(row[-1], int))
        leaders = [row[0] for row in result.rows if row[-1] == largest]
        label = "(missing)" if leaders[0] is None else str(leaders[0])
        text = f"{label} has {largest} rows in {name}. " + (
            "It is the largest group."
            if len(leaders) == 1
            else "Several groups tie for the largest count."
        )
        title, question = (
            f"How {name} is distributed",
            "Check data quality"
            if leaders[0] is None
            else f"Show all records where {name} equals {label}",
        )
    else:
        words = {
            "min": "Minimum",
            "max": "Maximum",
            "avg": "Average",
            "sum": "Total",
            "count": "Present values",
        }
        title = f"{words[aggregate]} {name}"
        value = result.rows[0][0]
        text = (
            f"{title}: {readable_number(value)}."
            if value is not None
            else f"No nonempty values matched the definition for {name}."
        )
        if aggregate == "avg":
            text += " Arithmetic mean of nonempty values; rounded to twelve decimal places."
        elif aggregate != "count":
            text += " Empty cells are excluded."
        if aggregate == "min" and isinstance(value, int | Decimal) and value < 0:
            text += (
                " Negative values are present. Check their source meaning before treating "
                "them as errors or removing them."
            )
        question = f"What is the {words[aggregate].lower()} {name}?"
    definitions = (context.definition or {}).get("columns", [])
    column: dict[str, Any] = next((item for item in definitions if item["name"] == name), {})
    if not step.distribution:
        if context.state == "confirmed":
            unit = column.get("currency") or column.get("unit")
            if unit:
                text += f" Declared unit: {unit}."
        else:
            text += " Column meaning and units are inferred, not confirmed."
    return DiscoveryFinding(
        f"{name}:{aggregate}",
        title,
        text,
        "distribution" if step.distribution else "metric",
        name,
        aggregate,
        question,
        result,
        lineage,
    )
