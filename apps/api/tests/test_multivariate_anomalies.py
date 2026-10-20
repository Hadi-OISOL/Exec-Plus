"""Use case: Verifies exact multivariate scoring independently with NumPy/SciPy.

What it does: Checks reference-only fit, scaling invariance, thresholds, resource
limits and labelled synthetic precision/recall without a customer-quality claim.
"""

from copy import deepcopy
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pytest
from scipy.spatial.distance import mahalanobis

from execplus.domain.ingestion import IngestionError
from execplus.domain.multivariate_anomalies import METHOD, detect_multivariate


def inputs(dimensions=2, count=60):
    raw = dict(
        kind="robust_distribution",
        model=METHOD,
        metrics=[f"m{i}" for i in range(dimensions)],
        identifier_column="id",
        cohort_column="group",
        reference_label="earlier",
        comparison_label="later",
        threshold="9",
    )
    rows = [
        [
            str(i),
            "earlier" if i < count else "later",
            *[Decimal((i * (j * 8 + 3) + i * i * (j + 1)) % 41) for j in range(dimensions)],
        ]
        for i in range(count + 10)
    ]
    return raw, rows


def fraction(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


@pytest.mark.parametrize("dimensions", [2, 3, 4])
def test_scipy_independent_covariance_oracle(dimensions):
    raw, rows = inputs(dimensions)
    result = detect_multivariate(raw, rows)
    reference = np.array([list(map(float, row[2:])) for row in rows[:60]])
    inv = np.linalg.inv(np.cov(reference, rowvar=False, ddof=1))
    center = reference.mean(axis=0)
    for row, saved in zip(rows[60:], result["records"][60:], strict=True):
        expected = mahalanobis(list(map(float, row[2:])), center, inv) ** 2
        assert float(fraction(saved["squared_distance"])) == pytest.approx(
            expected, rel=1e-11, abs=1e-11
        )
        assert saved["flagged"] == (expected > 9)
    assert all(
        row["squared_distance"] is None and row["flagged"] is None for row in result["records"][:60]
    )


def test_comparison_values_never_fit_reference_and_threshold_is_strict():
    raw, rows = inputs()
    first = detect_multivariate(raw, rows)
    changed = deepcopy(rows)
    changed[-1][2] = Decimal("1e30")
    other = detect_multivariate(raw, changed)
    assert first["reference"] == other["reference"]
    assert first["records"][:-1] == other["records"][:-1]
    distance = fraction(first["records"][60]["squared_distance"])
    # A terminating exact threshold from a diagonal reference has an exact equality check.
    reference = [
        [str(i), "earlier", Decimal((-1, 1)[i % 2]), Decimal((-1, 1)[(i // 2) % 2])]
        for i in range(32)
    ]
    rows = [*reference, ["x", "later", Decimal(4), Decimal(0)]]
    out = detect_multivariate({**raw, "threshold": "15.5"}, rows)
    assert fraction(out["records"][-1]["squared_distance"]) == Fraction("15.5")
    assert out["records"][-1]["flagged"] is False
    assert distance > 0


def test_shift_unit_scale_and_field_order_invariance():
    raw, rows = inputs()
    original = detect_multivariate(raw, rows)
    shifted = [
        [r[0], r[1], r[3] * Decimal(-100) + Decimal(123), r[2] * Decimal("0.01") - Decimal(5)]
        for r in rows
    ]
    altered = detect_multivariate({**raw, "metrics": list(reversed(raw["metrics"]))}, shifted)
    assert [r["squared_distance"] for r in original["records"]] == [
        r["squared_distance"] for r in altered["records"]
    ]
    assert [r["flagged"] for r in original["records"]] == [r["flagged"] for r in altered["records"]]


@pytest.mark.parametrize(
    "problem",
    [
        "constant",
        "singular",
        "condition",
        "missing",
        "float",
        "duplicate",
        "missing_id",
        "short",
        "too_many_reference",
        "too_many_rows",
        "wrong_group",
    ],
)
def test_invalid_data_is_refused_without_silent_imputation(problem):
    raw, rows = inputs()
    if problem == "constant":
        for row in rows[:60]:
            row[2] = Decimal(1)
    elif problem == "singular":
        for row in rows[:60]:
            row[3] = row[2] * 2
    elif problem == "condition":
        for i, row in enumerate(rows[:60]):
            row[3] = row[2] * 2 + Decimal(i % 2) * Decimal("1e-12")
    elif problem == "missing":
        rows[-1][2] = None
    elif problem == "float":
        rows[-1][2] = 1.1
    elif problem == "duplicate":
        rows[-1][0] = rows[0][0]
    elif problem == "missing_id":
        rows[-1][0] = None
    elif problem == "short":
        rows = rows[:29] + rows[60:]
    elif problem == "too_many_reference":
        raw, rows = inputs(count=501)
    elif problem == "too_many_rows":
        rows = rows * 15
    else:
        rows[-1][1] = "unknown"
    with pytest.raises(IngestionError):
        detect_multivariate(raw, rows)


def test_labelled_extreme_combinations_have_fixture_only_precision_recall():
    raw, rows = inputs()
    for row in rows[60:65]:
        row[2] = Decimal(10000)
    result = detect_multivariate(raw, rows)
    flagged = {r["record_id"] for r in result["findings"]}
    labels = {str(i) for i in range(60, 65)}
    tp, fp, fn = len(flagged & labels), len(flagged - labels), len(labels - flagged)
    assert (tp, fp, fn) == (5, 0, 0)
    assert Fraction(tp, tp + fp) == Fraction(tp, tp + fn) == 1
    assert result["evaluation"]["precision"] is None
    assert result["evaluation"]["calibrated"] is False


def test_largest_allowed_population_remains_complete_and_deterministic():
    raw, rows = inputs(4, 500)
    rows += [
        [str(i), "later", *[Decimal((i * (j + 3)) % 71) for j in range(4)]]
        for i in range(510, 1000)
    ]
    result = detect_multivariate(raw, rows)
    assert result["sample_count"] == 1000 and result["evaluated_records"] == 500
    assert result == detect_multivariate(raw, rows)
