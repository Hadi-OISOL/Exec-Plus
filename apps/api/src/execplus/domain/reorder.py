"""Use case: Answers "what should I reorder first?" with one stated rule, not a model guess.

What it does: Finds the stock-on-hand and reorder-point fields of an inventory-like file and
ranks the returned rows by how far stock is below the reorder point (or by lowest stock when
no reorder point exists). Every figure is a returned row value or a difference of two.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from execplus.domain.guidance import words
from execplus.domain.semantics import DatasetView

REORDER_ROUTE = "deterministic:reorder-rule-v1"

_ASKS = re.compile(
    r"\b(what|which|items?|skus?|products?)\b.*\b(should|to|need|needs)\b.*"
    r"\b(reorder|re order|restock|replenish|order more)\w*"
    r"|\b(running out|run out|out of stock|stock out|low on stock|low stock)\b"
    r"|\bbelow (their |the |its )?reorder\b"
)
_STOCK = re.compile(r"\b(on hand|stock|inventory|available)\b")
_NOT_STOCK = re.compile(r"\b(reorder|days|cost|value|price|sold|sales|lead|min|safety|max)\b")
_LABEL = re.compile(r"\b(sku|product|item|name|description|title)\b")


@dataclass(frozen=True, slots=True)
class ReorderFields:
    stock: str
    reorder: str | None
    labels: tuple[str, ...]


def asks_what_to_reorder(question: str) -> bool:
    return bool(_ASKS.search(words(question)))


def reorder_fields(view: DatasetView) -> ReorderFields | None:
    metrics = [column.name for column in view.columns if column.name in view.metrics]
    stock = [
        name
        for name in metrics
        if _STOCK.search(words(name)) and not _NOT_STOCK.search(words(name))
    ]
    if len(stock) != 1:
        return None
    reorder = [name for name in metrics if re.search(r"\breorder\b", words(name))]
    texts = [
        column.name
        for column in view.columns
        if column.name in view.dimensions and column.type == "text"
    ]
    labels = sorted(texts, key=lambda name: not _LABEL.search(words(name)))[:3]
    return ReorderFields(stock[0], reorder[0] if len(reorder) == 1 else None, tuple(labels))


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool) or not isinstance(value, int | Decimal | float):
        return None
    return Decimal(str(value))


def _text(value: Decimal) -> str:
    return f"{value.normalize():f}" if value == value.to_integral() else f"{value:f}"


def reorder_message(
    fields: ReorderFields,
    rows: tuple[tuple[Any, ...], ...],
    records: int,
    truncated: bool,
    limit: int = 10,
) -> str:
    """Rows are the label fields, then stock, then reorder point when present."""
    count = len(fields.labels)
    items: list[tuple[str, Decimal]] = []
    paired: list[tuple[str, Decimal, Decimal]] = []
    for row in rows:
        stock = _number(row[count])
        point = _number(row[count + 1]) if fields.reorder else None
        if stock is None:
            continue
        name = ", ".join("—" if value is None else str(value) for value in row[:count]) or "Row"
        items.append((name, stock))
        if point is not None:
            paired.append((name, stock, point))
    scope = (
        f"the {len(rows):,} rows with the lowest {fields.stock} (the file has {records:,})"
        if truncated
        else f"all {records:,} rows"
    )
    if fields.reorder is None:
        ranked = sorted(items, key=lambda item: item[1])[:limit]
        lines = [
            f"{i}. {name} — {fields.stock} {_text(s)}" for i, (name, s) in enumerate(ranked, 1)
        ]
        rule = (
            f"Rule used: lowest {fields.stock} first. This file has no reorder-point field, "
            "so stock is not compared with a target level."
        )
        return "\n\n".join([rule, f"Lowest stock in {scope}\n" + "\n".join(lines)])
    below = [item for item in paired if item[1] < item[2]]
    at = sum(1 for item in paired if item[1] == item[2])
    shortfall = sorted(below, key=lambda item: (item[1] - item[2], item[1], item[0]))[:limit]
    parts = [
        f"Rule used: items whose {fields.stock} is below their {fields.reorder}, largest "
        f"shortfall ({fields.reorder} minus {fields.stock}) first. Checked {scope}.",
        f"{len(below):,} items are below their reorder point; {at:,} are exactly at it.",
    ]
    if shortfall:
        parts.append(
            "Reorder first\n"
            + "\n".join(
                f"{i}. {name} — {fields.stock} {_text(s)}, {fields.reorder} {_text(p)}, "
                f"short by {_text(p - s)}"
                for i, (name, s, p) in enumerate(shortfall, 1)
            )
        )
    parts.append(
        "This uses only the stock and reorder-point values in the file; it does not "
        "account for sales speed, lead times or open orders."
    )
    return "\n\n".join(parts)
