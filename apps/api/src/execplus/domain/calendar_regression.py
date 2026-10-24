"""Use case: Fits deterministic calendar-effect regressions for advanced forecasts.

What it does: Builds day-of-week or month-of-year indicator features, an optional
linear trend, an optional declared 0/1 event and, for declared-regressor candidates,
a holiday indicator and numeric outside predictors, solves ordinary least squares in
Decimal arithmetic on one fitting window and projects later periods.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

METHOD_VERSION = "calendar-dummy-least-squares-v1"
DECLARED_METHOD_VERSION = "declared-regressor-least-squares-v1"
METHODS = ("calendar_regression", "calendar_profile")
TREND_ONLY = "regressor_trend"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
PIVOT_FLOOR = Decimal("1e-30")


@dataclass(frozen=True)
class CalendarInputs:
    periods: tuple[date, ...]
    events: tuple[int, ...] | None = None
    holidays: tuple[int, ...] | None = None
    predictors: tuple[tuple[Decimal, ...], ...] = ()
    predictor_names: tuple[str, ...] = ()

    @property
    def declared(self) -> bool:
        return self.holidays is not None or bool(self.predictors)


def calendar_kind(frequency: str) -> str:
    return "day_of_week" if frequency == "daily" else "month_of_year"


def feature_names(
    frequency: str,
    trend: bool,
    event: bool,
    inputs: CalendarInputs | None = None,
    method: str = "",
    declared: bool = False,
) -> tuple[str, ...]:
    levels = () if method == TREND_ONLY else WEEKDAYS[1:] if frequency == "daily" else MONTHS[1:]
    extra: tuple[str, ...] = ()
    if declared and inputs is not None:
        extra = (
            *(("holiday",) if inputs.holidays is not None else ()),
            *inputs.predictor_names,
        )
    return (
        "baseline",
        *(("trend",) if trend else ()),
        *levels,
        *(("event",) if event else ()),
        *extra,
    )


def features(
    inputs: CalendarInputs,
    frequency: str,
    index: int,
    trend: bool,
    event: bool,
    method: str = "",
    declared: bool = False,
) -> tuple[Decimal, ...]:
    period = inputs.periods[index]
    level = period.weekday() if frequency == "daily" else period.month - 1
    count = 6 if frequency == "daily" else 11
    row = [Decimal(1)]
    if trend:
        row.append(Decimal(index))
    if method != TREND_ONLY:
        row.extend(Decimal(int(level == item + 1)) for item in range(count))
    if event:
        row.append(Decimal((inputs.events or ())[index]))
    if declared:
        if inputs.holidays is not None:
            row.append(Decimal(inputs.holidays[index]))
        row.extend(values[index] for values in inputs.predictors)
    return tuple(row)


def solve(rows: list[tuple[Decimal, ...]], values: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    """Normal equations by Gauss-Jordan; a column without a usable pivot keeps coefficient 0."""
    width = len(rows[0])
    with localcontext() as context:
        context.prec, context.rounding = 60, ROUND_HALF_EVEN
        matrix = [
            [sum((row[i] * row[j] for row in rows), Decimal(0)) for j in range(width)]
            + [sum((row[i] * value for row, value in zip(rows, values, strict=True)), Decimal(0))]
            for i in range(width)
        ]
        pivots: dict[int, int] = {}
        used: set[int] = set()
        for column in range(width):
            candidates = [r for r in range(width) if r not in used]
            best = max(candidates, key=lambda r: (abs(matrix[r][column]), -r))
            if abs(matrix[best][column]) <= PIVOT_FLOOR:
                continue
            used.add(best)
            pivots[column] = best
            factor = matrix[best][column]
            matrix[best] = [value / factor for value in matrix[best]]
            for other in range(width):
                if other != best and matrix[other][column]:
                    scale = matrix[other][column]
                    matrix[other] = [
                        value - scale * pivot
                        for value, pivot in zip(matrix[other], matrix[best], strict=True)
                    ]
        return tuple(
            matrix[pivots[column]][width] if column in pivots else Decimal(0)
            for column in range(width)
        )


def fit(
    inputs: CalendarInputs,
    frequency: str,
    end: int,
    values: tuple[Decimal, ...],
    method: str,
    declared: bool = False,
) -> tuple[Decimal, ...]:
    trend, event = method in {"calendar_regression", TREND_ONLY}, inputs.events is not None
    rows = [
        features(inputs, frequency, index, trend, event, method, declared) for index in range(end)
    ]
    return solve(rows, values[:end])


def project(
    inputs: CalendarInputs,
    frequency: str,
    end: int,
    values: tuple[Decimal, ...],
    method: str,
    horizon: int,
    declared: bool = False,
) -> tuple[Decimal, ...]:
    trend, event = method in {"calendar_regression", TREND_ONLY}, inputs.events is not None
    coefficients = fit(inputs, frequency, end, values, method, declared)
    with localcontext() as context:
        context.prec, context.rounding = 60, ROUND_HALF_EVEN
        return tuple(
            sum(
                (
                    weight * feature
                    for weight, feature in zip(
                        coefficients,
                        features(inputs, frequency, index, trend, event, method, declared),
                        strict=True,
                    )
                ),
                Decimal(0),
            )
            for index in range(end, end + horizon)
        )
