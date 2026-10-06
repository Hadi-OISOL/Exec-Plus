"""Use case: Measures operational reporting against its legacy materialized reference.

What it does: Seeds a disposable local PostgreSQL schema with fictional metadata,
checks exact projection parity and retains timing, memory and query-plan evidence.
"""

from __future__ import annotations

import argparse
import contextvars
import dataclasses
import hashlib
import json
import math
import os
import platform
import statistics
import time
import tracemalloc
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.engine import make_url

from execplus.domain.product_usage import (
    ACTIVATION_ACTIONS,
    ACTIVITY_FEATURES,
    UsageFacts,
    report_start,
    week_start,
)
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.reporting import SQLReportingRepository
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
START = report_start(NOW, 12)
TRACE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("trace", default=None)


def capture_query(
    connection: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    many: bool,
) -> None:
    trace = TRACE.get()
    if trace is not None:
        trace["queries"] += 1
        trace["rows"] += max(cursor.rowcount, 0)
        trace["statements"].append((statement, parameters))


def old_overview(repo: SQLWorkspaceRepository, wid: UUID, manager: bool) -> dict[str, object]:
    workspace = repo.workspace(wid)
    members, datasets = repo.members(wid), repo.datasets(wid)
    usage, events = repo.usage_events(wid), repo.audit_events(wid)
    feedback = repo.feedback(wid) if manager else ()
    kinds = Counter(entry.action for entry in events)
    quantities: Counter[str] = Counter()
    for usage_entry in usage:
        quantities[usage_entry.kind] += usage_entry.quantity
    completed = {
        "workspace": True,
        "invite_teammate": len(members) > 1,
        "upload": quantities["upload"] > 0 or kinds["upload.stored"] > 0,
        "explore_dashboard_or_question": kinds["query.executed"] > 0,
        "save_analysis": kinds["saved_item.created"] > 0,
    }
    weeks: dict[str, set[UUID]] = {}
    for entry in events:
        iso = entry.created_at.isocalendar()
        weeks.setdefault(f"{iso.year}-W{iso.week:02}", set()).add(entry.actor_id)
    seen: set[UUID] = set()
    returning: set[UUID] = set()
    for week in sorted(weeks):
        returning.update(seen & weeks[week])
        seen.update(weeks[week])
    return {
        "checklist": [dict(id=key, complete=value) for key, value in completed.items()],
        "next_steps": [key for key, done in completed.items() if not done],
        "datasets": len(datasets),
        "seats": {"used": len(members), "limit": workspace.seat_limit},
        "feature_adoption": dict(sorted(kinds.items())) if manager else {},
        "weekly_active_users": {key: len(value) for key, value in sorted(weeks.items())}
        if manager
        else {},
        "returning_users": len(returning) if manager else None,
        "retention_definition": "An actor with activity in at least two ISO calendar weeks.",
        "usage": dict(sorted(quantities.items())) if manager else {},
        "support_signals": {
            "negative_feedback": sum(item.rating <= 2 for item in feedback),
            "failed_queries": kinds["query.failed"],
        }
        if manager
        else {},
    }


def old_totals(repo: SQLWorkspaceRepository, wid: UUID) -> dict[str, int]:
    workspace = repo.workspace(wid)
    uploads = [upload for dataset in repo.datasets(wid) for upload in repo.uploads(wid, dataset.id)]
    active = len(repo.members(wid))
    occupied = len(repo.members(wid)) + sum(
        item.status == "pending" and item.expires_at > NOW for item in repo.invitations(wid)
    )
    return {
        "active_seats": active,
        "reserved_seats": occupied - len(repo.members(wid)),
        "seat_limit": workspace.seat_limit,
        "uploads": len(uploads),
        "storage_bytes": sum(item.size for item in uploads),
    }


