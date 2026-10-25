"""Use case: Measures profile-v5 typed-Parquet ingest and query cost on synthetic big files.

What it does: Streams a synthetic CSV of N rows to disk, converts it with the production
converter in a fresh process (wall time and peak RSS), runs SUM/AVG/group-by/top-N/monthly
trend through the production executor, and checks every answer against exact integer
arithmetic computed while the file was generated. Data is generated on the fly, never committed.
"""

import argparse
import asyncio
import csv
import json
import multiprocessing
import random
import statistics
import sys
import time
from collections.abc import Callable
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

from execplus.domain.columnar import ColumnarManifest, ColumnarTable
from execplus.domain.compute import ColumnarBudget
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view, plan_query
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor

REGIONS = ("North", "South", "East", "West", "Central", "Islands", "Coast", "Hills")
PRODUCTS = tuple(f"Product {index:03d}" for index in range(200))
HEADERS = (
    "order id",
    "region",
    "sale_date",
    "customer code",
    "product",
    "amount",
    "units",
    "note",
)
NOTES = tuple(f"Delivered via channel {index} with standard handling" for index in range(40))


def peak_rss_kib() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    return 0


def generate(path: Path, rows: int, seed: int = 26) -> dict[str, Any]:
    generator = random.Random(seed)
    total = 0
    by_region: dict[str, list[int]] = {name: [0, 0] for name in REGIONS}
    by_month: dict[str, int] = {}
    by_customer: dict[str, int] = {}
    days = [
        f"{2023 + day // 365}-{(day % 365) // 31 % 12 + 1:02d}-{day % 28 + 1:02d}"
        for day in range(1095)
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        for index in range(rows):
            region = REGIONS[generator.randrange(8)]
            day = days[generator.randrange(1095)]
            customer = f"C{generator.randrange(100_000):06d}"
            cents = generator.randrange(-5_000, 2_500_000)
            amount = f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"
            writer.writerow(
                (
                    index + 1,
                    region,
                    day,
                    customer,
                    PRODUCTS[index % 200],
                    amount,
                    generator.randrange(50),
                    NOTES[index % 40],
                )
            )
            total += cents
            by_region[region][0] += cents
            by_region[region][1] += 1
            by_month[day[:7]] = by_month.get(day[:7], 0) + cents
            by_customer[customer] = by_customer.get(customer, 0) + cents
    top = sorted(by_customer.items(), key=lambda item: item[1], reverse=True)[:10]
    return {
        "total": total,
        "rows": rows,
        "by_region": by_region,
        "by_month": by_month,
        "top": top,
    }


def _ingest(source: str, work: str, queue: Any) -> None:
    started = time.perf_counter()
    conversion = DuckDBColumnarConverter(memory_limit_mb=2048, threads=4).convert(
        Path(source), "csv", Path(work)
    )
    queue.put(
        {
            "seconds": time.perf_counter() - started,
            "peak_rss_kib": peak_rss_kib(),
            "profile": conversion.profile,
            "parquet": conversion.parquet,
            "sha256": conversion.sha256,
            "size": conversion.size,
            "rows": conversion.rows,
            "errors": conversion.errors,
        }
    )


def _cents(value: Decimal) -> int:
    return int(value * 100)


async def _queries(
    ingest: dict[str, Any], expected: dict[str, Any], repeats: int
) -> dict[str, Any]:
    manifest = ColumnarManifest("bench", ingest["sha256"], ingest["size"], ingest["rows"], {})
    table = ColumnarTable(
        tuple(column["name"] for column in ingest["profile"]["columns"]),
        manifest,
        lambda: ingest["parquet"],
        lambda: TableData((), ()),
    )
    view = dataset_view(ingest["profile"])
    dataset_id = uuid4()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))
    executor = DuckDBQueryExecutor(
        15, 256, columnar=ColumnarBudget(timeout_seconds=600, memory_limit_mb=2048, threads=4)
    )
    with localcontext() as context:
        context.prec = 50
        average = (Decimal(expected["total"]) / 100 / expected["rows"]).quantize(Decimal("1e-12"))
    checks: dict[str, tuple[MetricRequest, Callable[[Any], bool]]] = {
        "sum": (
            MetricRequest("amount", AggregationKind.SUM),
            lambda rows: _cents(rows[0][0]) == expected["total"],
        ),
        "avg": (
            MetricRequest("amount", AggregationKind.AVG),
            lambda rows: rows[0][0] == average,
        ),
        "group_by_region": (
            MetricRequest("amount", AggregationKind.SUM, group_by=("region",)),
            lambda rows: (
                {name: _cents(value) for name, value in rows}
                == {name: entry[0] for name, entry in expected["by_region"].items()}
            ),
        ),
        "top_10_customers": (
            MetricRequest(
                "amount", AggregationKind.SUM, group_by=("customer code",), order="desc", limit=10
            ),
            lambda rows: [(name, _cents(value)) for name, value in rows] == expected["top"],
        ),
        "monthly_trend": (
            MetricRequest("amount", AggregationKind.SUM, group_by=("sale_date",), period="month"),
            lambda rows: (
                {str(name)[:7]: _cents(value) for name, value in rows} == expected["by_month"]
            ),
        ),
    }
    report: dict[str, Any] = {}
    for name, (request, check) in checks.items():
        plan = plan_query(scope, dataset_id, view, request, row_limit=100_000)
        timings = []
        exact = True
        for _ in range(repeats):
            started = time.perf_counter()
            result = await executor.execute(plan, scope, table, view)
            timings.append(time.perf_counter() - started)
            exact = exact and bool(check(result.rows))
        report[name] = {
            "first_seconds": round(timings[0], 3),
            "median_seconds": round(statistics.median(timings), 3),
            "exact": exact,
        }
    return report


def _query_process(
    ingest: dict[str, Any], expected: dict[str, Any], repeats: int, queue: Any
) -> None:
    report = asyncio.run(_queries(ingest, expected, repeats))
    queue.put({"queries": report, "peak_rss_kib": peak_rss_kib()})


def run(rows: int, directory: Path, repeats: int = 3) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / f"synthetic-{rows}.csv"
    started = time.perf_counter()
    expected = generate(source, rows)
    generated = time.perf_counter() - started
    work = directory / f"work-{rows}"
    work.mkdir(exist_ok=True)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_ingest, args=(str(source), str(work), queue))
    process.start()
    ingest = queue.get()
    process.join()
    process = context.Process(target=_query_process, args=(ingest, expected, repeats, queue))
    process.start()
    queried = queue.get()
    process.join()
    report = {
        "rows": rows,
        "csv_bytes": source.stat().st_size,
        "parquet_bytes": ingest["size"],
        "generate_seconds": round(generated, 1),
        "ingest_seconds": round(ingest["seconds"], 1),
        "ingest_peak_rss_mib": round(ingest["peak_rss_kib"] / 1024),
        "query_process_peak_rss_mib": round(queried["peak_rss_kib"] / 1024),
        "column_types": {column["name"]: column["type"] for column in ingest["profile"]["columns"]},
        "conversion_errors": ingest["errors"],
        "queries": queried["queries"],
    }
    source.unlink()
    Path(ingest["parquet"]).unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[1_000_000])
    parser.add_argument("--directory", type=Path, default=Path("data/columnar-benchmark"))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    reports = [run(rows, args.directory, args.repeats) for rows in args.rows]
    json.dump(reports, sys.stdout, indent=2)
    print()
    if not all(entry["exact"] for report in reports for entry in report["queries"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
