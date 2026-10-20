"""Reported conversations must highlight the answer, while old narratives remain immutable."""

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from execplus.application.services.insight_presentation import (
    build_insight_packet,
    display_number,
)
from execplus.application.services.response_synthesis import build_fact_packet
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer
from execplus.domain.response_synthesis import render_selection, validate_saved_narrative


def grouped(rows):
    line = CalculationLineage(
        uuid4(),
        uuid4(),
        uuid4(),
        "Crop observations",
        100,
        "*",
        "count",
        ("Region",),
        ("Season eq 'Rabi'",),
        "SELECT 1",
    )
    return QueryResult(line.query_id, ("Region", "__value"), tuple(rows), 100), line


def test_highest_group_is_not_lost_outside_alphabetic_preview():
    data = grouped([("Central", 5), ("East", 7), ("North", 7), ("South", 10), ("West", 7)])
    packet = build_insight_packet(data)
    result = render_selection(packet)
    assert result["version"] == "verified-narrative-v2"
    first = result["segments"][0]["text"]
    assert "South" in first and "10 records" in first and "highest" in first
    assert "__value" not in str(result)
    assert any("Season eq 'Rabi'" in s["text"] for s in result["segments"])
    assert validate_saved_narrative(packet, result)


def test_exact_ranking_ties_missing_negative_and_large_numbers():
    data = grouped(
        [
            ("a", Decimal("9007199254740993.000001")),
            ("b", Decimal("9007199254740993.000002")),
            ("c", None),
            ("d", Decimal("-1")),
            ("e", Decimal("9007199254740993.000002")),
        ]
    )
    text = render_selection(build_insight_packet(data))["segments"][0]["text"]
    assert "Region: b" in text and "Region: e" in text and "Region: a" not in text
    assert "share" in text
    assert data[0].rows[0][1] == Decimal("9007199254740993.000001")


def test_old_narrative_reopens_without_using_new_wording():
    data = grouped([("South", 10)])
    legacy = build_fact_packet(data)
    saved = render_selection(legacy)
    modern = build_insight_packet(data)
    assert validate_saved_narrative(legacy, saved)
    assert not validate_saved_narrative(modern, saved)
    tampered = {**saved, "version": "verified-narrative-v2"}
    assert not validate_saved_narrative(modern, tampered)


def test_display_rounding_preserves_tiny_values_and_receipt():
    assert display_number(Decimal("1741.469130434783")) == "1,741.47"
    assert display_number(Decimal("0.000003")) == "0.000003"
    assert display_number(Decimal("639.770000000000")) == "639.77"
    line = replace(grouped([])[1], aggregation="avg", metric="Rainfall_mm", grouping=())
    answer = VerifiedMetricAnswer("Rainfall_mm", Decimal("1741.469130434783"), line)
    packet = build_insight_packet(answer, units={str(line.query_id): "mm"})
    text = str(render_selection(packet))
    assert "Rainfall mm" in text and "1,741.47 mm" in text and "rounded" in text
    assert answer.value == Decimal("1741.469130434783")


def test_no_value_and_mismatched_evidence_fail_safely():
    data = grouped([("Central", None)])
    assert "No nonmissing" in str(render_selection(build_insight_packet(data)))
    assert build_insight_packet((replace(data[0], query_id=uuid4()), data[1])) is None


def test_mixed_currency_groups_are_not_ranked_without_common_unit():
    data = grouped([("USD", Decimal("100")), ("JPY", Decimal("10000"))])
    line = replace(data[1], aggregation="sum", metric="revenue", grouping=("currency",))
    result = replace(data[0], columns=("currency", "__value"))
    text = str(render_selection(build_insight_packet((result, line))))
    assert "highest" not in text and "common confirmed unit" in text
    assert "highest" in str(
        render_selection(build_insight_packet((result, line), units={str(line.query_id): "USD"}))
    )
