"""Score privacy-safe structured replays of the ExecPlus conversation harness.

The runner never calls a model or application. An adapter records normalized outcomes from
an offline or separately authorized hosted run; this script validates and scores that record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODES = {"offline_scripted", "hosted_synthetic"}
OUTCOMES = {"answered", "clarification", "refusal", "partial"}
CLAIM_KINDS = {"descriptive", "association", "causal", "uncertainty", "limitation"}
FORBIDDEN_LOG_FIELDS = {"raw_prompt", "raw_response", "provider_secret", "customer_data"}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _texts(value: Any, label: str, *, unique: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a text list")
    if unique and len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _nonnegative(value: Any, label: str, *, integer: bool = False) -> int | float:
    valid_type = type(value) is int if integer else type(value) in {int, float}
    if not valid_type or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return float(value) if not integer else int(value)


def load_corpus(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_bytes()
    body = _object(json.loads(content), "corpus")
    if body.get("version") != "agent-harness-corpus-v1":
        raise ValueError("Unsupported agent harness corpus")
    _text(body.get("evaluation_id"), "evaluation_id")
    datasets = body.get("datasets")
    cases = body.get("cases")
    if not isinstance(datasets, list) or not datasets or not isinstance(cases, list) or not cases:
        raise ValueError("Corpus must contain datasets and cases")
    dataset_ids = {_text(row.get("id"), "dataset id") for row in datasets if isinstance(row, dict)}
    if len(dataset_ids) != len(datasets):
        raise ValueError("Dataset IDs must be unique")
    case_ids: list[str] = []
    for row in cases:
        row = _object(row, "case")
        case_id = _text(row.get("id"), "case id")
        case_ids.append(case_id)
        if row.get("dataset_id") not in dataset_ids:
            raise ValueError(f"Case {case_id} names an unknown dataset")
        if row.get("expected_outcome") not in OUTCOMES:
            raise ValueError(f"Case {case_id} has an invalid expected outcome")
        _text(row.get("expected_intent"), f"{case_id} expected_intent")
        _texts(row.get("expected_tools"), f"{case_id} expected_tools", unique=False)
        _texts(row.get("required_filters"), f"{case_id} required_filters")
        _texts(row.get("forbidden_claim_kinds"), f"{case_id} forbidden_claim_kinds")
        if any(kind not in CLAIM_KINDS for kind in row["forbidden_claim_kinds"]):
            raise ValueError(f"Case {case_id} has an invalid forbidden claim kind")
        expected_values = row.get("expected_values")
        if not isinstance(expected_values, list):
            raise ValueError(f"Case {case_id} expected_values must be a list")
        for value in expected_values:
            value = _object(value, f"{case_id} expected value")
            _text(value.get("name"), "value name")
            _text(value.get("value"), "value")
            _text(value.get("unit"), "unit")
            _text(value.get("evidence_id"), "evidence_id")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Case IDs must be unique")
    return body, hashlib.sha256(content).hexdigest()


def _normalized_values(values: Any, label: str) -> set[tuple[str, str, str, str]]:
    if not isinstance(values, list):
        raise ValueError(f"{label} values must be a list")
    normalized = set()
    for value in values:
        value = _object(value, f"{label} value")
        normalized.add(
            (
                _text(value.get("name"), "value name"),
                _text(value.get("value"), "value"),
                _text(value.get("unit"), "unit"),
                _text(value.get("evidence_id"), "evidence_id"),
            )
        )
    if len(normalized) != len(values):
        raise ValueError(f"{label} contains duplicate values")
    return normalized


def _validate_observation(row: dict[str, Any], case_id: str) -> None:
    if FORBIDDEN_LOG_FIELDS.intersection(row):
        raise ValueError(f"Case {case_id} contains forbidden raw or private logging fields")
    if row.get("outcome") not in OUTCOMES:
        raise ValueError(f"Case {case_id} has an invalid outcome")
    _text(row.get("intent"), f"{case_id} intent")
    _texts(row.get("tools"), f"{case_id} tools", unique=False)
    _texts(row.get("filters"), f"{case_id} filters")
    _normalized_values(row.get("values"), case_id)
    evidence_ids = set(_texts(row.get("evidence_ids"), f"{case_id} evidence_ids"))
    claims = row.get("claims")
    if not isinstance(claims, list):
        raise ValueError(f"Case {case_id} claims must be a list")
    for claim in claims:
        claim = _object(claim, f"{case_id} claim")
        if claim.get("kind") not in CLAIM_KINDS:
            raise ValueError(f"Case {case_id} has an invalid claim kind")
        claim_evidence = _texts(claim.get("evidence_ids"), f"{case_id} claim evidence")
        if claim["kind"] in {"descriptive", "association", "causal"} and not claim_evidence:
            raise ValueError(f"Case {case_id} factual claim has no evidence")
        if not set(claim_evidence).issubset(evidence_ids):
            raise ValueError(f"Case {case_id} claim cites unrecorded evidence")
    _nonnegative(row.get("model_calls"), f"{case_id} model_calls", integer=True)
    _nonnegative(row.get("latency_ms"), f"{case_id} latency_ms")
    cost = row.get("verified_cost")
    if cost is not None:
        _nonnegative(cost, f"{case_id} verified_cost")


def score(corpus: dict[str, Any], corpus_sha256: str, replay: dict[str, Any]) -> dict[str, Any]:
    if replay.get("version") != "agent-harness-replay-v1":
        raise ValueError("Unsupported replay")
    if replay.get("evaluation_id") != corpus["evaluation_id"]:
        raise ValueError("Replay evaluation_id does not match the corpus")
    if replay.get("corpus_sha256") != corpus_sha256:
        raise ValueError("Replay is not bound to the exact corpus bytes")
    if replay.get("mode") not in MODES:
        raise ValueError("Replay mode must be offline_scripted or hosted_synthetic")
    _text(replay.get("run_id"), "run_id")
    _text(replay.get("implementation"), "implementation")
    rows = replay.get("cases")
    if not isinstance(rows, list):
        raise ValueError("Replay cases must be a list")
    expected = {case["id"]: case for case in corpus["cases"]}
    observed: dict[str, dict[str, Any]] = {}
    for item in rows:
        item = _object(item, "replay case")
        case_id = _text(item.get("id"), "case id")
        if case_id in observed or case_id not in expected:
            raise ValueError(f"Replay has duplicate or unknown case: {case_id}")
        _validate_observation(item, case_id)
        observed[case_id] = item
    if set(observed) != set(expected):
        raise ValueError("Replay must contain every corpus case exactly once")

    reports = []
    mismatch_claims = 0
    clarification_total = 0
    clarification_correct = 0
    followup_total = 0
    followup_passed = 0
    for case_id, spec in expected.items():
        item = observed[case_id]
        expected_values = _normalized_values(spec["expected_values"], case_id)
        actual_values = _normalized_values(item["values"], case_id)
        forbidden_claims = set(spec["forbidden_claim_kinds"])
        default_claims = (
            {"descriptive", "uncertainty", "limitation"}
            if spec["expected_outcome"] == "answered"
            else {"uncertainty", "limitation"}
        )
        allowed_claims = set(spec.get("allowed_claim_kinds", default_claims))
        claim_mismatches = sum(
            claim["kind"] in forbidden_claims or claim["kind"] not in allowed_claims
            for claim in item["claims"]
        )
        claim_mismatches += len(actual_values - expected_values)
        checks = {
            "outcome": item["outcome"] == spec["expected_outcome"],
            "intent": item["intent"] == spec["expected_intent"],
            "tools": item["tools"] == spec["expected_tools"],
            "filters": set(spec["required_filters"]) == set(item["filters"]),
            "values": actual_values == expected_values,
            "claims": claim_mismatches == 0,
            "evidence": {value[3] for value in actual_values}.issubset(item["evidence_ids"]),
        }
        passed = all(checks.values())
        mismatch_claims += claim_mismatches
        if spec["expected_outcome"] == "clarification":
            clarification_total += 1
            clarification_correct += passed
        if spec.get("followup"):
            followup_total += 1
            followup_passed += passed
        reports.append({"id": case_id, "passed": passed, "checks": checks})

    latencies = [observed[case_id]["latency_ms"] for case_id in expected]
    known_costs = [
        observed[case_id]["verified_cost"]
        for case_id in expected
        if observed[case_id]["verified_cost"] is not None
    ]
    passed_count = sum(report["passed"] for report in reports)
    return {
        "version": "agent-harness-score-v1",
        "evaluation_id": corpus["evaluation_id"],
        "corpus_sha256": corpus_sha256,
        "run_id": replay["run_id"],
        "implementation": replay["implementation"],
        "mode": replay["mode"],
        "case_count": len(reports),
        "passed_cases": passed_count,
        "task_success_rate": passed_count / len(reports),
        "followup_success_rate": followup_passed / followup_total if followup_total else None,
        "clarification_quality_rate": (
            clarification_correct / clarification_total if clarification_total else None
        ),
        "claim_mismatches": mismatch_claims,
        "model_calls": sum(observed[case_id]["model_calls"] for case_id in expected),
        "latency_median_ms": statistics.median(latencies),
        "latency_max_ms": max(latencies),
        "verified_cost_total": sum(known_costs) if len(known_costs) == len(reports) else None,
        "cost_note": "unknown unless every adapter observation contains provider-verified cost",
        "cases": reports,
    }


def comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    identity = ("evaluation_id", "corpus_sha256", "mode", "case_count")
    if any(before.get(key) != after.get(key) for key in identity):
        raise ValueError("Before/after scores are comparable only for the same corpus and mode")
    metrics = ("task_success_rate", "followup_success_rate", "clarification_quality_rate")
    return {
        "version": "agent-harness-comparison-v1",
        "mode": after["mode"],
        "before_run_id": before["run_id"],
        "after_run_id": after["run_id"],
        "deltas": {
            key: None if before[key] is None or after[key] is None else after[key] - before[key]
            for key in metrics
        }
        | {
            "claim_mismatches": after["claim_mismatches"] - before["claim_mismatches"],
            "model_calls": after["model_calls"] - before["model_calls"],
            "latency_median_ms": after["latency_median_ms"] - before["latency_median_ms"],
            "verified_cost_total": None
            if before["verified_cost_total"] is None or after["verified_cost_total"] is None
            else after["verified_cost_total"] - before["verified_cost_total"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path, default=ROOT / "docs/agent-harness-evaluation-corpus.json"
    )
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--before-score", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        corpus, digest = load_corpus(args.corpus)
        result = score(corpus, digest, _object(json.loads(args.replay.read_bytes()), "replay"))
        payload: dict[str, Any] = {"score": result}
        if args.before_score:
            prior = _object(json.loads(args.before_score.read_bytes()), "before score")
            payload["comparison"] = comparison(prior.get("score", prior), result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"{result['passed_cases']}/{result['case_count']} cases passed ({result['mode']})")
    return 0 if result["passed_cases"] == result["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
