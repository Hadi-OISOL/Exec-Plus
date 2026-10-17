"""Use case: Independently verifies trailing references, chronology and detection limits.

What it does: Exercises exact thresholds, same-season comparisons and dirty inputs,
and reports fixed labelled fixture accuracy without generalizing it to user data.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from statistics import median

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.rolling_anomalies import RollingRequest, detect_rolling
from test_temporal_anomalies import series


def request(points, start=20, **kwargs):
    return RollingRequest("daily", points[start].period, **kwargs)


def test_independent_median_mad_and_strict_past_only_reference():
    points = series([(i * 7) % 19 for i in range(80)])
    result = detect_rolling(points, request(points))
    for index, row in enumerate(result["history"][20:], 20):
        values = [Fraction(p.actual) for p in points[index - 20 : index]]
        center = median(values)
        mad = median([abs(v - center) for v in values])
        distance = abs(Fraction(points[index].actual) - center)
        assert Fraction(row["expected"]) == center
        assert Fraction(row["reference"]["mad"]) == mad
        assert row["flagged"] == (Fraction("0.67448975") * distance > Fraction("3.5") * mad)
        assert row["reference"]["end"] < row["period"]
    changed = (*points[:40], replace(points[40], actual=Decimal(9999)), *points[41:])
    altered = detect_rolling(changed, request(points))
    assert altered["history"][:40] == result["history"][:40]
    assert altered["history"][40]["reference"] == result["history"][40]["reference"]
    assert detect_rolling(points[:50], request(points))["history"] == result["history"][:50]


@pytest.mark.parametrize("frequency,lag", [("daily", 7), ("monthly", 12)])
def test_matching_seasonal_phases_do_not_compare_unlike_periods(frequency, lag):
    points = series([i % lag * 100 for i in range(20 * lag + 15)], frequency)
    value = detect_rolling(points, RollingRequest(frequency, points[20 * lag].period, 20, lag))
    assert value["findings"] == []
    for row in value["history"][20 * lag :]:
        assert Decimal(row["actual"]) == Decimal(row["expected"])
        assert row["reference"]["step"] == lag


def test_constant_iqr_materiality_and_fixed_labelled_precision_recall():
    points = series([10] * 20 + [10, 11, 20, 10, 10])
    value = detect_rolling(points, request(points, materiality="2"))
    flagged = {i for i, row in enumerate(value["history"]) if row["flagged"]}
    labels = {22}
    tp, fp, fn = len(flagged & labels), len(flagged - labels), len(labels - flagged)
    assert (tp, fp, fn) == (1, 0, 0)
    assert Fraction(tp, tp + fp) == Fraction(tp, tp + fn) == 1
    assert value["evaluation"]["precision"] is None
    assert value["history"][22]["reference"]["scale_method"] == "constant_reference"
    points = series([-2] * 6 + [0] * 11 + [2] * 3 + [-9, 7, 8])
    value = detect_rolling(points, request(points))
    assert value["history"][20]["reference"]["scale_method"] == "iqr"
    assert value["history"][20]["flagged"] is False


def test_exact_precision_and_context_independence():
    points = series(["1.00000000000000000000000000000000000001"] * 20 + [2, 1, 1])
    expected = detect_rolling(points, request(points))
    with localcontext() as context:
        context.prec = 4
        assert detect_rolling(points, request(points)) == expected
    assert Decimal(expected["history"][20]["expected"]) == Decimal(
        "1.00000000000000000000000000000000000001"
    )


@pytest.mark.parametrize(
    "changes",
    [
        dict(reference_window=19),
        dict(reference_window=121),
        dict(reference_window=True),
        dict(season_length=2),
        dict(season_length=True),
        dict(threshold="2"),
        dict(threshold="11"),
        dict(threshold=3.5),
        dict(materiality="-1"),
        dict(evaluation_start=date(2020, 1, 20)),
        dict(evaluation_start=date(2020, 1, 24)),
        dict(evaluation_start="2020-01-21"),
        dict(frequency="weekly"),
    ],
)
def test_invalid_requests_refuse(changes):
    points = series(range(25))
    with pytest.raises(IngestionError):
        detect_rolling(points, replace(request(points), **changes))


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "incomplete", "float", "nan", "monthly_day"]
)
def test_invalid_observations_refuse_without_imputation(mutation):
    points = list(series(range(25)))
    if mutation == "missing":
        del points[4]
    elif mutation == "duplicate":
        points[4] = points[3]
    elif mutation == "incomplete":
        points[4] = replace(points[4], complete=False)
    elif mutation == "float":
        points[4] = replace(points[4], actual=1.2)
    elif mutation == "nan":
        points[4] = replace(points[4], actual=Decimal("NaN"))
    req = request(points)
    if mutation == "monthly_day":
        req = replace(req, frequency="monthly")
    with pytest.raises(IngestionError):
        detect_rolling(tuple(points), req)


def test_constant_shift_adapts_and_does_not_claim_all_changed_points_detected():
    points = series([10] * 20 + [100] * 40)
    result = detect_rolling(points, request(points))
    flags = {i for i, row in enumerate(result["history"]) if row["flagged"]}
    assert flags == set(range(20, 25))
    assert len(flags) / 40 == 0.125
    assert "hide later" in " ".join(result["limitations"])
