"""Use case: Reviews unusual combinations against an explicitly chosen reference cohort.

What it does: Fits bounded exact reference-only covariance and retains rational
squared distances, record identities and assumptions without calibrated probabilities.
"""

from collections.abc import Sequence
from fractions import Fraction
from typing import Any

from execplus.domain.decision_analysis import checksum, encoded, fail, number
from execplus.domain.distribution_drift import _fraction

METHOD = "reference-mahalanobis-squared-v1"
CALIBRATED_METHOD = "reference-mahalanobis-calibrated-v1"
MAX_BITS = 8192


def is_multivariate(raw: dict[str, Any]) -> bool:
    return raw.get("kind") == "robust_distribution" and raw.get("model") in {
        METHOD,
        CALIBRATED_METHOD,
    }


def bounded(value: Fraction) -> Fraction:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_BITS:
        fail(
            "multivariate_precision", "The exact covariance exceeds the supported precision budget."
        )
    return value


def inverse(matrix: list[list[Fraction]]) -> list[list[Fraction]]:
    size = len(matrix)
    rows = [row[:] + [Fraction(i == j) for j in range(size)] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = next((i for i in range(column, size) if rows[i][column]), None)
        if pivot is None:
            fail(
                "multivariate_singular",
                "The reference measures are redundant; choose independent measures.",
            )
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [bounded(value / divisor) for value in rows[column]]
        for i in range(size):
            if i != column:
                factor = rows[i][column]
                rows[i] = [
                    bounded(a - factor * b) for a, b in zip(rows[i], rows[column], strict=True)
                ]
    return [row[size:] for row in rows]


def detect_multivariate(raw: dict[str, Any], rows: Sequence[Sequence[Any]]) -> dict[str, Any]:
    metrics = raw["metrics"]
    if (
        not isinstance(metrics, list)
        or not 2 <= len(metrics) <= 4
        or len(set(metrics)) != len(metrics)
    ):
        fail("multivariate_measures", "Choose two to four different confirmed measures.")
    reference, comparison = raw["reference_label"], raw["comparison_label"]
    if (
        not all(
            isinstance(label, str) and 1 <= len(label) <= 200 for label in (reference, comparison)
        )
        or reference == comparison
    ):
        fail("multivariate_cohorts", "Choose two different named reference and comparison groups.")
    if not isinstance(raw["threshold"], str):
        fail("multivariate_threshold", "Enter an exact positive squared-distance threshold.")
    threshold = Fraction(number(raw["threshold"]))
    if not 0 < threshold <= 1000000:
        fail(
            "multivariate_threshold",
            "Use a squared-distance threshold greater than zero and at most 1,000,000.",
        )
    if not 1 <= len(rows) <= 1000:
        fail("multivariate_size", "Use at most 1,000 complete rows across the selected groups.")
    seen = set()
    records: list[dict[str, Any]] = []
    values: list[list[Fraction]] = []
    for row in rows:
        if len(row) != len(metrics) + 2 or row[0] is None or isinstance(row[0], (bool, float)):
            fail(
                "multivariate_identity", "Every selected record needs one exact unique identifier."
            )
        identifier = str(row[0])
        if not identifier or len(identifier) > 200 or identifier in seen:
            fail(
                "multivariate_identity",
                "Record identifiers must be present, unique and at most 200 characters.",
            )
        seen.add(identifier)
        if not isinstance(row[1], str) or row[1] not in {reference, comparison}:
            fail(
                "multivariate_cohorts",
                "Use exact text groups from the selected reference and comparison cohorts.",
            )
        if any(isinstance(value, float) for value in row[2:]):
            fail("multivariate_exact", "Use exact decimal measures, not binary floating values.")
        decimals = [number(value) for value in row[2:]]
        values.append([Fraction(value) for value in decimals])
        records.append(
            dict(
                record_id=identifier,
                cohort=row[1],
                values=dict(zip(metrics, [encoded(v) for v in decimals], strict=True)),
            )
        )
    reference_values = [
        v for record, v in zip(records, values, strict=True) if record["cohort"] == reference
    ]
    count, dimensions = len(reference_values), len(metrics)
    if not 30 <= count <= 500 or count == len(rows):
        fail(
            "multivariate_reference_size",
            "Use 30-500 reference records and at least one comparison record.",
        )
    means = [sum((v[j] for v in reference_values), Fraction(0)) / count for j in range(dimensions)]
    scales = [max(abs(v[j] - means[j]) for v in reference_values) for j in range(dimensions)]
    if not all(scales):
        fail(
            "multivariate_constant", "Every reference measure must vary; remove constant measures."
        )
    normalized = [
        [bounded((v[j] - means[j]) / scales[j]) for j in range(dimensions)]
        for v in reference_values
    ]
    covariance = [
        [
            bounded(sum((v[i] * v[j] for v in normalized), Fraction(0)) / (count - 1))
            for j in range(dimensions)
        ]
        for i in range(dimensions)
    ]
    inv = inverse(covariance)
    condition = bounded(
        max(sum(map(abs, row), Fraction(0)) for row in covariance)
        * max(sum(map(abs, row), Fraction(0)) for row in inv)
    )
    if condition > 100000000:
        fail(
            "multivariate_condition",
            "The reference measures are too nearly dependent for a stable comparison.",
        )
    findings = []
    for record, value in zip(records, values, strict=True):
        record.update(squared_distance=None, flagged=None, phase="reference")
        if record["cohort"] == comparison:
            delta = [bounded((value[j] - means[j]) / scales[j]) for j in range(dimensions)]
            distance = bounded(
                sum(
                    (
                        delta[i] * inv[i][j] * delta[j]
                        for i in range(dimensions)
                        for j in range(dimensions)
                    ),
                    Fraction(0),
                )
            )
            if distance < 0:
                fail(
                    "multivariate_covariance",
                    "The reference covariance is not valid for this comparison.",
                )
            record.update(
                squared_distance=_fraction(distance),
                flagged=distance > threshold,
                phase="comparison",
            )
            if record["flagged"]:
                findings.append(
                    dict(
                        id=checksum(dict(method=METHOD, record_id=record["record_id"]))[:24],
                        **record,
                    )
                )
    return dict(
        version="multivariate-anomaly-v1",
        method_version=METHOD,
        metrics=metrics,
        identifier_column=raw["identifier_column"],
        cohort_column=raw["cohort_column"],
        reference_label=reference,
        comparison_label=comparison,
        threshold=_fraction(threshold),
        sample_count=len(rows),
        reference_count=count,
        evaluated_records=len(rows) - count,
        flagged_records=len(findings),
        records=records,
        findings=findings,
        reference=dict(
            means=[_fraction(v) for v in means],
            scales=[_fraction(v) for v in scales],
            normalized_sample_covariance=[[_fraction(v) for v in row] for row in covariance],
            normalized_inverse=[[_fraction(v) for v in row] for row in inv],
            infinity_condition=_fraction(condition),
            maximum_condition="100000000",
            fitted_on="reference_cohort_only",
            covariance_denominator=count - 1,
        ),
        evaluation=dict(labels_supplied=False, precision=None, recall=None, calibrated=False),
        limitations=[
            "Squared Mahalanobis distance describes unusual combinations, not "
            "proven errors, fraud or causes.",
            "Only the selected reference cohort fits the mean and sample "
            "covariance. Comparison values never fit their own reference.",
            "The reference must represent the population you intend to compare. "
            "Contamination, mixed groups and non-elliptical distributions can "
            "hide or exaggerate flags.",
            "Only the two explicitly selected cohorts and governed filters are "
            "included; other rows are outside this analysis.",
            "Different units are normalized using exact reference scales; no "
            "units are added or silently converted.",
            "The user-selected squared-distance threshold is a review rule, not a "
            "chi-square probability or calibrated false-alarm guarantee.",
            "Exact fractions determine flags; decimal displays may be rounded. "
            "Reference rows are fitting evidence, not evaluated alerts.",
            "No time order is inferred from row order. Precision and recall "
            "require independently labelled outcomes; reviews never retrain this "
            "saved result.",
        ],
    )
