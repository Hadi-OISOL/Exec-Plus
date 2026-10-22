"""Use case: Measures how ExecPlus handles questions and model outputs without a provider.

What it does: Scores labelled routing, model-output validation, summary grounding and
answer-binding cases, executes every routed calculation through DuckDB and compares it
with an independent standard-library Decimal oracle, then writes a JSON report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from execplus.application.services.answers import AnswerAssembler  # noqa: E402
from execplus.domain.compute import QueryBudget  # noqa: E402
from execplus.domain.errors import UnverifiedAnswerError  # noqa: E402
from execplus.domain.intent import RoutedIntent, route_response  # noqa: E402
from execplus.domain.models import (  # noqa: E402
    CalculationLineage,
    QueryResult,
    QuestionKind,
    WorkspaceScope,
)
from execplus.domain.offline_planner import offline_plan  # noqa: E402
from execplus.domain.profiling import TableData, profile  # noqa: E402
from execplus.domain.semantics import RECORD_COUNT, dataset_view, plan_query  # noqa: E402
from execplus.domain.summary_guard import is_grounded  # noqa: E402
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor  # noqa: E402

CASES = ROOT / "docs/offline-response-evaluation-cases.json"
VERSION = "offline-response-evaluation-v1"
HEADERS = ("region", "product", "channel", "units", "revenue", "cost")
ROWS = (
    ("North", "Tea", "Online", "40", "1200.10", "700.05"),
    ("North", "Tea", "Store", "15", "450.00", "260.40"),
    ("North", "Coffee", "Online", "22", "990.99", "610.00"),
    ("South", "Tea", "Store", "25", "730.25", "430.75"),
    ("South", "Coffee", "Online", "8", "360.30", "222.10"),
    ("South", "Juice", "Store", "31", "310.00", "190.90"),
    ("East", "Juice", "Online", "12", "125.55", "80.00"),
    ("East", "Coffee", "Store", "19", "870.40", "505.25"),
    ("East", "Tea", "Online", "7", "210.70", "120.35"),
    ("West", "Juice", "Store", "44", "455.45", "300.00"),
    ("West", "Coffee", "Online", "3", "135.00", "90.60"),
    ("West", "Tea", "Store", "18", "540.18", "315.15"),
)


def fixture() -> tuple[TableData, Any, WorkspaceScope, Any]:
    table = TableData(HEADERS, ROWS)
    view = dataset_view(profile(table))
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    return table, view, scope, dataset_id


def describe(routed: RoutedIntent | None) -> dict[str, Any]:
    if routed is None:
        return {"kind": "clarify"}
    if routed.kind == QuestionKind.PATTERNS:
        return {"kind": "patterns", "columns": list(routed.guide_columns)}
    if routed.kind == QuestionKind.NUMERICAL and routed.request is not None:
        request = routed.request
        plan: dict[str, Any] = {
            "kind": "numerical",
            "metric": request.metric,
            "aggregation": request.aggregation.value,
            "group_by": list(request.group_by),
        }
        if request.order:
            plan["order"] = request.order
        if request.limit is not None:
            plan["limit"] = request.limit
        return plan
    return {"kind": routed.kind.value}


def oracle(request: Any, rows: tuple[tuple[str, ...], ...]) -> list[list[Any]]:
    index = {name: position for position, name in enumerate(HEADERS)}
    groups: dict[tuple[str, ...], list[Decimal]] = defaultdict(list)
    for row in rows:
        key = tuple(row[index[name]] for name in request.group_by)
        value = (
            Decimal(1) if request.metric == RECORD_COUNT else Decimal(row[index[request.metric]])
        )
        groups[key].append(value)
    output: list[list[Any]] = []
    for key, values in groups.items():
        aggregation = request.aggregation.value
        if aggregation == "count":
            result = Decimal(len(values))
        elif aggregation == "sum":
            result = sum(values, Decimal(0))
        elif aggregation == "min":
            result = min(values)
        elif aggregation == "max":
            result = max(values)
        else:
            with localcontext() as context:
                context.prec = 50
                context.rounding = ROUND_HALF_EVEN
                result = (sum(values, Decimal(0)) / len(values)).quantize(Decimal("1e-12"))
        output.append([*key, result])
    if request.order:
        output.sort(key=lambda item: item[-1], reverse=request.order == "desc")
        if request.limit is not None:
            output = output[: request.limit]
    return output


async def execute(
    request: Any, table: TableData, view: Any, scope: WorkspaceScope, did: Any
) -> QueryResult:
    executor = DuckDBQueryExecutor(15, 256, budget=QueryBudget())
    plan = plan_query(scope, did, view, request, row_limit=1000)
    return await executor.execute(plan, scope, table, view)


def numeric_check(request: Any, result: QueryResult) -> dict[str, Any]:
    expected = oracle(request, ROWS)
    ordered = bool(request.order)
    actual_rows = [
        [Decimal(str(value)).normalize() if not isinstance(value, str) else value for value in row]
        for row in result.rows
    ]
    expected_rows = [
        [value.normalize() if isinstance(value, Decimal) else value for value in row]
        for row in expected
    ]
    if not ordered:
        actual_rows.sort(key=str)
        expected_rows.sort(key=str)
    return {
        "agrees": actual_rows == expected_rows,
        "expected": [[str(value) for value in row] for row in expected_rows],
        "actual": [[str(value) for value in row] for row in actual_rows],
    }


async def evaluate(cases_path: Path = CASES) -> dict[str, Any]:
    body = json.loads(cases_path.read_bytes())
    if body.get("version") != VERSION:
        raise ValueError("Unsupported evaluation case manifest.")
    table, view, scope, did = fixture()
    started = time.perf_counter()
    report: dict[str, Any] = {"version": VERSION, "fixture": body["fixture"], "cases": []}
    for case in body["routing"]:
        routed = offline_plan(case["question"], view)
        observed = describe(routed)
        entry: dict[str, Any] = {
            "id": case["id"],
            "category": "routing",
            "question": case["question"],
            "observed": observed,
            "passed": observed in case["expected"],
            "preferred": observed == case["expected"][0],
        }
        if routed is not None and routed.request is not None:
            result = await execute(routed.request, table, view, scope, did)
            entry["numeric"] = numeric_check(routed.request, result)
        report["cases"].append(entry)
    for case in body["model_outputs"]:
        routed = route_response(case["raw"], view)
        accepted = routed.kind != QuestionKind.UNSUPPORTED
        entry = {"id": case["id"], "category": "model_output", "accepted": accepted}
        if case["expected"] == "accept_literal":
            assert routed.request is not None
            result = await execute(routed.request, table, view, scope, did)
            entry["rows"] = [[None if v is None else str(v) for v in row] for row in result.rows]
            entry["passed"] = accepted and entry["rows"] == case["expected_rows"]
        else:
            entry["passed"] = accepted == (case["expected"] == "accept")
        entry["false_accept"] = accepted and case["expected"] == "reject"
        report["cases"].append(entry)
    for case in body["summaries"]:
        grounded = is_grounded(case["text"], tuple(Decimal(v) for v in case["evidence"]))
        report["cases"].append(
            {
                "id": case["id"],
                "category": "summary_grounding",
                "grounded": grounded,
                "passed": grounded == case["expected"],
                "false_accept": grounded and not case["expected"],
            }
        )
    for case in body["bindings"]:
        bound = binding(case["variant"], table, scope, did)
        report["cases"].append(
            {
                "id": case["id"],
                "category": "answer_binding",
                "observed": bound,
                "passed": bound == case["expected"],
                "false_accept": bound == "bound" and case["expected"] == "refused",
            }
        )
    report["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    report["summary"] = summarize(report["cases"])
    return report


def binding(variant: str, table: TableData, scope: WorkspaceScope, did: Any) -> str:
    query_id = uuid4()
    result = QueryResult(query_id, ("__value",), ((Decimal("6378.92"),),), len(table.rows))
    lineage = CalculationLineage(
        query_id,
        scope.workspace_id,
        did,
        "retail",
        len(table.rows),
        "revenue",
        "sum",
        (),
        (),
        "SQL",
    )
    column = "__value"
    if variant == "foreign_query":
        lineage = CalculationLineage(
            uuid4(),
            scope.workspace_id,
            did,
            "retail",
            len(table.rows),
            "revenue",
            "sum",
            (),
            (),
            "",
        )
    elif variant == "record_mismatch":
        result = QueryResult(query_id, ("__value",), ((Decimal("6378.92"),),), 11)
    elif variant == "missing_column":
        column = "profit"
    elif variant == "non_numeric":
        result = QueryResult(query_id, ("__value",), (("6378.92",),), len(table.rows))
    try:
        answer = AnswerAssembler().assemble_metric("Revenue", column, result, lineage)
    except UnverifiedAnswerError:
        return "refused"
    return "bound" if answer.value == result.rows[0][0] else "mismatch"


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for category in ("routing", "model_output", "summary_grounding", "answer_binding"):
        rows = [case for case in cases if case["category"] == category]
        passed = sum(case["passed"] for case in rows)
        summary[category] = {
            "cases": len(rows),
            "passed": passed,
            "accuracy": round(passed / len(rows), 4),
            "failed_ids": [case["id"] for case in rows if not case["passed"]],
            "false_accepts": sum(case.get("false_accept", False) for case in rows),
        }
    routing = [case for case in cases if case["category"] == "routing"]
    summary["routing"]["preferred"] = sum(case["preferred"] for case in routing)
    numeric = [case["numeric"] for case in routing if "numeric" in case]
    summary["numeric_agreement"] = {
        "executed": len(numeric),
        "agreeing": sum(item["agrees"] for item in numeric),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=CASES)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an earlier evaluation report.")
    report = asyncio.run(evaluate(args.cases))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
