"""Use case: Checks the fixed prediction-model recipe against independent recomputation.

What it does: Verifies the deterministic split, holdout metrics, baselines, leakage guards,
the regression path and the plain verdict without any language model.
"""

import math
import random
from dataclasses import replace
from uuid import uuid4

import numpy
import pandas
import pytest

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryResult
from execplus.domain.prediction_models import (
    holdout_positions,
    prediction_options,
    prediction_request,
    prediction_result,
)
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import apply_definition, infer_definition
from execplus.infrastructure.statistics.prediction import NumpyPredictionTrainer

TRAINER = NumpyPredictionTrainer()
HEADERS = ["outcome", "visits", "channel", "lead id", "call duration", "spend"]


def dataset(size=400, seed=7, signal=1.2):
    rng = random.Random(seed)
    rows = []
    for index in range(size):
        visits = rng.randint(0, 20)
        channel = rng.choice(["web", "phone", "partner"])
        spend = round(rng.gauss(100, 15), 2)
        score = signal * (visits - 10) / 5 + (0.8 if channel == "partner" else 0) + rng.gauss(0, 1)
        outcome = "yes" if score > 1.0 else "no"
        rows.append((outcome, visits, channel, f"L{index:05d}", rng.randint(1, 900), spend))
    return rows


def prepared(headers, rows, roles=None):
    table = TableData(tuple(headers), tuple(tuple(str(v) for v in row) for row in rows))
    observed = profile(table)
    definition = infer_definition(observed)
    definition["grain"] = "lead"
    for column in definition["columns"]:
        column.update((roles or {}).get(column["name"], {}))
        if column["role"] == "metric":
            column["unit"] = column.get("unit") or "units"
    view = apply_definition(dataset_view(observed), definition)
    view = replace(view, sources=({"understanding_id": str(uuid4())},))
    return DescriptionContext("Leads", observed, view, definition, "confirmed"), table


def run(headers, rows, raw, roles=None):
    context, table = prepared(headers, rows, roles)
    request = prediction_request(context, table, {"name": "Model", **raw})
    positions = [headers.index(name) for name in request["columns"]]
    value = QueryResult(
        uuid4(),
        tuple(request["columns"]),
        tuple(tuple(row[i] for i in positions) for row in rows),
        len(rows),
    )
    return request, prediction_result(value, request, TRAINER.fit, TRAINER.engine_version)


def test_holdout_is_fixed_stratified_and_twenty_percent():
    labels = ["yes"] * 50 + ["no"] * 250
    first, second = holdout_positions(labels), holdout_positions(labels)
    assert first == second and list(first) == sorted(set(first))
    assert sum(labels[i] == "yes" for i in first) == 10
    assert sum(labels[i] == "no" for i in first) == 50
    assert holdout_positions(["a"] * 300) != holdout_positions(["a"] * 301)[:60]


def independent_auc(target, score):
    pairs = wins = 0.0
    for p, sp in zip(target, score, strict=True):
        if p != 1:
            continue
        for q, sq in zip(target, score, strict=True):
            if q == 0:
                pairs += 1
                wins += 1.0 if sp > sq else 0.5 if sp == sq else 0.0
    return wins / pairs


def independent_classification(rows):
    frame = pandas.DataFrame(rows, columns=HEADERS)
    labels = frame["outcome"].tolist()
    test = numpy.zeros(len(frame), dtype=bool)
    test[list(holdout_positions([1.0 if v == "yes" else 0.0 for v in labels]))] = True
    y = (frame["outcome"] == "yes").to_numpy(float)
    visits = frame["visits"].astype(float)
    mean, std = visits[~test].mean(), visits[~test].std(ddof=0)
    dummies = pandas.get_dummies(frame["channel"]).astype(float)
    order = sorted(dummies.columns, key=lambda c: (-dummies[c][~test].sum(), c))
    spend = frame["spend"].astype(float)
    x = numpy.column_stack(
        [
            numpy.ones(len(frame)),
            (visits - mean) / std,
            dummies[order].to_numpy(),
            (spend - spend[~test].mean()) / spend[~test].std(ddof=0),
        ]
    )
    w = numpy.zeros(x.shape[1])
    penalty = numpy.eye(x.shape[1])
    penalty[0, 0] = 0
    xt, yt = x[~test], y[~test]
    for _ in range(100):
        p = 1 / (1 + numpy.exp(-xt @ w))
        gradient = xt.T @ (p - yt) + penalty @ w
        hessian = xt.T @ (xt * (p * (1 - p))[:, None]) + penalty
        w -= numpy.linalg.solve(hessian, gradient)
    probability = 1 / (1 + numpy.exp(-x[test] @ w))
    auc = independent_auc(list(y[test]), list(probability))
    accuracy = float(((probability >= 0.5) == (y[test] == 1)).mean())
    majority = 1.0 if yt.mean() > 0.5 else 0.0
    return auc, accuracy, float((y[test] == majority).mean())


