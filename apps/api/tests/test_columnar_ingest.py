"""Use case: Proves profile-v6 columnar ingest keeps the in-memory meaning and exact values.

What it does: Compares DuckDB aggregate profiles with the in-memory profile rules on varied
tables, checks typed Parquet values, refusal rules and recorded conversion errors.
"""

import csv
import gzip
import json
import os
import random
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from openpyxl import Workbook

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import PROFILE_V6, TableData, profile_for
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter

EXTENSIONS = Path(
    os.environ.get(
        "EXECPLUS_DUCKDB_EXTENSION_DIRECTORY",
        Path(__file__).resolve().parents[3] / "data" / "duckdb-extensions",
    )
)
POOL = {
    "number": ["1", "2.50", "-3", "1e3", "100e-2", "0.000", "12345678901234.123456", " 7 ", ""],
    "when": ["2024-01-05", "2024-02-30", "2023-12-31", "", "2024-01-05T10:00:00"],
    "moment": ["2024-01-05T10:00:00", "2024-01-05 23:59", "2024-01-06", ""],
    "stamp": ["2024-01-05T10:00:00Z", "2024-01-05T10:00+05:30", "2024-01-05T22:15:00.5-08:00"],
    "flag": ["true", "FALSE", "", "maybe"],
    "label": ["North", " South ", "north", "N/A", "", "\u00a0East"],
    "score": ["1", "2", "N/A", "n/a", "", "—", "3.25"],
    "month": ["1", "12", "7", ""],
    "order no": ["001", "002", "002", "17"],
    "Birthday": ["2024-01-01", "x"],
    "posted": ["2026-07-09", "Thu, 02 Apr 2026", "Fri, 02 Apr 2026", "2 April 2026", "02/04/2026"],
    "seen": [
        "Apr 2, 2026",
        "31 Feb 2026",
        "Tue, 30 Jun 2026 10:00:00 GMT",
        "2026-04-02T23:00-05:00",
    ],
}


def write(path, headers, rows, delimiter=","):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(headers)
        writer.writerows(rows)


def converter(**options):
    return DuckDBColumnarConverter(extension_directory=EXTENSIONS, memory_limit_mb=1024, **options)


def convert(tmp_path, headers, rows, **options):
    source = tmp_path / "source.csv"
    write(source, headers, rows)
    work = tmp_path / "work"
    work.mkdir()
    return converter(**options).convert(source, "source.csv", work)


@pytest.mark.parametrize("seed", range(40))
def test_profile_v6_matches_in_memory_rules(tmp_path, seed):
    generator = random.Random(seed)
    headers = tuple(generator.sample(sorted(POOL), k=generator.randint(2, len(POOL))))
    rows = [
        tuple(generator.choice(POOL[name]) for name in headers)
        for _ in range(generator.randint(1, 40))
    ]
    rows = [row if any(value.strip() for value in row) else ("x", *row[1:]) for row in rows]
    result = convert(tmp_path, headers, rows)
    expected = profile_for(TableData(headers, tuple(rows)), PROFILE_V6)
    assert result.profile == expected
    assert result.rows == len(rows)


def test_typed_parquet_keeps_exact_values_and_types(tmp_path):
    headers = ("amount", "units", "day", "seen at", "active", "region", "score")
    rows = [
        ("0.10", "1e3", "2024-01-01", "2024-01-01T10:00+05:00", "true", " North ", "N/A"),
        ("12345678901234567890.1234567", "-3", "2024-01-02", "2024-01-01T00:00Z", "FALSE", "", "2"),
        ("", "", "", "2024-01-01T01:00Z", "", "South", "3.5"),
    ]
    result = convert(tmp_path, headers, rows)
    assert result.errors == {}
    connection = duckdb.connect()
    described = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{result.parquet}')"
    ).fetchall()
    values = connection.execute(f"SELECT * FROM read_parquet('{result.parquet}')").fetchall()
    assert values[0][0] == Decimal("0.10")
    assert values[1][0] == Decimal("12345678901234567890.1234567")
    assert [item[1] for item in described][:6] == [
        "DECIMAL(38,12)",
        "BIGINT",
        "DATE",
        "TIMESTAMP",
        "BOOLEAN",
        "VARCHAR",
    ]
    assert values[0][1] == 1000 and values[2][1] is None
    assert str(values[0][3]) == "2024-01-01 05:00:00"
    assert values[0][4] is True and values[1][4] is False
    assert values[0][5] == "North" and values[1][5] is None
    assert values[0][6] is None and values[2][6] == Decimal("3.5")


