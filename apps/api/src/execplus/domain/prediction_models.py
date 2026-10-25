"""Use case: Defines the fixed, no-AI "Build a prediction model" recipe.

What it does: Validates a target and inputs on confirmed meaning, refuses leaking fields,
chooses a fixed-seed holdout and turns server-computed holdout metrics into a plain verdict.
"""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.exploration_selection import tokens
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.patterns import MAX_ROWS, pattern_plan
from execplus.domain.patterns import REQUEST_VERSION as PATTERN_REQUEST_VERSION
from execplus.domain.profiling import TableData
from execplus.domain.sampling import sample_positions
from execplus.domain.semantics import DatasetView, MetricRequest
from execplus.domain.understanding import governed_request, preferred_aggregation

METHOD = "prediction-model-v1"
REQUEST_VERSION = "prediction-request-v1"
SPLIT_METHOD = "stratified-floyd-splitmix64-v1"
SPLIT_SEED = 20261027
HOLDOUT_PERCENT = 20
MAX_INPUTS = 30
MAX_LEVELS = 50
MIN_ROWS = 50
MIN_CLASS = 10
IDENTIFIER_SHARE = Decimal("0.95")
NUMERIC = {"integer", "decimal"}
CATEGORY = {"text", "boolean"}
YES = {"yes", "y", "true", "t", "1"}
POST_OUTCOME = {
    "duration",
    "outcome",
    "result",
    "converted",
    "conversion",
    "churned",
    "won",
    "lost",
    "closed",
    "cancelled",
    "canceled",
    "refunded",
    "approved",
    "rejected",
    "final",
}
AUC_FLOOR = Decimal("0.55")
MAE_GAIN_FLOOR = Decimal("0.05")
SINGLE_INPUT_AUC = 0.97
SINGLE_INPUT_R2 = 0.95
TOP_WEIGHTS = 10
Z_95 = 1.96

Fit = Callable[
    [str, tuple[float, ...], tuple[tuple[str, str, tuple[Any, ...]], ...], tuple[int, ...]],
    dict[str, Any],
]


def is_prediction_model(raw: dict[str, Any]) -> bool:
    return raw.get("kind") == "robust_distribution" and raw.get("model") == METHOD


def invalid(message: str) -> None:
    raise IngestionError("prediction_input", message, 422)


def _task(column: dict[str, Any], metric: bool) -> str | None:
    if column["distinct_count"] == 2 and column["type"] in NUMERIC | CATEGORY:
        return "classification"
    if column["type"] in NUMERIC and metric:
        return "regression"
    return None


def _input_reason(column: dict[str, Any], role: str, rows: int, target: str | None = None) -> str:
    name = column["name"]
    if role in {"identifier", "ignored"}:
        return "Identifiers and ignored fields are never used as inputs."
    if (
        rows >= 20
        and (column["type"] in CATEGORY or (column["type"] == "integer" and role != "metric"))
        and column["distinct_count"] >= IDENTIFIER_SHARE * rows
    ):
        return (
            "Almost every row has a different value, so it acts like an ID and "
            "would only memorise rows."
        )
    name_tokens = tokens(name)
    target_tokens = tokens(target or "")
    if name_tokens & POST_OUTCOME or (target_tokens and target_tokens <= name_tokens):
        return (
            "Its name suggests it is only known after the outcome (for example a call "
            "duration or a final status), so it would leak the answer."
        )
    if column["type"] not in NUMERIC | CATEGORY:
        return "Dates and empty fields are not used as inputs in this version."
    if column["type_conflicts"]:
        return "Correct inconsistent values in this field first."
    if column["distinct_count"] <= 1:
        return "This field has only one value."
    if column["type"] in CATEGORY and column["distinct_count"] > MAX_LEVELS:
        return "It has more than 50 different values; group them into fewer categories first."
    return ""


def prediction_options(context: DescriptionContext) -> dict[str, Any]:
    definitions = {item["name"]: item for item in (context.definition or {}).get("columns", [])}
    rows = context.profile["row_count"]
    targets, inputs = [], []
    for column in context.profile["columns"]:
        role = definitions.get(column["name"], {}).get("role", column["role"])
        task = (
            None
            if role in {"identifier", "ignored"} or column["type_conflicts"]
            else _task(column, column["name"] in context.view.metrics)
        )
        if task:
            targets.append(dict(name=column["name"], task=task))
        reason = _input_reason(column, role, rows)
        inputs.append(
            dict(
                name=column["name"],
                kind="numeric" if column["type"] in NUMERIC else "category",
                excluded_reason=reason or None,
            )
        )
    return dict(
        model=METHOD,
        targets=targets,
        inputs=inputs,
        maximum_inputs=MAX_INPUTS,
        maximum_rows=MAX_ROWS,
        holdout_percent=HOLDOUT_PERCENT,
    )


