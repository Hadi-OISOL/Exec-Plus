"""Use case: Proves spelled-month dates are understood and one bad cell cannot block a list.

What it does: Checks the shared date parser, profile-v6 versus frozen v1-v5 profiles, and
reproduces the leads ranking failure on the in-memory and typed-Parquet query paths.
"""

import csv
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from execplus.domain.columnar import ColumnarManifest, ColumnarTable
from execplus.domain.errors import QueryDataError
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import (
    ALGORITHM,
    CURRENT_ALGORITHM,
    PROFILE_V2,
    PROFILE_V3,
    PROFILE_V5,
    PROFILE_V6,
    TableData,
    parse_date,
    profile_for,
)
from execplus.domain.semantics import (
    FilterOperator,
    MetricFilter,
    RowOrder,
    RowRequest,
    dataset_view,
    plan_rows,
)
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor

EXTENSIONS = Path(
    os.environ.get(
        "EXECPLUS_DUCKDB_EXTENSION_DIRECTORY",
        Path(__file__).resolve().parents[3] / "data" / "duckdb-extensions",
    )
)
HEADERS = (
    "total_score",
    "organization",
    "person",
    "role",
    "need",
    "evidence",
    "contact",
    "location",
    "intent_score",
    "fit_score",
    "source",
    "url",
    "posted_at",
    "next_step",
)


def leads(posted_eleven="Thu, 02 Apr 2026"):
    rows = []
    for index in range(1, 14):
        posted = f"2026-07-{index:02d}"
        if index == 11:
            posted = posted_eleven
        elif index == 12:
            posted = "Tue, 30 Jun 2026"
        rows.append(
            (
                str(50 + index * 3 % 17),
                f"Fictional Org {index}",
                f"Person {index}",
                "Engineer" if index % 2 else "Analyst",
                "Automation",
                "Job post",
                f"p{index}@example.test",
                "Remote",
                str(index % 5),
                str(index % 7),
                "WeWorkRemotely" if index in {11, 12} else "Board",
                f"https://example.test/{index}",
                posted,
                "Reach out",
            )
        )
    return TableData(HEADERS, tuple(rows))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-07-09", date(2026, 7, 9)),
        ("Thu, 02 Apr 2026", date(2026, 4, 2)),
        ("thu, 2 apr 2026", date(2026, 4, 2)),
        ("Thursday, 2 April 2026", date(2026, 4, 2)),
        ("02 Apr 2026", date(2026, 4, 2)),
        ("2 April 2026", date(2026, 4, 2)),
        ("Apr 2, 2026", date(2026, 4, 2)),
        ("April 2 2026", date(2026, 4, 2)),
        ("Sept 3, 2026", date(2026, 9, 3)),
        ("Tue, 30 Jun 2026 23:15:00 +0500", date(2026, 6, 30)),
        ("Tue, 30 Jun 2026 10:00 GMT", date(2026, 6, 30)),
        ("2026-04-02T23:30:00-05:00", date(2026, 4, 2)),
        ("2026-04-02 08:00", date(2026, 4, 2)),
        ("02/04/2026", None),
        ("2026/04/02", None),
        ("Fri, 02 Apr 2026", None),
        ("31 Feb 2026", None),
        ("Apr 2026", None),
        ("02 Apr 26", None),
        ("Thu, 02 Apr 2026 25:00", None),
        ("2 Foo 2026", None),
        ("2026-02-30", None),
        ("", None),
    ],
)
def test_parse_date_reads_only_unambiguous_dates(text, expected):
    assert parse_date(text) == expected


def test_profile_v6_types_the_mixed_column_without_invalid_dates():
    column = profile_for(leads(), PROFILE_V6)["columns"][HEADERS.index("posted_at")]
    assert column["type"] == "date"
    assert column["invalid_dates"] == 0
    assert (column["date_min"], column["date_max"]) == ("2026-04-02", "2026-07-13")


@pytest.mark.parametrize(
    "version", [ALGORITHM, PROFILE_V2, PROFILE_V3, CURRENT_ALGORITHM, PROFILE_V5]
)
def test_frozen_profiles_still_count_spelled_dates_as_invalid(version):
    result = profile_for(leads(), version)
    column = result["columns"][HEADERS.index("posted_at")]
    assert result["algorithm"] == version
    assert column["type"] == "date"
    assert column["invalid_dates"] == 2
    assert (column["date_min"], column["date_max"]) == ("2026-07-01", "2026-07-13")