def test_scale_grows_beyond_twelve_without_rounding(tmp_path):
    result = convert(tmp_path, ("amount",), [("0.12345678901234",), ("1",)])
    connection = duckdb.connect()
    kind = connection.execute(
        f"SELECT typeof(amount) FROM read_parquet('{result.parquet}') LIMIT 1"
    ).fetchone()
    assert kind == ("DECIMAL(38,14)",)
    assert connection.execute(
        f"SELECT sum(amount) FROM read_parquet('{result.parquet}')"
    ).fetchone() == (Decimal("1.12345678901234"),)


def test_conflicting_column_is_kept_as_text_with_legacy_message(tmp_path):
    rows = [("1", "a"), ("2", "b"), ("3", "c"), ("oops", "d")]
    result = convert(tmp_path, ("amount", "note"), rows)
    assert result.errors == {
        "amount": 'Column "amount", data row 4: expected a whole number in the signed 64-bit '
        "range. Correct the source and upload a new version. No values were rounded or skipped."
    }


def test_spelled_dates_become_the_same_typed_dates(tmp_path):
    rows = [
        ("2026-07-09", "a"),
        ("Thu, 02 Apr 2026", "b"),
        ("Tue, 30 Jun 2026 10:00:00 +0000", "c"),
        ("April 2 2026", "d"),
        ("", "e"),
    ]
    result = convert(tmp_path, ("posted_at", "note"), rows)
    assert result.errors == {}
    assert result.profile["columns"][0]["type"] == "date"
    assert result.profile["columns"][0]["date_min"] == "2026-04-02"
    values = (
        duckdb.connect()
        .execute(f"SELECT posted_at FROM read_parquet('{result.parquet}')")
        .fetchall()
    )
    assert [str(value) for (value,) in values] == [
        "2026-07-09",
        "2026-04-02",
        "2026-06-30",
        "2026-04-02",
        "None",
    ]


def test_ambiguous_numeric_date_is_flagged_not_nulled(tmp_path):
    rows = [("2026-07-09",), ("2026-07-10",), ("02/04/2026",)]
    result = convert(tmp_path, ("posted_at",), rows)
    assert result.errors["posted_at"].startswith(
        'Column "posted_at", data row 3: expected an unambiguous date such as '
        "2026-04-02 or 2 Apr 2026, not 02/04/2026."
    )
    values = (
        duckdb.connect()
        .execute(f"SELECT posted_at FROM read_parquet('{result.parquet}')")
        .fetchall()
    )
    assert values[2] == ("02/04/2026",)


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        ([("=SUM(A1)", "1")], "unsafe_formula"),
        ([("-x", "1")], "unsafe_formula"),
        ([("a\x01", "1")], "unsafe_content"),
        ([("a", "1"), ("", " ")], "malformed_csv"),
    ],
)
def test_unsafe_or_blank_rows_are_refused(tmp_path, rows, code):
    with pytest.raises(IngestionError) as error:
        convert(tmp_path, ("name", "value"), rows, formula_cells="reject")
    assert error.value.code == code


