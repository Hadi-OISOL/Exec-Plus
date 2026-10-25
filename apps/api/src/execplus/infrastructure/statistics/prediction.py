"""Use case: Trains the fixed prediction-model recipe with pinned NumPy/SciPy.

What it does: Encodes inputs from training rows only, fits L2 logistic or least-squares
linear regression, and scores the untouched holdout against a simple-guess baseline.
"""

from collections import Counter
from typing import Any

import numpy
import scipy
from scipy import optimize, special, stats

MIN_LEVEL_ROWS = 5
TOP_LEVELS = 20
MAX_ITERATIONS = 1000
MISSING = "(missing)"
OTHER = "(other values)"
Array = Any


def _numeric(values: tuple[Any, ...], train: Array) -> tuple[Array, list[str | None], int]:
    column = numpy.array([numpy.nan if v is None else float(v) for v in values])
    missing = numpy.isnan(column)
    seen = column[train & ~missing]
    mean = float(seen.mean()) if seen.size else 0.0
    scale = float(seen.std()) if seen.size else 0.0
    filled = numpy.where(missing, mean, column)
    return ((filled - mean) / (scale or 1.0))[:, None], [None], int(missing.sum())


def _category(values: tuple[Any, ...], train: Array) -> tuple[Array, list[str | None], int]:
    labels = [MISSING if v is None else str(v) for v in values]
    counts = Counter(label for label, used in zip(labels, train, strict=True) if used)
    kept = sorted(
        (label for label, count in counts.items() if count >= MIN_LEVEL_ROWS),
        key=lambda label: (-counts[label], label),
    )[:TOP_LEVELS]
    if len(kept) < len(counts):
        kept.append(OTHER)
    position = {label: index for index, label in enumerate(kept)}
    other = position.get(OTHER)
    matrix = numpy.zeros((len(labels), len(kept)))
    for row, label in enumerate(labels):
        index = position.get(label, other)
        if index is not None:
            matrix[row, index] = 1.0
    return matrix, list(kept), sum(1 for v in values if v is None)


def _auc(target: Array, score: Array) -> float:
    positives = int(target.sum())
    negatives = target.size - positives
    if not positives or not negatives:
        return 0.5
    ranks = stats.rankdata(score)
    return float(
        (ranks[target == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives)
    )


def _logistic(x: Array, y: Array) -> tuple[Array, int, bool]:
    design = numpy.hstack([numpy.ones((x.shape[0], 1)), x])

    def loss(w: Array) -> tuple[float, Array]:
        z = design @ w
        penalty = w.copy()
        penalty[0] = 0.0
        value = float(numpy.logaddexp(0.0, z).sum() - y @ z + 0.5 * penalty @ penalty)
        return value, design.T @ (special.expit(z) - y) + penalty

    fitted = optimize.minimize(
        loss,
        numpy.zeros(design.shape[1]),
        jac=True,
        method="L-BFGS-B",
        options=dict(maxiter=MAX_ITERATIONS),
    )
    return fitted.x, int(fitted.nit), bool(fitted.success)


def _linear(x: Array, y: Array) -> Array:
    design = numpy.hstack([numpy.ones((x.shape[0], 1)), x])
    return numpy.linalg.lstsq(design, y, rcond=None)[0]


def _predict(x: Array, w: Array) -> Array:
    return w[0] + x @ w[1:]


def _r2(y: Array, predicted: Array) -> float:
    total = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float(((y - predicted) ** 2).sum()) / total if total else 0.0


class NumpyPredictionTrainer:
    @property
    def engine_version(self) -> str:
        return f"prediction-numpy-{numpy.__version__}/scipy-{scipy.__version__}"

    def _score(
        self, task: str, x: Array, y: Array, train: Array
    ) -> tuple[float, dict[str, float], Array, int, bool]:
        test = ~train
        if task == "classification":
            w, iterations, converged = _logistic(x[train], y[train])
            probability = special.expit(_predict(x[test], w))
            auc = _auc(y[test], probability)
            accuracy = float(((probability >= 0.5) == (y[test] == 1)).mean())
            return auc, dict(auc=auc, accuracy=accuracy), w, iterations, converged
        w = _linear(x[train], y[train])
        predicted = _predict(x[test], w)
        r2 = _r2(y[test], predicted)
        errors = numpy.abs(y[test] - predicted)
        gains = numpy.abs(y[test] - y[train].mean()) - errors
        spread = float(gains.std(ddof=1)) / float(numpy.sqrt(gains.size))
        z = float(gains.mean()) / spread if spread else 0.0
        return r2, dict(mae=float(errors.mean()), r2=r2, improvement_z=z), w, 0, True

    def fit(
        self,
        task: str,
        target: tuple[float, ...],
        inputs: tuple[tuple[str, str, tuple[Any, ...]], ...],
        holdout: tuple[int, ...],
    ) -> dict[str, Any]:
        y = numpy.asarray(target, dtype=float)
        train = numpy.ones(y.size, dtype=bool)
        train[list(holdout)] = False
        blocks: list[Array] = []
        columns: list[tuple[str, str | None]] = []
        missing: dict[str, int] = {}
        single: dict[str, float] = {}
        for name, kind, values in inputs:
            block, levels, missing[name] = (_numeric if kind == "numeric" else _category)(
                values, train
            )
            blocks.append(block)
            columns.extend((name, level) for level in levels)
            single[name] = self._score(task, block, y, train)[0]
        x = numpy.hstack(blocks)
        _, metrics, w, iterations, converged = self._score(task, x, y, train)
        test = y[~train]
        if task == "classification":
            share = float(y[train].mean())
            majority = 1.0 if share > 0.5 else 0.0
            baseline = dict(
                positive=majority == 1.0,
                accuracy=float((test == majority).mean()),
            )
        else:
            guess = float(y[train].mean())
            baseline = dict(
                mae=float(numpy.abs(test - guess).mean()),
                r2=_r2(test, numpy.full(test.size, guess)),
            )
        return dict(
            metrics=metrics,
            baseline=baseline,
            weights=[
                dict(input=name, level=level, weight=float(weight))
                for (name, level), weight in zip(columns, w[1:], strict=True)
            ],
            missing=missing,
            single_input=single,
            features=x.shape[1],
            iterations=iterations,
            converged=converged,
        )
