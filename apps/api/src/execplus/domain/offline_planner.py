"""Use case: Plans simple data questions when the language model is turned off.

What it does: Matches field names loosely, recognises a small set of operations and
returns a validated plan only when nothing in the question would be silently dropped;
otherwise it offers varied questions that work without a model. The same executable
questions back clickable choices whenever a model plan cannot be validated.
"""

import json
import re
from typing import Any

from execplus.domain.conversation_requirements import loosely_named_metrics
from execplus.domain.guidance import words
from execplus.domain.intent import RoutedIntent, canonical_question, route_response
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import RECORD_COUNT, DatasetView

ROUTE = "deterministic:offline-plan-v1"
_UNIT_TOKENS = {"mm", "c", "kmh", "km", "cm", "kg", "ha", "hectare", "hours", "used", "type"}
_RESTRICTION = (
    r"\b(in|where|only|with|without|above|below|over|under|than|except|excluding|between|"
    r"during|after|before|since|not|mein|sirf|when|if)\b|[<>=]"
)
_SHARE = r"%|\b(percent|percentage|share|proportion|ratio|distribution|breakdown|split)\b"
_AGGREGATIONS = (
    ("avg", r"\b(average|averages|avg|mean|ausat)\b"),
    ("sum", r"\b(total|sum|kul)\b"),
    ("max", r"\b(maximum|max)\b"),
    ("min", r"\b(minimum|min)\b"),
)
_COUNT = r"\b(how many|count|number of|kitne|kitni|common|frequent|popular)\b"
_GROUP = r"\b(by|per|each|wise|across|vs|versus|compare|which|har)\b"
_HIGH = r"\b(highest|most|top|largest|biggest|zyada)\b"
_LOW = r"\b(lowest|least|bottom|smallest|kam)\b"
_MISSING = r"\b(missing|blank|empty|no|without)\b"
_RELATE = r"\b(relate|relates|related|relationship|correlat\w*|associated|depend\w*|affect\w*)\b"


def _matched(question: str, view: DatasetView) -> list[str]:
    tokens = set(words(question).split())
    tokens |= {token[:-1] for token in tokens if len(token) > 3 and token.endswith("s")}
    hits: dict[str, set[str]] = {}
    for column in view.columns:
        if "identifier" in column.tags:
            continue
        parts = set(words(column.name).split())
        core = parts - _UNIT_TOKENS or parts
        if core <= tokens:
            hits[column.name] = parts & tokens
    return [
        name for name, found in hits.items() if not any(found < other for other in hits.values())
    ]


def _measure_named_by_category(
    question: str, view: DatasetView, dimensions: list[str]
) -> list[str]:
    tokens = set(words(question).split())
    for name in dimensions:
        parts = set(words(name).split())
        found = parts & tokens
        owners = [
            column.name
            for column in view.columns
            if column.name in view.metrics
            and "identifier" not in column.tags
            and found <= set(words(column.name).split())
        ]
        if found != parts and len(owners) == 1:
            dimensions.remove(name)
            return owners
    return []


def _plan(kind: str, body: dict[str, Any], view: DatasetView) -> RoutedIntent | None:
    routed = route_response(json.dumps({"kind": kind, **body}), view)
    return None if routed.kind == QuestionKind.UNSUPPORTED else routed


def _missing_plan(text: str, question: str, view: DatasetView) -> RoutedIntent | None:
    if re.search(_GROUP, text) or re.search(r"\d", text):
        return None
    rest = re.sub(_MISSING + r"|\b(with|have|has|a|an|value|values)\b", " ", text)
    if re.search(_RESTRICTION, rest):
        return None
    names = list(dict.fromkeys([*_matched(question, view), *loosely_named_metrics(question, view)]))
    if len(names) != 1:
        return None
    filters = [{"column": names[0], "operator": "is_missing", "value": None}]
    if re.search(_COUNT, text):
        plan = {"metric": RECORD_COUNT, "aggregation": "count", "filters": filters}
        return _plan("numerical", {"plan": plan}, view)
    if re.search(r"\b(rows?|records?|show|list)\b", text):
        return _plan("rows", {"plan": {"columns": [], "filters": filters, "limit": 100}}, view)
    return None


