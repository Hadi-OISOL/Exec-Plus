"""Use case: Measures calendar-regressor forecasts against smoothing on seeded synthetic series.

What it does: Generates labelled weekly, yearly, event and non-seasonal series, runs the
advanced-v2 and advanced-v4 engines on identical history and reports untouched-test
mean absolute errors and selection counts. Synthetic results are not customer accuracy.
"""

import random
from datetime import date
from decimal import Decimal
from math import pi, sin
from typing import Any

from execplus.domain.advanced_forecasting import advanced_forecast
from execplus.domain.calendar_regression import CalendarInputs
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, next_period

SEED = 20261024
SEEDS = 10
SCENARIOS: dict[str, dict[str, Any]] = {
    "weekly_undeclared": dict(frequency="daily", length=140, horizon=7, season=None),
    "weekly_declared": dict(frequency="daily", length=140, horizon=7, season=7),
    "yearly_undeclared": dict(frequency="monthly", length=72, horizon=6, season=None),
    "yearly_declared": dict(frequency="monthly", length=72, horizon=6, season=12),
    "weekly_with_events": dict(frequency="daily", length=140, horizon=7, season=7, events=True),
    "no_seasonality": dict(frequency="daily", length=140, horizon=7, season=None, flat=True),
}


def _series(
    name: str, seed: int
) -> tuple[tuple[ForecastPoint, ...], tuple[int, ...], tuple[date, ...]]:
    spec = SCENARIOS[name]
    rng = random.Random(f"{SEED}-{name}-{seed}")
    cycle = 7 if spec["frequency"] == "daily" else 12
    total = spec["length"] + spec["horizon"]
    events = tuple(int(rng.random() < 0.06) for _ in range(total)) if spec.get("events") else ()
    period = date(2020, 1, 6)
    if spec["frequency"] == "monthly":
        period = date(2018, 1, 1)
    periods, points, level = [], [], 100.0
    for index in range(spec["length"]):
        if spec.get("flat"):
            level += rng.gauss(0.0, 2.0)
            value = level
        else:
            value = 100 + 0.2 * index + 15 * sin(2 * pi * index / cycle) + rng.gauss(0.0, 3.0)
            value += 40 * events[index] if events else 0
        points.append(ForecastPoint(period, Decimal(f"{value:.2f}")))
        periods.append(period)
        period = next_period(period, spec["frequency"])
    for _ in range(spec["horizon"]):
        periods.append(period)
        period = next_period(period, spec["frequency"])
    return tuple(points), events, tuple(periods)


def evaluate(name: str, seed: int) -> dict[str, Any]:
    spec = SCENARIOS[name]
    points, events, periods = _series(name, seed)
    request = ForecastRequest(spec["frequency"], spec["horizon"], spec["season"])
    base = advanced_forecast(points, request).to_record()
    calendar = CalendarInputs(periods, events or None)
    extended = advanced_forecast(points, request, calendar=calendar).to_record()
    return dict(
        v2_method=base["method"]["id"],
        v2_test_mae=base["accuracy"]["mae"],
        v4_method=extended["method"]["id"],
        v4_test_mae=extended["accuracy"]["mae"],
        calendar_selected=extended["regressors"]["selected"] == "calendar_regression",
    )


def evaluation_report(
    names: tuple[str, ...] = tuple(SCENARIOS), seeds: int = SEEDS
) -> dict[str, Any]:
    scenarios = {}
    for name in names:
        runs = [evaluate(name, seed) for seed in range(seeds)]
        v2 = sum((Decimal(run["v2_test_mae"]) for run in runs), Decimal(0)) / len(runs)
        v4 = sum((Decimal(run["v4_test_mae"]) for run in runs), Decimal(0)) / len(runs)
        scenarios[name] = dict(
            runs=runs,
            mean_v2_test_mae=format(v2.quantize(Decimal("0.001")), "f"),
            mean_v4_test_mae=format(v4.quantize(Decimal("0.001")), "f"),
            calendar_selected=sum(run["calendar_selected"] for run in runs),
            v4_better=sum(
                Decimal(run["v4_test_mae"]) < Decimal(run["v2_test_mae"]) for run in runs
            ),
            v4_worse=sum(Decimal(run["v4_test_mae"]) > Decimal(run["v2_test_mae"]) for run in runs),
        )
    return dict(
        seed=SEED,
        seeds=seeds,
        design=dict(
            seasonal="100 + 0.2*t + 15*sin(2*pi*t/cycle) + normal noise sd 3",
            events="6% of periods add +40; flags known for history and forecast periods",
            no_seasonality="random walk with normal steps sd 2",
        ),
        scenarios=scenarios,
        limitations=[
            "Synthetic series only; real calendars, holidays and breaks differ.",
            "Each test window is the untouched final holdout of one series.",
        ],
    )
