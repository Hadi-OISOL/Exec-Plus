"""Use case: Verifies new statistical and daily arithmetic paths in the packaged runtime.

What it does: Checks deterministic concurrent results, dependency notices and exact assumptions.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from importlib.metadata import distribution
from pathlib import Path
from typing import Any
from uuid import uuid4

from execplus.domain.models import QueryResult
from execplus.domain.patterns import pattern_result
from execplus.domain.scenarios import compare_scenarios
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics


def check() -> dict[str, Any]:
    engine = ScipyPatternStatistics()
    value = QueryResult(
        uuid4(),
        ("amount", "cost", "region"),
        tuple((Decimal(i), Decimal(i * 2), "A" if i < 21 else "B") for i in range(1, 41)),
        40,
    )
    request = dict(
        columns=list(value.columns),
        metrics=["amount", "cost"],
        group_metrics=["amount", "cost"],
        categories=["region"],
        selected=[],
        units={"amount": "units", "cost": "units"},
        exclusions=[],
    )
    result = pattern_result(
        value, request, engine.engine_version, engine.correlations, engine.categorical_association
    )
    relationship = next(
        item for item in result["findings"] if item["type"] == "numeric_relationship"
    )
    assert relationship["statistics"] == dict(pearson="1.000000", spearman="1.000000")
    groups = next(
        item
        for item in result["findings"]
        if item["type"] == "group_difference" and item["chart"]["y"] == "amount"
    )
    assert [item["y"] for item in groups["chart"]["points"]] == ["10.5", "30.5"]
    scenario = compare_scenarios(
        dict(
            metric="amount",
            aggregation="avg",
            assumptions_confirmed=True,
            alternatives=[
                dict(name="Daily assumption", operation="daily_change", daily_change="-2", days=3)
            ],
        ),
        ((Decimal("20.5"), 40, 40),),
    )
    assert scenario["alternatives"][0]["result"] == "14.5"
    assert scenario["alternatives"][0]["path"][-1] == dict(day=3, value="14.5")
    return result


def main() -> None:
    assert os.getuid() != 0, "Use the packaged non-root runtime."
    for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        assert os.environ.get(variable) == "1", variable
    for package in ("scipy", "numpy"):
        notices = [path for path in distribution(package).files or [] if "LICENSE" in str(path)]
        assert notices and all(Path(path.locate()).is_file() for path in notices)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: check(), range(8)))
    assert all(result == results[0] for result in results)
    print(
        "Eight pattern/daily computations match; exact values, pinned engine and notices verified."
    )


if __name__ == "__main__":
    main()
