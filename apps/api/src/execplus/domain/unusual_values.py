"""Use case: Finds unusual individual values in a file without asking the user for settings.

What it does: Picks eligible measures and one comparison group, then ranks robust MAD/IQR outliers.
"""

from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import number, quantile
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.exploration_selection import exploration_rank, tokens
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import MetricRequest, quote_identifier, validate_read_only
from execplus.domain.understanding import governed_request, preferred_aggregation

VERSION = "unusual-values-scan-v1"
THRESHOLD = Decimal("3.5")
SCALE = Decimal("0.67448975")
MAX_ROWS = 10_000
MAX_MEASURES = 12
MIN_VALUES = 8
MAX_GROUPS = 12
MAX_FLAGGED_SHARE = Decimal("0.1")
MAX_FINDINGS = 25
MAX_CLOSEST = 3
IDENTIFIER_WORDS = {"id", "code", "sku", "zip", "postal"}


@dataclass(frozen=True)
class Reference:
    median: Decimal
    mad: Decimal
    q1: Decimal
    q3: Decimal
    method: str

    def score(self, value: Decimal) -> tuple[bool, Decimal | None]:
        with localcontext() as context:
            context.prec = 128
            distance = abs(value - self.median)
            if self.mad:
                score = SCALE * distance / self.mad
                return score > THRESHOLD, score
            spread = self.q3 - self.q1
            if spread:
                return (
                    value < self.q1 - THRESHOLD * spread or value > self.q3 + THRESHOLD * spread,
                    None,
                )
            return value != self.median, None