def prediction_request(
    context: DescriptionContext, table: TableData, raw: dict[str, Any]
) -> dict[str, Any]:
    if context.state != "confirmed" or not context.view.sources[0].get("understanding_id"):
        raise ClarificationRequiredError(
            "Confirm what the data fields mean before building a prediction model."
        )
    if raw.get("filters"):
        invalid("Prediction models use every row; filters are not supported in this version.")
    view = context.view
    definitions = {item["name"]: item for item in (context.definition or {})["columns"]}
    profiles = {item["name"]: item for item in context.profile["columns"]}
    target, selected = raw["target_column"], list(raw.get("input_columns") or [])
    if target not in definitions:
        raise ClarificationRequiredError("Choose a target field that exists in this file.")
    column = profiles[target]
    task = (
        None
        if definitions[target]["role"] in {"identifier", "ignored"} or column["type_conflicts"]
        else _task(column, target in view.metrics)
    )
    if task is None:
        raise ClarificationRequiredError(
            f"{target} cannot be predicted here. Choose a yes/no or two-value field, "
            "or a numerical measure."
        )
    positive = raw.get("positive_label")
    if positive is not None and (task != "classification" or not 1 <= len(positive) <= 200):
        invalid("A positive outcome label applies only to a two-value target.")
    if len(selected) > MAX_INPUTS or len(set(selected)) != len(selected) or target in selected:
        invalid("Choose up to 30 different input fields, not including the target.")
    if any(name not in definitions for name in selected):
        invalid("Choose input fields that exist in this file.")
    filters: list[dict[str, Any]] = []
    if task == "regression":
        governed = governed_request(
            view, table, MetricRequest(target, preferred_aggregation(view, target))
        )
        filters = [
            dict(column=f.column, operator=f.operator.value, value=f.value)
            for f in sorted(
                governed.filters, key=lambda f: (f.column, f.operator.value, str(f.value))
            )
        ]
    inputs: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    rows = context.profile["row_count"]
    for name in selected or [name for name in definitions if name != target]:
        if name == target:
            continue
        reason = _input_reason(profiles[name], definitions[name]["role"], rows, target)
        if not reason and len(inputs) >= MAX_INPUTS:
            reason = "This model uses at most 30 inputs; choose this one explicitly."
        if reason:
            exclusions.append(dict(column=name, reason=reason))
        else:
            kind = "numeric" if profiles[name]["type"] in NUMERIC else "category"
            inputs.append(dict(name=name, kind=kind))
    refused = [item for item in exclusions if item["column"] in selected]
    if refused:
        raise ClarificationRequiredError(
            " ".join(f"{item['column']}: {item['reason']}" for item in refused)
        )
    if not inputs:
        raise ClarificationRequiredError("No usable input fields remain for this target.")
    definition = definitions[target]
    return dict(
        version=REQUEST_VERSION,
        method=METHOD,
        task=task,
        target=target,
        target_unit=(definition.get("currency") or definition.get("unit") or None)
        if task == "regression"
        else None,
        positive_label=positive,
        selected=selected,
        inputs=inputs,
        columns=[target, *(item["name"] for item in inputs)],
        filters=filters,
        exclusions=exclusions,
        limits=dict(
            rows=MAX_ROWS,
            inputs=MAX_INPUTS,
            category_levels=MAX_LEVELS,
            minimum_rows=MIN_ROWS,
            minimum_per_class=MIN_CLASS,
        ),
    )


def prediction_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, request: dict[str, Any]
) -> QueryPlan:
    if request["version"] != REQUEST_VERSION:
        invalid("The saved prediction method is not supported.")
    projection = dict(
        version=PATTERN_REQUEST_VERSION, columns=request["columns"], filters=request["filters"]
    )
    return replace(pattern_plan(scope, did, view, projection), question="Build a prediction model")


def holdout_positions(labels: list[Any]) -> tuple[int, ...]:
    """Fixed-seed 20% holdout, drawn separately within each outcome class."""
    groups: dict[str, list[int]] = {}
    for index, label in enumerate(labels):
        groups.setdefault(str(label), []).append(index)
    chosen: list[int] = []
    for key in sorted(groups):
        members = groups[key]
        size = (len(members) * HOLDOUT_PERCENT + 50) // 100
        chosen.extend(members[p] for p in sample_positions(len(members), size, SPLIT_SEED))
    return tuple(sorted(chosen))