def ranked(view, dataset_id, scope, **request):
    return plan_rows(
        scope,
        dataset_id,
        view,
        RowRequest(order_by=RowOrder("total_score", "desc"), **request),
        row_limit=5,
    )


def scope_for(dataset_id):
    return WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset_id}))


@pytest.mark.asyncio
async def test_v5_leads_ranking_is_answered_despite_spelled_dates():
    table = leads()
    view = dataset_view(profile_for(table, PROFILE_V5))
    dataset_id = uuid4()
    scope = scope_for(dataset_id)
    result = await DuckDBQueryExecutor(30, 256).execute(
        ranked(view, dataset_id, scope), scope, table, view
    )
    assert result.matched_records == 13
    position = result.columns.index("posted_at")
    assert {row[position] for row in result.rows} <= {
        date(2026, 7, day) for day in range(1, 14)
    } | {date(2026, 4, 2), date(2026, 6, 30)}


@pytest.mark.asyncio
async def test_bad_cell_only_blocks_questions_that_use_its_column():
    table = leads("02/04/2026")
    view = dataset_view(profile_for(table, PROFILE_V6))
    dataset_id = uuid4()
    scope = scope_for(dataset_id)
    executor = DuckDBQueryExecutor(30, 256)
    result = await executor.execute(ranked(view, dataset_id, scope), scope, table, view)
    position = result.columns.index("posted_at")
    assert result.rows[0][HEADERS.index("total_score")] == max(int(row[0]) for row in table.rows)
    assert all(isinstance(row[position], str | None) for row in result.rows)
    after = MetricFilter("posted_at", FilterOperator.GTE, "2026-07-01")
    with pytest.raises(QueryDataError) as error:
        await executor.execute(
            ranked(view, dataset_id, scope, filters=(after,)), scope, table, view
        )
    assert str(error.value).startswith(
        'Column "posted_at", data row 11: expected an unambiguous date such as 2026-04-02'
    )
    assert "Fictional Org" not in str(error.value)
    assert "WeWorkRemotely" not in str(error.value)


def columnar(tmp_path, table):
    tmp_path.mkdir()
    source = tmp_path / "leads.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(table.headers)
        writer.writerows(table.rows)
    work = tmp_path / "work"
    work.mkdir()
    conversion = DuckDBColumnarConverter(
        extension_directory=EXTENSIONS, memory_limit_mb=512, threads=2
    ).convert(source, "leads.csv", work)
    manifest = ColumnarManifest(
        "key", conversion.sha256, conversion.size, conversion.rows, conversion.errors
    )
    return (
        ColumnarTable(conversion.headers, manifest, lambda: conversion.parquet, lambda: table),
        dataset_view(conversion.profile),
        conversion,
    )


@pytest.mark.asyncio
async def test_columnar_leads_match_in_memory_and_tolerate_bad_display_cells(tmp_path):
    executor = DuckDBQueryExecutor(30, 256)
    dataset_id = uuid4()
    scope = scope_for(dataset_id)
    good = leads()
    snapshot, view, conversion = columnar(tmp_path / "good", good)
    assert conversion.errors == {}
    assert conversion.profile == profile_for(good, PROFILE_V6)
    plan = ranked(view, dataset_id, scope)
    assert await executor.execute(plan, scope, snapshot, view) == await executor.execute(
        plan, scope, good, view
    )
    bad = leads("02/04/2026")
    snapshot, view, conversion = columnar(tmp_path / "bad", bad)
    assert set(conversion.errors) == {"posted_at"}
    result = await executor.execute(ranked(view, dataset_id, scope), scope, snapshot, view)
    assert result.matched_records == 13
    after = MetricFilter("posted_at", FilterOperator.GTE, "2026-07-01")
    with pytest.raises(QueryDataError, match='Column "posted_at", data row 11: expected'):
        await executor.execute(
            ranked(view, dataset_id, scope, filters=(after,)), scope, snapshot, view
        )