def plain(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def reference(values: list[Decimal]) -> Reference:
    count = len(values)
    ordered = sorted(Counter(values).items())
    with localcontext() as context:
        context.prec = 128
        median = quantile(ordered, count, Decimal("0.5"))
        deviations = sorted(Counter(abs(value - median) for value in values).items())
        mad = quantile(deviations, count, Decimal("0.5"))
        q1, q3 = (quantile(ordered, count, Decimal(q)) for q in ("0.25", "0.75"))
    method = "mad" if mad else "iqr" if q3 - q1 else "constant_reference"
    return Reference(median, mad, q1, q3, method)


def _identifier(context: DescriptionContext) -> str | None:
    definition = {item["name"]: item for item in (context.definition or {}).get("columns", [])}
    for column in context.view.columns:
        if definition:
            if definition.get(column.name, {}).get("role") == "identifier":
                return column.name
        elif "identifier" in column.tags or tokens(column.name) & IDENTIFIER_WORDS:
            return column.name
    return None


def _group(context: DescriptionContext, identifier: str | None) -> str | None:
    rows = context.profile["row_count"]
    observed = {item["name"]: item for item in context.profile["columns"]}
    candidates = [
        name
        for name in context.view.dimensions
        if name != identifier
        and observed[name]["type"] != "date"
        and not observed[name]["type_conflicts"]
        and 2 <= observed[name]["distinct_count"] <= MAX_GROUPS
        and rows >= MIN_VALUES * observed[name]["distinct_count"]
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda name: exploration_rank(context, name))


def scan_request(context: DescriptionContext, table: TableData) -> dict[str, Any]:
    saved = any(source.get("understanding_id") for source in context.view.sources)
    if saved and context.state != "confirmed":
        raise ClarificationRequiredError(
            "Your saved data meanings are still a draft. Confirm them once, "
            "then unusual values can be checked automatically."
        )
    if context.profile["row_count"] > MAX_ROWS:
        raise ClarificationRequiredError(
            "The automatic check supports files with up to 10,000 rows. "
            "Use Advanced options to check one measure."
        )
    definition = {item["name"]: item for item in (context.definition or {}).get("columns", [])}
    observed = {item["name"]: item for item in context.profile["columns"]}
    identifier = _identifier(context)
    measures: list[str] = []
    units: dict[str, str | None] = {}
    exclusions: list[dict[str, str]] = []
    for name in sorted(context.view.metrics, key=lambda item: exploration_rank(context, item)):
        meaning = definition.get(name, {})
        reason = ""
        if name == identifier:
            reason = "This column identifies records rather than measuring them."
        elif meaning.get("unit_column"):
            reason = "Its unit changes from row to row, so values are not comparable."
        elif observed[name]["type_conflicts"]:
            reason = "Some values are not numbers; fix them before checking this column."
        elif context.profile["row_count"] - observed[name]["missing"] < MIN_VALUES:
            reason = "Fewer than eight filled-in values."
        elif observed[name]["distinct_count"] <= 1:
            reason = "Every value is the same."
        elif len(measures) >= MAX_MEASURES:
            reason = "The automatic check covers twelve measures; use Advanced options for more."
        else:
            try:
                governed = governed_request(
                    context.view,
                    table,
                    MetricRequest(name, preferred_aggregation(context.view, name)),
                )
            except ClarificationRequiredError as error:
                reason = str(error)
            else:
                if governed.filters:
                    reason = "Its saved definition limits which rows count; use Advanced options."
        if reason:
            exclusions.append(dict(column=name, reason=reason))
            continue
        measures.append(name)
        units[name] = meaning.get("currency") or meaning.get("unit") or None
    if not measures:
        raise ClarificationRequiredError(
            "No numeric column can be checked for unusual values yet. "
            + " ".join(f"{item['column']}: {item['reason']}" for item in exclusions[:3])
            if exclusions
            else "This file has no numeric columns that can be checked for unusual values."
        )
    return dict(
        version=VERSION,
        meaning="confirmed" if context.state == "confirmed" and saved else "inferred",
        identifier=identifier,
        group_column=_group(context, identifier),
        measures=measures,
        units=units,
        exclusions=exclusions,
    )


def scan_plan(scope: WorkspaceScope, did: UUID, request: dict[str, Any]) -> QueryPlan:
    columns = [
        name for name in (request["identifier"], request["group_column"]) if name is not None
    ] + request["measures"]
    fields = ", ".join(quote_identifier(name) for name in columns)
    sql = f'SELECT {fields} FROM "dataset" ORDER BY {fields} LIMIT {MAX_ROWS + 1}'
    validate_read_only(sql)
    return QueryPlan(uuid4(), scope.workspace_id, did, "Find unusual values", sql, ())


def _range(values: list[Decimal], reference_value: Reference) -> tuple[str, str]:
    usual = [value for value in values if not reference_value.score(value)[0]] or values
    return plain(min(usual)), plain(max(usual))


def _finding(
    request: dict[str, Any],
    row: tuple[Any, ...],
    name: str,
    value: Decimal,
    score: Decimal | None,
    reference_value: Reference,
    usual: tuple[str, str],
    group: str | None,
    unusual: bool = True,
) -> dict[str, Any]:
    unit = request["units"][name]
    suffix = f" {unit}" if unit else ""
    label = (
        f"{request['identifier']} {row[0]}"
        if request["identifier"] and row[0] is not None
        else "One row"
    )
    direction = "high" if value > reference_value.median else "low"
    compared = (
        f"other rows where {request['group_column']} is {group}"
        if group is not None
        else "the rest of the file"
    )
    rounded = None if score is None else score.quantize(Decimal("0.01"), ROUND_HALF_EVEN)
    return dict(
        row=label,
        column=name,
        value=plain(value),
        unit=unit,
        direction=direction,
        compared_with="group" if group is not None else "file",
        group=None if group is None else dict(column=request["group_column"], value=group),
        median=plain(reference_value.median),
        usual_low=usual[0],
        usual_high=usual[1],
        score=None if rounded is None else plain(rounded),
        method=reference_value.method,
        explanation=(
            f"{label}: {name} is {plain(value)}{suffix}, unusually {direction} compared with "
            f"{compared}. Usual values there are {usual[0]} to {usual[1]}{suffix} "
            f"(middle value {plain(reference_value.median)}{suffix})."
            if unusual
            else f"{label}: {name} is {plain(value)}{suffix}, further from the middle value "
            f"({plain(reference_value.median)}{suffix}) than most rows, but still inside "
            f"the usual range of {usual[0]} to {usual[1]}{suffix}."
        ),
        _rank=(score is None, -(score or Decimal(0)), name),
    )


def scan_result(value: QueryResult, request: dict[str, Any]) -> dict[str, Any]:
    if len(value.rows) > MAX_ROWS:
        raise ClarificationRequiredError(
            "The automatic check supports files with up to 10,000 rows."
        )
    offset = (request["identifier"] is not None) + (request["group_column"] is not None)
    group_index = offset - 1 if request["group_column"] is not None else None
    best: dict[tuple[int, str], dict[str, Any]] = {}
    closest: list[dict[str, Any]] = []
    measures = []
    exclusions = list(request["exclusions"])
    for position, name in enumerate(request["measures"]):
        index = offset + position
        present = [
            (row_number, number(row[index]))
            for row_number, row in enumerate(value.rows)
            if row[index] is not None
        ]
        if len(present) < MIN_VALUES:
            exclusions.append(dict(column=name, reason="Fewer than eight filled-in values."))
            continue
        references: list[tuple[str | None, list[tuple[int, Decimal]]]] = [(None, present)]
        if group_index is not None:
            groups: dict[str, list[tuple[int, Decimal]]] = {}
            for row_number, item in present:
                label = value.rows[row_number][group_index]
                if label is not None and str(label).strip():
                    groups.setdefault(str(label), []).append((row_number, item))
            references.extend(
                (label, members)
                for label, members in sorted(groups.items())
                if len(members) >= MIN_VALUES
            )
        flagged_here = 0
        whole = reference([item for _, item in present])
        for group, members in references:
            numbers = [item for _, item in members]
            reference_value = whole if group is None else reference(numbers)
            usual = _range(numbers, reference_value)
            scored = [
                (row_number, item, *reference_value.score(item)) for row_number, item in members
            ]
            unusual = [item for item in scored if item[2]]
            if len(unusual) > 1 and Decimal(len(unusual)) > MAX_FLAGGED_SHARE * len(members):
                if group is None:
                    exclusions.append(
                        dict(
                            column=name,
                            reason="Many values differ from the usual value, "
                            "so no single row stands out.",
                        )
                    )
                continue
            for row_number, item, _, score in unusual:
                finding = _finding(
                    request,
                    value.rows[row_number],
                    name,
                    item,
                    score,
                    reference_value,
                    usual,
                    group,
                )
                key = (row_number, name)
                if key not in best or finding["_rank"] < best[key]["_rank"]:
                    if key not in best:
                        flagged_here += 1
                    best[key] = finding
            if group is None:
                extremes = sorted(
                    (entry for entry in scored if entry[3] is not None),
                    key=lambda entry: -(entry[3] or Decimal(0)),
                )[:MAX_CLOSEST]
                closest.extend(
                    _finding(request, value.rows[row], name, item, score, whole, usual, None, False)
                    for row, item, _, score in extremes
                )
        low, high = _range([item for _, item in present], whole)
        measures.append(
            dict(
                column=name,
                unit=request["units"][name],
                checked=len(present),
                median=plain(whole.median),
                usual_low=low,
                usual_high=high,
                flagged=flagged_here,
            )
        )
    findings = sorted(best.values(), key=lambda item: item["_rank"])
    nearest = [] if findings else sorted(closest, key=lambda entry: entry["_rank"])[:MAX_CLOSEST]
    for entry in (*findings, *nearest):
        entry.pop("_rank", None)
    grouped = f" and within each {request['group_column']}" if request["group_column"] else ""
    summary = (
        f"We checked {len(measures)} measures across {len(value.rows)} rows{grouped}. "
        + (f"{len(findings)} values stand out." if len(findings) != 1 else "1 value stands out.")
        if findings
        else f"We checked {len(measures)} measures across {len(value.rows)} rows{grouped}. "
        "Nothing stands out: every value sits inside the usual range for its column."
    )
    return dict(
        version=VERSION,
        meaning=request["meaning"],
        rows=len(value.rows),
        identifier=request["identifier"],
        group_column=request["group_column"],
        threshold=plain(THRESHOLD),
        summary=summary,
        measures=measures,
        findings=findings[:MAX_FINDINGS],
        total_findings=len(findings),
        closest=nearest,
        exclusions=exclusions,
        limitations=[
            "Unusual means far from the other values in this file, not wrong, fraudulent "
            "or caused by anything in particular.",
            "Scores are robust distance measures (above 3.5 counts as unusual), not probabilities.",
            *(
                [
                    "Columns were chosen from automatically detected types because "
                    "data meanings are not confirmed yet; units are not shown."
                ]
                if request["meaning"] == "inferred"
                else []
            ),
        ],
    )
