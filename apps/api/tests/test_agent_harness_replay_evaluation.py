"""Adversarial checks for the privacy-safe agent harness replay scorer."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/evaluate_agent_harness_replays.py"
CORPUS = ROOT / "docs/agent-harness-evaluation-corpus.json"
RUNNER = ROOT / "scripts/run_agent_harness_evaluation.py"


@pytest.fixture(scope="module")
def evaluator():
    spec = importlib.util.spec_from_file_location("agent_harness_replay_evaluation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner(evaluator):
    sys.modules["evaluate_agent_harness_replays"] = evaluator
    spec = importlib.util.spec_from_file_location("agent_harness_runner", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(evaluator):
    return evaluator.load_corpus(CORPUS)


def passing_replay(corpus, *, mode="offline_scripted", run_id="candidate"):
    body, digest = corpus
    rows = []
    for case in body["cases"]:
        evidence = sorted({value["evidence_id"] for value in case["expected_values"]})
        rows.append(
            {
                "id": case["id"],
                "outcome": case["expected_outcome"],
                "intent": case["expected_intent"],
                "tools": case["expected_tools"],
                "filters": case["required_filters"],
                "values": case["expected_values"],
                "evidence_ids": evidence,
                "claims": [],
                "model_calls": 0,
                "latency_ms": 1,
                "verified_cost": None,
            }
        )
    return {
        "version": "agent-harness-replay-v1",
        "evaluation_id": body["evaluation_id"],
        "corpus_sha256": digest,
        "run_id": run_id,
        "implementation": "scripted fixture",
        "mode": mode,
        "cases": rows,
    }


def case(replay, case_id):
    return next(item for item in replay["cases"] if item["id"] == case_id)


def test_canonical_offline_replay_scores_all_dimensions(evaluator, corpus):
    result = evaluator.score(*corpus, passing_replay(corpus))
    assert result["passed_cases"] == result["case_count"] == 20
    assert result["task_success_rate"] == 1
    assert result["followup_success_rate"] == 1
    assert result["clarification_quality_rate"] == 1
    assert result["claim_mismatches"] == 0
    assert result["model_calls"] == 0
    assert result["verified_cost_total"] is None


@pytest.mark.parametrize(
    ("case_id", "field", "value", "failed_check"),
    [
        ("negated-region", "filters", [], "filters"),
        ("negated-region", "filters", ["region!=West", "year=2025"], "filters"),
        ("record-count-vs-field-count", "tools", ["governed_numeric_query"], "tools"),
        ("currency-and-unit", "values", [], "values"),
        ("permission-revoked", "outcome", "answered", "outcome"),
        ("source-revision-changed", "intent", "numeric_sum", "intent"),
    ],
)
def test_semantic_contract_failures_are_visible(
    evaluator, corpus, case_id, field, value, failed_check
):
    replay = passing_replay(corpus)
    case(replay, case_id)[field] = value
    result = evaluator.score(*corpus, replay)
    report = next(item for item in result["cases"] if item["id"] == case_id)
    assert not report["passed"]
    assert not report["checks"][failed_check]


def test_wrong_value_unit_and_evidence_are_claim_mismatches(evaluator, corpus):
    replay = passing_replay(corpus)
    observed = case(replay, "single-total-sales")
    observed["values"] = [
        {"name": "sales_sum", "value": "27.50", "unit": "EUR", "evidence_id": "invented"}
    ]
    observed["evidence_ids"] = ["invented"]
    result = evaluator.score(*corpus, replay)
    assert result["claim_mismatches"] == 1
    assert result["task_success_rate"] < 1


def test_forbidden_causal_claim_fails_even_with_correct_numbers(evaluator, corpus):
    replay = passing_replay(corpus)
    observed = case(replay, "single-total-sales")
    observed["claims"] = [
        {"kind": "causal", "evidence_ids": ["orders-r1:sum-sales"]}
    ]
    result = evaluator.score(*corpus, replay)
    assert result["claim_mismatches"] == 1
    assert not next(item for item in result["cases"] if item["id"] == observed["id"])["passed"]


def test_unexpected_association_and_ungrounded_factual_claims_fail(evaluator, corpus):
    replay = passing_replay(corpus)
    observed = case(replay, "single-total-sales")
    observed["claims"] = [
        {"kind": "association", "evidence_ids": ["orders-r1:sum-sales"]}
    ]
    assert evaluator.score(*corpus, replay)["claim_mismatches"] == 1
    observed["claims"] = [{"kind": "descriptive", "evidence_ids": []}]
    with pytest.raises(ValueError, match="no evidence"):
        evaluator.score(*corpus, replay)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda replay: replay["cases"].pop(),
        lambda replay: replay["cases"].append(deepcopy(replay["cases"][0])),
        lambda replay: replay["cases"][0].update(id="unknown"),
        lambda replay: replay.update(corpus_sha256="stale"),
        lambda replay: replay["cases"][0].update(latency_ms=float("nan")),
        lambda replay: replay["cases"][0].update(model_calls=-1),
        lambda replay: replay["cases"][0].update(raw_prompt="private text"),
    ],
)
def test_incomplete_stale_or_private_replays_are_rejected(evaluator, corpus, mutation):
    replay = passing_replay(corpus)
    mutation(replay)
    with pytest.raises(ValueError):
        evaluator.score(*corpus, replay)


def test_claim_cannot_cite_evidence_absent_from_normalized_record(evaluator, corpus):
    replay = passing_replay(corpus)
    case(replay, "single-total-sales")["claims"] = [
        {"kind": "descriptive", "evidence_ids": ["other-workspace:secret"]}
    ]
    with pytest.raises(ValueError, match="unrecorded evidence"):
        evaluator.score(*corpus, replay)


def test_before_after_comparison_requires_identical_mode_and_corpus(evaluator, corpus):
    before = evaluator.score(*corpus, passing_replay(corpus, run_id="before"))
    after = evaluator.score(*corpus, passing_replay(corpus, run_id="after"))
    report = evaluator.comparison(before, after)
    assert report["mode"] == "offline_scripted"
    assert set(report["deltas"].values()) == {0, None}
    hosted = deepcopy(after)
    hosted["mode"] = "hosted_synthetic"
    with pytest.raises(ValueError, match="same corpus and mode"):
        evaluator.comparison(before, hosted)


def test_verified_cost_requires_every_case(evaluator, corpus):
    replay = passing_replay(corpus, mode="hosted_synthetic")
    for item in replay["cases"]:
        item["verified_cost"] = 0.01
        item["model_calls"] = 1
    result = evaluator.score(*corpus, replay)
    assert result["verified_cost_total"] == pytest.approx(0.2)
    assert result["model_calls"] == 20
    replay["cases"][0]["verified_cost"] = None
    assert evaluator.score(*corpus, replay)["verified_cost_total"] is None


def test_command_adapter_uses_measured_time_and_structured_output(runner, corpus):
    body, _ = corpus
    selected = body["cases"][0]
    dataset = body["datasets"][0]
    adapter = """
import json, sys
request = json.load(sys.stdin)
case = request['case']
values = case['expected_values']
json.dump({
    'id': case['id'], 'outcome': case['expected_outcome'],
    'intent': case['expected_intent'], 'tools': case['expected_tools'],
    'filters': case['required_filters'], 'values': values,
    'evidence_ids': sorted({value['evidence_id'] for value in values}),
    'claims': [], 'model_calls': 0, 'latency_ms': 0, 'verified_cost': None,
}, sys.stdout)
"""
    result = runner.run_case([sys.executable, "-c", adapter], dataset, selected, 2)
    assert result["id"] == selected["id"]
    assert result["latency_ms"] > 0
    assert json.dumps(result).find("raw_response") == -1


def test_command_adapter_failure_does_not_retain_stderr(runner, corpus):
    body, _ = corpus
    selected = body["cases"][0]
    dataset = body["datasets"][0]
    adapter = "import sys; print('private detail', file=sys.stderr); raise SystemExit(2)"
    result = runner.run_case([sys.executable, "-c", adapter], dataset, selected, 2)
    assert result["intent"] == "adapter_failed"
    assert "private" not in json.dumps(result)
