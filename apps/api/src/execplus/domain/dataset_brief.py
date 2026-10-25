"""Use case: Gives the language model a compact, exact picture of a whole dataset.

What it does: Plans governed per-column statistic queries, assembles their exact results into the
versioned dataset-brief-v1 payload (shape, dates, column stats, quality flags, redacted samples)
and renders a bounded model-facing copy. All figures come from executed queries, never a model.
"""

import json
from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.data_brief import SENSITIVE_NAME, WITHHELD
from execplus.domain.guidance import DescriptionContext
from execplus.domain.label_matching import label_variants
from execplus.domain.models import QueryPlan, Scalar, WorkspaceScope
from execplus.domain.semantics import VALUE_ALIAS, quote_identifier, validate_read_only

VERSION = "dataset-brief-v1"
ROUTE = "deterministic:dataset-brief-v1"
GROUP_LIMIT = 1000
COLUMN_LIMIT = 40
TOP_VALUES = 5
SAMPLE_ROWS = 3
SAMPLE_TEXT = 40
MODEL_CHARS = 9000
NUMERIC = frozenset({"integer", "decimal"})
ORDERED = frozenset({"integer", "decimal", "date"})


def exact(value: Scalar) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        if value.is_zero():
            return "0"
        rendered = format(value, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _plan(scope: WorkspaceScope, dataset_id: UUID, question: str, sql: str) -> QueryPlan:
    validate_read_only(sql)
    return QueryPlan(uuid4(), scope.workspace_id, dataset_id, question, sql)


def values_plan(scope: WorkspaceScope, dataset_id: UUID, column: str) -> QueryPlan:
    name = quote_identifier(column)
    return _plan(
        scope,
        dataset_id,
        f"Brief: values of {column}",
        f'SELECT {name}, COUNT(*) AS "{VALUE_ALIAS}" FROM "dataset" '
        f"GROUP BY {name} ORDER BY {name} LIMIT {GROUP_LIMIT + 1}",
    )


def aggregate_plan(
    scope: WorkspaceScope, dataset_id: UUID, column: str, function: str
) -> QueryPlan:
    if function not in {"COUNT", "MIN", "MAX", "SUM"}:
        raise ValueError("Unsupported brief aggregate")
    return _plan(
        scope,
        dataset_id,
        f"Brief: {function.lower()} of {column}",
        f'SELECT {function}({quote_identifier(column)}) AS "{VALUE_ALIAS}" FROM "dataset" LIMIT 1',
    )


def top_plan(scope: WorkspaceScope, dataset_id: UUID, column: str) -> QueryPlan:
    name = quote_identifier(column)
    return _plan(
        scope,
        dataset_id,
        f"Brief: most frequent {column}",
        f'SELECT {name}, COUNT(*) AS "{VALUE_ALIAS}" FROM "dataset" GROUP BY {name} '
        f'ORDER BY "{VALUE_ALIAS}" DESC, {name} LIMIT {TOP_VALUES + 1}',
    )


def row_count_plan(scope: WorkspaceScope, dataset_id: UUID) -> QueryPlan:
    return _plan(
        scope,
        dataset_id,
        "Brief: record count",
        f'SELECT COUNT(*) AS "{VALUE_ALIAS}" FROM "dataset" LIMIT 1',
    )


def _top(groups: list[tuple[Scalar, int]]) -> list[list[str]]:
    present = [(value, count) for value, count in groups if value is not None]
    present.sort(key=lambda item: (-item[1], exact(item[0]) or ""))
    return [[exact(value) or "", str(count)] for value, count in present[:TOP_VALUES]]


def stats_from_groups(
    kind: str, rows_total: int, groups: list[tuple[Scalar, int]]
) -> dict[str, Any]:
    missing = sum(count for value, count in groups if value is None)
    present = [(value, count) for value, count in groups if value is not None]
    result: dict[str, Any] = dict(
        present=str(rows_total - missing),
        missing=str(missing),
        distinct=str(len(present)),
        top=_top(groups),
    )
    if kind in ORDERED and present:
        ordered = sorted(value for value, _ in present)
        result.update(min=exact(ordered[0]), max=exact(ordered[-1]))
    if kind in NUMERIC and present:
        with localcontext() as context:
            context.prec = 80
            total = sum((Decimal(str(value)) * count for value, count in present), Decimal(0))
        result["sum"] = exact(total)
    variants = label_variants(value for value, _ in present)
    if kind == "text" and variants:
        result["label_variants"] = [list(group[:3]) for group in variants[:3]]
    return result


def stats_from_aggregates(
    kind: str,
    rows_total: int,
    present: int,
    minimum: Scalar,
    maximum: Scalar,
    total: Scalar,
    top: list[tuple[Scalar, int]],
) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        present=str(present),
        missing=str(rows_total - present),
        distinct=f"more than {GROUP_LIMIT}",
        top=_top(top[:TOP_VALUES]),
    )
    if kind in ORDERED and present:
        result.update(min=exact(minimum), max=exact(maximum))
    if kind in NUMERIC and present:
        result["sum"] = exact(total)
    return result


def _flags(column: dict[str, Any], stats: dict[str, Any], rows: int) -> list[str]:
    flags = []
    if column.get("missing_placeholders"):
        flags.append("na_placeholders")
    if column.get("type_conflicts"):
        flags.append("type_conflicts")
    if column.get("invalid_dates"):
        flags.append("invalid_dates")
    if "identifier" in column.get("semantic_tags", []):
        flags.append("identifier")
    if stats.get("label_variants"):
        flags.append("label_variants")
    missing = int(stats.get("missing", "0"))
    if rows and missing * 2 > rows:
        flags.append("mostly_missing")
    if stats.get("distinct") == "1":
        flags.append("constant")
    if stats.get("distinct", "").startswith("more than") and column["type"] == "text":
        flags.append("high_cardinality")
    if stats.get("min", "").startswith("-") and column["type"] in NUMERIC:
        flags.append("has_negatives")
    return flags