def test_classification_metrics_match_independent_recomputation_and_beat_the_guess():
    rows = dataset()
    request, result = run(
        HEADERS, rows, {"target_column": "outcome", "input_columns": ["visits", "channel", "spend"]}
    )
    auc, accuracy, majority = independent_classification(rows)
    assert result["metrics"] == {"auc": f"{auc:.4f}", "accuracy": f"{accuracy:.4f}"}
    assert result["baseline"]["accuracy"] == f"{majority:.4f}"
    assert result["baseline"]["auc"] == "0.5000"
    assert result["positive_label"] == "yes"
    assert result["verdict"]["status"] == "beats_guess"
    assert result["verdict"]["text"].startswith("Beats the simple guess by ")
    assert result["coverage"]["holdout_rows"] == 80
    assert result["coverage"]["training_rows"] == 320
    assert result["method"]["seed"] == 20261027
    assert all(w["label"] == "associated with, not a cause" for w in result["weights"])
    assert result["weights"][0]["input"] == "visits"
    raw = {"target_column": "outcome", "input_columns": request["selected"]}
    assert result == run(HEADERS, rows, raw)[1]


def test_noise_target_is_not_better_than_guessing():
    rng = random.Random(3)
    rows = [(rng.choice(["yes", "no"]), *row[1:]) for row in dataset(seed=11)]
    _, result = run(HEADERS, rows, {"target_column": "outcome", "input_columns": ["spend"]})
    assert result["verdict"]["status"] == "not_useful"
    assert result["verdict"]["text"].startswith("Not better than guessing — don't use it.")


def test_default_inputs_exclude_ids_and_post_outcome_fields_with_reasons():
    request, _ = run(HEADERS, dataset(), {"target_column": "outcome"})
    assert [item["name"] for item in request["inputs"]] == ["visits", "channel", "spend"]
    reasons = {item["column"]: item["reason"] for item in request["exclusions"]}
    assert "acts like an ID" in reasons["lead id"] or "Identifiers" in reasons["lead id"]
    assert "known after the outcome" in reasons["call duration"]


@pytest.mark.parametrize("column", ["call duration", "lead id"])
def test_explicit_leaking_input_is_refused(column):
    with pytest.raises(ClarificationRequiredError, match=column):
        run(HEADERS, dataset(), {"target_column": "outcome", "input_columns": [column, "visits"]})


def test_single_input_that_mirrors_the_target_is_warned():
    rows = [(*row, "won" if row[0] == "yes" else "open") for row in dataset()]
    _, result = run(
        [*HEADERS, "stage"],
        rows,
        {"target_column": "outcome", "input_columns": ["stage", "visits"]},
    )
    assert any(
        w.startswith("stage alone predicts the target almost perfectly") for w in result["warnings"]
    )


