"""Use case: Proves profile-v5 columnar ingest keeps profile-v4 meaning and exact values.

What it does: Compares DuckDB aggregate profiles with the in-memory profile rules on varied
tables, checks typed Parquet values, refusal rules and recorded conversion errors.
"""

import csv
import random
from decimal import Decimal

import duckdb
import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import PROFILE_V5, TableData, profile_for
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter

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
}


def write(path, headers, rows, delimiter=","):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(headers)
        writer.writerows(rows)


def convert(tmp_path, headers, rows, format="csv"):
    source = tmp_path / "source.csv"
    write(source, headers, rows, {"csv": ",", "csv;s": ";", "csv;t": "\t"}[format])
    work = tmp_path / "work"
    work.mkdir()
    return DuckDBColumnarConverter(memory_limit_mb=256, threads=2).convert(source, format, work)


@pytest.mark.parametrize("seed", range(40))
def test_profile_v5_matches_in_memory_rules(tmp_path, seed):
    generator = random.Random(seed)
    headers = tuple(generator.sample(sorted(POOL), k=generator.randint(2, len(POOL))))
    rows = [
        tuple(generator.choice(POOL[name]) for name in headers)
        for _ in range(generator.randint(1, 40))
    ]
    rows = [row if any(value.strip() for value in row) else ("x", *row[1:]) for row in rows]
    result = convert(tmp_path, headers, rows)
    expected = profile_for(TableData(headers, tuple(rows)), PROFILE_V5)
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
        convert(tmp_path, ("name", "value"), rows)
    assert error.value.code == code


def test_inconsistent_columns_are_refused(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("a,b\n1,2\n3\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(IngestionError) as error:
        DuckDBColumnarConverter(memory_limit_mb=128).convert(source, "csv", work)
    assert error.value.code == "malformed_csv"


def test_semicolon_and_bom_sources_convert(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes("﻿region;amount\nNorth;1.5\nSouth;2\n".encode())
    work = tmp_path / "work"
    work.mkdir()
    result = DuckDBColumnarConverter(memory_limit_mb=128).convert(source, "csv;s", work)
    assert result.headers == ("region", "amount")
    assert result.profile["columns"][1]["type"] == "decimal"
