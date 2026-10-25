"""Use case: Checks the fixed-seed sample and exact helpers behind big-file row features.

What it does: Pins the sampling method, checks Parquet value/missing/position helpers,
the exact-totals query grammar, exact pattern totals against the row path, and the
columnar branches of governed checks and label lookups without external services.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest

from execplus.application.services.intent_router import _label_table, _short_labels
from execplus.domain import sampling
from execplus.domain.columnar import ColumnarManifest, ColumnarTable
from execplus.domain.errors import UnsafeQueryError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult, WorkspaceScope
from execplus.domain.patterns import pattern_plan, pattern_request, pattern_result
from execplus.domain.understanding import _has_blank, _unit_labels
from execplus.infrastructure.columnar.store import S3ColumnarStore
from execplus.infrastructure.file_parser import StructuredFileParser
from execplus.infrastructure.query.validation import validated_query
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics
from test_patterns import prepared


def test_sample_positions_are_pinned_uniform_and_bounded():
    assert sampling.sample_positions(1000, 5) == (246, 339, 344, 380, 929)
    positions = sampling.sample_positions(300_000, 10_000)
    assert len(set(positions)) == 10_000 and list(positions) == sorted(positions)
    assert positions[0] >= 0 and positions[-1] < 300_000
    assert sum(position < 150_000 for position in positions) in range(4_700, 5_300)
    assert sampling.sample_positions(7, 10) == tuple(range(7))
    assert sampling.parse_spec(sampling.spec(10_000)) == (sampling.SEED, 10_000)
    with pytest.raises(IngestionError):
        sampling.parse_spec("reservoir/1/10")
    assert "sample of 10,000 of 300,000 rows" in sampling.label(10_000, 300_000)


@pytest.fixture
def parquet(tmp_path):
    path = tmp_path / "snapshot.parquet"
    duckdb.connect().execute(
        f"""COPY (SELECT CASE WHEN range % 4 = 0 THEN 'b' ELSE 'a' END AS label,
        CASE WHEN range % 5 = 0 THEN NULL ELSE 'USD' END AS currency,
        (range / 100)::DECIMAL(18, 2) AS amount FROM range(1000)) TO '{path}'"""
    )
    return str(path)


def test_parquet_helpers_are_exact_over_every_row(parquet):
    store = S3ColumnarStore(None, "", Path("."), 1)
    assert store.values(parquet, "label", 10) == ("b", "a")
    assert store.values(parquet, "label", 1) == ("b",)
    assert store.missing(parquet, "currency") == 200
    assert store.missing(parquet, "label") == 0
    assert store.rows_at(parquet, (0, 1, 999)) == (
        ("b", "", "0"),
        ("a", "USD", "0.01"),
        ("a", "USD", "9.99"),
    )
    table = ColumnarTable(
        ("label", "currency", "amount"),
        ColumnarManifest("key", "sha", 1, 1000, {}),
        lambda: parquet,
        lambda: pytest.fail("big tables must not materialize rows"),
        reader=store,
    )
    assert table.sample(3).rows == store.rows_at(parquet, sampling.sample_positions(1000, 3))
    assert _has_blank(table, "currency") and not _has_blank(table, "label")
    assert _unit_labels(table, "currency") == {"usd", ""}
    assert _short_labels(table, "label") == ("b", "a")
    headers, rows = _label_table(table, ("label", "missing"))
    assert headers == ("label",) and set(rows) == {("b",), ("a",)}


def test_exact_totals_grammar_allows_only_plain_counts_and_sums():
    validated_query(
        'SELECT "g", COUNT(*), COUNT("m"), SUM("m") FROM "dataset" WHERE "m" > ? '
        'GROUP BY "g" ORDER BY "g" LIMIT 100000',
        {"dataset"},
        1,
    )
    for sql in (
        'SELECT SUM("a"), AVG("b") FROM "dataset" LIMIT 5',
        'SELECT SUM("a" * "b"), SUM("a") FROM "dataset" LIMIT 5',
        'SELECT COUNT(DISTINCT "a"), SUM("a") FROM "dataset" LIMIT 5',
    ):
        with pytest.raises(UnsafeQueryError):
            validated_query(sql, {"dataset"}, 0)


def test_exact_totals_reproduce_the_row_path_group_means_and_counts():
    headers = ["group", "kind", "amount", "reading"]
    rows = [
        (
            ("A", "B", "C")[index % 3],
            ("x", "y")[index % 2],
            Decimal(f"{(index % 3) * 10 + index % 7}.{index % 100:02d}"),
            Decimal(index % 11),
        )
        for index in range(300)
    ]
    rows[5] = (rows[5][0], rows[5][1], None, rows[5][3])
    context, table = prepared(headers, rows)
    request = pattern_request(context, table)
    engine = ScipyPatternStatistics()
    positions = [headers.index(name) for name in request["columns"]]
    value = QueryResult(
        uuid4(),
        tuple(request["columns"]),
        tuple(tuple(row[index] for index in positions) for row in rows),
        len(rows),
    )
    legacy = pattern_result(
        value, request, engine.engine_version, engine.correlations, engine.categorical_association
    )
    sampled = {**request, "sample": dict(spec=sampling.spec(10_000), source_rows=len(rows))}
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset())
    plan = pattern_plan(scope, uuid4(), context.view, sampled, totals=True)
    connection = duckdb.connect()
    connection.execute(
        'CREATE TABLE "dataset" ("group" VARCHAR, "kind" VARCHAR, '
        '"amount" DECIMAL(38, 12), "reading" DECIMAL(38, 12))'
    )
    connection.executemany('INSERT INTO "dataset" VALUES (?, ?, ?, ?)', rows)
    cursor = connection.execute(plan.sql, list(plan.params))
    totals = QueryResult(
        uuid4(), tuple(item[0] for item in cursor.description), tuple(cursor.fetchall()), 300
    )
    with pytest.raises(IngestionError):
        pattern_result(
            value,
            sampled,
            engine.engine_version,
            engine.correlations,
            engine.categorical_association,
        )
    exact = pattern_result(
        value,
        sampled,
        engine.engine_version,
        engine.correlations,
        engine.categorical_association,
        totals,
    )

    def by_kind(result, kind):
        return {
            tuple(item["columns"]): item
            for item in result["findings"] + result["exploratory"]
            if item["type"] == kind
        }

    for key, item in by_kind(legacy, "group_difference").items():
        match = by_kind(exact, "group_difference")[key]
        assert match["chart"]["points"] == item["chart"]["points"]
        assert match["support"] == item["support"] and match["score"] == item["score"]
    for key, item in by_kind(legacy, "category_association").items():
        match = by_kind(exact, "category_association")[key]
        assert match["chart"] == item["chart"] and match["score"] == item["score"]
    assert exact["coverage"]["sample"]["exact_matching_rows"] == 300
    assert any("sample of 300 of 300 rows" in text for text in exact["limitations"])


def test_raw_text_sample_keeps_exact_source_strings(tmp_path):
    content = "name,amount\n" + "".join(f" item {index} ,{index}.50\n" for index in range(50))
    parser = StructuredFileParser(extension_directory=tmp_path)
    table = parser.read_sample(BytesIO(content.encode()), "r:csv", (0, 7, 49), 50)
    assert table.headers == ("name", "amount")
    assert table.rows == ((" item 0 ", "0.50"), (" item 7 ", "7.50"), (" item 49 ", "49.50"))
    with pytest.raises(IngestionError):
        parser.read_sample(BytesIO(content.encode()), "r:csv", (0,), 51)