def test_short_rows_follow_the_shared_reader(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("a,b\n1,2\n3\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    result = converter().convert(source, "source.csv", work)
    assert result.headers == ("a,b",)
    assert result.profile["columns"][0]["type"] == "text"


def test_semicolon_and_bom_sources_convert(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes("﻿region;amount\nNorth;1.5\nSouth;2\n".encode())
    work = tmp_path / "work"
    work.mkdir()
    result = converter().convert(source, "source.csv", work)
    assert result.format == "r:csv"
    assert result.headers == ("region", "amount")
    assert result.profile["columns"][1]["type"] == "decimal"


def _sum(result, column):
    connection = duckdb.connect()
    return connection.execute(
        f'SELECT sum("{column}"), typeof(sum("{column}")) FROM read_parquet(?)', [result.parquet]
    ).fetchone()


def _write_source(source, name, rows):
    if name.endswith("json"):
        records = [{"region": r, "amount": a, "day": d} for r, a, d in rows]
        lines = [json.dumps(item) for item in records]
        text = "\n".join(lines) if name.endswith("ndjson") else json.dumps(records)
        source.write_text(text, encoding="utf-8")
    elif name.endswith(".gz"):
        text = "region,amount,day\n" + "\n".join(map(",".join, rows))
        source.write_bytes(gzip.compress(text.encode()))
    elif name.endswith(".tsv"):
        text = "region\tamount\tday\n" + "\n".join("\t".join(row) for row in rows)
        source.write_text(text, encoding="utf-8")
    else:
        duckdb.connect().execute(
            "COPY (SELECT * FROM (VALUES ('North', 0.10::DECIMAL(10,2), DATE '2024-01-01'), "
            "('South', 0.20::DECIMAL(10,2), DATE '2024-01-02')) t(region, amount, day)) "
            f"TO '{source}' (FORMAT parquet)"
        )


@pytest.mark.parametrize(
    "name", ["data.ndjson", "data.json", "data.csv.gz", "data.parquet", "data.tsv"]
)
def test_reader_formats_convert_to_exact_typed_parquet(tmp_path, name):
    source = tmp_path / name
    _write_source(source, name, [("North", "0.10", "2024-01-01"), ("South", "0.20", "2024-01-02")])
    work = tmp_path / "work"
    work.mkdir()
    result = converter().convert(source, name, work)
    assert result.format.startswith("r:")
    types = {column["name"]: column["type"] for column in result.profile["columns"]}
    assert types == {"region": "text", "amount": "decimal", "day": "date"}
    assert _sum(result, "amount") == (Decimal("0.300000000000"), "DECIMAL(38,12)")


@pytest.mark.skipif(
    not any(EXTENSIONS.glob(f"v{duckdb.__version__}/*/excel.duckdb_extension")),
    reason="bundled DuckDB excel extension is not installed",
)
def test_excel_scientific_notation_text_is_typed_exactly_as_read(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["code", "amount", "big"])
    sheet.append(["A", 0.1, 12345678901234568])
    sheet.append(["B", 0.2, 2])
    source = tmp_path / "book.xlsx"
    workbook.save(source)
    work = tmp_path / "work"
    work.mkdir()
    result = converter().convert(source, "book.xlsx", work)
    assert result.errors == {}
    assert _sum(result, "amount")[0] == Decimal("0.3")
    connection = duckdb.connect()
    big = connection.execute("SELECT big FROM read_parquet(?)", [result.parquet]).fetchall()
    assert big == [(12345678901234570,), (2,)]


def test_upload_sessions_accept_exactly_the_reader_extensions():
    from execplus.domain.upload_sessions import READER_EXTENSIONS, require_supported
    from execplus.infrastructure.readers.detection import EXTENSIONS as DETECTED

    assert frozenset(DETECTED) == READER_EXTENSIONS
    require_supported("orders.parquet", "application/octet-stream")
    require_supported("orders.csv", "text/csv")
    for name, kind in (("orders.csv", "application/pdf"), ("orders.pdf", "application/pdf")):
        with pytest.raises(IngestionError):
            require_supported(name, kind)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("a.csv", "r:csv"), ("a.b.csv.gz", "r:csv.gz"), ("x.backup.zip", "r:zip"), ("s.SAV", "r:sav")],
)
def test_stored_reader_format_names(filename, expected):
    from execplus.infrastructure.columnar.source_rows import stored_format

    assert stored_format(filename) == expected