def _meaning(context: DescriptionContext, name: str) -> dict[str, Any]:
    if context.state != "confirmed":
        return {}
    return next(
        (item for item in (context.definition or {}).get("columns", []) if item["name"] == name),
        {},
    )


def column_entry(
    context: DescriptionContext, column: dict[str, Any], stats: dict[str, Any] | None
) -> dict[str, Any]:
    meaning = _meaning(context, column["name"])
    rules = {
        item["column"]: item["aggregation"]
        for item in (context.definition or {}).get("metrics", [])
        if context.state == "confirmed"
    }
    entry: dict[str, Any] = dict(
        name=column["name"],
        type="datetime" if column.get("datetime") else column["type"],
        role=meaning.get("role") or ("metric" if column["role"] == "metric" else "dimension"),
        role_source="confirmed" if meaning else "inferred",
    )
    unit = meaning.get("currency") or meaning.get("unit") or ""
    if unit:
        entry["unit"] = unit
    if meaning.get("unit_column"):
        entry["unit_column"] = meaning["unit_column"]
    if column["name"] in rules:
        entry["aggregation"] = rules[column["name"]]
    if meaning.get("meaning"):
        entry["meaning"] = str(meaning["meaning"])[:100]
    if stats is None:
        entry["flags"] = ["not_profiled"]
        return entry
    entry.update({key: value for key, value in stats.items() if key != "label_variants"})
    if stats.get("label_variants"):
        entry["label_variants"] = stats["label_variants"]
    entry["flags"] = _flags(column, stats, context.profile["row_count"])
    return entry


def date_coverage(
    column: str, minimum: str | None, maximum: str | None, months: list[Scalar]
) -> dict[str, Any] | None:
    if not minimum or not maximum:
        return None
    observed = sorted({exact(value)[:7] for value in months if value is not None})  # type: ignore[index]
    start, end = date.fromisoformat(minimum[:10]), date.fromisoformat(maximum[:10])
    expected: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month) and len(expected) <= 1200:
        expected.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    gaps = [item for item in expected if item not in set(observed)]
    return dict(
        column=column,
        min=minimum,
        max=maximum,
        span_days=str((end - start).days),
        months_with_data=str(len(observed)),
        missing_months=gaps[:12],
        missing_month_count=str(len(gaps)),
    )


def _private(context: DescriptionContext, name: str) -> bool:
    column = context.view.column(name)
    return (
        bool(SENSITIVE_NAME.search(name))
        or (column is not None and "identifier" in column.tags)
        or _meaning(context, name).get("role") == "identifier"
    )


def samples(
    context: DescriptionContext, headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
) -> dict[str, Any]:
    withheld = [name for name in headers if _private(context, name)]
    return dict(
        rows=[
            {
                name: WITHHELD if name in withheld else cell.strip()[:SAMPLE_TEXT]
                for name, cell in zip(headers, row, strict=False)
            }
            for row in rows[:SAMPLE_ROWS]
        ],
        withheld=withheld,
    )


def quality(columns: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for check in profile.get("quality_checks", []):
        if check.get("count"):
            found.append(dict(code=check["code"], count=str(check["count"])))
    for column in columns:
        for flag in column.get("flags", []):
            if flag in {"na_placeholders", "label_variants", "type_conflicts", "invalid_dates"}:
                item: dict[str, Any] = dict(code=flag, column=column["name"])
                if flag == "label_variants":
                    item["examples"] = column.get("label_variants", [])[:2]
                found.append(item)
    return found[:30]


def assemble(
    context: DescriptionContext,
    rows: str,
    columns: list[dict[str, Any]],
    skipped: list[str],
    coverage: dict[str, Any] | None,
    findings: list[str],
    sample: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    definition = context.definition or {}
    return dict(
        version=VERSION,
        dataset=dict(
            name=context.name,
            rows=rows,
            columns=context.profile["column_count"],
            grain=definition.get("grain", "unknown") if context.state == "confirmed" else "unknown",
            domain=definition.get("domain", "auto"),
            definition_state=context.state,
        ),
        date_coverage=coverage,
        columns=columns,
        columns_listed_only=skipped,
        quality=quality(columns, context.profile),
        analyst_findings=findings,
        samples=sample,
        sources=list(context.view.sources),
        limitations=limitations,
    )


def model_view(
    brief: dict[str, Any], include_values: bool, limit: int = MODEL_CHARS, totals: bool = True
) -> str:
    """The brief as the model may read it: without samples/values unless the operator allows."""
    hidden = ({"top", "label_variants"} if not include_values else set()) | (
        set() if totals else {"sum"}
    )
    payload = {key: value for key, value in brief.items() if key not in {"sources", "samples"}}
    payload["columns"] = [
        {key: value for key, value in column.items() if key not in hidden}
        for column in brief["columns"]
    ]
    if include_values:
        payload["sample_rows"] = brief["samples"]["rows"]
    else:
        payload["quality"] = [
            {key: value for key, value in item.items() if key != "examples"}
            for item in brief["quality"]
        ]
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(text) > limit and payload["columns"]:
        dropped = payload["columns"].pop()
        payload["columns_listed_only"] = [dropped["name"], *payload["columns_listed_only"]]
        payload.pop("sample_rows", None)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text[:limit]


def planner_view(brief: dict[str, Any]) -> str:
    return model_view(brief, include_values=False, totals=False)