def reference_product(repo: SQLWorkspaceRepository, wid: UUID) -> UsageFacts:
    events, usage = repo.audit_events(wid), repo.usage_events(wid)
    members = {member.user_id for member in repo.members(wid)}
    first: dict[UUID, datetime] = {}
    last: dict[UUID, datetime] = {}
    weekly: dict[Any, list[Any]] = {}
    features: dict[str, list[Any]] = {}
    activity: dict[UUID, set[Any]] = defaultdict(set)
    for item in events:
        if item.created_at >= NOW or item.action not in ACTIVITY_FEATURES:
            continue
        first[item.actor_id] = min(first.get(item.actor_id, item.created_at), item.created_at)
        last[item.actor_id] = max(last.get(item.actor_id, item.created_at), item.created_at)
        if item.created_at < START:
            continue
        week = week_start(item.created_at.astimezone(timezone.utc).date())
        period = weekly.setdefault(week, [set(), 0])
        period[0].add(item.actor_id)
        period[1] += 1
        group = features.setdefault(ACTIVITY_FEATURES[item.action], [set(), 0])
        group[0].add(item.actor_id)
        group[1] += 1
        activity[item.actor_id].add(week)
    cohorts: Counter[Any] = Counter()
    retained: Counter[Any] = Counter()
    for actor, timestamp in first.items():
        if timestamp < START:
            continue
        cohort = week_start(timestamp.astimezone(timezone.utc).date())
        cohorts[cohort] += 1
        for active in activity[actor]:
            retained[(cohort, active)] += 1
    activated = {
        item.actor_id
        for item in events
        if item.created_at < NOW and item.action in ACTIVATION_ACTIONS and item.actor_id in members
    }
    summary = {
        "active_users": len(activity),
        "active_members": sum(actor in activity for actor in members),
        "current_members": len(members),
        "activated_members": len(activated),
        "never_active_members": sum(actor not in first for actor in members),
        "inactive_14d_members": sum(
            actor in last and last[actor] < NOW - timedelta(days=14) for actor in members
        ),
    }
    quantities: Counter[str] = Counter()
    for usage_entry in usage:
        if START <= usage_entry.created_at < NOW:
            quantities[usage_entry.kind] += usage_entry.quantity
    counts = Counter(item.action for item in events if START <= item.created_at < NOW)
    return UsageFacts(
        summary,
        tuple((period, len(values[0]), values[1]) for period, values in sorted(weekly.items())),
        tuple((name, len(values[0]), values[1]) for name, values in sorted(features.items())),
        tuple(sorted(cohorts.items())),
        tuple((cohort, active, count) for (cohort, active), count in sorted(retained.items())),
        {
            "uploads": quantities["upload"],
            "storage_bytes": quantities["storage_bytes"],
            "queries_completed": counts["query.executed"],
            "queries_failed": counts["query.failed"],
            "forecasts_created": counts["forecast.created"],
        },
    )


def normalized(value: Any) -> Any:
    if isinstance(value, UsageFacts):
        return {**dataclasses.asdict(value), "retained": sorted(value.retained)}
    return value


