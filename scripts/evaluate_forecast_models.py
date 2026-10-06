"""Use case: Evaluates optional statistical libraries outside the product runtime.

What it does: Compares candidates on fictional chronological splits with bounded isolated fits.
"""

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import logging
import math
import multiprocessing
import platform
import random
import time
import warnings
from datetime import date, datetime, timezone
from decimal import Decimal
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from execplus.domain.forecasting import (
    ForecastPoint,
    ForecastRequest,
    error_metrics,
    forecast,
    next_period,
)


def fixtures() -> list[dict[str, Any]]:
    generator = random.Random(404)
    noise = [generator.randrange(-8, 9) for _ in range(120)]
    records: list[tuple[str, str, int, int | None, list[int]]] = [
        ("constant_daily", "daily", 7, None, [100] * 120),
        ("linear_daily", "daily", 7, None, [100 + 2 * index for index in range(120)]),
        (
            "noisy_trend_daily",
            "daily",
            7,
            None,
            [100 + index + noise[index] for index in range(120)],
        ),
        ("weekly_daily", "daily", 7, 7, [20, 30, 15, 60, 30, 5, 10] * 20),
        ("yearly_monthly", "monthly", 6, 12, [10, 40, 20, 70, 35, 95, 40, 30, 75, 20, 50, 5] * 5),
        ("zero_monthly", "monthly", 3, 12, [0, 0, 10, 0, 0, 20] * 8),
        ("late_regime_change", "daily", 7, None, [100 + index for index in range(113)] + [20] * 7),
    ]
    result = []
    for name, frequency, horizon, season, values in records:
        dates = []
        period = date(2020, 1, 1)
        for _ in values:
            dates.append(period.isoformat())
            period = next_period(period, frequency)
        result.append(
            dict(
                name=name,
                frequency=frequency,
                horizon=horizon,
                season_length=season,
                dates=dates,
                values=[str(value) for value in values],
            )
        )
    return result


def _worker(
    connection: Connection,
    model: str,
    parameters: dict[str, Any],
    periods: list[str],
    values: list[str],
    future: list[str],
) -> None:
    logging.disable(logging.CRITICAL)
    start = time.monotonic()
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            if model == "arima":
                module = importlib.import_module("statsmodels.tsa.arima.model")
                instance = module.ARIMA(
                    [float(value) for value in values],
                    order=tuple(parameters["order"]),
                    enforce_stationarity=True,
                    enforce_invertibility=True,
                )
                fitted = instance.fit(method_kwargs={"maxiter": 50})
                if not fitted.mle_retvals.get("converged", False):
                    connection.send({"status": "failed", "code": "not_converged"})
                    return
                estimates = list(fitted.forecast(steps=len(future)))
            else:
                prophet = importlib.import_module("prophet")
                pandas = importlib.import_module("pandas")
                instance = prophet.Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    uncertainty_samples=0,
                    n_changepoints=5,
                )
                if parameters.get("season_length") == 7:
                    instance.add_seasonality(name="weekly", period=7, fourier_order=3)
                elif parameters.get("season_length") == 12:
                    instance.add_seasonality(name="yearly", period=365.25, fourier_order=3)
                instance.fit(
                    pandas.DataFrame(
                        {"ds": pandas.to_datetime(periods), "y": [float(value) for value in values]}
                    ),
                    seed=404,
                    iter=500,
                )
                estimates = list(
                    instance.predict(pandas.DataFrame({"ds": pandas.to_datetime(future)}))["yhat"]
                )
            if not all(math.isfinite(float(value)) for value in estimates):
                raise ValueError("nonfinite")
            connection.send(
                {
                    "status": "complete",
                    "estimates": [format(float(value), ".17g") for value in estimates],
                    "worker_ms": round((time.monotonic() - start) * 1000, 3),
                    "warnings": sorted({type(item.message).__name__ for item in captured}),
                }
            )
    except Exception as error:
        connection.send({"status": "failed", "code": type(error).__name__})
    finally:
        connection.close()