def _positive(counts: Counter[str], requested: str | None) -> str:
    labels = sorted(counts)
    if requested is not None:
        if requested not in counts:
            raise ClarificationRequiredError(
                f"{requested} is not a recorded value of the target. Choose one of: "
                + ", ".join(labels)
                + "."
            )
        return requested
    yes = [label for label in labels if label.strip().casefold() in YES]
    if len(yes) == 1:
        return yes[0]
    return min(reversed(labels), key=counts.__getitem__)


def auc_chance_margin(auc: float, positives: int, negatives: int) -> float:
    """95% half-width of AUC from Hanley and McNeil (1982), so chance wins are not reported."""
    q1, q2 = auc / (2 - auc), 2 * auc * auc / (1 + auc)
    variance = (
        auc * (1 - auc) + (positives - 1) * (q1 - auc * auc) + (negatives - 1) * (q2 - auc * auc)
    ) / (positives * negatives)
    return Z_95 * math.sqrt(max(variance, 0.0))


def _fixed(value: float, places: int = 4) -> str:
    text = f"{value:.{places}f}"
    return "0." + "0" * places if text.lstrip("-") == "0." + "0" * places else text


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _numeric_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise IngestionError(
            "prediction_input", "A numerical input holds a non-numerical value.", 422
        ) from None


