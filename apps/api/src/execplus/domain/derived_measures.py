"""Use case: Answers rates, ratios and net differences from two governed component totals.

What it does: Recognises 'rate from A to B', 'A per B', 'X rate', 'ratio of A to B' and
'A minus B' requests whose parts map to known measures or category values, plans both totals
with the same grouping, and combines the returned exact values with Decimal arithmetic.
A language model never supplies the number; unclear parts return clickable choices.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Literal

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.guidance import words
from execplus.domain.models import Scalar
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
)
from execplus.domain.understanding import measure_unit

DERIVED_VERSION = "derived-v1"
DERIVED_ROUTE = "deterministic:derived-measure-v1"
SPEC_KEYS = ("version", "operation", "name", "percent", "order", "left", "right", "unit")

_STOP = frozenset(
    {"the", "a", "an", "of", "our", "my", "total", "overall", "what", "is", "show", "me", "by"}
)
_SYNONYMS = {
    "cost": ("spend", "expense"),
    "spend": ("cost", "expense"),
    "spending": ("spend", "cost", "expense"),
    "expense": ("cost", "spend"),
    "sale": ("revenue", "sales"),
    "revenue": ("sales",),
}
_FILLER = frozenset(
    [
        "what",
        "whats",
        "is",
        "are",
        "was",
        "the",
        "a",
        "an",
        "our",
        "my",
        "your",
        "which",
        "who",
        "has",
        "have",
        "had",
        "show",
        "me",
        "give",
        "tell",
        "calculate",
        "compute",
        "find",
        "get",
        "overall",
        "total",
        "current",
        "lowest",
        "highest",
        "least",
        "most",
        "best",
        "worst",
        "top",
        "smallest",
        "largest",
        "biggest",
        "cheapest",
        "minimum",
        "maximum",
        "by",
        "each",
        "every",
        "all",
        "across",
        "for",
        "of",
        "and",
        "please",
        "rate",
        "rates",
        "ratio",
        "conversion",
        "net",
        "do",
        "does",
        "we",
        "i",
        "us",
        "how",
        "much",
        "kya",
        "hai",
        "batao",
        "value",
    ]
)
_RATE_NAMES = frozenset({"conversion", "the", "a", "growth", "overall", "this", "what", "our"})
_WORDS = r"((?:\w+ ){0,4}\w+)"
_LOW = r"\b(lowest|least|smallest|worst|minimum|cheapest)\b"
_HIGH = r"\b(highest|most|largest|best|top|maximum|biggest)\b"


@dataclass(frozen=True, slots=True)
class DerivedRequest:
    operation: Literal["ratio", "difference"]
    name: str
    left: MetricRequest
    right: MetricRequest
    percent: bool = False
    order: Literal["asc", "desc"] | None = None
    unit: str = ""

    def spec(self) -> dict[str, Any]:
        return dict(
            version=DERIVED_VERSION,
            operation=self.operation,
            name=self.name,
            percent=self.percent,
            order=self.order,
            left=component_label(self.left),
            right=component_label(self.right),
            unit=self.unit,
        )


@dataclass(frozen=True, slots=True)
class DerivedChoices:
    message: str
    choices: tuple[str, ...]


def component_label(request: MetricRequest) -> str:
    scope = ", ".join(f"{item.column} = {item.value}" for item in request.filters)
    return f"{request.metric} ({scope})" if scope else request.metric


def stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _same(asked: str, token: str) -> bool:
    a, b = stem(asked), stem(token)
    return a == b or (min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)))


def _eligible(view: DatasetView) -> list[str]:
    return [
        column.name
        for column in view.columns
        if column.name in view.metrics and "identifier" not in column.tags
    ]


def measures_for(term: str, view: DatasetView) -> list[str]:
    """Measures named by a short phrase: name tokens/prefixes, then synonyms, then meanings."""
    asked = [token for token in words(term).split() if token not in _STOP]
    if not asked:
        return []

    def covered(tokens: list[str], options: list[str]) -> bool:
        return all(any(_same(word, token) for token in tokens) for word in options)

    names = _eligible(view)
    direct = [name for name in names if covered(words(name).split(), asked)]
    if direct:
        return direct
    for index, word in enumerate(asked):
        for synonym in _SYNONYMS.get(stem(word), ()):
            options = [*asked[:index], synonym, *asked[index + 1 :]]
            found = [name for name in names if covered(words(name).split(), options)]
            if found:
                return found
    meanings = {
        str(item["name"]): words(str(item.get("meaning", ""))).split()
        for item in (view.definition or {}).get("columns", [])
        if item.get("name") in names
    }
    return [name for name, tokens in meanings.items() if tokens and covered(tokens, asked)]


def _value_for(term: str, values: dict[str, tuple[str, ...]]) -> tuple[str, str] | None:
    asked = [stem(token) for token in words(term).split() if token not in _STOP]
    found = [
        (column, label)
        for column, labels in values.items()
        for label in labels
        if asked and [stem(token) for token in words(label).split()] == asked
    ]
    return found[0] if len(found) == 1 else None


def _group(text: str, view: DatasetView) -> tuple[str | None, list[tuple[int, int]]]:
    found: list[tuple[str, tuple[int, int]]] = []
    for column in view.columns:
        if (
            column.name not in view.dimensions
            or column.type != "text"
            or "identifier" in column.tags
        ):
            continue
        label = re.escape(words(column.name))
        for match in re.finditer(
            rf"\b(?:by|per|each|across|which|for each) {label}s?\b|\b{label}s? wise\b", text
        ):
            found.append((column.name, match.span()))
    names = {name for name, _ in found}
    if len(names) > 1:
        raise ValueError("Several groupings")
    return (found[0][0] if found else None), [span for _, span in found]


def _phrases(tokens: list[str], end: int, *, before: bool) -> list[tuple[str, int, int]]:
    spans = []
    for size in (3, 2, 1):
        start, stop = (end - size, end) if before else (end, end + size)
        if start >= 0 and stop <= len(tokens):
            spans.append((" ".join(tokens[start:stop]), start, stop))
    return spans


def _measure(term: str, view: DatasetView) -> str | None:
    found = measures_for(term, view)
    return found[0] if len(found) == 1 else None


def _first_measure(
    spans: list[tuple[str, int, int]], view: DatasetView
) -> tuple[str, int, int] | None:
    for term, start, stop in spans:
        if (name := _measure(term, view)) is not None:
            return name, start, stop
    return None


def _char_span(tokens: list[str], start: int, stop: int) -> tuple[int, int]:
    begin = len(" ".join(tokens[:start])) + (1 if start else 0)
    return begin, begin + len(" ".join(tokens[start:stop]))


def _leftover_is_clean(
    text: str, spans: list[tuple[int, int]], view: DatasetView, used: set[str], group: str | None
) -> bool:
    """Only filler words may remain, so no unparsed filter or period is silently dropped."""
    kept = list(text)
    for start, stop in spans:
        kept[start:stop] = [" "] * (stop - start)
    known = {
        stem(token)
        for name in (*used, *((group,) if group else ()))
        for token in words(name).split()
    }
    return all(token in _FILLER or stem(token) in known for token in "".join(kept).split())


def _edge_measure(phrase: str, view: DatasetView, *, last: bool) -> str | None:
    for name in sorted(_eligible(view), key=len, reverse=True):
        label = words(name)
        if (phrase.endswith(label) if last else phrase.startswith(label)) and (
            len(phrase) == len(label) or phrase[-len(label) - 1 if last else len(label)] == " "
        ):
            return name
    tokens = phrase.split()
    for size in (3, 2, 1):
        if size <= len(tokens):
            part = tokens[-size:] if last else tokens[:size]
            if (found := _measure(" ".join(part), view)) is not None:
                return found
    return None


def _ratio_parts(
    text: str, tokens: list[str], view: DatasetView
) -> tuple[str, str, str, bool, list[tuple[int, int]]] | DerivedChoices | None:
    """(numerator, denominator, name, percent, spans) for one ratio phrasing."""
    if found := re.search(r"\brates? from (.+?) to (.+?)(?= by | per | for | across |$)", text):
        source = _edge_measure(found.group(1), view, last=False)
        target = _edge_measure(found.group(2), view, last=False)
        if not (source and target):
            return None
        spans = [found.span()]
        name = "rate"
        if conversion := re.search(r"\bconversion\b", text):
            spans.append(conversion.span())
            name = "conversion rate"
        return target, source, name, True, spans
    patterns = (
        (r"\bratio of (.+?) to (.+?)(?= by | for | across |$)", False),
        (rf"\b{_WORDS} to {_WORDS} ratio\b", False),
        (rf"\b{_WORDS} divided by {_WORDS}\b", False),
        (rf"\b{_WORDS} as a percentage of {_WORDS}\b", True),
    )
    for pattern, percent in patterns:
        if found := re.search(pattern, text):
            left = _edge_measure(found.group(1), view, last=True)
            right = _edge_measure(found.group(2), view, last=False)
            if not (left and right):
                return None
            name = "percentage" if percent else f"{left} to {right} ratio"
            return left, right, name, percent, [found.span()]
    if "per" in tokens:
        index = tokens.index("per")
        top = _first_measure(_phrases(tokens, index, before=True), view)
        bottom = _first_measure(_phrases(tokens, index + 1, before=False), view)
        if not (top and bottom):
            return None
        begin, _ = _char_span(tokens, top[1], top[2])
        _, end = _char_span(tokens, bottom[1], bottom[2])
        return top[0], bottom[0], text[begin:end], False, [(begin, end)]
    for found in re.finditer(r"\b(\w+) rates?\b", text):
        term = found.group(1)
        if term in _RATE_NAMES:
            continue
        pairs = []
        for numerator in measures_for(term, view):
            parts = words(numerator).split()
            key = [token for token in parts if not _same(term, token)]
            pairs += [
                (numerator, other)
                for other in _eligible(view)
                if other != numerator
                and key
                and len(words(other).split()) == len(parts)
                and all(token in words(other).split() for token in key)
            ]
        if len(pairs) == 1:
            return pairs[0][0], pairs[0][1], f"{term} rate", True, [found.span()]
        if len(pairs) > 1:
            return DerivedChoices(
                f"This file has {len(pairs)} possible {term} rates, one per pair of fields. "
                "Which one should I calculate?",
                tuple(f"What is {num} as a percentage of {den}?" for num, den in pairs[:3]),
            )
    return None


def derived_request(
    question: str, view: DatasetView, values: dict[str, tuple[str, ...]] | None = None
) -> DerivedRequest | DerivedChoices | None:
    """A rate/ratio/difference whose two parts are clear, choices when unclear, else None."""
    values = values or {}
    raw = re.sub(r"\s*[\u2212\u2013]\s*|\s+-\s+", " minus ", question)
    text = words(raw)
    tokens = text.split()
    try:
        group, group_spans = _group(text, view)
    except ValueError:
        return None
    order: Literal["asc", "desc"] | None = None
    if group and re.search(_LOW, text):
        order = "asc"
    elif group and re.search(_HIGH, text):
        order = "desc"
    group_by = (group,) if group else ()

    def total(metric: str, *filters: MetricFilter) -> MetricRequest:
        return MetricRequest(metric, AggregationKind.SUM, group_by, tuple(filters))

    if "minus" in tokens or re.search(r"\bsubtract\w*\b", text):
        if "minus" not in tokens:
            return None
        index = tokens.index("minus")
        before, after = (
            _phrases(tokens, index, before=True),
            _phrases(tokens, index + 1, before=False),
        )
        left_value = next(
            ((v, s, e) for term, s, e in before if (v := _value_for(term, values))), None
        )
        right_value = next(
            ((v, s, e) for term, s, e in after if (v := _value_for(term, values))), None
        )
        name = "net" if re.search(r"\bnet\b", text) else "difference"
        if left_value and right_value and left_value[0][0] == right_value[0][0]:
            column = left_value[0][0]
            span = _char_span(tokens, left_value[1], right_value[2])
            outside = text[: span[0]] + " " * (span[1] - span[0]) + text[span[1] :]
            named = [
                name_
                for term in re.findall(r"\b\w+(?: \w+)?\b", outside)
                for name_ in [_measure(term, view)]
                if name_
            ]
            candidates = list(dict.fromkeys(named)) or _eligible(view)
            if len(candidates) != 1:
                labels = left_value[0][1], right_value[0][1]
                return DerivedChoices(
                    f"Which measure should I use for {labels[0]} minus {labels[1]}?",
                    tuple(
                        f"What is the total of {measure} for {labels[0]} minus {labels[1]}?"
                        for measure in candidates[:3]
                    ),
                )
            measure = candidates[0]
            spans = [span, *group_spans]
            spans += [found.span() for found in re.finditer(r"\bnet \w+", text)]
            for term in words(measure).split():
                spans += [found.span() for found in re.finditer(rf"\b{re.escape(term)}\b", text)]
            if not _leftover_is_clean(text, spans, view, {measure}, group):
                return None
            unit, currency = measure_unit(view.definition, measure)
            return DerivedRequest(
                "difference",
                name,
                total(measure, MetricFilter(column, FilterOperator.IEQ, left_value[0][1])),
                total(measure, MetricFilter(column, FilterOperator.IEQ, right_value[0][1])),
                order=order,
                unit=currency or unit,
            )
        left = _first_measure(before, view)
        right = _first_measure(after, view)
        if not (left and right) or left[0] == right[0]:
            return None
        left_unit = measure_unit(view.definition, left[0])
        right_unit = measure_unit(view.definition, right[0])
        if left_unit != right_unit and any(left_unit) and any(right_unit):
            raise UnsupportedQuestionError(
                f"{left[0]} and {right[0]} have different units, so subtracting them would "
                "not give a meaningful number."
            )
        spans = [_char_span(tokens, left[1], right[2]), *group_spans]
        if not _leftover_is_clean(text, spans, view, {left[0], right[0]}, group):
            return None
        return DerivedRequest(
            "difference",
            name,
            total(left[0]),
            total(right[0]),
            order=order,
            unit=left_unit[1] or left_unit[0] or right_unit[1] or right_unit[0],
        )
    parts = _ratio_parts(text, tokens, view)
    if parts is None or isinstance(parts, DerivedChoices):
        return parts
    numerator, denominator, name, percent, spans = parts
    if not _leftover_is_clean(text, [*spans, *group_spans], view, {numerator, denominator}, group):
        return None
    currency = measure_unit(view.definition, numerator)[1]
    return DerivedRequest(
        "ratio",
        name,
        total(numerator),
        total(denominator),
        percent=percent,
        order=order,
        unit="" if percent else currency,
    )


def _decimal(value: Scalar) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    number = Decimal(str(value))
    return number if number.is_finite() else None


def _shown(value: Decimal) -> str:
    if value == value.to_integral_value():
        return format(value, ",.0f")
    return format(value.quantize(Decimal("0.01"), ROUND_HALF_EVEN), ",f")


def _cell(value: Decimal) -> str:
    return "0" if value.is_zero() else format(value, "f")


def combine(
    spec: dict[str, Any],
    left: list[tuple[Scalar, Scalar]],
    right: list[tuple[Scalar, Scalar]],
    group: str | None,
) -> dict[str, Any]:
    """Exact rows and a one-paragraph message for two returned component results."""
    if spec.get("version") != DERIVED_VERSION:
        raise ValueError("Unsupported derived measure version")
    ratio = spec["operation"] == "ratio"
    percent = bool(spec["percent"])
    by_group = {key: value for key, value in right}
    rows: list[tuple[Scalar, Decimal | None, Decimal | None, Decimal | None, str]] = []
    for key, raw in left:
        a, b = _decimal(raw), _decimal(by_group.get(key))
        note = ""
        value: Decimal | None = None
        if a is None or b is None:
            note = "a part is missing"
        elif ratio and b.is_zero():
            note = f"not defined because {spec['right']} is 0"
        elif ratio:
            with localcontext() as context:
                context.prec = 50
                exact = a / b * (100 if percent else 1)
            value = exact.quantize(Decimal("0.0001" if percent else "0.000001"), ROUND_HALF_EVEN)
        else:
            value = a - b
        rows.append((key, value, a, b, note))
    for key, raw in right:
        if key not in {item[0] for item in left}:
            rows.append((key, None, None, _decimal(raw), "a part is missing"))
    if spec.get("order") in ("asc", "desc"):
        ranked = sorted(
            (row for row in rows if row[1] is not None),
            key=lambda row: row[1] or Decimal(0),
            reverse=spec["order"] == "desc",
        )
        rows = ranked + [row for row in rows if row[1] is None]
    sign = "÷" if ratio else "\u2212"
    suffix = "%" if percent else f" {spec['unit']}" if spec.get("unit") else ""
    title = spec["name"] + (" (%)" if percent else "")
    columns = [*([group] if group else []), title, spec["left"], spec["right"]]

    def text(value: Decimal | None) -> str | None:
        return None if value is None else _cell(value)

    table = [
        [*([key] if group else []), text(value), text(a), text(b)] for key, value, a, b, _ in rows
    ]
    formula = f"{spec['name']} = {spec['left']} {sign} {spec['right']}"
    if percent:
        formula += " \u00d7 100"
    described = []
    for key, value, a, b, note in rows[:5]:
        prefix = f"{key if key is not None else 'missing'}: " if group else ""
        if value is None:
            described.append(f"{prefix}{note}")
        else:
            described.append(
                f"{prefix}{_shown(value)}{suffix} ({_shown(a or Decimal(0))} {sign} "
                f"{_shown(b or Decimal(0))})"
            )
    lead = (
        "Lowest first: "
        if spec.get("order") == "asc"
        else "Highest first: "
        if spec.get("order") == "desc"
        else "Result: "
        if not group
        else ""
    )
    more = f" … and {len(rows) - 5} more in the table." if len(rows) > 5 else ""
    summary = f"{lead}{'; '.join(described)}.{more}"
    return dict(
        spec,
        formula=formula,
        group=group,
        columns=columns,
        rows=table,
        summary=summary,
        message=f"{formula}{' by ' + group if group else ''}. I ran each total as its own "
        "verified query and combined the two returned values exactly; the AI did not "
        f"calculate it. {summary}",
    )
