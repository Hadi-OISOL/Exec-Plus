"""Use case: Reproduces the RD-Agent pilot's bank result with Osalytix's prediction recipe.

What it does: Trains the product trainer on the pilot's exact train/holdout split, and
separately runs the full domain recipe (own fixed-seed split) on the original bank.csv.
Usage: python scripts/reproduce_prediction_pilot.py <rd-agent-pilot folder>
"""

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from execplus.domain.models import QueryResult
from execplus.domain.prediction_models import holdout_positions, prediction_result
from execplus.infrastructure.statistics.prediction import NumpyPredictionTrainer

NUMERIC = {"age", "balance", "day", "campaign", "pdays", "previous"}


def rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def inputs(records: list[dict[str, str]]) -> tuple[tuple[str, str, tuple[object, ...]], ...]:
    names = [n for n in records[0] if n not in {"id", "y", "duration"}]
    return tuple(
        (
            name,
            "numeric" if name in NUMERIC else "category",
            tuple(float(r[name]) if name in NUMERIC else r[name] for r in records),
        )
        for name in names
    )


def main(root: Path) -> None:
    trainer = NumpyPredictionTrainer()
    competition = root / "ds_data" / "bank-subscribe"
    train = rows(competition / "train" / "train.csv")
    labels = {r["id"]: r["y"] for r in rows(root / "holdout" / "holdout_labels.csv")}
    test = [{**r, "y": labels[r["id"]]} for r in rows(competition / "test" / "test.csv")]
    records = train + test
    pilot = trainer.fit(
        "classification",
        tuple(float(r["y"]) for r in records),
        inputs(records),
        tuple(range(len(train), len(records))),
    )
    bank = rows(root / "download" / "bank.csv", ";")
    columns = ["y", *(n for n in bank[0] if n not in {"y", "duration"})]
    value = QueryResult(
        uuid4(),
        tuple(columns),
        tuple(tuple(Decimal(r[n]) if n in NUMERIC else r[n] for n in columns) for r in bank),
        len(bank),
    )
    request = dict(
        task="classification",
        target="y",
        target_unit=None,
        positive_label=None,
        columns=columns,
        inputs=[dict(name=n, kind="numeric" if n in NUMERIC else "category") for n in columns[1:]],
        exclusions=[dict(column="duration", reason="post-outcome")],
    )
    product = prediction_result(value, request, trainer.fit, trainer.engine_version)
    print(
        json.dumps(
            dict(
                pilot_split=dict(
                    train_rows=len(train),
                    holdout_rows=len(test),
                    auc=round(pilot["metrics"]["auc"], 4),
                    accuracy=round(pilot["metrics"]["accuracy"], 4),
                    majority_accuracy=round(pilot["baseline"]["accuracy"], 4),
                    pilot_sklearn_auc=0.7376,
                ),
                product_split=dict(
                    holdout_rows=len(holdout_positions([r["y"] for r in bank])),
                    metrics=product["metrics"],
                    baseline=product["baseline"],
                    verdict=product["verdict"]["text"],
                ),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
