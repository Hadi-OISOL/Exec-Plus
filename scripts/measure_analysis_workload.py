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
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--new-methods", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = args.source.resolve()
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
        )
        runtime = build_runtime(settings)
        identity = runtime.identity
        assert isinstance(identity, LocalSessionIdentity)
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

            def prepare(index: int) -> tuple[dict[str, str], str, list[str], str, dict[str, Any]]:
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
                    did = call(headers, "POST", f"/workspaces/{wid}/datasets", json={"name": name})[
                        "id"
                    ]
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
                    'Compare the relationship between "amount" and "cost" within groups of "city".'
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
                assert {item["candidate"]: item["quantity"] for item in result["allocations"]} == (
                    {"A": 1, "B": 0, "C": 1} if new else {"A": 2, "B": 1, "C": 0}
                )
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
                    roots[1].split("/uploads/")[0] + "/decision-analysis/" + decision["run"]["id"],
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
                    final_usage.ru_utime + final_usage.ru_stime - after.ru_utime - after.ru_stime, 3
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
            for item in storage.list_objects_v2(Bucket=bucket).get("Contents", []):
                storage.delete_object(Bucket=bucket, Key=item["Key"])
            storage.delete_bucket(Bucket=bucket)
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{namespace}" CASCADE'))
        admin.dispose()
    assert report is not None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests": report["common_requests"],
                "errors": report["errors"],
            }
        )
    )


if __name__ == "__main__":
    main()
