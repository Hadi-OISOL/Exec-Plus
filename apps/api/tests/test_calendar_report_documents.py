"""Use case: Checks exact calendar evidence in portable analytical reports.

What it does: Independently verifies unchanged periods, rational distances,
missing-reference gaps and public policy redaction without new calculations.
"""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from execplus.application.services.analysis_report_documents import build_analysis_report
from execplus.domain.distribution_drift import DriftRequest, compare_drift
from execplus.domain.temporal_anomalies import (
    TemporalAnomalyRequest,
    TemporalPoint,
    detect_seasonal,
)
from test_analysis_report_documents import NOW, decision, table, text


def points(values, offset=0):
    return tuple(
        TemporalPoint(date(2020, 1, 1) + timedelta(days=index + offset), Decimal(value))
        for index, value in enumerate(values)
    )


def test_seasonal_report_preserves_every_phase_and_null_reference_without_recalculating():
    result = detect_seasonal(
        points([str(10 + (i % 7) * 20 + (100 if i == 28 else 0)) for i in range(49)]),
        TemporalAnomalyRequest("daily", 7, date(2020, 1, 28)),
    )
    record = decision(result, {"metric": "metric"})
    original = deepcopy(record)
    content = build_analysis_report("anomaly", record, NOW)
    assert record == original
    history = table(content, "Every chronological period and seasonal reference")
    assert len(history.rows) == 49
    assert history.columns == tuple(result["history"][0])
    assert history.rows[28][history.columns.index("actual")] == "110"
    assert history.rows[28][history.columns.index("expected")] == "10"
    assert content.charts[0].series[1].values[:28] == (None,) * 28
    assert content.charts[0].series[0].values == tuple(
        str(10 + (i % 7) * 20 + (100 if i == 28 else 0)) for i in range(49)
    )
    assert "2020-01-28" in content.charts[0].notes[0]
    assert "not a future forecast" in content.charts[0].notes[0]
    assert "not probabilities" in text(content)


def test_drift_report_keeps_nonterminating_fraction_and_two_disjoint_observed_series():
    result = compare_drift(
        points(["0"] * 8), points(["0"] * 8 + ["3"], 20), DriftRequest("daily", "0.1", "0")
    )
    record = decision(result, {"metric": "metric"})
    original = deepcopy(record)
    content = build_analysis_report("anomaly", record, NOW)
    assert record == original
    distances = table(content, "Exact distribution distances")
    assert distances.rows[0][1:] == ("1", "9", "0.1111111111111111111111111111", False)
    assert distances.rows[1][1:] == ("1", "3", "0.3333333333333333333333333333", False)
    assert len(table(content, "Every period in both declared windows").rows) == 17
    assert len(table(content, "Exact empirical distribution and distance contributions").rows) == 2
    assert content.charts[0].labels == tuple(row["period"] for row in result["observations"])
    assert content.charts[0].series[0].values == ("0",) * 8 + (None,) * 9
    assert content.charts[0].series[1].values == (None,) * 8 + ("0",) * 8 + ("3",)
    assert "not filled or joined" in content.charts[0].notes[0]


def test_calendar_report_redacts_original_fingerprints_without_changing_private_receipt():
    result = compare_drift(
        points(["0"] * 8), points(["1"] * 8, 8), DriftRequest("daily", "0.2", "0")
    )
    record = decision(result, {"metric": "metric"})
    record["run"]["evidence"]["sources"][0] = dict(
        record["run"]["evidence"]["sources"][0], access_restricted="true"
    )
    original = deepcopy(record)
    content = build_analysis_report("anomaly", record, NOW)
    assert record == original
    assert "withheld_for_restricted_access" in text(content)
    assert "a" * 64 not in text(content)
    assert "b" * 64 not in text(content)