def offline_plan(question: str, view: DatasetView) -> RoutedIntent | None:
    text = " ".join(words(question).replace("for each", "each").split())
    if re.search(_MISSING, text):
        return _missing_plan(text, question, view)
    top = re.search(r"\btop (\d{1,3})\b", text)
    if re.search(_RESTRICTION, text) or re.search(r"\d", re.sub(r"\btop \d{1,3}\b", "", text)):
        return None
    names = _matched(question, view)
    metrics = [name for name in names if name in view.metrics]
    dimensions = [
        name
        for name in names
        if name in view.dimensions and (column := view.column(name)) and column.type == "text"
    ]
    share = bool(re.search(_SHARE, question.casefold()))
    if not metrics and not share and not re.search(_COUNT, text):
        metrics = _measure_named_by_category(question, view, dimensions)
    if re.search(_RELATE, text) and metrics and not dimensions:
        return _plan("patterns", {"columns": metrics[:12]}, view)
    order = "desc" if re.search(_HIGH, text) else "asc" if re.search(_LOW, text) else None
    grouped = bool(re.search(_GROUP, text)) or bool((order or share) and dimensions)
    if len(dimensions) > (2 if grouped and not order else 1) or len(metrics) > 1:
        return None
    group_by = dimensions if grouped else []
    if dimensions and not group_by:
        return None
    if not metrics:
        if not group_by and not re.search(_COUNT, text):
            return None
        plan: dict[str, Any] = {
            "metric": RECORD_COUNT,
            "aggregation": "count",
            "group_by": group_by,
        }
    else:
        if share and not group_by:
            return _plan("rows", {"plan": {"columns": metrics, "filters": [], "limit": 1000}}, view)
        aggregation = next(
            (name for name, pattern in _AGGREGATIONS if re.search(pattern, text)), None
        )
        if aggregation is None:
            aggregation = next(
                (
                    entry["aggregation"]
                    for entry in (view.definition or {}).get("metrics", [])
                    if entry["column"] == metrics[0]
                ),
                "sum" if share else "avg" if group_by else None,
            )
        if aggregation is None:
            return None
        plan = {"metric": metrics[0], "aggregation": aggregation, "group_by": group_by}
    if order and group_by:
        plan["order"] = order
        if top:
            plan["limit"] = int(top.group(1))
    elif order or top:
        return None
    return _plan("numerical", {"plan": plan}, view)


def offline_choices(question: str, view: DatasetView) -> tuple[str, ...]:
    names = _matched(question, view)
    measures = [
        c.name for c in view.columns if c.name in view.metrics and "identifier" not in c.tags
    ]
    categories = [
        c.name
        for c in view.columns
        if c.name in view.dimensions and c.type == "text" and "identifier" not in c.tags
    ]
    measures.sort(key=lambda name: name not in names)
    categories.sort(key=lambda name: name not in names)
    choices = []
    if measures and categories:
        choices.append(f"Show the average of {measures[0]} by {categories[0]}")
    if categories:
        choices.append(
            f"How many records are there by {categories[-1 if len(categories) > 1 else 0]}?"
        )
    if len(measures) > 1:
        choices.append(f"Does {measures[0]} relate to {measures[1]}?")
    choices.append("Check data quality")
    return tuple(dict.fromkeys(choices))[:4]


def executable_choice(choice: str, view: DatasetView) -> bool:
    planned = canonical_question(choice, view)
    return planned is not None and planned.kind != QuestionKind.UNSUPPORTED


def working_choices(question: str, view: DatasetView) -> tuple[str, ...]:
    """Up to three related questions that plan deterministically on this file."""
    operation = "average" if re.search(_AGGREGATIONS[0][1], words(question)) else "total"
    named = dict.fromkeys(
        [
            *(name for name in _matched(question, view) if name in view.metrics),
            *loosely_named_metrics(question, view),
        ]
    )
    candidates = [f"What is the {operation} of {name}?" for name in list(named)[:2]]
    candidates += offline_choices(question, view)
    return tuple(choice for choice in dict.fromkeys(candidates) if executable_choice(choice, view))[
        :3
    ]
