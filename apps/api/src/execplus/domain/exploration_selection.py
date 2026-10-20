"""Use case: Chooses bounded useful explorations from authorized field metadata.

What it does: Ranks explicit focus and likely outcomes without declaring causes or units.
"""

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from execplus.domain.guidance import DescriptionContext

OUTCOMES = {"revenue", "sales", "profit", "yield", "harvest", "outcome", "production"}
MEASURES = {"amount", "quantity", "cost", "stock", "balance", "value"}
GROUPS = {"region", "irrigation", "crop", "category", "country", "city", "status", "stage"}
ADDITIVE = {"revenue", "sales", "profit", "amount", "quantity", "cost", "stock", "count"}
NONADDITIVE = {
    "ph",
    "temperature",
    "humidity",
    "moisture",
    "price",
    "rate",
    "ratio",
    "percentage",
    "percent",
    "score",
    "average",
    "yield",
    "balance",
}


def tokens(name: str) -> set[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return set(re.findall(r"[a-z]+", separated.lower()))


def exploration_rank(
    context: "DescriptionContext", name: str, selected: tuple[str, ...] = ()
) -> tuple[int, int, int, str]:
    column = next(item for item in context.profile["columns"] if item["name"] == name)
    words = tokens(name)
    priority = 0 if words & OUTCOMES else 1 if words & (MEASURES | GROUPS) else 2
    return (0 if name in selected else 1, priority, column["missing"], name.casefold())


def suggested_aggregation(name: str) -> str:
    words = tokens(name)
    return "sum" if words & ADDITIVE and not words & NONADDITIVE else "avg"


def anomaly_default(context: "DescriptionContext") -> dict[str, Any] | None:
    if context.state != "confirmed" or not any(
        source.get("understanding_id") for source in context.view.sources
    ):
        return None
    observed = {item["name"]: item for item in context.profile["columns"]}
    candidates = [
        column
        for column in (context.view.definition or {}).get("columns", [])
        if column["name"] in context.view.metrics
        and (column.get("currency") or column.get("unit"))
        and not column.get("unit_column")
        and not observed[column["name"]]["type_conflicts"]
        and observed[column["name"]]["distinct_count"] <= 1000
        and context.profile["row_count"] - observed[column["name"]]["missing"] >= 8
    ]
    if not candidates:
        return None
    column = min(candidates, key=lambda item: exploration_rank(context, item["name"]))
    return dict(
        metric=column["name"],
        unit=column["currency"] or column["unit"],
        threshold="3.5",
        materiality="0",
        minimum_segment_size=8,
        reason="Check observed values against their snapshot median using the standard "
        "3.5 threshold and no minimum size of difference. This is an exploratory check, "
        "not a seasonal test, error verdict or probability. Saved measure filters still apply.",
    )
