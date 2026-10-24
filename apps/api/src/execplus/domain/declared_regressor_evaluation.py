"""Use case: Measures holiday and outside-predictor forecasts on seeded synthetic series.

What it does: Generates labelled holiday-closure, predictor-driven and unrelated-predictor
series, runs the advanced-v2, advanced-v4 and advanced-v5 engines on identical history
and reports untouched-test mean absolute errors and selections. Not customer accuracy.
"""

import random
from datetime import date
from decimal import Decimal
from math import pi, sin
from typing import Any

from execplus.domain.advanced_forecasting import advanced_forecast
from execplus.domain.calendar_regression import CalendarInputs
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, next_period
from execplus.domain.pakistan_holidays import holidays as table_holidays

SEED = 20261024
SEEDS = 10
LENGTH = 140
HORIZON = 7
SCENARIOS = (
    "holiday_closures",
    "predictor_driven",
    "predictor_wrong_future",
    "unrelated_predictor",
)


def _series(
    name: str, seed: int
) -> tuple[tuple[ForecastPoint, ...], CalendarInputs, tuple[Decimal, ...]]:
    group = "predictor" if name.startswith("predictor") else name
    rng = random.Random(f"{SEED}-{group}-{seed}")
    total = LENGTH + HORIZON
    periods = [date(2024, 1, 1)]
    while len(periods) < total:
        periods.append(next_period(periods[-1], "daily"))
    fixed = set(table_holidays(periods[0], periods[-1]))
    holidays = tuple(int(day in fixed or rng.random() < 0.05) for day in periods)
    drift = [0.0]
    for _ in range(total - 1):
        drift.append(drift[-1] + rng.gauss(0.0, 1.0))
    noise = [rng.uniform(-5.0, 5.0) for _ in range(total)]
    values = []
    for index in range(total):
        if name == "holiday_closures":
            value = 100 + 0.1 * index + 10 * sin(2 * pi * index / 7) - 35 * holidays[index]
            value += rng.gauss(0.0, 3.0)
        elif name.startswith("predictor"):
            value = 50 + 3 * drift[index] - 2 * noise[index] + rng.gauss(0.0, 2.0)
        else:
            value = 100 + 2 * drift[index] + rng.gauss(0.0, 2.0)
        values.append(value)
    exact = tuple(Decimal(f"{value:.2f}") for value in values)
    points = tuple(
        ForecastPoint(period, value)
        for period, value in zip(periods[:LENGTH], exact[:LENGTH], strict=True)
    )
    future = exact[LENGTH:]
    if name == "holiday_closures":
        return points, CalendarInputs(tuple(periods), holidays=holidays), future
    predictors: tuple[tuple[Decimal, ...], ...] = (
        tuple(Decimal(f"{value:.2f}") for value in drift),
        tuple(Decimal(f"{value:.2f}") for value in noise),
    )
    if name == "predictor_wrong_future":
        error = random.Random(f"{SEED}-future-error-{seed}")
        predictors = tuple(
            (
                *series[:LENGTH],
                *(value + Decimal(f"{error.gauss(0, 3):.2f}") for value in series[LENGTH:]),
            )
            for series in predictors
        )
    if name == "unrelated_predictor":
        unrelated = random.Random(f"{SEED}-unrelated-{seed}")
        predictors = (tuple(Decimal(f"{unrelated.gauss(0, 1):.2f}") for _ in range(total)),)
    names = tuple(f"x{index + 1}" for index in range(len(predictors)))
    inputs = CalendarInputs(tuple(periods), predictors=predictors, predictor_names=names)
    return points, inputs, future


def _future_mae(record: dict[str, Any], future: tuple[Decimal, ...]) -> str:
    errors = [
        abs(actual - Decimal(row["estimate"]))
        for actual, row in zip(future, record["predictions"], strict=True)
    ]
    return format(sum(errors, Decimal(0)) / len(errors), "f")


def evaluate(name: str, seed: int) -> dict[str, Any]:
    points, declared, future = _series(name, seed)
    request = ForecastRequest("daily", HORIZON, 7)
    base = advanced_forecast(points, request).to_record()
    calendar = advanced_forecast(
        points, request, calendar=CalendarInputs(declared.periods)
    ).to_record()
    extended = advanced_forecast(points, request, calendar=declared).to_record()
    return dict(
        v2_test_mae=base["accuracy"]["mae"],
        v4_test_mae=calendar["accuracy"]["mae"],
        v5_test_mae=extended["accuracy"]["mae"],
        v2_future_mae=_future_mae(base, future),
        v4_future_mae=_future_mae(calendar, future),
        v5_future_mae=_future_mae(extended, future),
        v5_method=extended["method"]["id"],
        v5_selected=extended["regressors"]["selected"],
    )


def _mean(runs: list[dict[str, Any]], key: str) -> str:
    total = sum((Decimal(run[key]) for run in runs), Decimal(0)) / len(runs)
    return format(total.quantize(Decimal("0.001")), "f")


def evaluation_report(names: tuple[str, ...] = SCENARIOS, seeds: int = SEEDS) -> dict[str, Any]:
    scenarios = {}
    for name in names:
        runs = [evaluate(name, seed) for seed in range(seeds)]
        scenarios[name] = dict(
            runs=runs,
            mean_v2_test_mae=_mean(runs, "v2_test_mae"),
            mean_v4_test_mae=_mean(runs, "v4_test_mae"),
            mean_v5_test_mae=_mean(runs, "v5_test_mae"),
            mean_v2_future_mae=_mean(runs, "v2_future_mae"),
            mean_v4_future_mae=_mean(runs, "v4_future_mae"),
            mean_v5_future_mae=_mean(runs, "v5_future_mae"),
            declared_selected=sum(run["v5_selected"] == "declared_regressors" for run in runs),
            v5_better_than_v4=sum(
                Decimal(run["v5_test_mae"]) < Decimal(run["v4_test_mae"]) for run in runs
            ),
            v5_worse_than_v4=sum(
                Decimal(run["v5_test_mae"]) > Decimal(run["v4_test_mae"]) for run in runs
            ),
        )
    return dict(
        seed=SEED,
        seeds=seeds,
        design=dict(
            holiday_closures="100 + 0.1t + 10 sin(2 pi t / 7) - 35 on Pakistan fixed-date "
            "holidays and 5% extra declared closure days, normal noise sd 3; 7-day cycle "
            "declared",
            predictor_driven="50 + 3 x1 - 2 x2 + normal noise sd 2; x1 random walk, "
            "x2 uniform(-5, 5); true future predictor values supplied",
            predictor_wrong_future="same as predictor_driven, but each supplied future "
            "predictor value has normal error sd 3",
            unrelated_predictor="random walk 100 + 2 w + noise sd 2 with one unrelated "
            "standard-normal predictor",
        ),
        scenarios=scenarios,
        limitations=[
            "Synthetic series only; real holidays and predictors are noisier and future "
            "predictor values are usually uncertain.",
            "Each test window is the untouched final 7-day holdout of one series; future MAE "
            "scores the 7 forecast periods against generated later actuals.",
        ],
    )
