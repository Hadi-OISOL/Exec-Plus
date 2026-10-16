"""Use case: Evaluates bounded exponential-smoothing forecasts on regular series.

What it does: Selects fixed registered parameter candidates using three rolling
origins, then scores an untouched holdout. Exact actuals remain separate from
approximate estimates and empirical error ranges. No model/provider is involved.
"""

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import product
from typing import Any

from execplus.domain.forecasting import (
    MAX_HISTORY,
    MIN_HOLDOUT,
    MIN_TRAINING,
    ForecastPoint,
    ForecastRequest,
    ForecastResult,
    _estimated,
    _invalid,
    _number,
    _points,
    _request,
    _window,
    compare_forecast,
    error_metrics,
    next_period,
)
from execplus.domain.forecasting import (
    VERSION as BASIC_VERSION,
)

VERSION = "forecast-v2"
ENGINE = "advanced-v2"
REGISTRY_VERSION = "smoothing-grid-v1"
ROLLING_ORIGINS = 3
MAX_CANDIDATES = 43
MAX_STATE_UPDATES = 160_000
FAMILIES = ("auto", "simple_exponential", "holt", "damped_holt", "holt_winters_additive")
METHOD_CATALOG = (
    {"id": "auto", "label": "Compare all eligible methods", "requires_season": False},
    {"id": "simple_exponential", "label": "Smooth a changing level", "requires_season": False},
    {"id": "holt", "label": "Follow a continuing trend", "requires_season": False},
    {"id": "damped_holt", "label": "Let a trend gradually flatten", "requires_season": False},
    {
        "id": "holt_winters_additive",
        "label": "Model a declared repeating cycle",
        "requires_season": True,
    },
)


@dataclass(frozen=True)
class Candidate:
    method: str
    alpha: str = "0"
    beta: str = "0"
    phi: str = "1"
    gamma: str = "0"
    season: int | None = None

    def parameters(self) -> dict[str, Any]:
        if self.method in {"last_value", "seasonal_naive"}:
            return {"season_length": self.season}
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "phi": self.phi,
            "gamma": self.gamma,
            "season_length": self.season,
            "initialization": (
                "two_cycle_means_detrended_first_cycle"
                if self.season
                else "first_value"
                if self.method == "simple_exponential"
                else "first_value_first_difference"
            ),
        }


