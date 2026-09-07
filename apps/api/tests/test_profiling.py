"""Use case: Proves deterministic metadata, quality scoring and recipe semantics.

What it does: Uses fixed synthetic fixtures and independent expected outputs for CSV and Excel.
"""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import Workbook

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import (
    ALGORITHM,
    Revision,
    TableData,
    cell_type,
    profile,
    reconstruct,
    transform,
)
from execplus.domain.samples import SAMPLES, sample_csv
from execplus.infrastructure.file_parser import StructuredFileParser


def step(**values):
    return {"trim": False, "drop_duplicates": False, "drop_missing": False, "mapping": {}, **values}


def test_quality_fixture_has_exact_counts_score_and_explanations():
    table = TableData(
        ("sale_date", "amount", "sku"),
        (
            ("2026-01-01", "10", "001"),
            ("2026-01-01", "10", "001"),
            ("2026-02-30", "bad", "002"),
            ("", "30", "003"),
        ),
    )
    result = profile(table)
    assert result == profile(table)
    assert result["quality_score"] == "90.00"
    checks = {check["code"]: check for check in result["quality_checks"]}
    assert {name: item["count"] for name, item in checks.items()} == {
        "missing_values": 1,
        "duplicate_rows": 1,
        "type_conflicts": 1,
        "invalid_dates": 1,
        "unsupported_structures": 0,
    }
    assert all(len(item["explanation"]) > 30 for item in checks.values())
    date, amount, sku = result["columns"]
    assert date["type"] == "date" and date["date_min"] == date["date_max"] == "2026-01-01"
    assert date["role"] == "dimension" and date["semantic_tags"] == ["date"]
    assert amount["type"] == "integer" and amount["role"] == "metric"
    assert amount["semantic_tags"] == ["amount"] and amount["type_conflicts"] == 1
    assert sku["type"] == "text" and sku["semantic_tags"] == ["identifier"]
    assert sku["distinct_count"] == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", "empty"),
        (" true ", "boolean"),
        ("001", "text"),
        ("NaN", "text"),
        ("Infinity", "text"),
        ("1.25", "decimal"),
        ("-1", "integer"),
        ("2024-02-29", "date"),
        ("2025-02-29", "invalid_date"),
        ("03/04/2026", "text"),
    ],
)
def test_types_do_not_guess_ambiguous_dates_or_destroy_identifiers(value, expected):
    assert cell_type(value) == expected


def test_recipe_order_reconstruction_and_integrity():
    original = TableData(("label", "amount"), ((" A ", "10"), ("A", "10"), ("B", "")))
    cleaning = step(trim=True, drop_duplicates=True, drop_missing=True, mapping={"amount": "sales"})
    output = transform(original, cleaning)
    assert output == TableData(("label", "sales"), (("A", "10"),))
    assert len(original.rows) == 3 and original.headers == ("label", "amount")
    revision = Revision(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        None,
        ALGORITHM,
        "a" * 64,
        output.checksum(),
        [cleaning],
        profile(output),
        uuid4(),
        datetime.now(timezone.utc),
    )
    assert reconstruct(original, revision) == output
    with pytest.raises(IngestionError, match="integrity"):
        reconstruct(original, replace(revision, output_checksum="b" * 64))
    with pytest.raises(IngestionError, match="version"):
        reconstruct(original, replace(revision, algorithm="future"))


@pytest.mark.parametrize(
    "mapping", [{"unknown": "x"}, {"a": "b"}, {"a": ""}, {"a": "=bad"}, {"a": "B"}, {"a": "x\x00"}]
)
def test_invalid_mapping_is_actionable(mapping):
    with pytest.raises(IngestionError, match=r"Map only|unique"):
        transform(TableData(("a", "b"), (("1", "2"),)), step(mapping=mapping))


def test_empty_output_is_rejected_and_missing_columns_profile():
    table = TableData(("a", "b"), (("1", ""),))
    assert profile(table)["columns"][1]["type"] == "empty"
    with pytest.raises(IngestionError, match="every row"):
        transform(table, step(drop_missing=True))


def test_csv_excel_equivalent_profiles_and_trailing_missing_cells():
    workbook = Workbook()
    workbook.active.append(["date", "amount", "note"])
    workbook.active.append([datetime(2026, 1, 1), 12.5, "ok"])
    workbook.active.append([datetime(2026, 1, 2), 20])
    content = BytesIO()
    workbook.save(content)
    parser = StructuredFileParser()
    parser.parse(
        content, "test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    excel = parser.read_table(content, "xlsx")
    csv = parser.read_table(
        BytesIO(b"date,amount,note\n2026-01-01,12.5,ok\n2026-01-02,20,\n"), "csv"
    )
    assert excel == csv
    assert profile(excel) == profile(csv)


@pytest.mark.parametrize("sample", SAMPLES)
def test_versioned_samples_have_fixed_shapes_and_reproducible_profiles(sample):
    content = sample_csv(sample["id"])
    assert content == sample_csv(sample["id"])
    parser = StructuredFileParser()
    structure = parser.parse(BytesIO(content), sample["id"] + ".csv", "text/csv")
    result = profile(parser.read_table(BytesIO(content), "csv"))
    expected = {"finance-v1": (4, "98.75"), "sales-v1": (3, "93.33"), "inventory-v1": (3, "100.00")}
    assert (structure.row_count, result["quality_score"]) == expected[sample["id"]]
    assert result["column_count"] == 4


def test_no_op_preserves_headers_and_mixed_booleans_are_reported():
    table = TableData((" flag ",), (("true",), ("false",), ("unknown",)))
    assert transform(table, step()) == table
    column = profile(table)["columns"][0]
    assert column["type"] == "boolean" and column["type_conflicts"] == 1


@pytest.mark.parametrize(
    ("sample_id", "checksum"),
    [
        ("finance-v1", "3e17e3ce8a34f074fb4ccc4770c7868c6eb4ee735ba8d9efb4484579f7a56870"),
        ("sales-v1", "4ea37d677be0dc77b8c9cb98ef08933e104a8d3467dfd434e821cba048fc7f0c"),
        ("inventory-v1", "0f6f400e796b6a7046f4dbbc7511c398048cc800f5080c9ee83d7c3e21f9def6"),
    ],
)
def test_sample_version_bytes_are_frozen(sample_id, checksum):
    assert sha256(sample_csv(sample_id)).hexdigest() == checksum