def fit(
    model: str,
    parameters: dict[str, Any],
    fixture: dict[str, Any],
    end: int,
    future: list[str],
    timeout: float,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(writer, model, parameters, fixture["dates"][:end], fixture["values"][:end], future),
    )
    start = time.monotonic()
    process.start()
    writer.close()
    try:
        if not reader.poll(timeout):
            return {
                "status": "timeout",
                "code": "fit_deadline",
                "wall_ms": round((time.monotonic() - start) * 1000, 3),
            }
        try:
            result: dict[str, Any] = reader.recv()
        except EOFError:
            result = {"status": "failed", "code": "worker_exit"}
        result["wall_ms"] = round((time.monotonic() - start) * 1000, 3)
        return result
    finally:
        reader.close()
        process.join(timeout=0.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join()
        process.close()


def evaluate(fixture: dict[str, Any], timeout: float) -> dict[str, Any]:
    points = tuple(
        ForecastPoint(date.fromisoformat(period), Decimal(value))
        for period, value in zip(fixture["dates"], fixture["values"], strict=True)
    )
    start = time.monotonic()
    runtime = forecast(
        points, ForecastRequest(fixture["frequency"], fixture["horizon"], fixture["season_length"])
    ).to_record()
    runtime_ms = round((time.monotonic() - start) * 1000, 3)
    train_count = runtime["windows"]["training"]["count"]
    validation_count = runtime["windows"]["validation"]["count"]
    selection_end = train_count + validation_count
    validation_dates = fixture["dates"][train_count:selection_end]
    test_dates = fixture["dates"][selection_end:]
    experiments = []
    for model, choices in (
        ("arima", [{"order": [1, 1, 0]}, {"order": [0, 1, 1]}]),
        ("prophet", [{"season_length": fixture["season_length"]}]),
    ):
        candidates = []
        for parameters in choices:
            result = fit(model, parameters, fixture, train_count, validation_dates, timeout)
            candidate = {"parameters": parameters, **result}
            if result["status"] == "complete":
                candidate["validation"] = error_metrics(
                    tuple(point.actual for point in points[train_count:selection_end]),
                    tuple(Decimal(value) for value in result["estimates"]),
                )
            candidates.append(candidate)
        completed = [candidate for candidate in candidates if candidate["status"] == "complete"]
        record: dict[str, Any] = {"model": model, "candidates": candidates}
        if completed:
            selected = min(completed, key=lambda candidate: Decimal(candidate["validation"]["mae"]))
            tested = fit(model, selected["parameters"], fixture, selection_end, test_dates, timeout)
            record.update(selected_parameters=selected["parameters"], test=tested)
            if tested["status"] == "complete":
                record["accuracy"] = error_metrics(
                    tuple(point.actual for point in points[selection_end:]),
                    tuple(Decimal(value) for value in tested["estimates"]),
                )
        experiments.append(record)
    return {
        "fixture": fixture["name"],
        "fixture_sha256": hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest(),
        "frequency": fixture["frequency"],
        "rows": len(points),
        "windows": runtime["windows"],
        "runtime": {
            "method": runtime["method"],
            "accuracy": runtime["accuracy"],
            "elapsed_ms": runtime_ms,
        },
        "optional_models": experiments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fit-timeout-seconds", type=float, default=15)
    args = parser.parse_args()
    if not 1 <= args.fit_timeout_seconds <= 60:
        parser.error("Fit timeout must be between one and sixty seconds.")
    if args.output.exists():
        parser.error("Choose a new evidence file; existing reports are retained.")
    versions = {
        name: importlib.metadata.version(name)
        for name in ("statsmodels", "prophet", "cmdstanpy", "numpy", "pandas", "scipy")
    }
    report: dict[str, Any] = {
        "file_use_case": "Measures optional forecast candidates outside the product runtime.",
        "responsibility": "Uses fictional data, separated selection/test splits and bounded fits.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "versions": versions,
        "fit_timeout_seconds": args.fit_timeout_seconds,
        "limitations": [
            "Seven controlled fictional fixtures are not representative customer acceptance.",
            "Each optional fit runs in a fresh process; wall time includes startup and imports.",
            "Optional libraries use floating-point estimation; source actuals remain Decimal.",
            "No model is selected for runtime by this script. "
            "Accuracy is untouched-test MAE/RMSE, not a percentage-accurate claim.",
        ],
        "official_sources": [
            "https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html",
            "https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMAResults.get_forecast.html",
            "https://facebook.github.io/prophet/docs/diagnostics.html",
            "https://facebook.github.io/prophet/docs/uncertainty_intervals.html",
        ],
        "cases": [],
    }
    for fixture in fixtures():
        report["cases"].append(evaluate(fixture, args.fit_timeout_seconds))
        print(f"Evaluated {fixture['name']}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Evidence written to {args.output}")


if __name__ == "__main__":
    main()
