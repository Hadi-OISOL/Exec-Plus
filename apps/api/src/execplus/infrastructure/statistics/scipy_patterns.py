"""Use case: Computes bounded exploratory association scores with pinned open-source tools.

What it does: Wraps SciPy statistics, rejects unstable output and exposes its library version.
"""

import math
import warnings

import numpy
import scipy
from scipy import stats


class ScipyPatternStatistics:
    @property
    def engine_version(self) -> str:
        return f"scipy-{scipy.__version__}/numpy-{numpy.__version__}"

    def correlations(
        self,
        left: tuple[float, ...],
        right: tuple[float, ...],
        left_ranks: tuple[float, ...],
        right_ranks: tuple[float, ...],
    ) -> tuple[float | None, float] | None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", stats.ConstantInputWarning)
            warnings.simplefilter("error", stats.NearConstantInputWarning)
            try:
                pearson = (
                    float(stats.pearsonr(left, right).statistic)
                    if len(set(left)) == len(set(left_ranks))
                    and len(set(right)) == len(set(right_ranks))
                    else None
                )
                spearman = float(stats.spearmanr(left_ranks, right_ranks).statistic)
            except (ValueError, FloatingPointError, Warning):
                return None
        if not all(
            math.isfinite(value) and -1 <= value <= 1
            for value in (pearson, spearman)
            if value is not None
        ):
            return None
        return pearson, spearman

    def categorical_association(self, counts: tuple[tuple[int, ...], ...]) -> float | None:
        try:
            value = float(
                stats.contingency.association(
                    numpy.asarray(counts), method="cramer", correction=False
                )
            )
        except (ValueError, FloatingPointError):
            return None
        return value if math.isfinite(value) and 0 <= value <= 1 else None
