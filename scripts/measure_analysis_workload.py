"""Use case: Measures a declared local eight-user analysis workload on fictional data.

What it does: Runs real database/storage requests in disposable namespaces and records
application latency, CPU/RSS and exact-result checks; it is not production load acceptance.
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--new-methods", action="store_true")
    parser.add_argument("--next-batch", action="store_true")
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 10 <= args.duration_seconds <= 300:
        parser.error("Duration must be between ten and three hundred seconds")
    source = args.source.resolve()
    output = args.output.resolve()
    project = Path(__file__).resolve().parents[1]
    if output.exists() or not output.is_relative_to(project):
        parser.error("Choose a new output file inside the runner project")
    ignored = subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=project, check=False)
    if ignored.returncode != 0:
        parser.error("Workload reports must use an ignored project-local path")
    if not args.worker:
        env = dict(os.environ, PYTHONPATH=str(source / "apps/api/src"))
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--source",
                str(source),
                "--output",
                str(args.output.resolve()),
                *(["--new-methods"] if args.new_methods else []),
                *(
                    ["--next-batch", "--duration-seconds", str(args.duration_seconds)]
                    if args.next_batch
                    else []
                ),
            ],
            env=env,
            check=True,
            cwd=source,
        )
        return

    import boto3
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    import execplus
    from execplus.bootstrap import build_runtime
    from execplus.config import Settings
    from execplus.infrastructure.identity import LocalSessionIdentity
    from execplus.main import create_app

    assert Path(execplus.__file__).resolve().is_relative_to(source)
    base_url = make_url(os.environ["EXECPLUS_TEST_DATABASE_URL"])
    endpoint = os.environ.get("EXECPLUS_TEST_OBJECT_STORE_ENDPOINT", "http://localhost:9000")
    assert base_url.host in {"localhost", "127.0.0.1"}, "Use isolated local test infrastructure"
    assert urlparse(endpoint).hostname in {"localhost", "127.0.0.1"}
    namespace = "evaluation_" + uuid4().hex
    bucket = namespace.replace("_", "-")
    url = base_url.update_query_dict({"options": f"-csearch_path={namespace}"}).render_as_string(
        hide_password=False
    )
    admin = create_engine(base_url)
    storage = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("EXECPLUS_TEST_OBJECT_STORE_ACCESS_KEY", "execplus"),
        aws_secret_access_key=os.getenv("EXECPLUS_TEST_OBJECT_STORE_SECRET_KEY", "change-me"),
    )
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{namespace}"'))
    private_fixture = TemporaryDirectory(prefix="execplus-workload-source-")
    runtime = None
    bucket_created = False
    report = None
    observations = b"city,amount,cost\n" + b"".join(
        f"{'North' if i < 20 else 'South'},{i + 1},{2 * i + 3}\n".encode() for i in range(40)
    )
    actions = b"city,amount,cost,hours\nA,8,3,1\nB,6,2,2\nC,10,5,2\n"
    try:
        storage.create_bucket(Bucket=bucket)
        bucket_created = True
        engine = create_engine(url)
        config = Config(str(source / "alembic.ini"))
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        engine.dispose()
        settings_overrides: dict[str, Any] = {"_env_file": None}
        settings = Settings(
            **settings_overrides,
            environment="test",
            database_url=url,
            object_store_endpoint=endpoint,
            object_store_bucket=bucket,
            object_store_access_key=os.getenv("EXECPLUS_TEST_OBJECT_STORE_ACCESS_KEY", "execplus"),
            object_store_secret_key=os.getenv("EXECPLUS_TEST_OBJECT_STORE_SECRET_KEY", "change-me"),
            llm_mode="disabled",
            llm_selection_model="",
            llm_selection_base_url="",
            source_secret_directory=private_fixture.name,
            source_allow_test_loopback=args.next_batch,
        )
        runtime = build_runtime(settings)
        identity = runtime.identity
        assert isinstance(identity, LocalSessionIdentity)
        if args.next_batch:
            report = next_batch_workload(source, runtime, settings, args.duration_seconds)
        else:
            with TestClient(create_app(settings, runtime)) as client:

                def call(headers: dict[str, str], method: str, path: str, **kwargs: Any) -> Any:
                    response = client.request(method, path, headers=headers, **kwargs)
                    assert response.status_code < 400, (
                        method,
                        path,
                        response.status_code,
                        response.text,
                    )
                    return response.json()

                def prepare(
                    index: int,
                ) -> tuple[dict[str, str], str, list[str], str, dict[str, Any]]:
                    token = identity.provision(f"workload-{index}-{namespace}@example.test")
                    headers = {"Authorization": "Bearer " + token}
                    wid = call(
                        headers,
                        "POST",
                        "/workspaces",
                        json={"name": "Fictional workload", "seat_limit": 3},
                    )["id"]
                    roots = []
                    for name, content in [("Observations", observations), ("Actions", actions)]:
                        did = call(
                            headers, "POST", f"/workspaces/{wid}/datasets", json={"name": name}
                        )["id"]
                        root = f"/workspaces/{wid}/datasets/{did}/uploads"
                        uid = call(
                            {**headers, "Content-Type": "text/csv"},
                            "POST",
                            root + "?filename=fictional.csv",
                            content=content,
                        )["id"]
                        root += "/" + uid
                        meaning = call(headers, "GET", root + "/understanding")
                        definition = meaning["definition"]
                        definition.update(
                            grain="record",
                            domain="operations",
                            description="Declared fictional evaluation records",
                        )
                        for column in definition["columns"]:
                            column.update(
                                role="dimension" if column["name"] == "city" else "metric",
                                unit="" if column["name"] == "city" else "units",
                                currency="",
                            )
                        call(
                            headers,
                            "POST",
                            root + "/understanding",
                            json={
                                "revision_id": meaning["revision_id"],
                                "expected_version": meaning["version"],
                                "state": "confirmed",
                                "definition": definition,
                            },
                        )
                        roots.append(root)
                    tid = call(headers, "POST", roots[0] + "/threads", json={})["id"]
                    options = call(headers, "GET", roots[1] + "/decision-analysis/options")
                    allocation = dict(
                        name="Fictional exact allocation",
                        revision_id=options["revision_id"],
                        understanding_id=options["understanding_id"],
                        entity_column="city",
                        cost_column="cost",
                        benefit_column="amount",
                        budget="8",
                        quantum="1",
                        maximum_quantity=2,
                        assumptions_confirmed=True,
                    )
                    return headers, wid, roots, f"/workspaces/{wid}/threads/{tid}", allocation

                actors = [prepare(index) for index in range(8)]

                def journey(
                    actor: tuple[dict[str, str], str, list[str], str, dict[str, Any]],
                    new: bool = False,
                ) -> list[tuple[str, float]]:
                    headers, wid, roots, thread, allocation = actor
                    timings: list[tuple[str, float]] = []

                    def measured(label: str, method: str, path: str, **kwargs: Any) -> Any:
                        start = time.perf_counter()
                        value = call(headers, method, path, **kwargs)
                        timings.append((label, (time.perf_counter() - start) * 1000))
                        return value

                    if not new:
                        value = measured(
                            "query",
                            "POST",
                            roots[0] + "/query",
                            json={"metric": "amount", "aggregation": "sum"},
                        )
                        assert str(value["rows"][0][0]) == "820"
                        qid = value["lineage"]["query_id"]
                        replay = measured(
                            "query_replay", "POST", f"/workspaces/{wid}/queries/{qid}/replay"
                        )
                        assert replay["rows"] == value["rows"]
                    question = (
                        'Compare the relationship between "amount" and "cost" '
                        'within groups of "city".'
                        if new
                        else "Find patterns between amount and cost"
                    )
                    answer = measured(
                        "group_comparison" if new else "patterns",
                        "POST",
                        thread + "/ask",
                        json={"question": question},
                    )
                    assert answer["answer"]["kind"] == "patterns", answer
                    pattern = answer["answer"]["patterns"]
                    expected_scores = {"pearson": "1.000000", "spearman": "1.000000"}
                    if new:
                        assert pattern["version"] == "group-relationship-comparison-v1"
                        assert pattern["coverage"]["covered_rows"] == 40
                        assert pattern["pooled"]["statistics"] == expected_scores
                        assert len(pattern["groups"]) == 2
                        assert all(
                            group["statistics"] == expected_scores for group in pattern["groups"]
                        )
                    else:
                        assert pattern["version"] == "pattern-exploration-v1"
                        numerical = [
                            item
                            for item in pattern["findings"]
                            if item["type"] == "numeric_relationship"
                        ]
                        assert len(numerical) == 1 and numerical[0]["statistics"] == expected_scores
                    reopened = measured(
                        "group_reopen" if new else "pattern_reopen",
                        "GET",
                        thread + f"/turns/{answer['turn']['id']}/answer",
                    )
                    assert reopened == answer["answer"]
                    body = {
                        **allocation,
                        **(
                            {
                                "prerequisites": [{"candidate": "A", "requires": "C"}],
                                "exclusions": [{"first": "B", "second": "C"}],
                            }
                            if new
                            else {}
                        ),
                    }
                    decision = measured(
                        "selection_rules" if new else "allocation",
                        "POST",
                        roots[1] + "/decision-analysis/allocations",
                        json=body,
                    )
                    result = decision["run"]["result"]
                    assert result["benefit"] == ("18" if new else "22") and result["cost"] == "8"
                    assert {
                        item["candidate"]: item["quantity"] for item in result["allocations"]
                    } == ({"A": 1, "B": 0, "C": 1} if new else {"A": 2, "B": 1, "C": 0})
                    if new:
                        assert result["method_version"] == "selection-rules-enumeration-v1"
                        assert result["selection_rules"] == {
                            key: body[key] for key in ("prerequisites", "exclusions")
                        }
                        assert result["verification"] == {
                            "quantities": "passed",
                            "resources": "passed",
                            "selection_rules": "passed",
                        }
                    saved = measured(
                        "selection_reopen" if new else "allocation_reopen",
                        "GET",
                        roots[1].split("/uploads/")[0]
                        + "/decision-analysis/"
                        + decision["run"]["id"],
                    )
                    assert saved["run"] == decision["run"]
                    return timings

                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(journey, actors))  # One untimed warm-up per actor.
                    before = resource.getrusage(resource.RUSAGE_SELF)
                    start = time.perf_counter()
                    common = [
                        sample
                        for _ in range(3)
                        for group in pool.map(journey, actors)
                        for sample in group
                    ]
                    common_elapsed = time.perf_counter() - start
                    after = resource.getrusage(resource.RUSAGE_SELF)
                    extra = []
                    extra_elapsed = None
                    if args.new_methods:
                        start = time.perf_counter()
                        extra = [
                            sample
                            for _ in range(2)
                            for group in pool.map(lambda actor: journey(actor, True), actors)
                            for sample in group
                        ]
                        extra_elapsed = time.perf_counter() - start
                    final_usage = resource.getrusage(resource.RUSAGE_SELF)

                def summarize(samples: list[tuple[str, float]]) -> dict[str, Any]:
                    result = {}
                    for label in sorted({label for label, _ in samples}):
                        values = sorted(value for name, value in samples if name == label)
                        result[label] = {
                            "count": len(values),
                            "median_ms": round(statistics.median(values), 3),
                            "p95_ms_nearest_rank": round(
                                values[int(0.95 * len(values) + 0.999999) - 1], 3
                            ),
                            "max_ms": round(max(values), 3),
                        }
                    return result

                report = dict(
                    source=str(source),
                    loaded_module=str(Path(execplus.__file__).resolve()),
                    fixture_sha256=[
                        hashlib.sha256(value).hexdigest() for value in (observations, actions)
                    ],
                    users=8,
                    common_rounds=3,
                    common_requests=len(common),
                    errors=0,
                    common_elapsed_seconds=round(common_elapsed, 3),
                    common=summarize(common),
                    common_cpu_seconds=round(
                        after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 3
                    ),
                    process_peak_rss_kib=after.ru_maxrss,
                    new_method_requests=len(extra),
                    new_method_elapsed_seconds=round(extra_elapsed, 3)
                    if extra_elapsed is not None
                    else None,
                    new_methods=summarize(extra),
                    new_method_cpu_seconds=round(
                        final_usage.ru_utime
                        + final_usage.ru_stime
                        - after.ru_utime
                        - after.ru_stime,
                        3,
                    )
                    if args.new_methods
                    else None,
                    final_process_peak_rss_kib=final_usage.ru_maxrss,
                    cpu_count=os.cpu_count(),
                    platform=platform.platform(),
                    python_version=platform.python_version(),
                    limits=(
                        "ASGI TestClient with real local PostgreSQL/MinIO; model disabled. "
                        "Latency excludes browser/network. RSS is API/test process peak, excludes "
                        "database/storage processes. Short fictional workload, "
                        "not sustained production acceptance."
                    ),
                )

    finally:
        if runtime is not None:
            runtime.engine.dispose()
        if bucket_created:
            for page in storage.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for item in page.get("Contents", []):
                    storage.delete_object(Bucket=bucket, Key=item["Key"])
            storage.delete_bucket(Bucket=bucket)
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{namespace}" CASCADE'))
        admin.dispose()
        private_fixture.cleanup()
    assert report is not None
    report["isolation"] = {"schema": namespace, "bucket": bucket, "cleanup_completed": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests": report.get("http_requests", report.get("common_requests")),
                "status": report.get("status", "passed"),
                "errors": report.get("errors", len(report.get("failures", []))),
            }
        )
    )

    if report.get("status") == "failed":
        raise SystemExit(1)


def next_batch_workload(source: Path, runtime: Any, settings: Any, duration: int) -> dict[str, Any]:
    from collections import Counter
    from contextlib import contextmanager
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal
    from importlib import import_module
    from threading import Barrier, Event, Lock, Thread
    from types import SimpleNamespace
    from uuid import UUID

    from fastapi.testclient import TestClient

    from execplus.domain.usage_metering import TokenUsage, UsageAttribution
    from execplus.main import create_app

    sys.path.insert(0, str(source / "apps/api/tests"))
    company_fixture = import_module("test_company_consolidation_integration").fixture
    source_db = import_module("test_postgres_source").source_db
    scenario_request = import_module("test_source_scenarios").request
    confirm = import_module("test_understanding").confirm
    context = import_module("test_understanding").context
    dataset = import_module("test_workspace_integration").dataset
    upload = import_module("test_workspace_integration").upload

    lock = Lock()
    stop = Event()
    phase = "setup"
    samples: list[dict[str, Any]] = []
    checks: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    resources: list[dict[str, Any]] = []
    retained: list[tuple[dict[str, str], str, bytes, Any]] = []
    fixture_hashes: list[str] = []
    watched = [
        "scripts/measure_analysis_workload.py",
        "apps/api/tests/test_company_consolidation_integration.py",
        "apps/api/tests/test_postgres_source.py",
        "apps/api/tests/test_source_scenarios.py",
        "apps/api/tests/test_understanding.py",
        "apps/api/tests/test_workspace_integration.py",
        "docs/next-batch-evaluation-cases.json",
        "apps/api/src/execplus/domain/source_scenarios.py",
        "apps/api/src/execplus/domain/temporal_anomalies.py",
        "apps/api/src/execplus/domain/distribution_drift.py",
        "apps/api/src/execplus/domain/company_consolidation.py",
        *[
            "apps/api/src/execplus/application/services/" + name + ".py"
            for name in (
                "source_imports",
                "usage_metering",
                "integration_access",
                "company_consolidation",
                "calendar_analysis",
                "decision_analysis",
                "analytics",
                "workspaces",
                "refresh",
            )
        ],
        "apps/api/src/execplus/infrastructure/sources/postgres.py",
    ]
    code_hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in watched
    }

    def checked(condition: bool, label: str) -> None:
        if not condition:
            raise AssertionError(label)
        with lock:
            checks[label] += 1

    def sample_resource(label: str) -> dict[str, Any]:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        current_rss = next(
            int(line.split()[1])
            for line in Path("/proc/self/status").read_text().splitlines()
            if line.startswith("VmRSS:")
        )
        return {
            "label": label,
            "utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_seconds": round(time.monotonic(), 3),
            "cpu_seconds": usage.ru_utime + usage.ru_stime,
            "current_rss_kib": current_rss,
            "peak_rss_kib": usage.ru_maxrss,
            "system_load_1m": os.getloadavg()[0],
        }

    with contextmanager(source_db.__wrapped__)(
        Path(settings.source_secret_directory)
    ) as source_db_fixture:
        source_before = source_db_fixture.admin.execute(
            "SELECT * FROM samples ORDER BY id"
        ).fetchall()
        with TestClient(create_app(settings, runtime)) as client:
            env = SimpleNamespace(client=client, runtime=runtime, engine=runtime.engine)

            def request(
                headers: dict[str, str],
                label: str,
                method: str,
                path: str,
                *,
                expected: tuple[int, ...] = (200, 201),
                binary: bool = False,
                **kwargs: Any,
            ) -> Any:
                started = time.perf_counter()
                response = client.request(method, path, headers=headers, **kwargs)
                elapsed = (time.perf_counter() - started) * 1000
                with lock:
                    samples.append(
                        dict(
                            phase=phase,
                            label=label,
                            ms=elapsed,
                            status=response.status_code,
                            expected=response.status_code in expected,
                        )
                    )
                if response.status_code not in expected:
                    error = response.json().get("error", {}).get("code", "unexpected_status")
                    raise AssertionError(f"{label}:{response.status_code}:{error}")
                if expected == (404,):
                    checked(True, "private_denial")
                    return None
                return response.content if binary else response.json()

            def add_source(headers: dict[str, str], wid: str, content: bytes, kind: str) -> str:
                did = dataset(env, headers, wid)
                response = upload(env, headers, wid, did, content)
                checked(response.status_code == 201, "fixture_uploaded")
                root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
                current = context(env, headers, root)
                current["definition"].update(grain="record", domain="operations")
                for column in current["definition"]["columns"]:
                    name = column["name"]
                    if name == "day":
                        continue
                    column.update(role="dimension" if name in {"city", "region"} else "metric")
                    column.update(unit="", currency="")
                    if column["role"] == "metric":
                        if kind == "scenario" and name != "quantity":
                            column["currency"] = "USD"
                        else:
                            column["unit"] = "items" if name == "quantity" else "units"
                checked(
                    confirm(env, headers, root, current).status_code == 201, "fixture_confirmed"
                )
                retained.append((headers, root, content, context(env, headers, root)))
                fixture_hashes.append(hashlib.sha256(content).hexdigest())
                return root

            actors = []
            for index in range(8):
                headers, actor, _, company_path, company_body, company_roots, contents = (
                    company_fixture(env)
                )
                wid = company_body["companies"][0]["workspace_id"]
                runtime.operations.change_staff(actor.email, "admin")
                for root, content in zip(company_roots, contents, strict=True):
                    retained.append((headers, root, content, context(env, headers, root)))
                    fixture_hashes.append(hashlib.sha256(content).hexdigest())
                ordinary = b"city,amount,cost\n" + b"".join(
                    f"{'North' if i < 20 else 'South'},{i + 1},{2 * i + 3}\n".encode()
                    for i in range(40)
                )
                query_root = add_source(headers, wid, ordinary, "ordinary")
                scenario_root = add_source(
                    headers,
                    wid,
                    b"region,quantity,sales,cost,fixed\nNorth,2,10,6,3\nSouth,3,20,8,4\n",
                    "scenario",
                )
                calendar_roots = []
                for values in (
                    [10 + (i % 7) * 20 + (100 if i == 28 else 0) for i in range(49)],
                    [0] * 4 + [2] * 4 + [1] * 4 + [3] * 4,
                ):
                    content = (
                        "day,region,amount\n"
                        + "".join(
                            f"{date(2020, 1, 1) + timedelta(days=i)},North,{value}\n"
                            for i, value in enumerate(values)
                        )
                    ).encode()
                    calendar_roots.append(add_source(headers, wid, content, "calendar"))
                key = request(
                    headers,
                    "issue_key",
                    "POST",
                    f"/workspaces/{wid}/integrations/keys",
                    json={
                        "name": "Fictional workload key",
                        "dataset_ids": [query_root.split("/")[4]],
                        "operations": ["query:read"],
                        "expires_seconds": 3600,
                    },
                )
                import_did = dataset(env, headers, wid)
                sid = str(uuid4())
                approved = {
                    "schema_name": "public",
                    "table": "samples",
                    "columns": ["region", "revenue"],
                }
                request(
                    headers,
                    "register_source",
                    "PUT",
                    f"/admin/workspaces/{wid}/sources/{sid}",
                    json={
                        "expected_version": 0,
                        "label": "Local fictional read-only source",
                        "host": "localhost",
                        "address": "127.0.0.1",
                        "port": source_db_fixture.source.port,
                        "database": source_db_fixture.source.database,
                        "secret_ref": "fixture",
                        "tables": [approved],
                    },
                )
                saved_company = request(
                    headers, "consolidation", "POST", company_path, json=company_body
                )
                actors.append(
                    dict(
                        index=index,
                        headers=headers,
                        actor=actor,
                        wid=wid,
                        query_root=query_root,
                        scenario_root=scenario_root,
                        calendar_roots=calendar_roots,
                        key_headers={"Authorization": "Bearer " + key["secret"]},
                        company_path=company_path,
                        company_body=company_body,
                        saved_company=saved_company,
                        imports=f"/workspaces/{wid}/datasets/{import_did}/source-imports",
                        selection={**approved, "source_id": sid, "source_version": 1},
                        usage_attempts=0,
                    )
                )

            def common(actor: dict[str, Any]) -> None:
                headers, root, wid = actor["headers"], actor["query_root"], actor["wid"]
                answer = request(
                    headers,
                    "query",
                    "POST",
                    root + "/query",
                    json={"metric": "amount", "aggregation": "sum"},
                )
                checked(Decimal(str(answer["rows"][0][0])) == 820, "exact_query")
                replay = request(
                    headers,
                    "query_replay",
                    "POST",
                    f"/workspaces/{wid}/queries/{answer['lineage']['query_id']}/replay",
                )
                checked(replay["rows"] == answer["rows"], "exact_replay")
                other = actors[(actor["index"] + 1) % len(actors)]
                request(
                    headers,
                    "private_consolidation_denial",
                    "GET",
                    other["company_path"] + "/" + other["saved_company"]["run"]["id"],
                    expected=(404,),
                )

            def feature(actor: dict[str, Any], kind: int, cycle: int) -> None:
                headers, wid = actor["headers"], actor["wid"]
                if kind == 0:
                    body = {**actor["selection"], "request_id": str(uuid4())}
                    imported = request(
                        headers, "source_import", "POST", actor["imports"], json=body
                    )
                    checked(imported["status"] == "imported", "source_imported")
                    retry = request(
                        headers, "source_idempotent_retry", "POST", actor["imports"], json=body
                    )
                    checked(retry == imported, "source_idempotency")
                    root = (
                        actor["imports"].removesuffix("/source-imports")
                        + "/uploads/"
                        + imported["upload_id"]
                    )
                    content = request(
                        headers, "import_content", "GET", root + "/content", binary=True
                    )
                    checked(
                        content
                        == b"region,revenue\nKarachi,0.100000000000\nLahore,0.200000000000\n",
                        "exact_import_bytes",
                    )
                elif kind == 1:
                    scope = UsageAttribution(UUID(wid), actor["actor"].id, uuid4(), "conversation")
                    started = time.perf_counter()
                    meter = runtime.usage_metering
                    attempt = meter.reserve(
                        scope, uuid4(), "fictional-workload", "no-provider-called"
                    )
                    meter.start(scope, attempt.id)
                    settled = meter.finish(scope, attempt.id, "succeeded", TokenUsage(100, 50, 20))
                    with lock:
                        samples.append(
                            dict(
                                phase=phase,
                                label="synthetic_usage_lifecycle",
                                ms=(time.perf_counter() - started) * 1000,
                                status=None,
                                expected=True,
                            )
                        )
                    checked(settled.cost is None, "unpriced_cost_unknown")
                    actor["usage_attempts"] += 1
                    summary = request(
                        headers, "model_usage_summary", "GET", f"/workspaces/{wid}/model-usage"
                    )
                    checked(
                        summary["counts"]["attempts"] == actor["usage_attempts"],
                        "exact_usage_attempts",
                    )
                    checked(
                        summary["counts"]["unknown_cost_attempts"] == actor["usage_attempts"],
                        "unknown_cost_preserved",
                    )
                elif kind == 2:
                    answer = request(
                        actor["key_headers"],
                        "integration_query",
                        "POST",
                        "/integration/v1" + actor["query_root"] + "/query",
                        json={"metric": "amount", "aggregation": "sum"},
                    )
                    checked(Decimal(str(answer["rows"][0][0])) == 820, "exact_integration_query")
                    request(
                        actor["key_headers"],
                        "integration_scope_denial",
                        "POST",
                        "/integration/v1" + actor["scenario_root"] + "/query",
                        json={"metric": "quantity", "aggregation": "sum"},
                        expected=(404,),
                    )
                elif kind == 3:
                    for calendar_index, method in enumerate(
                        ("seasonal-residual-mad-iqr-v1", "empirical-window-distance-v1")
                    ):
                        root = actor["calendar_roots"][calendar_index]
                        options = request(
                            headers, "calendar_options", "GET", root + "/decision-analysis/options"
                        )
                        body = dict(
                            name="Fictional calendar workload",
                            model=method,
                            revision_id=options["revision_id"],
                            understanding_id=options["understanding_id"],
                            metric="amount",
                            aggregation="sum",
                            time_column="day",
                            frequency="daily",
                            coverage_confirmed=True,
                            materiality="0",
                            filters=[],
                        )
                        if calendar_index == 0:
                            body.update(
                                coverage_start="2020-01-01",
                                coverage_end="2020-02-18",
                                training_end="2020-01-28",
                                season_length=7,
                                threshold="3.5",
                            )
                            suffix = "/seasonal-anomalies"
                        else:
                            body.update(
                                reference_start="2020-01-01",
                                reference_end="2020-01-08",
                                comparison_start="2020-01-09",
                                comparison_end="2020-01-16",
                                minimum_cdf_separation="0.2",
                            )
                            suffix = "/distribution-drift"
                        value = request(
                            headers,
                            suffix[1:],
                            "POST",
                            root + "/decision-analysis" + suffix,
                            json=body,
                        )
                        result = value["run"]["result"]
                        if calendar_index == 0:
                            checked(
                                [item["period"] for item in result["findings"]]
                                == ["2020-01-29", "2020-02-05"],
                                "exact_seasonal_findings",
                            )
                            checked(
                                result["history"][28]["actual"] == "110"
                                and result["history"][28]["expected"] == "10",
                                "exact_seasonal_reference",
                            )
                        else:
                            distance = result["wasserstein_distance"]
                            checked(
                                int(distance["numerator"]) == int(distance["denominator"])
                                and result["maximum_cdf_separation"]["display"] == "0.5",
                                "exact_drift",
                            )
                        opened = request(
                            headers,
                            "calendar_replay",
                            "GET",
                            root.split("/uploads/")[0] + "/decision-analysis/" + value["run"]["id"],
                        )
                        checked(opened["run"] == value["run"], "exact_calendar_replay")
                elif kind == 4:
                    root = actor["scenario_root"]
                    options = request(
                        headers, "scenario_options", "GET", root + "/decision-analysis/options"
                    )
                    body = dict(
                        **scenario_request(),
                        name="Fictional workload scenario",
                        revision_id=options["revision_id"],
                        understanding_id=options["understanding_id"],
                    )
                    value = request(
                        headers,
                        "source_scenario",
                        "POST",
                        root + "/decision-analysis/source-scenarios",
                        json=body,
                    )
                    result = value["run"]["result"]
                    checked(
                        Decimal(result["baseline"]["revenue"]) == 80
                        and Decimal(result["alternatives"][0]["result"]["remaining"])
                        == Decimal("37.6"),
                        "exact_source_scenario",
                    )
                    opened = request(
                        headers,
                        "scenario_replay",
                        "GET",
                        root.split("/uploads/")[0] + "/decision-analysis/" + value["run"]["id"],
                    )
                    checked(opened["run"] == value["run"], "exact_scenario_replay")
                else:
                    value = request(
                        headers,
                        "consolidation",
                        "POST",
                        actor["company_path"],
                        json=actor["company_body"],
                    )
                    checked(
                        value["run"]["result"]["consolidated"]
                        == [
                            {"group_account": "Cash", "amount": "200"},
                            {"group_account": "Equity", "amount": "-200"},
                            {"group_account": "Internal", "amount": "0"},
                        ],
                        "exact_consolidation",
                    )
                    opened = request(
                        headers,
                        "consolidation_replay",
                        "GET",
                        actor["company_path"] + "/" + value["run"]["id"],
                    )
                    checked(opened == value, "exact_consolidation_replay")

            def preserve() -> None:
                for headers, root, content, meaning in retained:
                    actual = request(
                        headers, "preserved_content", "GET", root + "/content", binary=True
                    )
                    checked(actual == content, "source_bytes_unchanged")
                    actual_meaning = request(
                        headers, "preserved_meaning", "GET", root + "/understanding"
                    )
                    checked(actual_meaning == meaning, "source_meaning_unchanged")
                checked(
                    source_db_fixture.admin.execute("SELECT * FROM samples ORDER BY id").fetchall()
                    == source_before,
                    "external_source_rows_unchanged",
                )

            def summarize(selected: str) -> dict[str, Any]:
                values = [item for item in samples if item["phase"] == selected]
                result = {}
                for label in sorted({item["label"] for item in values}):
                    group = [item for item in values if item["label"] == label]
                    timings = sorted(item["ms"] for item in group)
                    result[label] = dict(
                        count=len(group),
                        median_ms=round(statistics.median(timings), 3),
                        p95_ms_nearest_rank=round(
                            timings[int(0.95 * len(timings) + 0.999999) - 1], 3
                        ),
                        max_ms=round(max(timings), 3),
                        unexpected_statuses=sum(not item["expected"] for item in group),
                    )
                return result

            elapsed = 0.0
            cycles = [0] * 8
            phase_times = {}
            try:
                with ThreadPoolExecutor(max_workers=8) as pool:
                    phase = "warmup"
                    for kind in range(6):
                        list(
                            pool.map(
                                lambda actor, selected=kind: feature(actor, selected, 0), actors
                            )
                        )
                    preserve()
                    phase = "before"
                    started = time.perf_counter()
                    for _ in range(3):
                        list(pool.map(common, actors))
                    phase_times[phase] = time.perf_counter() - started
                    resources.append(sample_resource("before_sustained"))
                    phase = "sustained"
                    barrier = Barrier(8)
                    started = time.perf_counter()

                    def sampler() -> None:
                        while not stop.wait(20):
                            with lock:
                                resources.append(sample_resource("interval"))

                    monitor = Thread(target=sampler, daemon=True)
                    monitor.start()

                    def user_loop(actor: dict[str, Any]) -> None:
                        barrier.wait()
                        began = time.monotonic()
                        cycle = 0
                        try:
                            while time.monotonic() - began < duration and not stop.is_set():
                                common(actor)
                                feature(actor, (cycle + actor["index"]) % 6, cycle)
                                cycles[actor["index"]] += 1
                                cycle += 1
                                stop.wait(
                                    max(
                                        0,
                                        min(began + duration, began + cycle * 10)
                                        - time.monotonic(),
                                    )
                                )
                        except Exception as error:
                            with lock:
                                failures.append(
                                    dict(
                                        phase=phase,
                                        type=type(error).__name__,
                                        detail=str(error)[:200],
                                    )
                                )
                            stop.set()

                    list(pool.map(user_loop, actors))
                    elapsed = time.perf_counter() - started
                    stop.set()
                    monitor.join(timeout=2)
                    resources.append(sample_resource("after_sustained"))
                    phase = "after"
                    started = time.perf_counter()
                    for _ in range(3):
                        list(pool.map(common, actors))
                    phase_times[phase] = time.perf_counter() - started
                    preserve()
            except Exception as error:
                failures.append(
                    dict(phase=phase, type=type(error).__name__, detail=str(error)[:200])
                )
                stop.set()
            code_after = {
                name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in watched
            }
            changed = [name for name in watched if code_after[name] != code_hashes[name]]
            sustained = summarize("sustained")
            gates = dict(
                completed_duration=elapsed >= duration,
                eight_users_completed=all(value >= duration // 10 for value in cycles),
                no_unexpected_errors=not failures and all(item["expected"] for item in samples),
                operation_p95_under_5_seconds=bool(sustained)
                and all(value["p95_ms_nearest_rank"] <= 5000 for value in sustained.values()),
                process_peak_under_1_gib=bool(resources)
                and max(value["peak_rss_kib"] for value in resources) <= 1024 * 1024,
                operation_source_unchanged=not changed,
                sources_preserved=checks["source_bytes_unchanged"] == 2 * len(retained)
                and checks["source_meaning_unchanged"] == 2 * len(retained)
                and checks["external_source_rows_unchanged"] == 2,
            )
            return dict(
                version="next-batch-local-workload-v1",
                status="passed" if all(gates.values()) else "failed",
                source=str(source),
                users=8,
                workspaces=16,
                duration_requested_seconds=duration,
                sustained_elapsed_seconds=round(elapsed, 3),
                cycles_by_user=cycles,
                cadence_seconds=10,
                measurements={
                    name: summarize(name)
                    for name in ("setup", "warmup", "before", "sustained", "after")
                },
                http_requests=sum(item["status"] is not None for item in samples),
                sustained_http_requests=sum(
                    item["phase"] == "sustained" and item["status"] is not None for item in samples
                ),
                expected_http_denials=sum(
                    item["status"] == 404 and item["expected"] for item in samples
                ),
                unexpected_http_statuses=sum(not item["expected"] for item in samples),
                failures=failures,
                declared_thresholds={
                    "duration_seconds": duration,
                    "cycles_per_user": duration // 10,
                    "unexpected_errors": 0,
                    "operation_p95_ms": 5000,
                    "process_peak_rss_kib": 1024 * 1024,
                },
                checks=dict(checks),
                gates=gates,
                phase_elapsed_seconds=phase_times,
                resources=resources,
                code_sha256=code_hashes,
                changed_operation_sources=changed,
                fixture_sha256=sorted(set(fixture_hashes)),
                cpu_count=os.cpu_count(),
                platform=platform.platform(),
                python_version=platform.python_version(),
                limits=[
                    "Internal fictional workload only; no production gate is cleared.",
                    (
                        "Eight independent actors each own two company workspaces; this "
                        "does not measure many users contending on one workspace."
                    ),
                    (
                        "ASGI TestClient with real local PostgreSQL/MinIO and a separate "
                        "SELECT-only source database; no browser or external network latency."
                    ),
                    (
                        "Each actor starts at most one cycle per ten seconds; operations "
                        "are sequential within each actor, not constant eight-request concurrency."
                    ),
                    (
                        "Before/after are identical probes of one build around sustained "
                        "work, not old/new application performance comparisons."
                    ),
                    (
                        "Process CPU/current RSS/peak RSS exclude PostgreSQL, object "
                        "storage and provider processes; system load is context only."
                    ),
                    (
                        "Usage attempts contain declared fictional counters and no price: "
                        "cost stays unknown; no hosted provider, quota or invoice "
                        "performance claim."
                    ),
                    (
                        "CP-SAT, hosted model quality, embedding/webhook throughput, "
                        "email/payment delivery and external customer sources are excluded."
                    ),
                    (
                        "Integration/embed/webhook failure semantics are covered "
                        "separately by fixed evaluation, not all by this repeated workload."
                    ),
                ],
            )


if __name__ == "__main__":
    main()