def seed(engine: Engine, events: int) -> UUID:
    wid, other = uuid4(), uuid4()
    actors = [uuid4() for _ in range(50)]
    history_start = START - timedelta(weeks=2)
    actions = (*ACTIVITY_FEATURES, "query.executed", "query.failed", "conversation.complete")
    with engine.begin() as connection:
        connection.execute(
            s.users.insert(),
            [
                dict(
                    id=actor,
                    email=f"benchmark-{index}@example.invalid",
                    display_name="Fictional user",
                    created_at=history_start,
                )
                for index, actor in enumerate(actors)
            ],
        )
        for workspace in (wid, other):
            connection.execute(
                s.workspaces.insert(),
                dict(
                    id=workspace,
                    name="Fictional reporting benchmark",
                    seat_limit=50,
                    created_at=history_start,
                    updated_at=history_start,
                ),
            )
            connection.execute(
                s.memberships.insert(),
                [
                    dict(
                        workspace_id=workspace,
                        user_id=actor,
                        role="owner" if index == 0 else "member",
                        created_at=history_start,
                    )
                    for index, actor in enumerate(actors[:48])
                ],
            )
            connection.execute(
                s.invitations.insert(),
                [
                    dict(
                        id=uuid4(),
                        workspace_id=workspace,
                        email=f"pending-{i}@example.invalid",
                        role="member",
                        status="pending",
                        expires_at=NOW + timedelta(days=300),
                        invited_by=actors[0],
                        created_at=history_start,
                    )
                    for i in range(2)
                ],
            )
            for index in range(20):
                dataset_id = uuid4()
                connection.execute(
                    s.datasets.insert(),
                    dict(
                        id=dataset_id,
                        workspace_id=workspace,
                        name=f"Fictional data {index}",
                        created_by=actors[0],
                        created_at=history_start,
                        updated_at=history_start,
                    ),
                )
                connection.execute(
                    s.uploads.insert(),
                    [
                        dict(
                            id=uuid4(),
                            workspace_id=workspace,
                            dataset_id=dataset_id,
                            filename="fictional.csv",
                            content_type="text/csv",
                            size=1024 + upload_index,
                            storage_key=f"benchmark-only/{workspace}/{dataset_id}/{upload_index}",
                            checksum="0" * 64,
                            status="stored",
                            format="csv",
                            row_count=10,
                            column_count=3,
                            created_by=actors[0],
                            created_at=history_start,
                        )
                        for upload_index in range(10)
                    ],
                )
            count = events if workspace == wid else events // 4
            for offset in range(0, count, 1000):
                audit, usage = [], []
                for index in range(offset, min(offset + 1000, count)):
                    actor_index = index % len(actors)
                    begin = actor_index % 8
                    width = 10 - begin if actor_index % 10 == 0 else 14 - begin
                    week = begin + (index // len(actors)) % width
                    created = history_start + timedelta(weeks=week, hours=(index % 12))
                    if index % 997 == 0:
                        created = NOW + timedelta(days=1)
                    action = actions[(index // 50) % len(actions)]
                    if actor_index == 47:
                        action = "query.executed"
                    resource = uuid4()
                    audit.append(
                        dict(
                            id=uuid4(),
                            workspace_id=workspace,
                            actor_id=actors[actor_index],
                            action=action,
                            resource_type="benchmark",
                            resource_id=resource,
                            created_at=created,
                        )
                    )
                    kind = ("upload", "storage_bytes", "profile", "sample", "seat_added")[index % 5]
                    usage.append(
                        dict(
                            id=uuid4(),
                            workspace_id=workspace,
                            actor_id=actors[actor_index],
                            kind=kind,
                            quantity=1024 + index % 100 if kind == "storage_bytes" else 1,
                            resource_id=resource,
                            created_at=created,
                        )
                    )
                connection.execute(s.audit_events.insert(), audit)
                connection.execute(s.usage_events.insert(), usage)
            connection.execute(
                s.feedback.insert(),
                [
                    dict(
                        id=uuid4(),
                        workspace_id=workspace,
                        actor_id=actors[index % 50],
                        feature="dashboard",
                        rating=1 + index % 5,
                        category="helpful",
                        release="fictional-benchmark",
                        created_at=history_start + timedelta(days=index % 80),
                    )
                    for index in range(200)
                ],
            )
        for name in (
            "users",
            "workspaces",
            "memberships",
            "invitations",
            "datasets",
            "uploads",
            "audit_events",
            "usage_events",
            "feedback",
        ):
            connection.execute(text(f'ANALYZE "{name}"'))
    return wid


def stats(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def measure(call: Callable[[], Any], repetitions: int) -> tuple[dict[str, Any], dict[str, Any]]:
    call()
    elapsed, query_counts, rows = [], [], []
    trace: dict[str, Any] = {}
    for _ in range(repetitions):
        trace = {"queries": 0, "rows": 0, "statements": []}
        token = TRACE.set(trace)
        try:
            start = time.perf_counter()
            call()
            elapsed.append((time.perf_counter() - start) * 1000)
        finally:
            TRACE.reset(token)
        query_counts.append(trace["queries"])
        rows.append(trace["rows"])
    tracemalloc.start()
    try:
        call()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {
        **stats(elapsed),
        "samples_ms": [round(value, 3) for value in elapsed],
        "query_counts": query_counts,
        "returned_rows": rows,
        "python_peak_bytes_separate_run": peak,
    }, trace


def query_plans(engine: Engine, trace: dict[str, Any]) -> list[dict[str, Any]]:
    def outline(node: dict[str, Any]) -> dict[str, Any]:
        selected = {
            key: node[key]
            for key in (
                "Node Type",
                "Relation Name",
                "Index Name",
                "Actual Rows",
                "Actual Loops",
                "Actual Total Time",
                "Shared Hit Blocks",
                "Shared Read Blocks",
            )
            if key in node
        }
        if "Plans" in node:
            selected["Plans"] = [outline(child) for child in node["Plans"]]
        return selected

    result = []
    with engine.connect() as connection:
        for statement, parameters in trace["statements"]:
            plan = connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement,
                parameters,
            ).scalar_one()[0]
            result.append({"execution_ms": plan["Execution Time"], "plan": outline(plan["Plan"])})
    return result


def run(engine: Engine, wid: UUID, repetitions: int) -> dict[str, Any]:
    def call(kind: str, manager: bool = True) -> Any:
        with engine.connect() as connection:
            legacy = SQLWorkspaceRepository(connection)
            report = SQLReportingRepository()
            report.connection = connection
            if kind == "legacy_overview":
                return old_overview(legacy, wid, manager)
            if kind == "new_overview":
                return report.activation_overview(wid, manager=manager)
            if kind == "legacy_totals":
                return old_totals(legacy, wid)
            if kind == "new_totals":
                return report.usage_totals(wid, NOW)
            if kind == "reference_product":
                return reference_product(legacy, wid)
            return report.product_usage_facts(wid, START, NOW)

    assert call("legacy_overview") == call("new_overview"), "Manager overview parity failed"
    assert call("legacy_overview", False) == call("new_overview", False), "Member parity failed"
    assert call("legacy_totals") == call("new_totals"), "Usage-total parity failed"
    expected = normalized(call("reference_product"))
    assert expected == normalized(call("new_product")), "Product cohort reference parity failed"
    measurements: dict[str, Any] = {}
    plans: dict[str, Any] = {}
    for kind in ("legacy_overview", "new_overview", "legacy_totals", "new_totals", "new_product"):
        measurements[kind], trace = measure(partial(call, kind), repetitions)
        if kind.startswith("new_"):
            plans[kind] = query_plans(engine, trace)
        print(json.dumps({"stage": "measured", "projection": kind}), flush=True)

    def concurrent(_: int) -> dict[str, Any]:
        trace: dict[str, Any] = {"queries": 0, "rows": 0, "statements": []}
        token = TRACE.set(trace)
        try:
            start = time.perf_counter()
            actual = call("new_product")
            elapsed = (time.perf_counter() - start) * 1000
            assert normalized(actual) == expected, "Concurrent projection parity failed"
            return {"elapsed_ms": elapsed, "queries": trace["queries"], "rows": trace["rows"]}
        finally:
            TRACE.reset(token)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        concurrent_results = list(pool.map(concurrent, range(8)))
    bounded = max(item["rows"] for item in concurrent_results)
    assert bounded <= 300, "SQL projection returned an unbounded event history"
    return {
        "parity": {
            "manager_overview": True,
            "member_overview": True,
            "usage_totals": True,
            "independent_product_reference": True,
            "concurrent_product_reference": True,
        },
        "measurements": measurements,
        "query_plans": plans,
        "concurrent_eight": {
            **stats([item["elapsed_ms"] for item in concurrent_results]),
            "wall_ms": round((time.perf_counter() - start) * 1000, 3),
            "max_rows_returned": bounded,
            "calls": concurrent_results,
        },
        "result_checksum": hashlib.sha256(
            json.dumps(expected, default=str, sort_keys=True).encode()
        ).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=20_000)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1_000 <= args.events <= 200_000 or not 3 <= args.repetitions <= 20:
        parser.error("Use 1,000-200,000 events and 3-20 repetitions.")
    url = os.getenv("EXECPLUS_TEST_DATABASE_URL", "")
    parsed = make_url(url) if url else None
    if parsed is None or parsed.host not in {"localhost", "127.0.0.1"} or parsed.port != 15433:
        parser.error("Use the isolated local PostgreSQL test endpoint on port 15433.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = args.output.open("x")
    os.chmod(args.output, 0o600)
    schema = "benchmark_operations_" + uuid4().hex
    admin = create_engine(url)
    engine = create_engine(
        url,
        pool_size=8,
        max_overflow=0,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=30000"},
    )
    record: dict[str, Any] = {
        "file_use_case": "Records reproducible fictional operational reporting measurements.",
        "responsibility": "Preserves exact parity, timing, memory and safe SQL-plan evidence.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "fixture": {
            "audit_events": args.events,
            "usage_events": args.events,
            "other_tenant_events_each": args.events // 4,
            "datasets_per_tenant": 20,
            "uploads_per_tenant": 200,
            "historical_actors": 50,
            "current_members": 48,
            "window_weeks": 12,
            "history_weeks": 14,
        },
        "environment": {"python": platform.python_version(), "platform": platform.system()},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_baseline": "9c2445d legacy projection logic, without authorization wrappers",
        "schema_name": schema,
        "limitations": [
            "Local disposable database; not VPS or representative production load.",
            "Seven warm samples by default, fixed method order; host is not reserved or idle.",
            "Eight concurrent repository calls exclude HTTP/UI/authentication overhead.",
            "tracemalloc measures Python allocations only, not PostgreSQL or native RSS.",
            "Legacy usage totals exclude the compatible unbounded usage-event response.",
        ],
    }
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
        )
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            record["environment"]["postgresql"] = connection.execute(
                text("SHOW server_version")
            ).scalar_one()
        print(json.dumps({"stage": "seed", "events_each": args.events}), flush=True)
        wid = seed(engine, args.events)
        event.listen(engine, "after_cursor_execute", capture_query)
        record.update(run(engine, wid, args.repetitions))
        record["passed"] = True
    except Exception as error:
        record["failure_type"] = type(error).__name__
        print(json.dumps({"stage": "failed", "type": type(error).__name__}), flush=True)
        if isinstance(error, AssertionError):
            record["failure_code"] = str(error)
        raise SystemExit(1) from None
    finally:
        try:
            engine.dispose()
            if created:
                with admin.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            record["disposable_schema_removed"] = True
        except Exception as error:
            record["cleanup_failure_type"] = type(error).__name__
            record["passed"] = False
            raise SystemExit(1) from None
        finally:
            admin.dispose()
            output.write(json.dumps(record, indent=2, default=str) + "\n")
            output.close()
    print(json.dumps({"passed": True, "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()
