"""Use case: Measures a repeatable synthetic local analytics workflow.

What it does: Reuses exact fixture bytes and existing API integration helpers in
fresh cached-image containers, recording first/warm latency, throughput, process
memory, source hashes and exact-answer checks. No production endpoint is accepted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import os
import platform
import resource
import statistics
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import date, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def fixture_bytes(directory: Path) -> tuple[bytes, bytes, list[tuple[str, ...]]]:
    """Preserve the original XLSX ZIP bytes across runs; verify actual cell values."""
    from openpyxl import Workbook

    records: list[tuple[str, ...]] = [
        (
            f"item-{i}",
            (date(2025, 1, 1) + timedelta(days=i % 365)).isoformat(),
            f"{i % 17}.125",
            str(i % 9),
        )
        for i in range(3000)
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("item", "date", "revenue", "cost"))
    writer.writerows(records)
    csv_value = stream.getvalue().encode()
    if directory.is_symlink():
        raise ValueError("Fixture directory must not be a symlink.")
    directory.mkdir(parents=True, exist_ok=True)
    csv_path, xlsx_path = directory / "sales.csv", directory / "sales.xlsx"
    if any(path.is_symlink() for path in (csv_path, xlsx_path)):
        raise ValueError("Fixture files must not be symlinks.")
    if csv_path.exists() and csv_path.read_bytes() != csv_value:
        raise ValueError("Existing CSV differs from this benchmark fixture; preserve it.")
    if not xlsx_path.exists():
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.append(("item", "date", "revenue", "cost"))
        for row in records:
            sheet.append(row)
        workbook.save(xlsx_path)
        workbook.close()
    if not csv_path.exists():
        csv_path.write_bytes(csv_value)
    return csv_value, xlsx_path.read_bytes(), records


def measure(
    report: dict[str, Any],
    name: str,
    call: Callable[[], Any],
    check: Callable[[Any], None] | None = None,
) -> Any:
    samples, memory = [], []
    result = None
    for _ in range(4):
        started = time.perf_counter()
        result = call()
        samples.append((time.perf_counter() - started) * 1000)
        memory.append(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
        if check is not None:
            check(result)
    median = statistics.median(samples[1:])
    report["measurements"][name] = {
        "first_ms": round(samples[0], 3),
        "warm_ms": [round(value, 3) for value in samples[1:]],
        "warm_median_ms": round(median, 3),
        "warm_serial_operations_per_second": round(1000 / median, 3),
        "process_high_water_rss_mib": [round(value, 3) for value in memory],
    }
    return result


def run(source: Path, output: Path, fixtures: Path) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new report path; previous measurements are retained.")
    output.parent.mkdir(parents=True, exist_ok=True)
    for key in tuple(os.environ):
        if key.startswith(
            ("EXECPLUS_", "AWS_", "OPENAI_", "ANTHROPIC_", "DEEPSEEK_", "DATABASE_", "SMTP_")
        ):
            del os.environ[key]
    os.environ.update(
        EXECPLUS_ENVIRONMENT="test",
        EXECPLUS_LLM_MODE="disabled",
        EXECPLUS_EMAIL_MODE="disabled",
        EXECPLUS_VECTOR_MODE="disabled",
    )
    sys.path[:0] = [str(source / "apps/api/src"), str(source / "apps/api/tests")]
    parser_type = importlib.import_module(
        "execplus.infrastructure.file_parser"
    ).StructuredFileParser
    renderer_type = importlib.import_module(
        "execplus.infrastructure.exports.portable"
    ).PortableRenderer
    exported = importlib.import_module("test_portable_exports")
    studies = importlib.import_module("test_studies")
    workspaces = importlib.import_module("test_workspace_integration")
    forecasts = importlib.import_module("test_forecast_integration")
    integration = importlib.import_module("conftest")
    local = importlib.import_module("rehearse_local_recovery")
    report: dict[str, Any] = {
        "version": "execplus-local-workflow-benchmark-v1",
        "passed": False,
        "scope": (
            "Fictional local fixture only; no production-scale acceptance or OS cold-cache claim."
        ),
        "fixture_version": "two-phase-baseline-probe-v1",
        "measurements": {},
        "checks": {},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "load_average": os.getloadavg(),
            "operation_repetitions": 4,
        },
        "timing": (
            "First operation after imports, then three repeated operations. "
            "No OS cache flush. Serial throughput only; no concurrency capacity claim."
        ),
        "memory": (
            "Process high-water RSS includes imports and prior operations; "
            "not isolated per-operation peak and excludes containers."
        ),
        "source_files_sha256": {
            str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((source / "apps/api/src").rglob("*.py"))
        },
    }
    started = time.perf_counter()
    previous_cwd = Path.cwd()
    try:
        os.chdir(source)
        raw, xlsx, records = fixture_bytes(fixtures)
        report["fixture_sha256"] = {
            "csv": hashlib.sha256(raw).hexdigest(),
            "xlsx": hashlib.sha256(xlsx).hexdigest(),
        }
        parser = parser_type()
        combined = getattr(parser, "parse_table", None)
        report["parser_path"] = (
            "combined validated traversal" if callable(combined) else "legacy validate then read"
        )

        def parse(body: bytes, extension: str, mime: str) -> Any:
            stream = io.BytesIO(body)
            if callable(combined):
                _, table = combined(stream, "fictional." + extension, mime)
            else:
                structure = parser.parse(stream, "fictional." + extension, mime)
                table = parser.read_table(stream, structure.format)
            if table.rows != tuple(records):
                raise ValueError("Parsed fixture cells differ from their exact synthetic values.")
            return table

        measure(report, "parse_csv", lambda: parse(raw, "csv", "text/csv"))
        measure(
            report,
            "parse_xlsx",
            lambda: parse(
                xlsx, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        payload = exported.content(
            rows=tuple(
                (row[0], Decimal(row[2]), None if index % 17 == 0 else Decimal(row[3]))
                for index, row in enumerate(records[:300])
            )
        )
        renderer = renderer_type()
        for kind in ("pdf", "xlsx", "csv"):
            value = measure(report, "export_" + kind, partial(renderer.render, payload, kind))
            report["measurements"]["export_" + kind]["bytes"] = len(value)
        with local.disposable_services() as services:
            url = f"postgresql+psycopg://execplus:execplus@127.0.0.1:{services['pg_port']}/postgres"
            endpoint = f"http://127.0.0.1:{services['object_port']}"
            os.environ.update(
                EXECPLUS_TEST_DATABASE_URL=url,
                EXECPLUS_DATABASE_URL=url,
                EXECPLUS_TEST_OBJECT_STORE_ENDPOINT=endpoint,
                EXECPLUS_OBJECT_STORE_ENDPOINT=endpoint,
            )
            report["container_images"] = services["images"]
            fixture = integration.integration.__wrapped__()
            env = next(fixture)
            try:
                headers, _, wid, _, _, root = studies.prepare(env, raw)

                def ingestion() -> Any:
                    target = workspaces.dataset(env, headers, wid)
                    response = workspaces.upload(env, headers, wid, target, raw)
                    assert response.status_code == 201, response.status_code
                    assert response.json()["row_count"] == 3000
                    return response

                measure(report, "api_ingestion_profile", ingestion)

                def request(path: str, body: dict[str, Any] | None = None) -> Any:
                    response = (
                        env.client.get(root + path, headers=headers)
                        if body is None
                        else env.client.post(root + path, headers=headers, json=body)
                    )
                    assert response.status_code == 200, (response.status_code, response.text[:300])
                    return response.json()

                measure(report, "api_profile_read", lambda: request("/profile"))
                expected = sum((Decimal(row[2]) for row in records), Decimal(0))

                def exact(result: Any) -> None:
                    assert Decimal(result["rows"][0][0]) == expected

                measure(
                    report,
                    "api_query",
                    lambda: request(
                        "/query",
                        {"metric": "revenue", "aggregation": "sum", "group_by": [], "filters": []},
                    ),
                    exact,
                )
                measure(report, "api_dashboard", lambda: request("/dashboard", {"filters": []}))
                report["checks"]["exact_revenue"] = str(expected)
                forecast_headers, _, _, _, _, forecast_root = studies.prepare(
                    env, forecasts.daily()
                )

                def forecast() -> Any:
                    response = forecasts.create(env, forecast_headers, forecast_root)
                    assert response.status_code == 201, response.status_code
                    assert Decimal(
                        response.json()["result"]["predictions"][0]["estimate"]
                    ) == Decimal("4.1")
                    return response.json()

                measure(report, "api_forecast", forecast)
                report["checks"]["forecast_first_estimate"] = "4.1"
                study = studies.run(
                    env,
                    headers,
                    root,
                    method={"kind": "metric", "column": "revenue", "aggregation": "sum"},
                )
                assert study.status_code == 201, study.status_code
                study_id = study.json()["version"]["id"]
                for kind in ("pdf", "xlsx", "csv"):

                    def export(selected: str = kind) -> bytes:
                        response = env.client.get(
                            f"/workspaces/{wid}/study-versions/{study_id}/export.{selected}",
                            headers=headers,
                        )
                        assert response.status_code == 200, response.status_code
                        return bytes(response.content)

                    value = measure(report, "api_export_" + kind, export)
                    report["measurements"]["api_export_" + kind]["bytes"] = len(value)
            finally:
                with suppress(StopIteration):
                    next(fixture)
        report["passed"] = True
    except BaseException as error:
        report["failure_type"] = type(error).__name__
        raise
    finally:
        os.chdir(previous_cwd)
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        report["peak_process_rss_mib"] = round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3
        )
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.source.resolve(), args.output.resolve(), args.fixtures.resolve())
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "output": str(args.output),
                "elapsed_seconds": report["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