def prediction_result(
    value: QueryResult, request: dict[str, Any], fit: Fit, engine_version: str
) -> dict[str, Any]:
    if len(value.rows) > MAX_ROWS:
        invalid(
            "Prediction models are limited to 10,000 rows for this file; no partial sample "
            "was used. Re-upload it to use the large-file sample."
        )
    names = request["columns"]
    if tuple(names) != value.columns or any(len(row) != len(names) for row in value.rows):
        invalid("The model evidence does not match its declared fields.")
    task = request["task"]
    rows = [row for row in value.rows if row[0] is not None]
    dropped = len(value.rows) - len(rows)
    if len(rows) < MIN_ROWS:
        raise ClarificationRequiredError(
            f"At least {MIN_ROWS} rows with a recorded target are needed; found {len(rows)}."
        )
    positive = None
    if task == "classification":
        counts = Counter(str(row[0]) for row in rows)
        if len(counts) != 2:
            raise ClarificationRequiredError("The target must have exactly two recorded values.")
        positive = _positive(counts, request["positive_label"])
        if min(counts.values()) < MIN_CLASS:
            raise ClarificationRequiredError(
                f"Each outcome needs at least {MIN_CLASS} rows to test a model honestly."
            )
        target = tuple(1.0 if str(row[0]) == positive else 0.0 for row in rows)
        negative = next(label for label in counts if label != positive)
    else:
        target = tuple(_numeric_value(row[0]) or 0.0 for row in rows)
        if len(set(target)) < 2:
            raise ClarificationRequiredError("The target has only one recorded value.")
    holdout = holdout_positions(list(target) if task == "classification" else [0] * len(rows))
    inputs = tuple(
        (
            item["name"],
            item["kind"],
            tuple(
                _numeric_value(row[index + 1])
                if item["kind"] == "numeric"
                else (None if row[index + 1] is None else str(row[index + 1]))
                for row in rows
            ),
        )
        for index, item in enumerate(request["inputs"])
    )
    fitted = fit(task, target, inputs, holdout)
    metrics, baseline = fitted["metrics"], fitted["baseline"]
    warnings: list[str] = []
    for name, score in sorted(fitted["single_input"].items()):
        if task == "classification" and score >= SINGLE_INPUT_AUC:
            warnings.append(
                f"{name} alone predicts the target almost perfectly (AUC {_fixed(score, 2)} on "
                "held-back rows). Check that it is known before the outcome; otherwise remove it."
            )
        if task == "regression" and score >= SINGLE_INPUT_R2:
            warnings.append(
                f"{name} alone explains almost all of the target (R² {_fixed(score, 2)} on "
                "held-back rows). Check that it is known before the outcome; otherwise remove it."
            )
    if not fitted["converged"]:
        warnings.append("The fitting step stopped at its iteration limit; treat results with care.")
    holdout_rows = len(holdout)
    if task == "classification":
        auc = Decimal(_fixed(metrics["auc"]))
        guess = positive if baseline["positive"] else negative
        held_positive = sum(1 for i in holdout if target[i] == 1.0)
        chance = auc_chance_margin(float(auc), held_positive, holdout_rows - held_positive)
        beats = auc >= AUC_FLOOR and float(auc) - chance > 0.5
        gain = _fixed(float(auc) - 0.5, 2)
        verdict = (
            f"Beats the simple guess by {gain} AUC points: on {holdout_rows:,} held-back rows "
            f"it ranks {positive} cases above {negative} cases with AUC "
            f"{_fixed(metrics['auc'], 2)} "
            "(0.50 is guessing)."
            if beats
            else f"Not better than guessing — don't use it. On {holdout_rows:,} held-back rows "
            f"its AUC is {_fixed(metrics['auc'], 2)}; 0.50 is a coin flip and chance alone "
            f"can move it by about {_fixed(chance, 2)} on this many rows."
        )
        details = [
            f"It labels {_percent(metrics['accuracy'])} of held-back rows correctly; always "
            f"guessing {guess} would label {_percent(baseline['accuracy'])} correctly.",
            "AUC measures how well it orders likely and unlikely cases; accuracy can stay near "
            "the simple guess when one outcome is rare.",
        ]
        shown_metrics = dict(auc=_fixed(metrics["auc"]), accuracy=_fixed(metrics["accuracy"]))
        shown_baseline = dict(label=guess, auc="0.5000", accuracy=_fixed(baseline["accuracy"]))
    else:
        gain_value = 1 - metrics["mae"] / baseline["mae"] if baseline["mae"] > 0 else 0.0
        beats = (
            Decimal(_fixed(gain_value)) >= MAE_GAIN_FLOOR
            and metrics["r2"] > 0
            and metrics["improvement_z"] > Z_95
        )
        unit = f" {request['target_unit']}" if request["target_unit"] else ""
        verdict = (
            f"Beats the simple guess by {_percent(gain_value)}: on {holdout_rows:,} held-back rows "
            f"its average error is {_fixed(metrics['mae'], 2)}{unit} versus "
            f"{_fixed(baseline['mae'], 2)}{unit} when always guessing the average."
            if beats
            else "Not better than guessing — don't use it. On "
            f"{holdout_rows:,} held-back rows its average error is {_fixed(metrics['mae'], 2)}"
            f"{unit} versus {_fixed(baseline['mae'], 2)}{unit} for always guessing the average."
        )
        details = [
            f"R² is {_fixed(metrics['r2'], 2)} (1.00 is perfect, 0 is no better than the average).",
        ]
        shown_metrics = dict(mae=_fixed(metrics["mae"]), r2=_fixed(metrics["r2"]))
        shown_baseline = dict(mae=_fixed(baseline["mae"]), r2=_fixed(baseline["r2"]))
    weights = sorted(
        fitted["weights"], key=lambda w: (-abs(round(w["weight"], 6)), w["input"], w["level"] or "")
    )[:TOP_WEIGHTS]
    direction = (
        (f"more likely {positive}", f"less likely {positive}")
        if task == "classification"
        else ("higher target", "lower target")
    )
    return dict(
        version=METHOD,
        engine_version=engine_version,
        task=task,
        target=request["target"],
        positive_label=positive,
        verdict=dict(status="beats_guess" if beats else "not_useful", text=verdict),
        details=details,
        metrics=shown_metrics,
        baseline=shown_baseline,
        weights=[
            dict(
                input=w["input"],
                level=w["level"],
                weight=_fixed(w["weight"]),
                direction=direction[0] if w["weight"] > 0 else direction[1],
                label="associated with, not a cause",
            )
            for w in weights
        ],
        warnings=warnings,
        method=dict(
            name="Logistic regression (L2, C=1)"
            if task == "classification"
            else "Linear regression (least squares)",
            inputs="Numbers are standardised on training rows; missing numbers use the "
            "training average. Categories become yes/no columns; values seen in fewer than "
            "five training rows share one column per field; missing is its own value.",
            split=f"{HOLDOUT_PERCENT}% held back"
            + (" within each outcome" if task == "classification" else "")
            + f" ({SPLIT_METHOD}, seed {SPLIT_SEED}); the model never trains on these rows.",
            seed=SPLIT_SEED,
            iterations=fitted["iterations"],
        ),
        coverage=dict(
            source_rows=value.records_analyzed,
            used_rows=len(rows),
            missing_target_rows=dropped,
            training_rows=len(rows) - holdout_rows,
            holdout_rows=holdout_rows,
            encoded_columns=fitted["features"],
            missing_inputs={name: count for name, count in fitted["missing"].items() if count},
        ),
        inputs=[item["name"] for item in request["inputs"]],
        exclusions=request["exclusions"],
        limitations=[
            "Weights describe associations in this file, not causes: changing an input will "
            "not necessarily change the outcome.",
            "Scores come from one fixed held-back split of past rows; new or different data "
            "can perform worse.",
            "No AI chose the method or produced any number; every figure was computed on the "
            "server.",
        ],
    )
