"""Use case: Proves streamed database exports write the same file as the in-memory import path.

What it does: Compares nested, flat and refused rows against records_to_csv without a database.
"""

import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from execplus.domain.connectors import records_to_csv, write_rows_csv
from execplus.domain.ingestion import IngestionError


def streamed(columns, rows, max_rows=100, max_bytes=1 << 20):
    target = io.BytesIO()
    write_rows_csv(columns, rows, target, max_rows=max_rows, max_bytes=max_bytes)
    return target.getvalue()


def test_nested_and_flat_rows_match_the_in_memory_file_byte_for_byte():
    columns = ["id", "amount", "at", "meta", "tags", "lines"]
    rows = [
        (
            1,
            Decimal("12345678901234.5678"),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            {"tier": "gold", "n": 1.5},
            ["a", "b"],
            [{"x": 1}],
        ),
        (2, Decimal("-0.0001"), None, None, [], [{"x": 2}, {"x": 3}]),
        (3, None, None, {"tier": None, "extra": True}, None, None),
    ]
    legacy = records_to_csv([dict(zip(columns, row, strict=True)) for row in rows])
    assert streamed(columns, rows) == legacy
    flat = [(1, "a,b", Decimal("1.10")), (2, 'quote "x"', None)]
    names = ["id", "text", "n"]
    assert streamed(names, flat) == records_to_csv(
        [dict(zip(names, row, strict=True)) for row in flat]
    )


@pytest.mark.parametrize(
    ("columns", "rows", "limits", "code"),
    [
        (["a", "a"], [(1, 2)], {}, "ambiguous_source_columns"),
        (["a", ""], [(1, 2)], {}, "unnamed_source_columns"),
        (["a"], [], {}, "empty_source"),
        (["a"], [(1,), (2,), (3,)], {"max_rows": 2}, "source_too_large"),
        (["a"], [("x" * 100,)], {"max_bytes": 50}, "source_too_large"),
        (["a"], [(b"\x00",)], {}, "connector_binary_value"),
    ],
)
def test_unsafe_or_oversized_rows_are_refused(columns, rows, limits, code):
    with pytest.raises(IngestionError) as refused:
        streamed(columns, rows, **limits)
    assert refused.value.code == code
