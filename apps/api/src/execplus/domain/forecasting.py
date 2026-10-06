"""Use case: Produces bounded basic forecasts from verified complete-period actuals.

What it does: Separates method selection from holdout scoring and preserves exact source values.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import pairwise
from typing import Any, cast

from execplus.domain.ingestion import IngestionError

VERSION = "forecast-v1"
MAX_HISTORY = 1200
HORIZON_LIMITS = {"daily": 30, "monthly": 12}
MIN_HISTORY = {"daily": 28, "monthly": 12}
MIN_TRAINING = {"daily": 14, "monthly": 6}
MIN_HOLDOUT = {"daily": 4, "monthly": 3}
SEASON_LENGTHS = {"daily": 7, "monthly": 12}


@dataclass(frozen=True)
class ForecastPoint:
    period: date
    actual: Decimal
    complete: bool = True


@dataclass(frozen=True)
class ForecastRequest:
    frequency: str
    horizon: int
    season_length: int | None = None


@dataclass(frozen=True)
class ForecastResult:
    serialized: str

    def to_record(self) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.serialized)
        return result


def _invalid(code: str, message: str) -> IngestionError:
    return IngestionError(code, message, 422)


def next_period(period: date, frequency: str) -> date:
    try:
        if frequency == "daily":
            return period + timedelta(days=1)
        if frequency == "monthly":
            return date(period.year + (period.month == 12), period.month % 12 + 1, 1)
    except (ValueError, OverflowError):
        raise _invalid(
            "forecast_date_range", "Forecast dates exceed the supported calendar."
        ) from None
    raise _invalid("forecast_frequency", "Choose daily or monthly periods.")


def _number(value: Decimal, estimate: bool = False) -> None:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or len(value.as_tuple().digits) > (128 if estimate else 60)
        or value.adjusted() > (80 if estimate else 50)
        or cast(int, value.as_tuple().exponent) < (-100 if estimate else -38)
    ):
        raise _invalid("forecast_value", "Forecast actuals must be finite bounded decimal values.")


def _estimated(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 18
        context.rounding = ROUND_HALF_EVEN
        return format(+value, "f")


def _request(request: ForecastRequest) -> None:
    if request.frequency not in HORIZON_LIMITS:
        raise _invalid("forecast_frequency", "Choose daily or monthly periods.")
    if (
        type(request.horizon) is not int
        or not 1 <= request.horizon <= HORIZON_LIMITS[request.frequency]
    ):
        raise _invalid("forecast_horizon", "Choose at most thirty days or twelve months ahead.")
    if request.season_length is not None and (
        type(request.season_length) is not int
        or request.season_length != SEASON_LENGTHS[request.frequency]
    ):
        raise _invalid(
            "forecast_season", "Supported seasonal cycles are seven days or twelve months."
        )


def _points(points: tuple[ForecastPoint, ...], frequency: str, contiguous: bool) -> None:
    if len(points) > MAX_HISTORY:
        raise _invalid("forecast_history_limit", "Use at most 1200 aggregated periods.")
    previous: date | None = None
    for point in points:
        if type(point.period) is not date or type(point.complete) is not bool:
            raise _invalid(
                "forecast_period", "Use explicit calendar dates and period completeness."
            )
        if frequency == "monthly" and point.period.day != 1:
            raise _invalid(
                "forecast_period", "Monthly periods must use the first day of the month."
            )
        _number(point.actual)
        if previous is not None and point.period <= previous:
            raise _invalid("forecast_order", "Periods must be unique and sorted chronologically.")
        if contiguous and previous is not None and next_period(previous, frequency) != point.period:
            raise _invalid(
                "forecast_missing_period",
                "History has missing periods. Missing values are not zero.",
            )
        if contiguous and not point.complete:
            raise _invalid("forecast_incomplete_period", "Use only declared complete periods.")
        previous = point.period


def _predict(
    method: str, values: tuple[Decimal, ...], steps: int, window: int
) -> tuple[Decimal, ...]:
    if method == "last_value":
        result = (values[-1],) * steps
    elif method == "recent_mean":
        mean = sum(values[-window:], Decimal(0)) / min(window, len(values))
        result = (mean,) * steps
    elif method == "linear_trend":
        size = len(values)
        center = Decimal(size - 1) / 2
        average = sum(values, Decimal(0)) / size
        covariance = sum(
            ((Decimal(index) - center) * (value - average) for index, value in enumerate(values)),
            Decimal(0),
        )
        variance = sum(((Decimal(index) - center) ** 2 for index in range(size)), Decimal(0))
        slope = covariance / variance
        result = tuple(average + slope * (Decimal(size + step) - center) for step in range(steps))
    elif method == "seasonal_naive":
        result = tuple(values[-window + step % window] for step in range(steps))
    else:
        raise _invalid("forecast_method", "This forecast method is unavailable.")
    return tuple(Decimal(_estimated(value)) for value in result)


def error_metrics(actuals: tuple[Decimal, ...], estimates: tuple[Decimal, ...]) -> dict[str, Any]:
    if len(actuals) != len(estimates):
        raise _invalid("forecast_comparison", "Actual and estimate lengths must match.")
    for actual in actuals:
        _number(actual)
    for estimate in estimates:
        _number(estimate, estimate=True)
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        count = len(actuals)
        errors = tuple(
            abs(actual - estimate) for actual, estimate in zip(actuals, estimates, strict=True)
        )
        zero_count = sum(actual == 0 for actual in actuals)
        total_error = sum(errors, Decimal(0))
        total_actual = sum((abs(actual) for actual in actuals), Decimal(0))
        mae = total_error / count if count else None
        rmse = (
            (sum((error * error for error in errors), Decimal(0)) / count).sqrt() if count else None
        )
        wape = total_error / total_actual * 100 if total_actual else None
        mape = (
            sum(
                (error / abs(actual) for actual, error in zip(actuals, errors, strict=True)),
                Decimal(0),
            )
            / count
            * 100
            if count and not zero_count
            else None
        )
        return {
            "count": count,
            "mae": _estimated(mae) if mae is not None else None,
            "rmse": _estimated(rmse) if rmse is not None else None,
            "wape_percent": _estimated(wape) if wape is not None else None,
            "mape_percent": _estimated(mape) if mape is not None else None,
            "mape_count": count - zero_count,
            "zero_actual_count": zero_count,
        }


def _window(points: tuple[ForecastPoint, ...]) -> dict[str, Any]:
    return {
        "start": points[0].period.isoformat(),
        "end": points[-1].period.isoformat(),
        "count": len(points),
    }


def _prediction(period: date, value: Decimal, rmse: Decimal, step: int) -> dict[str, str]:
    width = Decimal(2) * rmse * Decimal(step).sqrt()
    return {
        "period": period.isoformat(),
        "estimate": _estimated(value),
        "lower": _estimated(value - width),
        "upper": _estimated(value + width),
    }


def forecast(points: tuple[ForecastPoint, ...], request: ForecastRequest) -> ForecastResult:
    _request(request)
    _points(points, request.frequency, contiguous=True)
    holdout = max(request.horizon, MIN_HOLDOUT[request.frequency])
    minimum = max(MIN_HISTORY[request.frequency], MIN_TRAINING[request.frequency] + 2 * holdout)
    if len(points) < minimum:
        raise _invalid(
            "forecast_insufficient_history",
            f"This horizon needs at least {minimum} complete {request.frequency} periods "
            "for separate training, validation and testing.",
        )
    training = points[: -2 * holdout]
    validation = points[-2 * holdout : -holdout]
    testing = points[-holdout:]
    recent_window = 7 if request.frequency == "daily" else 3
    methods = [("last_value", 1), ("recent_mean", recent_window), ("linear_trend", 1)]
    limitations = [
        "Estimates and error metrics use 18 significant decimal digits with half-even rounding; "
        "source actuals retain their exact decimal values.",
        "One chronological validation window selects the method; "
        "a later untouched test window measures error. "
        "This is not a sustained accuracy guarantee.",
        "Ranges use twice prior holdout RMSE multiplied by the square root of steps ahead. "
        "They are heuristic ranges, not calibrated confidence intervals.",
        "External events, holidays, causal drivers and changing conditions are not modelled. "
        "Negative estimates are not silently clipped.",
        "MAPE is unavailable when any actual is zero; "
        "WAPE is unavailable when all actuals are zero.",
    ]
    if request.season_length is not None:
        if len(training) >= 2 * request.season_length:
            methods.append(("seasonal_naive", request.season_length))
        else:
            limitations.append(
                "Seasonal naive was excluded: "
                "its initial training window needs two full declared cycles."
            )
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        train_values = tuple(point.actual for point in training)
        validation_actuals = tuple(point.actual for point in validation)
        candidates: list[dict[str, Any]] = []
        selection_errors = []
        for method, window in methods:
            estimates = _predict(method, train_values, holdout, window)
            metrics = error_metrics(validation_actuals, estimates)
            candidates.append(
                {"method": method, "parameters": {"window": window}, "metrics": metrics}
            )
            selection_errors.append(Decimal(metrics["mae"]))
        selected_index = min(
            range(len(methods)), key=lambda index: (selection_errors[index], index)
        )
        selected, selected_window = methods[selected_index]
        validation_rmse = Decimal(candidates[selected_index]["metrics"]["rmse"])
        test_estimates = _predict(
            selected, tuple(point.actual for point in points[:-holdout]), holdout, selected_window
        )
        test_actuals = tuple(point.actual for point in testing)
        accuracy = error_metrics(test_actuals, test_estimates)
        baseline_accuracy = error_metrics(
            test_actuals,
            _predict("last_value", tuple(point.actual for point in points[:-holdout]), holdout, 1),
        )
        backtest = []
        for step, (point, estimate) in enumerate(zip(testing, test_estimates, strict=True), 1):
            backtest.append(
                {
                    **_prediction(point.period, estimate, validation_rmse, step),
                    "actual": format(point.actual, "f"),
                    "error": format(point.actual - estimate, "f"),
                    "absolute_error": format(abs(point.actual - estimate), "f"),
                }
            )
        future_values = _predict(
            selected, tuple(point.actual for point in points), request.horizon, selected_window
        )
        future_rmse = Decimal(accuracy["rmse"])
        predictions = []
        period = points[-1].period
        for step, estimate in enumerate(future_values, 1):
            period = next_period(period, request.frequency)
            predictions.append(_prediction(period, estimate, future_rmse, step))
        if future_rmse == 0:
            limitations.append(
                "The test window had zero observed error, so ranges collapse to the estimate. "
                "Future error can still be nonzero."
            )
        record = {
            "version": VERSION,
            "frequency": request.frequency,
            "horizon": request.horizon,
            "season_length": request.season_length,
            "method": {"id": selected, "version": 1, "parameters": {"window": selected_window}},
            "windows": {
                "training": _window(training),
                "validation": _window(validation),
                "test": _window(testing),
                "test_training": _window(points[:-holdout]),
                "forecast_training": _window(points),
            },
            "selection": {
                "criterion": "validation_mae",
                "tie_break": "candidate_order",
                "candidates": candidates,
            },
            "history": [
                {"period": point.period.isoformat(), "actual": format(point.actual, "f")}
                for point in points
            ],
            "backtest": backtest,
            "accuracy": accuracy,
            "benchmark": {
                "method": "last_value",
                "accuracy": baseline_accuracy,
                "beats_baseline_mae": Decimal(accuracy["mae"]) < Decimal(baseline_accuracy["mae"]),
                "mae_difference": _estimated(
                    Decimal(baseline_accuracy["mae"]) - Decimal(accuracy["mae"])
                ),
            },
            "predictions": predictions,
            "uncertainty": {
                "method": "holdout_rmse_sqrt_horizon",
                "label": "Heuristic error range; no guaranteed coverage",
                "coverage_guaranteed": False,
                "backtest_error_source": "validation",
                "future_error_source": "test",
                "backtest_coverage": {
                    "inside": sum(
                        Decimal(row["lower"]) <= Decimal(row["actual"]) <= Decimal(row["upper"])
                        for row in backtest
                    ),
                    "count": len(backtest),
                    "label": "Observed holdout coverage only; not promised future coverage",
                },
            },
            "limitations": limitations,
        }
    return ForecastResult(
        json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )


def compare_forecast(record: dict[str, Any], actuals: tuple[ForecastPoint, ...]) -> dict[str, Any]:
    try:
        if record["version"] != VERSION:
            raise ValueError
        request = ForecastRequest(record["frequency"], record["horizon"], record["season_length"])
        _request(request)
        predictions = record["predictions"]
        if not isinstance(predictions, list) or len(predictions) != request.horizon:
            raise ValueError
        dates = tuple(date.fromisoformat(row["period"]) for row in predictions)
        if any(next_period(left, request.frequency) != right for left, right in pairwise(dates)):
            raise ValueError
        if any(
            not isinstance(row[key], str)
            for row in predictions
            for key in ("estimate", "lower", "upper")
        ):
            raise ValueError
        values = tuple(Decimal(row["estimate"]) for row in predictions)
        for row, value in zip(predictions, values, strict=True):
            _number(value, estimate=True)
            lower, upper = Decimal(row["lower"]), Decimal(row["upper"])
            _number(lower, estimate=True)
            _number(upper, estimate=True)
            if not lower <= value <= upper:
                raise ValueError
    except (KeyError, ValueError, TypeError, ArithmeticError):
        raise _invalid("forecast_record", "The saved forecast cannot be compared safely.") from None
    _points(actuals, request.frequency, contiguous=False)
    by_period = {point.period: point for point in actuals}
    observed = []
    estimated = []
    rows = []
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        for prediction, period, value in zip(predictions, dates, values, strict=True):
            point = by_period.get(period)
            complete = point is not None and point.complete
            actual = point.actual if point is not None and complete else None
            error = actual - value if actual is not None else None
            rows.append(
                {
                    **prediction,
                    "actual": format(actual, "f") if actual is not None else None,
                    "error": format(error, "f") if error is not None else None,
                    "absolute_error": format(abs(error), "f") if error is not None else None,
                    "status": "observed" if complete else "pending",
                    "pending_reason": None
                    if complete
                    else "incomplete_period"
                    if point
                    else "not_observed",
                }
            )
            if actual is not None:
                observed.append(actual)
                estimated.append(value)
    return {
        "rows": rows,
        "metrics": error_metrics(tuple(observed), tuple(estimated)),
        "observed_count": len(observed),
        "pending_count": len(rows) - len(observed),
    }