def test_regression_path_matches_pandas_and_mean_baseline():
    rng = random.Random(5)
    rows = [
        (round(3 * x + rng.gauss(0, 2), 3), x) for x in (rng.uniform(0, 10) for _ in range(300))
    ]
    request, result = run(
        ["revenue", "ads"],
        rows,
        {"target_column": "revenue"},
        roles={"revenue": {"role": "metric", "currency": "PKR"}},
    )
    frame = pandas.DataFrame(rows, columns=["revenue", "ads"]).astype(float)
    test = numpy.zeros(len(frame), dtype=bool)
    test[list(holdout_positions([0] * len(frame)))] = True
    train, held = frame[~test], frame[test]
    slope = train["revenue"].cov(train["ads"]) / train["ads"].var()
    intercept = train["revenue"].mean() - slope * train["ads"].mean()
    error = held["revenue"] - (intercept + slope * held["ads"])
    r2 = 1 - (error**2).sum() / ((held["revenue"] - held["revenue"].mean()) ** 2).sum()
    guess = (held["revenue"] - train["revenue"].mean()).abs().mean()
    assert request["task"] == "regression"
    assert result["metrics"] == {"mae": f"{error.abs().mean():.4f}", "r2": f"{r2:.4f}"}
    assert result["baseline"]["mae"] == f"{guess:.4f}"
    assert result["verdict"]["status"] == "beats_guess"
    assert "PKR" in result["verdict"]["text"]


def test_unsupported_targets_filters_and_labels_are_refused():
    rows = dataset()
    with pytest.raises(ClarificationRequiredError, match="cannot be predicted"):
        run(HEADERS, rows, {"target_column": "channel"})
    with pytest.raises(IngestionError, match="filters"):
        run(HEADERS, rows, {"target_column": "outcome", "filters": [{"column": "channel"}]})
    with pytest.raises(ClarificationRequiredError, match="not a recorded value"):
        run(HEADERS, rows, {"target_column": "outcome", "positive_label": "maybe"})
    with pytest.raises(ClarificationRequiredError, match="At least 50 rows"):
        run(HEADERS, rows[:40], {"target_column": "outcome"})


def test_options_list_targets_and_input_reasons():
    context, _ = prepared(HEADERS, dataset())
    options = prediction_options(context)
    assert {"name": "outcome", "task": "classification"} in options["targets"]
    assert {"name": "spend", "task": "regression"} in options["targets"]
    reasons = {item["name"]: item["excluded_reason"] for item in options["inputs"]}
    assert reasons["visits"] is None and reasons["call duration"]


def test_sklearn_agrees_when_available():
    sklearn = pytest.importorskip("sklearn")
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, roc_auc_score

    assert sklearn.__version__
    rows = dataset()
    _, result = run(
        HEADERS, rows, {"target_column": "outcome", "input_columns": ["visits", "channel", "spend"]}
    )
    frame = pandas.DataFrame(rows, columns=HEADERS)
    test = numpy.zeros(len(frame), dtype=bool)
    test[list(holdout_positions([1.0 if v == "yes" else 0.0 for v in frame["outcome"]]))] = True
    numeric = frame[["visits", "spend"]].astype(float)
    numeric = (numeric - numeric[~test].mean()) / numeric[~test].std(ddof=0)
    x = pandas.concat([numeric, pandas.get_dummies(frame["channel"]).astype(float)], axis=1)
    y = (frame["outcome"] == "yes").astype(int)
    model = LogisticRegression(C=1.0, tol=1e-10, max_iter=10000).fit(x[~test], y[~test])
    p = model.predict_proba(x[test])[:, 1]
    assert math.isclose(float(result["metrics"]["auc"]), roc_auc_score(y[test], p), abs_tol=1e-4)
    assert math.isclose(
        float(result["metrics"]["accuracy"]), accuracy_score(y[test], p >= 0.5), abs_tol=1e-4
    )
    rng = random.Random(5)
    rows = [
        (round(3 * v + rng.gauss(0, 2), 3), v) for v in (rng.uniform(0, 10) for _ in range(300))
    ]
    _, result = run(
        ["revenue", "ads"],
        rows,
        {"target_column": "revenue"},
        roles={"revenue": {"role": "metric", "currency": "PKR"}},
    )
    frame = pandas.DataFrame(rows, columns=["revenue", "ads"]).astype(float)
    test = numpy.zeros(len(frame), dtype=bool)
    test[list(holdout_positions([0] * len(frame)))] = True
    line = LinearRegression().fit(frame[["ads"]][~test], frame["revenue"][~test])
    predicted = line.predict(frame[["ads"]][test])
    assert result["metrics"] == {
        "mae": f"{mean_absolute_error(frame['revenue'][test], predicted):.4f}",
        "r2": f"{r2_score(frame['revenue'][test], predicted):.4f}",
    }
