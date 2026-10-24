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


_DERIVED = (
    r"\b(rate|rates|ratio|per|minus|net|margin|percentage|percent|proportion|divided|"
    r"difference)\b"
)
_RATIO = r"\b(rate|rates|ratio|per|percentage|percent|proportion|divided)\b"
_WHEN = r"\b(when|what time|which (day|date|week|month|hour|time))\b"
_SYNONYMS = {"cost": "spend", "costs": "spend", "spend": "cost", "expense": "cost spend"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _named_measures(text: str, view: DatasetView) -> tuple[list[str], int]:
    tokens = words(text).split()
    positions = [{_stem(token), *map(_stem, _SYNONYMS.get(token, "").split())} for token in tokens]
    expanded = " ".join([text, *(_SYNONYMS.get(token, "") for token in tokens)])
    found = dict.fromkeys(
        [
            *(name for name in _matched(text, view) if name in view.metrics),
            *loosely_named_metrics(expanded, view),
        ]
    )

    def position(name: str) -> int:
        parts = {_stem(token) for token in words(name).split()}
        return next((i for i, stems in enumerate(positions) if stems & parts), len(positions))

    ordered = sorted(found, key=lambda name: (position(name), name))
    return ordered, len({position(name) for name in ordered})


def _named_categories(
    text: str, view: DatasetView, values: dict[str, tuple[str, ...]]
) -> list[str]:
    asked = {_stem(token) for token in words(text).split()}
    by_value = [
        name
        for name, labels in values.items()
        if any(
            len(words(label)) >= 3 and {_stem(token) for token in words(label).split()} <= asked
            for label in labels
        )
    ]
    return list(
        dict.fromkeys(
            [
                *(
                    name
                    for name in _matched(text, view)
                    if name in view.dimensions
                    and (column := view.column(name))
                    and column.type == "text"
                ),
                *by_value,
            ]
        )
    )


def _denominator(numerator: str, named: list[str], view: DatasetView) -> str | None:
    parts = set(words(numerator).split())
    scored = [
        (len(parts & set(words(name).split())), name)
        for name in sorted(view.metrics)
        if name not in named
        and (column := view.column(name)) is not None
        and "identifier" not in column.tags
    ]
    best = max(scored, default=(0, ""), key=lambda item: item[0])
    return best[1] if best[0] else None


def working_choices(
    question: str,
    view: DatasetView,
    context: str = "",
    values: dict[str, tuple[str, ...]] | None = None,
    lead: tuple[str, ...] = (),
    groups: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Up to three questions that plan deterministically, most relevant to the question first.

    Fields, grouping and category values named in the question rank first, then those of the
    previous turn (context). A rate or difference offers each component total separately,
    grouped the way the user asked.
    """
    values = values or {}
    text = words(question)
    asked, concepts = _named_measures(question, view)
    named = list(dict.fromkeys([*lead, *asked]))
    categories = list(dict.fromkeys([*groups, *_named_categories(question, view, values)]))
    derived = bool(re.search(_DERIVED, text))
    if re.search(_RATIO, text) and named and concepts <= 1:
        denominator = _denominator(named[0], named, view)
        if denominator:
            named.insert(1, denominator)
    if not named:
        named = _named_measures(context, view)[0]
    if not named and derived:
        named = [
            column.name
            for column in view.columns
            if column.name in view.metrics and "identifier" not in column.tags
        ][:1]
    if not categories:
        categories = _named_categories(context, view, values) if not asked else []
    group = f" by {categories[0]}" if categories else ""
    dates = [
        column.name
        for column in view.columns
        if column.name in view.dimensions and (column.type == "date" or column.has_time)
    ]
    when = bool(re.search(_WHEN, text))
    candidates: list[str] = []
    if when and dates:
        candidates += [f"Which {dates[0]} has the highest maximum {name}?" for name in named[:2]]
    operation = (
        "maximum"
        if when
        else "average"
        if re.search(_AGGREGATIONS[0][1], text) and not derived
        else "total"
    )
    candidates += [f"What is the {operation} of {name}{group}?" for name in named[:3]]
    if categories and not named:
        candidates.append(f"How many records are there{group}?")
    relevant = {*named, *categories}

    def score(choice: str) -> int:
        return sum(bool(re.search(rf"\b{re.escape(name)}\b", choice)) for name in relevant)

    generic = sorted(offline_choices(question, view), key=score, reverse=True)
    working = [choice for choice in dict.fromkeys(candidates) if executable_choice(choice, view)]
    working += [
        choice
        for choice in generic
        if choice not in working
        and executable_choice(choice, view)
        and (score(choice) or not working)
    ]
    return tuple(working[:3])
