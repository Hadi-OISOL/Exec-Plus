"""Use case: Recommends how to show a verified data answer and what to ask next.

What it does: Chooses a chart type from the executed operation and returned value types,
derives exact shares of a returned total, and phrases follow-up questions from real
field names. It never calculates a new business result beyond the returned rows.
"""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from execplus.domain.guidance import words
from execplus.domain.models import CalculationLineage
from execplus.domain.semantics import RECORD_COUNT, VALUE_ALIAS, DatasetView, quote_identifier


def decimal_text(value: Decimal) -> str:
    """Exact positional text: never scientific notation such as 0E-12 (receipts are unchanged)."""
    return "0" if value.is_zero() else format(value, "f")


_REQUESTED = (
    ("pie", r"\b(pie|donut|doughnut)\b"),
    ("line", r"\b(line|trend)\b"),
    ("scatter", r"\bscatter\b"),
    ("histogram", r"\bhistogram\b"),
    ("bar", r"\b(bar|column) (chart|graph)\b|\bbars?\b"),
    ("table", r"\btable\b"),
)
_SHARE = r"%|\b(percent|percentage|share|proportion|ratio|distribution|breakdown|split)\b"
_WORD = {"avg": "average", "sum": "total", "min": "minimum", "max": "maximum", "count": "count"}


def _ranked(lineage: CalculationLineage) -> bool:
    return "ORDER BY " + quote_identifier(VALUE_ALIAS) in lineage.sql


def _numeric(value: object) -> bool:
    return isinstance(value, int | float | Decimal) and not isinstance(value, bool)


def _numeric_column(rows: tuple[tuple[Any, ...], ...], index: int) -> bool:
    present = [row[index] for row in rows if row[index] is not None]
    return bool(present) and all(_numeric(value) for value in present)


def recommended_chart(
    question: str,
    lineage: CalculationLineage,
    columns: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
) -> dict[str, Any]:
    text = question.casefold()
    requested = next((kind for kind, pattern in _REQUESTED if re.search(pattern, text)), None)
    if lineage.aggregation == "rows":
        numeric = [name for i, name in enumerate(columns) if _numeric_column(rows, i)]
        if len(columns) == 1 and numeric:
            return {"type": "histogram", "x": columns[0]}
        if len(columns) == 2 and len(numeric) == 2:
            return {"type": "scatter", "x": columns[0], "y": columns[1]}
        return {"type": "table"}
    groups = lineage.grouping
    if not groups:
        return {"type": "kpi"}
    if len(groups) > 1:
        return {"type": "grouped_bar", "x": groups[0], "series": groups[1], "y": columns[-1]}
    if rows and all(isinstance(row[0], date) for row in rows if row[0] is not None):
        return {"type": requested if requested in {"bar", "table"} else "line", "x": groups[0]}
    whole = lineage.aggregation in {"count", "sum"} and len(rows) <= 12 and not _ranked(lineage)
    if whole and (requested == "pie" or (requested is None and re.search(_SHARE, text))):
        return {"type": "pie", "label": groups[0], "value": columns[-1]}
    return {"type": requested if requested in {"bar", "line", "table"} else "bar", "x": groups[0]}


def share_of_total(
    lineage: CalculationLineage, rows: tuple[tuple[Any, ...], ...]
) -> list[dict[str, str]]:
    if (
        lineage.aggregation not in {"count", "sum"}
        or len(lineage.grouping) != 1
        or _ranked(lineage)
    ):
        return []
    values = [row[-1] for row in rows]
    if not values or not all(_numeric(value) and value >= 0 for value in values):
        return []
    total = sum(Decimal(str(value)) for value in values)
    if total == 0:
        return []
    return [
        {
            "label": "" if row[0] is None else str(row[0]),
            "percent": str(
                (Decimal(str(row[-1])) * 100 / total).quantize(Decimal("0.1"), ROUND_HALF_UP)
            ),
        }
        for row in rows
    ]


def follow_up_questions(
    question: str,
    lineage: CalculationLineage,
    rows: tuple[tuple[Any, ...], ...],
    view: DatasetView,
) -> tuple[str, ...]:
    used = {lineage.metric, *lineage.grouping}
    used |= {item.split(" ", 1)[0] for item in lineage.filters}
    dimensions = [
        column.name
        for column in view.columns
        if column.name in view.dimensions
        and column.type == "text"
        and "identifier" not in column.tags
        and column.name not in used
    ]
    measures = [
        column.name
        for column in view.columns
        if column.name in view.metrics
        and "identifier" not in column.tags
        and column.name not in used
    ]
    metric, group = lineage.metric, lineage.grouping[0] if lineage.grouping else ""
    other = dimensions[0] if dimensions else ""
    measure = measures[0] if measures else ""
    ranked = _ranked(lineage)
    if lineage.aggregation == "rows":
        found = [
            f"How many records are there by {other}?" if other else "",
            f"What is the average {measure} by {other}?" if measure and other else "",
        ]
    elif metric == RECORD_COUNT:
        found = [
            f"Which {group} has the most records?"
            if group and len(rows) > 1 and not ranked
            else "",
            f"How many records are there by {other}?" if other else "",
            f"What is the average {measure} by {group or other}?"
            if measure and (group or other)
            else "",
        ]
    else:
        operation = _WORD.get(lineage.aggregation, lineage.aggregation)
        found = [
            f"Which {group} has the highest {operation} {metric}?"
            if group and len(rows) > 1 and not ranked
            else "",
            f"Show {operation} {metric} by {other}" if other else "",
            f"Does {metric} relate to {measure}?" if measure else "",
        ]
    asked = words(question)
    return tuple(item for item in dict.fromkeys(found) if item and words(item) != asked)[:3]