def _approximate(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        return Decimal(_estimated(value)).normalize()


def minimum_history(request: ForecastRequest, family: str = "auto") -> int:
    _request(request)
    if family not in FAMILIES:
        raise _invalid("forecast_method", "Choose a registered advanced forecast method.")
    if family == "holt_winters_additive" and request.season_length is None:
        raise _invalid(
            "forecast_season_required", "Declare the repeating cycle for this seasonal method."
        )
    training = MIN_TRAINING[request.frequency]
    if family == "holt_winters_additive":
        training = max(training, 2 * (request.season_length or 0))
    return training + (ROLLING_ORIGINS + 1) * max(request.horizon, MIN_HOLDOUT[request.frequency])


def registered_candidates(
    request: ForecastRequest, family: str, training_count: int
) -> tuple[Candidate, ...]:
    minimum_history(request, family)
    candidates = [Candidate("last_value")]
    seasonal = request.season_length is not None and training_count >= 2 * request.season_length
    if seasonal:
        candidates.append(Candidate("seasonal_naive", season=request.season_length))
    if family in {"auto", "simple_exponential"}:
        candidates.extend(Candidate("simple_exponential", alpha) for alpha in ("0.2", "0.5", "0.8"))
    if family in {"auto", "holt", "damped_holt"}:
        for alpha, beta in product(("0.2", "0.5", "0.8"), ("0.1", "0.3")):
            if family in {"auto", "holt"}:
                candidates.append(Candidate("holt", alpha, beta))
            if family in {"auto", "damped_holt"}:
                candidates.extend(
                    Candidate("damped_holt", alpha, beta, phi) for phi in ("0.8", "0.95")
                )
    if seasonal and family in {"auto", "holt_winters_additive"}:
        for alpha, beta, gamma, phi in product(
            ("0.2", "0.5", "0.8"), ("0.1", "0.3"), ("0.1", "0.3"), ("1", "0.9")
        ):
            if Decimal(gamma) <= 1 - Decimal(alpha):
                candidates.append(
                    Candidate(
                        "holt_winters_additive", alpha, beta, phi, gamma, request.season_length
                    )
                )
    if not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise _invalid(
            "forecast_work_limit", "The candidate registry exceeds its fixed evaluation budget."
        )
    return tuple(candidates)


def predict(candidate: Candidate, values: tuple[Decimal, ...], horizon: int) -> tuple[Decimal, ...]:
    """Registered component equations; initialization uses only this fitting window."""
    if len(values) < 2 or not 1 <= horizon <= 30:
        raise _invalid("forecast_method", "This fitting window or horizon is unsupported.")
    if candidate.method == "last_value":
        return (_approximate(values[-1]),) * horizon
    season = candidate.season
    if candidate.method == "seasonal_naive":
        if not season or len(values) < 2 * season:
            raise _invalid("forecast_season_required", "Use two complete cycles before fitting.")
        return tuple(_approximate(values[-season + index % season]) for index in range(horizon))
    if candidate.method not in FAMILIES[1:]:
        raise _invalid("forecast_method", "This smoothing method is not registered.")
    alpha, beta, phi, gamma = map(
        Decimal, (candidate.alpha, candidate.beta, candidate.phi, candidate.gamma)
    )
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        level, trend = values[0], values[1] - values[0]
        seasons: list[Decimal] = []
        start = 1
        if candidate.method == "simple_exponential":
            trend = Decimal(0)
        if candidate.method == "holt_winters_additive":
            if not season or len(values) < 2 * season:
                raise _invalid(
                    "forecast_season_required", "Use two complete cycles before fitting."
                )
            first = sum(values[:season], Decimal(0)) / season
            second = sum(values[season : 2 * season], Decimal(0)) / season
            trend = (second - first) / season
            level = first + trend * Decimal(season - 1) / 2
            seasons = [
                values[index] - (first + trend * (Decimal(index) - Decimal(season - 1) / 2))
                for index in range(season)
            ]
            start = season
        for index in range(start, len(values)):
            actual = values[index]
            if candidate.method == "simple_exponential":
                level = alpha * actual + (1 - alpha) * level
                continue
            old_level = level
            old_season = seasons[index % season] if seasons and season else Decimal(0)
            projection = level + phi * trend
            level = alpha * (actual - old_season) + (1 - alpha) * projection
            trend = beta * (level - old_level) + (1 - beta) * phi * trend
            if seasons and season:
                seasons[index % season] = gamma * (actual - projection) + (1 - gamma) * old_season
        estimates = []
        trend_weight = Decimal(0)
        for step in range(1, horizon + 1):
            trend_weight += phi**step
            seasonal_value = (
                seasons[(len(values) + step - 1) % season] if seasons and season else Decimal(0)
            )
            estimate = level + trend_weight * trend + seasonal_value
            estimate = _approximate(estimate)
            _number(estimate, estimate=True)
            estimates.append(estimate)
        return tuple(estimates)


def _range_width(errors: tuple[Decimal, ...]) -> Decimal:
    """Nearest-rank 90th percentile, a display rule without a coverage guarantee."""
    ranked = sorted(errors)
    return ranked[(9 * len(ranked) + 9) // 10 - 1]


def _prediction(period: str, estimate: Decimal, width: Decimal) -> dict[str, str]:
    return {
        "period": period,
        "estimate": _estimated(estimate),
        "lower": _estimated(estimate - width),
        "upper": _estimated(estimate + width),
    }


def advanced_forecast(
    points: tuple[ForecastPoint, ...], request: ForecastRequest, family: str = "auto"
) -> ForecastResult:
    required = minimum_history(request, family)
    _points(points, request.frequency, contiguous=True)
    if len(points) < required:
        raise _invalid(
            "forecast_insufficient_history",
            f"Advanced forecasting needs at least {required} complete {request.frequency} periods "
            "for three rolling validation windows and an untouched test window.",
        )
    holdout = max(request.horizon, MIN_HOLDOUT[request.frequency])
    first_origin = len(points) - 4 * holdout
    origins = tuple(first_origin + index * holdout for index in range(ROLLING_ORIGINS))
    candidates = registered_candidates(request, family, first_origin)
    work = len(candidates) * sum(origins) + (len(points) - holdout) + len(points)
    if len(points) > MAX_HISTORY or work > MAX_STATE_UPDATES:
        raise _invalid(
            "forecast_work_limit",
            "This forecast exceeds the bounded candidate evaluation workload.",
        )
    values = tuple(point.actual for point in points)
    with localcontext() as context:
        context.prec = 128
        context.rounding = ROUND_HALF_EVEN
        scores: list[dict[str, Any]] = []
        residual_sets: list[tuple[Decimal, ...]] = []
        validation_actuals = tuple(
            values[index] for origin in origins for index in range(origin, origin + holdout)
        )
        for candidate in candidates:
            estimates = tuple(
                value
                for origin in origins
                for value in predict(candidate, values[:origin], holdout)
            )
            metrics = error_metrics(validation_actuals, estimates)
            residual_sets.append(
                tuple(
                    abs(actual - estimate)
                    for actual, estimate in zip(validation_actuals, estimates, strict=True)
                )
            )
            scores.append(
                {
                    "method": candidate.method,
                    "parameters": candidate.parameters(),
                    "metrics": metrics,
                }
            )
        chosen = min(
            range(len(candidates)),
            key=lambda index: (Decimal(scores[index]["metrics"]["mae"]), index),
        )
        selected = candidates[chosen]
        width = _range_width(residual_sets[chosen])
        test_points = points[-holdout:]
        estimates = predict(selected, values[:-holdout], holdout)
        backtest = []
        for point, estimate in zip(test_points, estimates, strict=True):
            row = _prediction(point.period.isoformat(), estimate, width)
            difference = point.actual - Decimal(row["estimate"])
            row.update(
                actual=format(point.actual, "f"),
                error=format(difference, "f"),
                absolute_error=format(abs(difference), "f"),
            )
            backtest.append(row)
        test_actuals = tuple(point.actual for point in test_points)
        accuracy = error_metrics(test_actuals, tuple(Decimal(row["estimate"]) for row in backtest))
        baseline_estimates = predict(candidates[0], values[:-holdout], holdout)
        baseline_accuracy = error_metrics(
            test_actuals, tuple(Decimal(_estimated(value)) for value in baseline_estimates)
        )
        future = predict(selected, values, request.horizon)
        period = points[-1].period
        predictions = []
        for estimate in future:
            period = next_period(period, request.frequency)
            predictions.append(_prediction(period.isoformat(), estimate, width))
        limitations = [
            "Fixed registered smoothing candidates are compared, "
            "not every possible forecasting model.",
            "Three expanding chronological validation windows select parameters; "
            "the later test window does not select the method.",
            "Error ranges use the selected candidate's pooled validation absolute errors. "
            "Selection and calibration reuse validation data; "
            "this is not independent calibrated coverage.",
            "The same empirical width is shown for each horizon. Errors can vary by horizon, "
            "regime or external event; three origins provide limited evidence.",
            "Additive methods permit negative estimates. No clipping, missing-period imputation, "
            "holiday effects or inferred future regressors are used.",
            "Historical evaluations do not establish customer accuracy, "
            "causality or action benefits.",
        ]
        excluded = []
        if request.season_length and first_origin < 2 * request.season_length:
            excluded.append(
                {
                    "method": "seasonal methods",
                    "reason": "The first training window has fewer than two declared cycles.",
                }
            )
            limitations.append(excluded[-1]["reason"])
        if width == 0:
            limitations.append(
                "Validation errors were zero, so ranges collapse. "
                "Future errors can still be nonzero."
            )
        record = {
            "version": VERSION,
            "frequency": request.frequency,
            "horizon": request.horizon,
            "season_length": request.season_length,
            "method": {"id": selected.method, "version": 1, "parameters": selected.parameters()},
            "windows": {
                "training": _window(points[:first_origin]),
                "validation": _window(points[first_origin:-holdout]),
                "test_training": _window(points[:-holdout]),
                "test": _window(test_points),
                "forecast_training": _window(points),
            },
            "selection": {
                "criterion": "rolling_validation_mae",
                "tie_break": "registered_candidate_order",
                "registry_version": REGISTRY_VERSION,
                "requested_family": family,
                "candidates": scores,
                "excluded": excluded,
                "folds": [
                    {
                        "training": _window(points[:origin]),
                        "validation": _window(points[origin : origin + holdout]),
                    }
                    for origin in origins
                ],
                "state_updates_bound": work,
                "state_updates_limit": MAX_STATE_UPDATES,
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
                "method": "pooled_rolling_validation_absolute_error_rank_v1",
                "label": "Empirical validation-error range; no guaranteed coverage",
                "coverage_guaranteed": False,
                "calibration_independent": False,
                "width": _estimated(width),
                "error_count": len(residual_sets[chosen]),
                "display_percentile": "90",
                "backtest_error_source": "rolling_validation",
                "future_error_source": "rolling_validation",
                "backtest_coverage": {
                    "inside": sum(
                        Decimal(row["lower"]) <= Decimal(row["actual"]) <= Decimal(row["upper"])
                        for row in backtest
                    ),
                    "count": len(backtest),
                    "label": "Observed untouched-test coverage only; not promised future coverage",
                },
            },
            "limitations": limitations,
        }
        return ForecastResult(
            json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        )


def compare_advanced_forecast(
    record: dict[str, Any], actuals: tuple[ForecastPoint, ...]
) -> dict[str, Any]:
    if record.get("version") != VERSION:
        raise _invalid("forecast_record", "This advanced forecast version is unavailable.")
    return compare_forecast({**record, "version": BASIC_VERSION}, actuals)
